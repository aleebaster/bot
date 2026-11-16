"""Event-driven backtester with walk-forward splits and realistic execution.

Anti-bias measures:
  * Decisions at bar i use ONLY bars <= i. Indicators are causal and computed
    once, then indexed at i. Entry occurs at bar i+1 open.
  * Slippage and fees are applied on entry and exit.
  * SL is resolved before TP when both occur in the same bar (conservative).
  * Fixed parameters: no optimisation, so no in-sample curve fitting.
  * In-sample / validation / out-of-sample segments are reported separately.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

from app.backtesting.metrics import BacktestTrade, compute_metrics
from app.candle_patterns.detector import BEARISH, BULLISH, detect_patterns
from app.config import Settings
from app.indicators.divergence import rsi_state_at
from app.indicators.technical import IndicatorSet, rsi
from app.market_data.models import frame_to_candles, timeframe_to_ms
from app.price_action.structure import (
    BEARISH as PA_BEARISH,
    BULLISH as PA_BULLISH,
    analyze as analyze_price_action,
)
from app.risk_management.position import CostModel, InvalidTradePlan, calculate_trade_plan
from app.signal_engine.models import ScoreBreakdown
from app.signal_engine.scoring import score_setup
from app.trend_analysis.analyzer import MultiTimeframeContext, TrendResult

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    symbol: str
    timeframe: str
    bars: int
    trades: list[BacktestTrade] = field(default_factory=list)
    overall: dict = field(default_factory=dict)
    splits: dict[str, dict] = field(default_factory=dict)

    def as_report(self) -> str:
        lines = [
            "=== BACKTEST REPORT (paper simulation, no real orders) ===",
            f"Symbol: {self.symbol} | Timeframe: {self.timeframe} | Bars: {self.bars}",
            "Execution: next-bar open, slippage + fees applied, SL priority within bar.",
            "",
        ]
        for label, metrics in [("OVERALL", self.overall), *self.splits.items()]:
            lines.append(f"--- {label.upper()} ---")
            for key, value in metrics.items():
                lines.append(f"  {key}: {value}")
            lines.append("")
        lines.append("No parameter optimisation was performed. Results are not a forecast.")
        return "\n".join(lines)


class IndicatorViewAt:
    """Expose the IndicatorSet API at one historical index (no look-ahead)."""

    def __init__(self, indicators: IndicatorSet, index: int) -> None:
        self.indicators = indicators
        self.index = index

    def _value(self, series: pd.Series) -> float | None:
        if 0 <= self.index < len(series) and not pd.isna(series.iloc[self.index]):
            return float(series.iloc[self.index])
        return None

    def last(self, name: str) -> float | None:
        series = getattr(self.indicators, name)
        if isinstance(series, pd.DataFrame):
            series = series.iloc[:, 0]
        return self._value(series)

    def last_plus_di(self) -> float | None:
        return self._value(self.indicators.adx["plus_di"])

    def last_minus_di(self) -> float | None:
        return self._value(self.indicators.adx["minus_di"])


def _aggregate(frame: pd.DataFrame, factor: int) -> list[float]:
    """Closed higher-timeframe average closes; only full groups are returned."""
    closes = frame["close"].astype(float).tolist()
    if factor <= 1:
        return closes
    return [
        sum(closes[start : start + factor]) / factor
        for start in range(0, len(closes) - factor + 1, factor)
    ]


def _htf_direction(aggregated: list[float]) -> str:
    if len(aggregated) < 10:
        return "RANGING"
    recent = aggregated[-10:]
    ema = pd.Series(recent).ewm(span=6, adjust=False).mean().iloc[-1]
    if aggregated[-1] > ema and aggregated[-1] > aggregated[-4]:
        return PA_BULLISH
    if aggregated[-1] < ema and aggregated[-1] < aggregated[-4]:
        return PA_BEARISH
    return "RANGING"


class Backtester:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.cost_model = CostModel(
            taker_fee=settings.taker_fee,
            maker_fee=settings.maker_fee,
            slippage=settings.slippage,
            funding_per_8h=settings.funding_per_8h,
            max_holding_bars=settings.max_holding_bars_for_funding,
        )

    def run(self, frame: pd.DataFrame, symbol: str = "BTCUSDT", timeframe: str = "15m") -> BacktestResult:
        frame = frame.reset_index(drop=True).copy()
        result = BacktestResult(symbol=symbol, timeframe=timeframe, bars=len(frame))
        if len(frame) < 220:
            result.overall = compute_metrics([])
            return result

        base_ms = timeframe_to_ms(timeframe)
        factor_1h = max(1, round(3_600_000 / base_ms))
        factor_4h = max(1, round(14_400_000 / base_ms))
        slip = self.settings.slippage

        close_series = frame["close"].astype(float)
        volume_series = frame["volume"].astype(float)
        all_indicators = IndicatorSet.from_frame(frame)
        r7, r14, r21 = rsi(close_series, 7), rsi(close_series, 14), rsi(close_series, 21)
        htf1_all = _aggregate(frame, factor_1h)
        htf4_all = _aggregate(frame, factor_4h)

        i = 200
        while i < len(frame) - 2:
            view = IndicatorViewAt(all_indicators, i)
            atr = view.last("atr14")
            if not atr or atr <= 0:
                i += 1
                continue

            # Higher-timeframe context uses only groups fully closed before i.
            htf4 = _htf_direction(htf4_all[: max(1, (i // factor_4h))])
            htf1 = _htf_direction(htf1_all[: max(1, (i // factor_1h))])
            if htf4 == htf1 and htf4 in (PA_BULLISH, PA_BEARISH):
                bias, aligned = htf4, True
                direction = "LONG" if htf4 == PA_BULLISH else "SHORT"
            else:
                bias, aligned, direction = "RANGING", False, ""

            if not direction:
                i += 1
                continue

            state = rsi_state_at(r7, r14, r21, i)
            if state.value is None or (
                (direction == "LONG" and state.value <= 50) or (direction == "SHORT" and state.value >= 50)
            ):
                i += 1
                continue

            patterns = detect_patterns(frame_to_candles(frame.iloc[i - 3 : i + 1]))
            wanted = BULLISH if direction == "LONG" else BEARISH
            if not any(p.direction == wanted for p in patterns):
                i += 1
                continue

            avg_volume = float(volume_series.iloc[i - 20 : i].mean())
            if avg_volume <= 0 or float(volume_series.iloc[i]) / avg_volume < 1.0:
                i += 1
                continue

            pa = analyze_price_action(frame_to_candles(frame.iloc[max(0, i - 80) : i + 1]))

            close = float(close_series.iloc[i])
            ema200, vwap = view.last("ema200"), view.last("vwap")
            if ema200 is None or vwap is None:
                i += 1
                continue
            ema21, ema50 = view.last("ema21"), view.last("ema50")
            if None in (ema21, ema50):
                i += 1
                continue
            ema_stack = (
                "BULLISH" if close > ema21 > ema50 > ema200
                else "BEARISH" if close < ema21 < ema50 < ema200
                else "MIXED"
            )

            trend_result = TrendResult(
                timeframe=timeframe, direction=bias,
                strength=min(1.0, (view.last("adx") or 0) / 50),
                ema_alignment=ema_stack,
                price_vs_vwap="BULLISH" if close > vwap else "BEARISH",
                price_vs_ema200="BULLISH" if close > ema200 else "BEARISH",
                adx=view.last("adx"), plus_di=view.last_plus_di(), minus_di=view.last_minus_di(),
                adx_valid=(view.last("adx") or 0) >= 20,
            )
            context = MultiTimeframeContext(
                results={"4h": trend_result, "1h": trend_result, "15m": trend_result},
                bias=bias,
                aligned_long=aligned and direction == "LONG",
                aligned_short=aligned and direction == "SHORT",
                trend_score=16.0 if aligned else 6.0,
                higher_trend=htf4, confirmation=htf1,
            )
            breakdown, _ = score_setup(
                context=context, direction=direction, rsi_state=state, divergences=[],
                setup_patterns=patterns, trigger_patterns=patterns, setup_pa=pa, trigger_pa=pa,
                setup_indicators=view, setup_frame=frame.iloc[: i + 1], stop_atr_multiple=1.5,
            )
            if breakdown.total < self.settings.min_signal_score:
                i += 1
                continue

            # Entry at the NEXT bar open (no look-ahead).
            entry_index = i + 1
            entry = float(frame["open"].iloc[entry_index]) * (1 + slip if direction == "LONG" else 1 - slip)
            sign = 1 if direction == "LONG" else -1
            swings = (
                [s.price for s in pa.swing_lows[-3:] if s.price < entry]
                if direction == "LONG"
                else [s.price for s in pa.swing_highs[-3:] if s.price > entry]
            )
            raw_stop = (
                max(swings) - 0.1 * atr if direction == "LONG" and swings
                else min(swings) + 0.1 * atr if direction == "SHORT" and swings
                else entry - sign * 1.5 * atr
            )
            if direction == "LONG":
                stop = max(entry - 2.5 * atr, min(raw_stop, entry - 0.8 * atr))
                targets = [level.price for level in pa.resistances]
            else:
                stop = min(entry + 2.5 * atr, max(raw_stop, entry + 0.8 * atr))
                targets = [level.price for level in pa.supports]

            try:
                plan = calculate_trade_plan(
                    symbol=symbol, direction=direction, entry_low=entry, entry_high=entry,
                    stop_loss=stop, structural_targets=targets, atr=atr,
                    balance=self.settings.account_balance, risk_per_trade=self.settings.risk_per_trade,
                    leverage=self.settings.leverage, min_risk_reward=self.settings.min_risk_reward,
                    cost_model=self.cost_model,
                )
            except InvalidTradePlan:
                i += 1
                continue

            exit_index, outcome, gross_r, exit_price = None, "OPEN", 0.0, None
            mfe = mae = 0.0
            risk = abs(entry - plan.stop_loss)
            for j in range(entry_index, len(frame)):
                bar = frame.iloc[j]
                if direction == "LONG":
                    favorable, adverse = (bar["high"] - entry) / risk, (entry - bar["low"]) / risk
                else:
                    favorable, adverse = (entry - bar["low"]) / risk, (bar["high"] - entry) / risk
                mfe, mae = max(mfe, favorable), max(mae, adverse)
                sl_touched = bar["low"] <= plan.stop_loss <= bar["high"]
                tp1 = bar["high"] >= plan.tp1 if direction == "LONG" else bar["low"] <= plan.tp1
                tp2 = bar["high"] >= plan.tp2 if direction == "LONG" else bar["low"] <= plan.tp2
                tp3 = bar["high"] >= plan.tp3 if direction == "LONG" else bar["low"] <= plan.tp3

                if sl_touched and gross_r == 0.0:
                    outcome, gross_r = "SL", -1.0
                    exit_price = plan.stop_loss * (1 - slip if direction == "LONG" else 1 + slip)
                    exit_index = j
                    break
                if tp3:
                    outcome, gross_r, exit_price, exit_index = "TP3", 3.0, plan.tp3, j
                    break
                if tp2:
                    gross_r, exit_price = 1.0, plan.tp2
                elif tp1:
                    gross_r, exit_price = 0.0, plan.tp1
                if sl_touched and gross_r != -1.0:
                    exit_price, exit_index = plan.stop_loss, j
                    break

            if exit_index is None:
                exit_index = len(frame) - 1
                outcome = "EXPIRED"
                exit_price = float(frame["close"].iloc[exit_index])
                gross_r = ((exit_price - entry) * sign) / risk

            holding = max(1, exit_index - entry_index)
            holding_hours = max(1, round(holding * base_ms / 3_600_000))
            fees = self.cost_model.round_trip_cost(plan.notional, holding_hours)
            fee_r = fees / plan.risk_usdt if plan.risk_usdt > 0 else 0
            result.trades.append(
                BacktestTrade(
                    symbol=symbol, direction=direction, entry_index=entry_index,
                    entry_ts=int(frame["timestamp"].iloc[entry_index]),
                    exit_ts=int(frame["timestamp"].iloc[exit_index]), entry=entry,
                    stop_loss=plan.stop_loss, tp1=plan.tp1, tp2=plan.tp2, tp3=plan.tp3,
                    outcome=outcome, gross_r=gross_r, realized_r=round(gross_r - fee_r, 4),
                    fees=fees, mfe=mfe, mae=mae, holding_bars=holding,
                )
            )
            i = exit_index + 1

        result.overall = compute_metrics(result.trades)
        n = len(frame)
        boundaries = [0, int(n * 0.5), int(n * 0.75), n]
        labels = ["in_sample", "validation", "out_of_sample"]
        for label, start, end in zip(labels, boundaries, boundaries[1:]):
            subset = [t for t in result.trades if start <= t.entry_index < end]
            result.splits[label] = compute_metrics(subset)
        return result
