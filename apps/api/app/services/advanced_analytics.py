"""Advanced PRISMFlow analytics: walk-forward, stress testing, benchmark comparison,
rule-violation journaling, and trader behavior intelligence.

These functions are deterministic and dependency-light so they work in local demos,
unit tests, API routes, and offline report generation.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any, Dict, Iterable, List


def _float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return default
        return float(v)
    except Exception:
        return default


def _read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            rows.append({"raw": line})
    return rows


def append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, sort_keys=True) + "\n")


def r_values_from_trades(trades: Iterable[Dict[str, Any]]) -> List[float]:
    return [_float(t.get("r_multiple", t.get("R_multiple", 0))) for t in trades]


def curve(vals: List[float]) -> List[float]:
    total = 0.0
    out: List[float] = []
    for v in vals:
        total += v
        out.append(round(total, 6))
    return out


def max_dd(vals_or_curve: List[float]) -> float:
    if not vals_or_curve:
        return 0.0
    peak = vals_or_curve[0]
    worst = 0.0
    for x in vals_or_curve:
        peak = max(peak, x)
        worst = min(worst, x - peak)
    return round(abs(worst), 6)


def expectancy(vals: List[float]) -> Dict[str, Any]:
    n = len(vals)
    wins = [v for v in vals if v > 0]
    losses = [v for v in vals if v < 0]
    gross = sum(vals)
    return {
        "trades": n,
        "gross_R": round(gross, 6),
        "avg_R": round(gross / n, 6) if n else 0.0,
        "median_R": round(median(vals), 6) if n else 0.0,
        "stdev_R": round(pstdev(vals), 6) if n > 1 else 0.0,
        "win_rate": round(len(wins) / n, 6) if n else 0.0,
        "profit_factor": round(sum(wins) / abs(sum(losses)), 6) if losses and abs(sum(losses)) > 1e-12 else ("inf" if wins else 0.0),
        "max_drawdown_R": max_dd(curve(vals)),
    }


def walk_forward_analysis(vals: List[float], train_window: int = 20, test_window: int = 10) -> Dict[str, Any]:
    """Simple rolling walk-forward check over realized R multiples.

    A real institutional version would re-optimize parameters per train window.
    This deterministic MVP validates stability by comparing train expectancy vs
    immediately following unseen test expectancy.
    """
    if len(vals) < train_window + test_window:
        return {"status": "INSUFFICIENT_DATA", "windows": [], "required_min_trades": train_window + test_window}
    windows = []
    start = 0
    while start + train_window + test_window <= len(vals):
        train = vals[start:start + train_window]
        test = vals[start + train_window:start + train_window + test_window]
        train_m = expectancy(train)
        test_m = expectancy(test)
        windows.append({
            "window": len(windows) + 1,
            "train_start_trade_index": start,
            "train_trades": train_window,
            "test_trades": test_window,
            "train_avg_R": train_m["avg_R"],
            "test_avg_R": test_m["avg_R"],
            "test_max_drawdown_R": test_m["max_drawdown_R"],
            "passed": test_m["avg_R"] > 0 and test_m["max_drawdown_R"] <= max(3.0, abs(train_m["avg_R"]) * 10),
        })
        start += test_window
    pass_rate = sum(1 for w in windows if w["passed"]) / len(windows) if windows else 0.0
    return {
        "status": "PASS" if pass_rate >= 0.6 else "FAIL_OR_UNSTABLE",
        "pass_rate": round(pass_rate, 6),
        "windows": windows,
        "interpretation": "Checks whether strategy behavior remains acceptable on unseen rolling segments.",
    }


def stress_test(vals: List[float]) -> Dict[str, Any]:
    if not vals:
        return {"status": "INSUFFICIENT_DATA", "scenarios": []}
    scenarios = []
    definitions = [
        ("base", 0.0, 1.0, 0),
        ("extra_cost_0_10R_per_trade", -0.10, 1.0, 0),
        ("extra_cost_0_25R_per_trade", -0.25, 1.0, 0),
        ("losses_25pct_worse", 0.0, 1.25, 0),
        ("miss_best_trade", 0.0, 1.0, 1),
        ("miss_best_3_trades", 0.0, 1.0, 3),
    ]
    for name, cost, loss_mult, remove_best in definitions:
        adjusted = [(v * loss_mult if v < 0 else v) + cost for v in vals]
        if remove_best > 0 and adjusted:
            adjusted = sorted(adjusted)[:-remove_best] if len(adjusted) > remove_best else []
        m = expectancy(adjusted)
        scenarios.append({"scenario": name, **m, "passed": m["avg_R"] > 0 and m["max_drawdown_R"] <= 8.0})
    pass_rate = sum(1 for s in scenarios if s["passed"]) / len(scenarios)
    return {
        "status": "ROBUST" if pass_rate >= 0.67 else "FRAGILE",
        "pass_rate": round(pass_rate, 6),
        "scenarios": scenarios,
        "interpretation": "Tests whether edge survives costs, worse losses, and missing the best trades.",
    }


def benchmark_comparison(trades: List[Dict[str, Any]], market_csv: Path | None = None) -> Dict[str, Any]:
    vals = r_values_from_trades(trades)
    strategy = expectancy(vals)
    bench: Dict[str, Any] = {"available": False, "reason": "market_csv_not_found_or_not_provided"}
    if market_csv and market_csv.exists():
        rows = _read_csv(market_csv)
        closes = [_float(r.get("close", r.get("price", 0))) for r in rows]
        closes = [x for x in closes if x > 0]
        if len(closes) >= 2:
            ret_pct = ((closes[-1] / closes[0]) - 1.0) * 100.0
            bench = {
                "available": True,
                "first_close": closes[0],
                "last_close": closes[-1],
                "buy_hold_return_pct": round(ret_pct, 6),
                "note": "Benchmark is buy-and-hold BTC over the input CSV period; not directly comparable to R without account risk assumptions.",
            }
    return {
        "strategy_R_metrics": strategy,
        "benchmark": bench,
        "verdict": "NEEDS_RISK_NORMALIZATION" if bench.get("available") else "BENCHMARK_DATA_MISSING",
    }


def detect_rule_violations(trades: List[Dict[str, Any]], journal_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    violations: List[Dict[str, Any]] = []
    by_trade = {str(t.get("trade_id", t.get("id", ""))): t for t in trades}
    for e in journal_entries:
        is_violation = bool(e.get("rule_broken")) or bool(e.get("manual_override")) or str(e.get("entry_type", "")).lower() in {"chase", "revenge", "override"}
        if not is_violation:
            continue
        trade_id = str(e.get("trade_id", ""))
        trade = by_trade.get(trade_id, {})
        r = _float(e.get("r_impact", trade.get("r_multiple", trade.get("R_multiple", 0))))
        violations.append({
            "trade_id": trade_id or None,
            "rule_broken": e.get("rule_broken", "manual_override"),
            "emotional_state": e.get("emotional_state", "unknown"),
            "note": e.get("note", ""),
            "r_impact": round(r, 6),
        })
    grouped: Dict[str, int] = {}
    emotional: Dict[str, int] = {}
    total_r = 0.0
    for v in violations:
        grouped[str(v["rule_broken"])] = grouped.get(str(v["rule_broken"]), 0) + 1
        emotional[str(v["emotional_state"])] = emotional.get(str(v["emotional_state"]), 0) + 1
        total_r += _float(v["r_impact"])
    return {
        "manual_rule_violations_detected": len(violations),
        "manual_rule_violation_R_impact": round(total_r, 6),
        "violations": violations,
        "rule_counts": dict(sorted(grouped.items(), key=lambda kv: kv[1], reverse=True)),
        "emotional_state_counts": dict(sorted(emotional.items(), key=lambda kv: kv[1], reverse=True)),
        "status": "TRACKING_ACTIVE" if journal_entries else "NO_MANUAL_JOURNAL_ENTRIES_YET",
    }


def behavioral_intelligence(trades: List[Dict[str, Any]], journal_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    vals = r_values_from_trades(trades)
    all_metrics = expectancy(vals)
    discipline = detect_rule_violations(trades, journal_entries)
    violation_ids = {str(v.get("trade_id")) for v in discipline["violations"] if v.get("trade_id")}
    clean_vals = [_float(t.get("r_multiple", t.get("R_multiple", 0))) for t in trades if str(t.get("trade_id", t.get("id", ""))) not in violation_ids]
    clean_metrics = expectancy(clean_vals)
    insights = []
    if discipline["manual_rule_violations_detected"]:
        insights.append(f"You broke/overrode rules {discipline['manual_rule_violations_detected']} times; estimated impact {discipline['manual_rule_violation_R_impact']}R.")
    else:
        insights.append("No manual rule breaks are logged yet; continue journaling every discretionary override.")
    if clean_metrics["trades"] and clean_metrics["avg_R"] > all_metrics["avg_R"]:
        insights.append("When excluding logged violations, expectancy improves. Discipline is directly affecting results.")
    elif clean_metrics["trades"]:
        insights.append("Logged violations are not yet clearly worse than clean trades; more samples are needed.")
    weakness = "insufficient_journal_data"
    if discipline["rule_counts"]:
        weakness = next(iter(discipline["rule_counts"].keys()))
    return {
        "all_trades": all_metrics,
        "clean_rule_following_trades": clean_metrics,
        "discipline": discipline,
        "biggest_behavioral_weakness": weakness,
        "insights": insights,
    }


def load_journal(output_dir: Path) -> List[Dict[str, Any]]:
    return _read_jsonl(output_dir / "journal_entries.jsonl")


def add_journal_entry(output_dir: Path, entry: Dict[str, Any]) -> Path:
    append_jsonl(output_dir / "journal_entries.jsonl", entry)
    return output_dir / "journal_entries.jsonl"
