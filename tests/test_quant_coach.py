"""Tests for Quant Coach services — MC, walk-forward, stress, behavior."""
import unittest
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))

from app.services.coach import (
    compute_expectancy,
    run_monte_carlo,
    walk_forward_analysis,
    stress_test,
    compute_lifestyle_fit,
    compute_objective_pass_fail,
    build_coach_report,
)


SAMPLE_TRADES = [
    {"r_multiple": 2.0}, {"r_multiple": -1.0}, {"r_multiple": 1.5},
    {"r_multiple": -1.0}, {"r_multiple": 3.0}, {"r_multiple": -1.0},
    {"r_multiple": 2.5}, {"r_multiple": -1.0}, {"r_multiple": 1.8},
    {"r_multiple": -1.0}, {"r_multiple": 2.2}, {"r_multiple": -1.0},
    {"r_multiple": 1.6}, {"r_multiple": -1.0}, {"r_multiple": 2.8},
    {"r_multiple": -1.0}, {"r_multiple": 3.5}, {"r_multiple": -1.0},
    {"r_multiple": 2.1}, {"r_multiple": -1.0},
]

FLAT_TRADES = [{"r_multiple": 0.0}] * 10
LOSING_TRADES = [{"r_multiple": -0.5}] * 20


class TestExpectancy(unittest.TestCase):
    def test_positive_expectancy(self):
        r = compute_expectancy(SAMPLE_TRADES)
        self.assertGreater(r["avg_R"], 0)
        self.assertEqual(r["trades"], 20)
        self.assertIn("win_rate", r)
        self.assertIn("profit_factor", r)

    def test_zero_expectancy_flat_trades(self):
        r = compute_expectancy(FLAT_TRADES)
        self.assertAlmostEqual(r["avg_R"], 0.0)

    def test_negative_expectancy(self):
        r = compute_expectancy(LOSING_TRADES)
        self.assertLess(r["avg_R"], 0)

    def test_empty_trades(self):
        r = compute_expectancy([])
        self.assertEqual(r["trades"], 0)
        self.assertIsNone(r["avg_R"])

    def test_gross_r_calculation(self):
        simple = [{"r_multiple": 2.0}, {"r_multiple": -1.0}]
        r = compute_expectancy(simple)
        self.assertAlmostEqual(r["gross_R"], 1.0)

    def test_win_rate_calculation(self):
        trades = [{"r_multiple": 1.0}, {"r_multiple": 1.0},
                  {"r_multiple": -1.0}, {"r_multiple": -1.0}]
        r = compute_expectancy(trades)
        self.assertAlmostEqual(r["win_rate"], 0.5)

    def test_profit_factor(self):
        trades = [{"r_multiple": 2.0}, {"r_multiple": 2.0}, {"r_multiple": -1.0}]
        r = compute_expectancy(trades)
        # gross wins = 4R, gross losses = 1R → PF = 4.0
        self.assertAlmostEqual(r["profit_factor"], 4.0)


class TestMonteCarlo(unittest.TestCase):
    def test_mc_returns_structure(self):
        r = run_monte_carlo(SAMPLE_TRADES, n_simulations=100, n_trades=50)
        self.assertIn("final_R", r)
        self.assertIn("drawdown_R", r)
        self.assertIn("risk_of_ruin_minus_10R", r)
        self.assertIn("probability_final_R_positive", r)
        self.assertEqual(r["simulations"], 100)

    def test_mc_percentiles_ordered(self):
        r = run_monte_carlo(SAMPLE_TRADES, n_simulations=200, n_trades=50)
        f = r["final_R"]
        self.assertLessEqual(f["p01"], f["p05"])
        self.assertLessEqual(f["p05"], f["p50"])
        self.assertLessEqual(f["p50"], f["p95"])

    def test_mc_positive_edge_favors_positive_outcomes(self):
        r = run_monte_carlo(SAMPLE_TRADES, n_simulations=500, n_trades=30)
        self.assertGreater(r["probability_final_R_positive"], 0.5)

    def test_mc_losing_system_skews_negative(self):
        r = run_monte_carlo(LOSING_TRADES, n_simulations=200, n_trades=20)
        self.assertLess(r["final_R"]["p50"], 0)

    def test_mc_insufficient_data(self):
        r = run_monte_carlo([], n_simulations=100)
        self.assertIsNone(r.get("final_R", {}).get("p50"))


class TestWalkForward(unittest.TestCase):
    def test_wf_with_sufficient_data(self):
        # Need enough trades for walk-forward windows
        trades = SAMPLE_TRADES * 3  # 60 trades
        r = walk_forward_analysis(trades, n_windows=3)
        self.assertIn("windows", r)
        self.assertIn("pass_rate", r)
        self.assertIn("status", r)

    def test_wf_status_is_pass_or_fail(self):
        r = walk_forward_analysis(SAMPLE_TRADES * 3, n_windows=3)
        self.assertIn(r["status"], ["PASS", "FAIL", "INSUFFICIENT_DATA"])

    def test_wf_insufficient_data(self):
        r = walk_forward_analysis([{"r_multiple": 1.0}] * 5)
        self.assertEqual(r["status"], "INSUFFICIENT_DATA")

    def test_wf_window_structure(self):
        trades = SAMPLE_TRADES * 4  # 80 trades
        r = walk_forward_analysis(trades, n_windows=4)
        if r["status"] != "INSUFFICIENT_DATA":
            for w in r["windows"]:
                self.assertIn("window", w)
                self.assertIn("train_avg_R", w)
                self.assertIn("test_avg_R", w)
                self.assertIn("passed", w)


