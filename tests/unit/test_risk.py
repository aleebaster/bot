"""Trade planning, RR, stop validation, sizing and cost tests."""

from __future__ import annotations

import pytest

from app.constants import LONG, SHORT
from app.risk_management.manager import RiskManager
from app.risk_management.position import (
    CostModel,
    InvalidTradePlan,
    calculate_trade_plan,
    round_price,
)
from app.config import Settings


COSTS = CostModel(taker_fee=0.0004, maker_fee=0.0002, slippage=0.0005, funding_per_8h=0.0001)


def plan(**overrides):
    params = dict(
        symbol="BTCUSDT",
        direction=LONG,
        entry_low=99.0,
        entry_high=101.0,
        stop_loss=98.0,
        structural_targets=[110.0],
        atr=2.0,
        balance=1000.0,
        risk_per_trade=0.005,
        leverage=1.0,
        min_risk_reward=2.0,
        cost_model=COSTS,
    )
    params.update(overrides)
    return calculate_trade_plan(**params)


def test_take_profit_model() -> None:
    p = plan()
    assert p.tp1 == pytest.approx(102.0)
    assert p.tp2 == pytest.approx(104.0)
    assert p.tp3 == pytest.approx(110.0)  # nearest structural level beyond 3R
    assert p.risk_reward >= 2.0


def test_position_sizing_uses_risk_per_trade() -> None:
    p = plan()
    assert p.risk_usdt == pytest.approx(5.0)
    assert p.position_size == pytest.approx(2.5)
    assert p.notional == pytest.approx(250.0)
    assert p.margin == pytest.approx(250.0)


def test_leverage_reduces_margin_not_risk() -> None:
    p = plan(leverage=5.0)
    assert p.margin == pytest.approx(50.0)
    assert p.risk_usdt == pytest.approx(5.0)


def test_short_plan_direction() -> None:
    p = plan(direction=SHORT, entry_low=99.0, entry_high=101.0, stop_loss=102.0, structural_targets=[90.0])
    assert p.stop_loss > p.entry
    assert p.tp1 < p.entry
    assert p.tp3 < p.tp2


def test_stop_on_wrong_side_rejected() -> None:
    with pytest.raises(InvalidTradePlan):
        plan(stop_loss=102.0)
    with pytest.raises(InvalidTradePlan):
        plan(direction=SHORT, entry_low=99.0, entry_high=101.0, stop_loss=98.0)


def test_stop_atr_filter_rejects_tiny_stop() -> None:
    with pytest.raises(InvalidTradePlan, match="ATR"):
        plan(stop_loss=99.99)


def test_rr_below_minimum_rejected() -> None:
    with pytest.raises(InvalidTradePlan, match="RR"):
        plan(min_risk_reward=10.0)


def test_costs_exceed_reward_rejected() -> None:
    expensive = CostModel(taker_fee=0.5, maker_fee=0.5, slippage=0.5)
    with pytest.raises(InvalidTradePlan, match="reward"):
        plan(cost_model=expensive)


def test_round_price() -> None:
    assert round_price(1.234567891) == 1.23456789


def test_risk_manager_concurrency_and_validation() -> None:
    manager = RiskManager(Settings(max_concurrent_ideas=2))
    ok, _ = manager.can_open(1)
    assert ok
    blocked, reason = manager.can_open(2)
    assert not blocked and "concurrent" in reason.lower()
    valid, _ = manager.validate(plan())
    assert valid
