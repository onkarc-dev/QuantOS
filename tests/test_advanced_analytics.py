"""Advanced analytics tests — updated for v3 API."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.services.coach import (
    walk_forward_analysis, stress_test, compute_expectancy,
    compute_rule_discipline, build_coach_report,
)

SAMPLE_TRADES = [{"r_multiple": v} for v in
    [1.0, -0.4, 0.8, -0.3, 1.2, -0.5, 0.9, 0.7, -0.2, 1.1] * 4]


class TestWalkForward(unittest.TestCase):
    def test_insufficient_data_small_input(self):
        r = walk_forward_analysis([{"r_multiple": 1}, {"r_multiple": -1}])
        self.assertEqual(r["status"], "INSUFFICIENT_DATA")

    def test_valid_shape_with_enough_trades(self):
        r = walk_forward_analysis(SAMPLE_TRADES, n_windows=3)
        self.assertIn(r["status"], {"PASS", "FAIL", "INSUFFICIENT_DATA"})
        if r["status"] != "INSUFFICIENT_DATA":
            self.assertIn("windows", r)
            self.assertGreaterEqual(r.get("pass_rate", 0), 0)
            self.assertLessEqual(r.get("pass_rate", 0), 1)


class TestStressTesting(unittest.TestCase):
    def test_stress_test_structure(self):
        trades = [{"r_multiple": v} for v in [1.5, -1.0, 2.0, -0.5, 1.2, -0.7, 1.8, -1.0, 0.9, -0.5]]
        r = stress_test(trades)
        self.assertIn(r["status"], {"ROBUST", "MARGINAL", "FRAGILE"})
        self.assertGreaterEqual(len(r["scenarios"]), 5)

    def test_each_scenario_has_required_fields(self):
        trades = [{"r_multiple": v} for v in [2.0, -1.0, 1.5, -1.0, 2.5, -1.0] * 3]
        r = stress_test(trades)
        for sc in r["scenarios"]:
            self.assertIn("scenario", sc)
            self.assertIn("avg_R", sc)
            self.assertIn("passed", sc)


class TestBenchmarkShim(unittest.TestCase):
    def test_expectancy_on_minimal_trade(self):
        r = compute_expectancy([{"r_multiple": 1.0}])
        self.assertEqual(r["trades"], 1)
        self.assertAlmostEqual(r["avg_R"], 1.0)


class TestRuleViolations(unittest.TestCase):
    def test_violation_counts(self):
        violations = [
            {"rule_broken": "chased_breakout", "emotional_state": "fomo", "r_impact": -1.2},
            {"rule_broken": "chased_breakout", "emotional_state": "greedy", "r_impact": -0.8},
            {"rule_broken": "over_sized", "emotional_state": "neutral", "r_impact": -2.0},
        ]
        r = compute_rule_discipline(violations)
        self.assertEqual(r["manual_rule_violations_detected"], 3)
        self.assertAlmostEqual(r["manual_rule_violation_R_impact"], -4.0)
        self.assertEqual(r["rule_counts"]["chased_breakout"], 2)
        self.assertEqual(r["most_common_rule"], "chased_breakout")


class TestCoachReportSections(unittest.TestCase):
    def test_full_report_has_all_keys(self):
        violations = [{"rule_broken": "chased_breakout", "emotional_state": "fomo", "r_impact": -1.0}]
        report = build_coach_report(SAMPLE_TRADES, violations=violations, config={"timeframe": "1h"})
        required = [
            "final_verdict", "metrics", "monte_carlo", "walk_forward_analysis",
            "stress_testing", "lifestyle_fit", "rule_discipline",
            "objective_analysis", "strengths", "weaknesses",
            "coach_insights", "next_actions", "disclaimer",
        ]
        for key in required:
            self.assertIn(key, report, f"Missing: {key}")

    def test_behavioral_data_in_report(self):
        violations = [{"rule_broken": "chased_breakout", "emotional_state": "fomo", "r_impact": -1.2}]
        report = build_coach_report(SAMPLE_TRADES, violations=violations, config={})
        disc = report["rule_discipline"]
        self.assertEqual(disc["manual_rule_violations_detected"], 1)
        self.assertIn("chased_breakout", disc["rule_counts"])
        self.assertLess(disc["manual_rule_violation_R_impact"], 0)


if __name__ == "__main__":
    unittest.main()
