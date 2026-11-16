"""Tests for the isolated V6 forward-validation module (no network needed)."""

from __future__ import annotations

import ast
from pathlib import Path

from experiments.v6.metrics import metrics, v0_rows, v6_entered
from experiments.v6.telegram_design import (
    format_confirmed_entry,
    format_early_signal,
    format_expired,
    format_invalidated,
)
from experiments.v6.data import window_ms


def sample_row(status="ENTERED"):
    return {
        "symbol": "BTCUSDT", "direction": "LONG", "entry": 100.0, "stop_loss": 98.0,
        "tp1": 102.0, "tp2": 104.0, "tp3": 106.0, "close": 100.5,
        "confirmation_score": 72, "false_signal_risk": 45,
        "next_bar_entry": 100.4, "next_bar_score": 84, "next_bar_risk": 20,
        "entry_shift_atr": 0.2, "status": status, "reason": "next bar rejected",
        "outcome": "TP2", "realized_r": 0.9, "gross_r": 1.0, "fees": 0.1,
        "outcome_v0": "SL", "realized_r_v0": -1.1, "gross_r_v0": -1.0,
        "holding_bars": 5, "entry_ts": 1767225600000, "exit_ts": 1767229200000,
        "entry_index": 500, "direction_value": "LONG",
    }


def test_window_is_cronologically_separated() -> None:
    start, end = window_ms("2026-01-01", "2026-06-20")
    previous_start, _ = window_ms("2026-06-21", "2026-11-16")
    assert end < previous_start


def test_v6_formatters_use_real_values() -> None:
    row = sample_row()
    early = format_early_signal(row)
    assert "EARLY SIGNAL DETECTED" in early
    assert "BTCUSDT" in early
    assert "WAITING FOR CONFIRMATION" in early
    confirmed = format_confirmed_entry(row)
    assert "CONFIRMED ENTRY" in confirmed
    assert "Нова зона входу: 100.40000000" in confirmed
    assert "Stop Loss: 98.40000000" in confirmed
    assert "Take Profit 3: 106.40000000" in confirmed
    assert "Confirmation Score: 84/100" in confirmed
    assert "False Signal Risk: 20/100" in confirmed
    assert "SIGNAL INVALIDATED" in format_invalidated(row)
    assert "SIGNAL EXPIRED" in format_expired(row)


def test_v6_metrics_helpers() -> None:
    rows = [sample_row()]
    v0 = v0_rows(rows)
    assert v0[0]["outcome"] == "SL"
    assert v6_entered(rows)[0]["status"] == "ENTERED"
    m = metrics(v0)
    assert m["trades"] == 1 and m["sl_rate"] == 100.0


def test_production_does_not_import_experiment() -> None:
    root = Path(__file__).resolve().parents[2] / "app"
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "experiments" in node.module:
                raise AssertionError(f"Production imports experiment: {path}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "experiments" in alias.name:
                        raise AssertionError(f"Production imports experiment: {path}")
