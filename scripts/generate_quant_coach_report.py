#!/usr/bin/env python3
"""Generate PRISMFlow Quant Coach Report from an output directory.

Usage:
  python scripts/generate_quant_coach_report.py outputs/demo_user/demo_job
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.services.coach import coach_report, write_coach_report  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("output_dir", nargs="?", default=str(ROOT / "outputs" / "demo_user" / "demo_job"))
    ap.add_argument("--print", action="store_true", dest="print_json")
    args = ap.parse_args()
    out_dir = Path(args.output_dir)
    if not out_dir.exists():
        print(f"Output directory not found: {out_dir}", file=sys.stderr)
        return 2
    report_path = write_coach_report(out_dir)
    report = coach_report(out_dir)
    if args.print_json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Quant Coach report written: {report_path}")
        print(f"Final verdict: {report['final_verdict']}")
        print(f"Lifestyle fit: {report['lifestyle_fit']['label']} ({report['lifestyle_fit']['score']}/100)")
        print(f"Avg R: {report['metrics']['avg_R']} | Max DD: {report['metrics']['max_drawdown_R']}R")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
