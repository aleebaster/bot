"""Validate paper trading mechanics on deterministic and historical data.

Writes data/paper_validation.json. No real orders, no credentials.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.backtesting.engine import Backtester
from app.config import get_settings
from app.database.manager import DatabaseManager
from app.database.statistics import compute_statistics
from app.market_data.exchange import ExchangeClient
from app.market_data.models import Candle, candles_to_frame, frame_to_candles
from app.market_data.store import CandleStore
from app.paper_trading.engine import PaperTradingEngine
from app.risk_management.position import CostModel, TradePlan, calculate_trade_plan
from app.signal_engine.models import ScoreBreakdown, Signal
from app.telegram_bot.notifier import TelegramNotifier

BASE_TS = 1_800_000_000_000
COSTS = CostModel(taker_fee=0.0004, maker_fee=0.0002, slippage=0.0005, funding_per_8h=0.0001)


def make_signal(signal_id: str, direction: str, entry: float, stop: float, prices: dict, now: int) -> Signal:
    sign = 1 if direction == "LONG" else -1
    plan = calculate_trade_plan(
        symbol="BTCUSDT", direction=direction,
        entry_low=entry, entry_high=entry, stop_loss=stop,
        structural_targets=[prices["tp3"]], atr=abs(entry - stop) / 1.5,
        balance=1000.0, risk_per_trade=0.005, leverage=1.0,
        min_risk_reward=2.0, cost_model=COSTS,
    )
    return Signal(
        symbol="BTCUSDT", direction=direction, timestamp=now, signal_id=signal_id,
        timeframes=["5m", "15m"], setup_timeframe="15m", trigger_timeframe="5m",
        plan=plan, score=85, score_breakdown=ScoreBreakdown(), rsi14=55.0,
        trend="TEST", atr=plan.atr, market_context="validation",
        expiration=now + 86_400_000,
    )


async def run_scenario(name: str, direction: str, candles: list[Candle], expected_outcome: str) -> dict:
    settings = get_settings()
    db = DatabaseManager("sqlite+aiosqlite:///:memory:")
    await db.init()
    paper = PaperTradingEngine(settings, db, TelegramNotifier(settings))
    entry = candles[0].open
    stop = entry - 2.0 if direction == "LONG" else entry + 2.0
    sign = 1 if direction == "LONG" else -1
    prices = {
        "tp1": entry + sign * 2.0, "tp2": entry + sign * 4.0, "tp3": entry + sign * 6.0,
    }
    signal = make_signal(name, direction, entry, stop, prices, candles[0].timestamp)
    try:
        await paper.open_from_signal(signal)
        events = await paper.update({"BTCUSDT": candles})
        stats = compute_statistics(await paper.signals.all_records())
        from app.database.repository import PaperPositionRepository
        positions = await PaperPositionRepository(db).list_open()
        return {
            "scenario": name,
            "direction": direction,
            "expected_outcome": expected_outcome,
            "actual_outcome": stats and (stats.get("wins", 0), stats.get("losses", 0)),
            "events": [e.kind for e in events],
            "position_still_open": len(positions),
            "closed_signals": stats["total_signals"],
            "win_rate": stats["win_rate"],
            "profit_factor": stats["profit_factor"],
            "expectancy_r": stats["expectancy_r"],
            "max_drawdown_r": stats["max_drawdown_r"],
            "fees_usdt": round(signal.plan.estimated_cost, 4),
            "risk_usdt": signal.plan.risk_usdt,
        }
    finally:
        await db.close()


async def replay_historical(frame, settings) -> dict:
    """Cross-validate Backtester trades against PaperTradingEngine outcomes."""
    backtest = Backtester(settings).run(frame, "BTCUSDT", "15m")
    if not backtest.trades:
        return {"backtest_trades": 0, "note": "No strategy trades in this sample; nothing to replay."}

    db = DatabaseManager("sqlite+aiosqlite:///:memory:")
    await db.init()
    paper = PaperTradingEngine(settings, db, TelegramNotifier(settings))
    candles = frame_to_candles(frame)
    results = []
    try:
        for index, trade in enumerate(backtest.trades):
            plan = calculate_trade_plan(
                symbol="BTCUSDT", direction=trade.direction,
                entry_low=trade.entry, entry_high=trade.entry, stop_loss=trade.stop_loss,
                structural_targets=[trade.tp3], atr=abs(trade.entry - trade.stop_loss) / 1.5,
                balance=settings.account_balance, risk_per_trade=settings.risk_per_trade,
                leverage=settings.leverage, min_risk_reward=settings.min_risk_reward,
                cost_model=paper.tracker.cost_model,
            )
            signal = Signal(
                symbol="BTCUSDT", direction=trade.direction, timestamp=trade.entry_ts,
                signal_id=f"replay-{index}", timeframes=["5m", "15m"],
                setup_timeframe="15m", trigger_timeframe="5m", plan=plan, score=85,
                score_breakdown=ScoreBreakdown(), rsi14=55.0, trend="REPLAY", atr=plan.atr,
                market_context="historical replay", expiration=trade.entry_ts + 4 * 3_600_000,
            )
            await paper.open_from_signal(signal)
            subset = [c for c in candles if trade.entry_ts <= c.timestamp <= trade.exit_ts]
            await paper.update({"BTCUSDT": subset})
        stats = compute_statistics(await paper.signals.all_records())
        return {
            "backtest_trades": len(backtest.trades),
            "backtest_outcomes": [t.outcome for t in backtest.trades],
            "paper_closed": stats["total_signals"],
            "paper_win_rate": stats["win_rate"],
            "paper_expectancy_r": stats["expectancy_r"],
            "paper_max_drawdown_r": stats["max_drawdown_r"],
        }
    finally:
        await db.close()


def scenario_candles(direction: str, path: str) -> list[Candle]:
    sign = 1 if direction == "LONG" else -1
    entry = 100.0
    sl = entry - sign * 2.0
    tp1, tp2, tp3 = entry + sign * 2, entry + sign * 4, entry + sign * 6

    def bar(i: int, low: float, high: float) -> Candle:
        assert low <= entry <= high
        return Candle(BASE_TS + i * 300_000, entry, high, low, entry, 1000)

    if direction == "LONG":
        if path == "sl_before_tp":
            return [bar(0, sl - 0.1, entry + 0.5)]
        if path == "tp1_then_sl":
            return [bar(0, entry - 0.5, tp1 + 0.1), bar(1, sl - 0.1, entry + 0.5)]
        if path == "tp3":
            return [bar(0, entry - 0.5, tp3 + 0.2)]
        if path == "same_bar_sl_tp":
            return [bar(0, sl - 0.2, tp3 + 0.2)]
    else:
        if path == "sl_before_tp":
            return [bar(0, entry - 0.5, sl + 0.1)]
        if path == "tp1_then_sl":
            return [bar(0, tp1 - 0.1, entry + 0.5), bar(1, entry - 0.5, sl + 0.1)]
        if path == "tp3":
            return [bar(0, tp3 - 0.2, entry + 0.5)]
        if path == "same_bar_sl_tp":
            return [bar(0, tp3 - 0.2, sl + 0.2)]
    raise ValueError(path)


async def main() -> None:
    settings = get_settings()
    scenarios = []
    for path, expected in (
        ("sl_before_tp", "SL"), ("tp1_then_sl", "TP1"), ("tp3", "TP3"), ("same_bar_sl_tp", "SL")
    ):
        scenarios.append(await run_scenario(f"{path}_long", "LONG", scenario_candles("LONG", path), expected))
    scenarios.append(await run_scenario("sl_short", "SHORT", scenario_candles("SHORT", "sl_before_tp"), "SL"))

    exchange = ExchangeClient(settings)
    await exchange.connect()
    store = CandleStore()
    historical = {}
    try:
        candles = await exchange.fetch_ohlcv("BTCUSDT", "15m", limit=settings.ohlcv_limit)
        store.upsert_many("BTCUSDT", "15m", candles)
        historical = await replay_historical(store.frame("BTCUSDT", "15m"), settings)
    finally:
        await exchange.close()

    report = {"generated_at_ms": exchange.now_ms, "scenarios": scenarios, "historical": historical}
    Path("data").mkdir(exist_ok=True)
    Path("data/paper_validation.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    for row in scenarios:
        print(
            f"{row['scenario']:<22} events={row['events']} closed={row['closed_signals']} "
            f"WR={row['win_rate']:.1f}% PF={row['profit_factor']} E={row['expectancy_r']:.4f}R "
            f"MDD={row['max_drawdown_r']:.4f}R fees={row['fees_usdt']} USDT"
        )
    print(f"\nHistorical replay: {historical}")
    print("Saved: data/paper_validation.json")


if __name__ == "__main__":
    asyncio.run(main())