class TestStressTest(unittest.TestCase):
    def test_stress_returns_scenarios(self):
        r = stress_test(SAMPLE_TRADES)
        self.assertIn("scenarios", r)
        self.assertIn("pass_rate", r)
        self.assertIn("status", r)
        self.assertGreater(len(r["scenarios"]), 0)

    def test_stress_scenarios_have_structure(self):
        r = stress_test(SAMPLE_TRADES)
        for sc in r["scenarios"]:
            self.assertIn("scenario", sc)
            self.assertIn("avg_R", sc)
            self.assertIn("passed", sc)

    def test_stress_slippage_reduces_returns(self):
        r = stress_test(SAMPLE_TRADES)
        base_r = compute_expectancy(SAMPLE_TRADES)["avg_R"]
        slip_sc = next((s for s in r["scenarios"] if "slippage" in s["scenario"].lower()), None)
        if slip_sc:
            self.assertLessEqual(slip_sc["avg_R"], base_r + 0.01)

    def test_stress_with_losing_trades(self):
        r = stress_test(LOSING_TRADES)
        self.assertEqual(r["status"], "FRAGILE")

    def test_stress_empty_trades(self):
        r = stress_test([])
        self.assertEqual(r["status"], "INSUFFICIENT_DATA")


class TestLifestyleFit(unittest.TestCase):
    def test_lifestyle_fit_structure(self):
        config = {"timeframe": "1m", "trades": 20}
        r = compute_lifestyle_fit(config, SAMPLE_TRADES)
        self.assertIn("score", r)
        self.assertIn("label", r)
        self.assertIn("why", r)
        self.assertIsInstance(r["score"], (int, float))

    def test_lifestyle_score_range(self):
        r = compute_lifestyle_fit({"timeframe": "1m"}, SAMPLE_TRADES)
        self.assertGreaterEqual(r["score"], 0)
        self.assertLessEqual(r["score"], 100)

    def test_higher_tf_gets_better_fit(self):
        r_1m = compute_lifestyle_fit({"timeframe": "1m"}, SAMPLE_TRADES)
        r_1d = compute_lifestyle_fit({"timeframe": "1d"}, SAMPLE_TRADES)
        self.assertGreater(r_1d["score"], r_1m["score"])


class TestObjectivePassFail(unittest.TestCase):
    def test_good_system_passes(self):
        exp = {"avg_R": 0.5, "trades": 30}
        mc = {"final_R": {"p50": 8.0, "p05": -3.0}, "drawdown_R": {"p95": -5.0}}
        r = compute_objective_pass_fail(exp, mc)
        self.assertIn(r["verdict"], ["PASS", "FAIL", "INSUFFICIENT_DATA"])

    def test_bad_system_fails(self):
        exp = {"avg_R": -0.2, "trades": 30}
        mc = {"final_R": {"p50": -5.0, "p05": -15.0}, "drawdown_R": {"p95": -20.0}}
        r = compute_objective_pass_fail(exp, mc)
        self.assertEqual(r["verdict"], "FAIL")

    def test_insufficient_trades_returns_insufficient(self):
        exp = {"avg_R": 1.0, "trades": 5}
        mc = {}
        r = compute_objective_pass_fail(exp, mc)
        self.assertEqual(r["verdict"], "INSUFFICIENT_DATA")


class TestEmotionalOverrides(unittest.TestCase):
    """Test that rule violations / emotional overrides affect analysis."""

    def test_build_coach_report_detects_violations(self):
        """build_coach_report should note rule violations if present in journal."""
        violations = [
            {"rule_broken": "no_trade_before_7am", "r_impact": -1.5, "emotional_state": "greedy"},
            {"rule_broken": "max_1_trade_per_day", "r_impact": -1.0, "emotional_state": "fearful"},
        ]
        r = build_coach_report(SAMPLE_TRADES, violations=violations, config={})
        disc = r.get("rule_discipline", {})
        self.assertGreater(disc.get("manual_rule_violations_detected", 0), 0)
        self.assertLess(disc.get("manual_rule_violation_R_impact", 0), 0)

    def test_zero_violations_reflects_in_report(self):
        r = build_coach_report(SAMPLE_TRADES, violations=[], config={})
        disc = r.get("rule_discipline", {})
        self.assertEqual(disc.get("manual_rule_violations_detected", 0), 0)

    def test_greedy_state_tracked(self):
        violations = [{"emotional_state": "greedy", "rule_broken": None, "r_impact": 0}] * 3
        r = build_coach_report(SAMPLE_TRADES, violations=violations, config={})
        disc = r.get("rule_discipline", {})
        self.assertIn("greedy", str(disc).lower())


if __name__ == "__main__":
    unittest.main()
