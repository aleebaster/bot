"""Trade planning: entry zone, structural stop, R-multiple targets, sizing and costs."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.constants import LONG, SHORT

ROUND_DP = 8


def round_price(value: float) -> float:
    return round(float(value), ROUND_DP)


@dataclass(frozen=True)
class CostModel:
    taker_fee: float = 0.0004
    maker_fee: float = 0.0002
    slippage: float = 0.0005
    funding_per_8h: float = 0.0001
    max_holding_bars: int = 24

    def round_trip_cost(self, notional: float, holding_bars_1h: int = 8) -> float:
        """Estimated total cost in quote currency (fees + slippage + funding)."""
        fees = notional * (self.taker_fee + self.maker_fee)
        slippage = notional * self.slippage * 2
        funding_bars = min(holding_bars_1h, self.max_holding_bars)
        funding = notional * abs(self.funding_per_8h) * (funding_bars / 8)
        return fees + slippage + funding


@dataclass(frozen=True)
class TradePlan:
    symbol: str
    direction: str
    entry_low: float
    entry_high: float
    entry: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    risk_reward: float
    atr: float
    stop_distance: float
    stop_atr_multiple: float
    position_size: float
    notional: float
    margin: float
    risk_usdt: float
    estimated_cost: float
    target_reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_low": self.entry_low,
            "entry_high": self.entry_high,
            "entry": self.entry,
            "stop_loss": self.stop_loss,
            "tp1": self.tp1,
            "tp2": self.tp2,
            "tp3": self.tp3,
            "risk_reward": self.risk_reward,
            "atr": self.atr,
            "stop_distance": self.stop_distance,
            "position_size": self.position_size,
            "notional": self.notional,
            "margin": self.margin,
            "risk_usdt": self.risk_usdt,
            "estimated_cost": self.estimated_cost,
            "target_reasons": list(self.target_reasons),
        }


class InvalidTradePlan(ValueError):
    """Raised when a setup cannot pass hard trade-planning filters."""


def calculate_trade_plan(
    symbol: str,
    direction: str,
    entry_low: float,
    entry_high: float,
    stop_loss: float,
    structural_targets: list[float],
    atr: float,
    balance: float,
    risk_per_trade: float,
    leverage: float,
    min_risk_reward: float,
    cost_model: CostModel,
    holding_bars_1h: int = 8,
) -> TradePlan:
    """Build a validated trade plan or raise :class:`InvalidTradePlan`.

    Hard rules enforced here (before scoring):
      * SL must be on the correct side of entry and non-trivial.
      * Stop distance must be ATR-plausible (0.3x .. 4x ATR).
      * RR must meet the configured minimum.
      * Position margin must not exceed the account balance.
      * Expected reward at TP1 must exceed estimated trading costs.
    """
    if direction not in (LONG, SHORT):
        raise InvalidTradePlan("Unknown direction")
    if entry_high < entry_low or entry_low <= 0 or stop_loss <= 0 or atr <= 0:
        raise InvalidTradePlan("Invalid numeric inputs")

    entry = (entry_low + entry_high) / 2.0
    risk_per_unit = abs(entry - stop_loss)
    if risk_per_unit <= 0:
        raise InvalidTradePlan("Zero stop distance")

    if direction == LONG and stop_loss >= entry:
        raise InvalidTradePlan("Long stop must be below entry")
    if direction == SHORT and stop_loss <= entry:
        raise InvalidTradePlan("Short stop must be above entry")

    stop_atr_multiple = risk_per_unit / atr
    if not 0.3 <= stop_atr_multiple <= 4.0:
        raise InvalidTradePlan(f"Stop distance {stop_atr_multiple:.2f}x ATR is not plausible")

    sign = 1 if direction == LONG else -1
    tp1 = entry + sign * risk_per_unit * 1.0
    tp2 = entry + sign * risk_per_unit * 2.0
    base_tp3 = entry + sign * risk_per_unit * 3.0

    # Prefer the nearest structural level beyond 3R as TP3 when available.
    beyond = [float(t) for t in structural_targets if (t - entry) * sign >= risk_per_unit * 3.0]
    target_reasons = ["TP1 = 1R", "TP2 = 2R"]
    if beyond:
        tp3 = min(beyond) if direction == LONG else max(beyond)
        target_reasons.append(f"TP3 = next structural level {tp3:.8f} beyond 3R")
    else:
        tp3 = base_tp3
        target_reasons.append("TP3 = 3R (no further structural level)")

    risk_reward = abs(tp3 - entry) / risk_per_unit
    if risk_reward < min_risk_reward:
        raise InvalidTradePlan(f"RR {risk_reward:.2f} below minimum {min_risk_reward}")

    risk_usdt = balance * risk_per_trade
    position_size = risk_usdt / risk_per_unit
    notional = position_size * entry
    margin = notional / leverage
    if margin > balance:
        # Scale down so margin fits the account; risk stays <= configured risk.
        scale = balance / margin
        position_size *= scale
        notional *= scale
        margin = balance
        risk_usdt = position_size * risk_per_unit

    estimated_cost = cost_model.round_trip_cost(notional, holding_bars_1h)
    expected_reward = position_size * abs(tp1 - entry)
    if expected_reward <= estimated_cost:
        raise InvalidTradePlan("Expected TP1 reward does not cover fees/slippage/funding")

    return TradePlan(
        symbol=symbol,
        direction=direction,
        entry_low=round_price(entry_low),
        entry_high=round_price(entry_high),
        entry=round_price(entry),
        stop_loss=round_price(stop_loss),
        tp1=round_price(tp1),
        tp2=round_price(tp2),
        tp3=round_price(tp3),
        risk_reward=round(risk_reward, 2),
        atr=round_price(atr),
        stop_distance=round_price(risk_per_unit),
        stop_atr_multiple=round(stop_atr_multiple, 2),
        position_size=round(position_size, 6),
        notional=round(notional, 2),
        margin=round(margin, 2),
        risk_usdt=round(risk_usdt, 2),
        estimated_cost=round(estimated_cost, 4),
        target_reasons=target_reasons,
    )
