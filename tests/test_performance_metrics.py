import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
os.environ.setdefault("PRISMFLOW_SECRET_KEY", "unit-test-secret-key-with-enough-length")

from app.services.performance_metrics import build_performance_and_robustness


def t(r, day=1, minute=0, holding=1):
    return {
        "r_multiple": r,
        "entry_time": f"2026-06-{day:02d} 09:{minute:02d}",
        "exit_time": f"2026-06-{day:02d} 09:{minute + holding:02d}",
        "holding_bars": holding,
    }


def test_empty_trades_return_null_ratios_and_warnings():
    out = build_performance_and_robustness([])
    assert out["risk_adjusted"]["sharpe"] is None
    assert out["expectancy"]["expectancy_R_per_trade"] is None
    assert out["robustness"]["trade_count_sufficiency_warning"] is True
    assert "No out-of-sample validation is available yet." in out["warnings"]


def test_losing_strategy_has_negative_expectancy_and_drawdown():
    out = build_performance_and_robustness([t(-1, 1, i % 50) for i in range(40)])
    assert out["expectancy"]["expectancy_R_per_trade"] < 0
    assert out["risk"]["max_drawdown_R"] < 0
    assert out["risk"]["max_consecutive_losses"] == 40


def test_winning_strategy_has_positive_expectancy_without_low_label_by_default():
    trades = [t(1.2 if i % 3 else -0.4, 1 + i // 10, i % 50) for i in range(90)]
    out = build_performance_and_robustness(trades)
    assert out["expectancy"]["expectancy_R_per_trade"] > 0
    assert out["risk_adjusted"]["sharpe"] is not None
    assert out["robustness"]["overfitting_risk_label"] in {"MEDIUM", "HIGH"}


def test_one_day_high_frequency_strategy_warns():
    trades = [t(0.05, 1, i % 50) for i in range(80)]
    out = build_performance_and_robustness(trades, start_time="2026-06-01", end_time="2026-06-01")
    assert any("One-day-only" in w for w in out["warnings"])
    assert any("Excessive trades per day" in w for w in out["warnings"])
    assert out["robustness"]["overfitting_risk_label"] == "HIGH"


def test_low_trade_count_warning():
    out = build_performance_and_robustness([t(1), t(-1)])
    assert out["robustness"]["trade_count_sufficiency_warning"] is True
    assert any("Too few trades" in w for w in out["warnings"])


def test_extreme_profit_factor_warning():
    trades = [t(1.0, 1 + i // 10, i % 50) for i in range(31)] + [t(-0.01, 5, 1)]
    out = build_performance_and_robustness(trades)
    assert any("Extreme profit factor" in w for w in out["warnings"])
    assert out["robustness"]["overfitting_risk_score"] >= 35


def test_no_walk_forward_and_out_of_sample_warnings():
    out = build_performance_and_robustness([t(0.3, 1 + i // 10, i % 50) for i in range(40)])
    assert out["robustness"]["walk_forward"]["available"] is False
    assert out["robustness"]["out_of_sample"]["available"] is False
    assert any("No walk-forward" in w for w in out["warnings"])
    assert any("No out-of-sample" in w for w in out["warnings"])
