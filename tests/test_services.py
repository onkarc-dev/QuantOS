"""Tests for core services."""
import unittest
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))

from app.services.production_readiness import readiness_check


class TestProductionReadiness(unittest.TestCase):
    """Test production readiness checker."""

    def test_readiness_check_returns_structured_result(self):
        result = readiness_check()
        self.assertIn("score_out_of_10", result)
        self.assertIn("checks_passed", result)
        self.assertIn("checks_total", result)
        self.assertIn("production_ready", result)
        self.assertIn("honest_verdict", result)
        self.assertIn("checks", result)

    def test_readiness_has_critical_checks(self):
        result = readiness_check()
        critical = [c for c in result["checks"] if c["severity"] == "critical"]
        self.assertGreater(len(critical), 0)
        # Critical checks include: safe_mode, no real-money, BTC-only scope
        verdicts = [c["check"] for c in critical]
        self.assertIn("No real-money execution", verdicts)
        self.assertIn("BTC-only paper/backtest scope", verdicts)

    def test_readiness_honest_verdict(self):
        result = readiness_check()
        verdict = result["honest_verdict"]
        self.assertIn(verdict, [
            "PRODUCTION_CANDIDATE",
            "STRONG_MVP_NEEDS_HARDENING",
            "SOLID_LOCAL_DEMO",
            "EARLY_MVP",
        ])

    def test_readiness_detects_missing_engine_binary(self):
        """Readiness should detect if C++ binary is missing (but not fail)."""
        result = readiness_check()
        engine_checks = [c for c in result["checks"] if "engine" in c["area"].lower()]
        self.assertGreater(len(engine_checks), 0)


class TestEngine(unittest.TestCase):
    """Test engine runner error handling (minimal — full test requires binary)."""

    def test_engine_error_categorization(self):
        from app.services.engine_runner import _classify_engine_error
        # Test error classification
        category = _classify_engine_error(1, "not found", "")
        self.assertEqual(category, "binary_not_found")
        category = _classify_engine_error(124, "", "timeout")
        self.assertEqual(category, "engine_timeout")
        category = _classify_engine_error(139, "Segmentation fault", "")
        self.assertEqual(category, "engine_crash_segfault")


if __name__ == "__main__":
    unittest.main()
