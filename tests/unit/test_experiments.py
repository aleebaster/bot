"""Tests for the isolated experiment helpers (no production behaviour affected)."""

from __future__ import annotations

from experiments.features import bootstrap_ci, bucket, metrics
from experiments.run_variants import synthetic_wait_row, variants


def row(outcome, r, **overrides):
    base = {
        "symbol": "BTCUSDT", "direction": "LONG", "entry_index": 100, "entry_ts": 1000,
        "exit_ts": 2000, "outcome": outcome, "realized_r": r, "gross_r": r + 0.1,
        "fees": 0.1, "holding_bars": 5, "kept": True, "verdict": "EARLY ENTRY",
        "confirmation_score": 72, "false_signal_risk": 45, "countertrend": False,
        "regime": "bull", "volatility_regime": "normal", "relative_volume": 1.3,
        "adx_valid": True, "split": "in_sample", "walk_forward_window": 0,
        "reject_reasons": ["Late entry"], "next_bar_approved": True,
        "projected_outcome": "SL", "projected_r": -0.9, "next_bar_entry": 101.0,
    }
    base.update(overrides)
    return base


def test_metrics_outcome_rates() -> None:
    rows = [row("TP3", 3.0), row("TP2", 1.0), row("SL", -1.0)]
    m = metrics(rows)
    assert m["trades"] == 3
    assert m["tp3_rate"] == 33.33
    assert m["tp2_rate"] == 66.67
    assert m["sl_rate"] == 33.33


def test_bucket_is_causal_and_exhaustive() -> None:
    rows = [row("SL", -1.0, score=40), row("SL", -1.0, score=75), row("SL", -1.0, score=95)]
    result = bucket(rows, "score", [50, 80, 101], ["low", "mid", "high"])
    assert {k: v["trades"] for k, v in result.items()} == {"low": 1, "mid": 1, "high": 1}


def test_bootstrap_ci_deterministic() -> None:
    values = [1.0, -1.0, 0.5, 2.0]
    assert bootstrap_ci(values) == bootstrap_ci(values)


def test_variants_drop_early_and_keep_baseline() -> None:
    rows = [
        row("TP3", 3.0, verdict="CONFIRMED ENTRY", confirmation_score=85, false_signal_risk=20),
        row("SL", -1.0, verdict="EARLY ENTRY"),
    ]
    result = variants(rows)
    assert result["V0_baseline_current"][0]["verdict"] == "CONFIRMED ENTRY" or len(result["V0_baseline_current"]) == 2
    assert len(result["V1_drop_early"]) == 1


def test_synthetic_wait_row_uses_projected_outcome() -> None:
    r = row("SL", -1.0, projected_outcome="TP2", projected_r=1.2)
    copy = synthetic_wait_row(r)
    assert copy["outcome"] == "TP2"
    assert copy["realized_r"] == 1.2
    assert copy["entry_index"] == 101
