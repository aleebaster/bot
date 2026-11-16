"""Risk manager: concurrency limits, sizing and hard pre-trade checks."""

from __future__ import annotations

import logging

from app.config import Settings
from app.risk_management.position import (
    CostModel,
    InvalidTradePlan,
    TradePlan,
    calculate_trade_plan,
)

logger = logging.getLogger(__name__)


class RiskManager:
    """Enforces portfolio-level risk limits. Never places orders."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.cost_model = CostModel(
            taker_fee=settings.taker_fee,
            maker_fee=settings.maker_fee,
            slippage=settings.slippage,
            funding_per_8h=settings.funding_per_8h,
            max_holding_bars=settings.max_holding_bars_for_funding,
        )

    def can_open(self, active_ideas: int) -> tuple[bool, str]:
        if active_ideas >= self.settings.max_concurrent_ideas:
            return False, f"Max concurrent ideas reached ({active_ideas}/{self.settings.max_concurrent_ideas})"
        return True, ""

    def plan(
        self,
        symbol: str,
        direction: str,
        entry_low: float,
        entry_high: float,
        stop_loss: float,
        structural_targets: list[float],
        atr: float,
        holding_bars_1h: int = 8,
    ) -> TradePlan:
        return calculate_trade_plan(
            symbol=symbol,
            direction=direction,
            entry_low=entry_low,
            entry_high=entry_high,
            stop_loss=stop_loss,
            structural_targets=structural_targets,
            atr=atr,
            balance=self.settings.account_balance,
            risk_per_trade=self.settings.risk_per_trade,
            leverage=self.settings.leverage,
            min_risk_reward=self.settings.min_risk_reward,
            cost_model=self.cost_model,
            holding_bars_1h=holding_bars_1h,
        )

    def validate(self, plan: TradePlan) -> tuple[bool, str]:
        try:
            if plan.risk_reward < self.settings.min_risk_reward:
                return False, "RR below minimum"
            if plan.stop_loss <= 0 or plan.entry <= 0:
                return False, "Invalid prices"
            return True, ""
        except InvalidTradePlan as exc:  # defensive
            return False, str(exc)
