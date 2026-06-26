"""QuantOS 9.5+ quality gate.

Run from repo root:
    py -3.12 scripts\quality_gate.py

This suite is intentionally dependency-light. It checks the highest-risk areas
that determine whether QuantOS feels production-grade on a local machine:
- C++ engine binaries exist and launch safely.
- Backend exposes health/readiness/engine diagnostics.
- Live paper status contract has 10 markets and engine diagnostics.
- Frontend paper-trading page no longer depends on one fragile key.
- Frontend build-critical files exist.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
API_BASE = os.getenv("QUANTOS_API_BASE", "http://127.0.0.1:8000")

CHECKS: List[Tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(condition), detail))
    icon = "PASS" if condition else "FAIL"
    print(f"[{icon}] {name}{' — ' + detail if detail else ''}")


def get_json(path: str, timeout: float = 3.0) -> Dict[str, Any]:
    with urllib.request.urlopen(API_BASE + path, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def file_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def check_engine_binaries() -> None:
    rel = ROOT / "build" / "Release"
    backtest = rel / "prism_backtest.exe"
    live = rel / "prism_live_paper_trading.exe"
    websockets = rel / "websockets.dll"
    check("Backtest binary exists", backtest.exists(), str(backtest))
    check("Live paper binary exists", live.exists(), str(live))
    check("WebSocket DLL exists", websockets.exists(), str(websockets))

    if live.exists():
        try:
            out = subprocess.run([str(live), "--help"], cwd=str(ROOT), capture_output=True, text=True, timeout=5)
            combined = (out.stdout or "") + (out.stderr or "")
            check("Live binary safe standby/help", "STANDBY" in combined and "--managed-run" in combined, combined[:180].replace("\n", " "))
        except Exception as exc:
            check("Live binary safe standby/help", False, str(exc))


def check_backend_contracts() -> None:
    try:
        health = get_json("/health")
        check("Backend health endpoint", health.get("status") == "ok", str(health)[:140])
    except Exception as exc:
        check("Backend health endpoint", False, f"Start backend first: {exc}")
        return

    try:
        diag = get_json("/system/engine-diagnostics")
        check("Engine diagnostics endpoint", bool(diag.get("backtest_status") and diag.get("live_paper_status")), str(diag)[:160])
        check("Diagnostics sees backtest", diag.get("ready_for_backtests") is True or diag.get("backtest_exists") is True, str(diag.get("backtest_binary")))
        check("Diagnostics sees live paper", diag.get("ready_for_live_paper") is True or diag.get("live_paper_exists") is True, str(diag.get("live_paper_binary")))
    except urllib.error.HTTPError as exc:
        # Auth is not required for this endpoint; HTTP errors are real issues.
        check("Engine diagnostics endpoint", False, f"HTTP {exc.code}")
    except Exception as exc:
        check("Engine diagnostics endpoint", False, str(exc))

    try:
        readiness = get_json("/readiness")
        check("Readiness endpoint", "db" in readiness and "issues" in readiness, str(readiness)[:160])
    except Exception as exc:
        check("Readiness endpoint", False, str(exc))

    try:
        live = get_json("/live-paper/status")
        markets = live.get("markets") or live.get("supported_markets") or []
        check("Live status endpoint returns payload", isinstance(live, dict) and "status" in live, str(live)[:160])
        check("Live status includes markets alias", isinstance(markets, list) and len(markets) == 10, f"count={len(markets)}")
        check("Live status includes engine diagnostics", isinstance(live.get("engine"), dict), str(live.get("engine"))[:140])
    except urllib.error.HTTPError as exc:
        # Depending on auth state, this can be 401. That is acceptable if frontend login is expected.
        check("Live status endpoint reachable or auth-protected", exc.code in {401, 403}, f"HTTP {exc.code}; login required is acceptable")
    except Exception as exc:
        check("Live status endpoint returns payload", False, str(exc))


def check_frontend_static_contracts() -> None:
    paper = file_text("apps/web/app/paper-trading/page.tsx")
    check("Paper page builds market rows from fallbacks", "buildMarketRows" in paper and "supported_markets" in paper and "symbol_states" in paper)
    check("Paper page renders all supported symbols", "SUPPORTED_SYMBOLS.map" in paper and "10 Binance Markets Monitor" in paper)
    check("Paper page uses adaptive polling", "active ? 1500 : 5000" in paper)
    check("Paper page removed waiting-only failure row", "Market monitor waiting for backend status" not in paper)

    nav = file_text("apps/web/components/TopNav.tsx")
    check("Active navigation exists", "usePathname" in nav and "textDecorationLine" in nav)

    api = file_text("apps/web/lib/api.ts")
    check("Frontend points to local API by default", "127.0.0.1:8000" in api or "localhost:8000" in api)


def check_repo_hygiene() -> None:
    required = [
        "apps/api/app/main.py",
        "apps/api/app/routes/live_paper.py",
        "apps/api/app/services/live_paper.py",
        "apps/api/app/routes/system.py",
        "apps/web/app/paper-trading/page.tsx",
        "apps/web/app/backtests/page.tsx",
        "apps/web/app/analytics/page.tsx",
        "apps/web/app/quant-coach/page.tsx",
        "CMakeLists.txt",
    ]
    for p in required:
        check(f"Required file present: {p}", (ROOT / p).exists())


def main() -> int:
    print("\nQuantOS 9.5 Quality Gate\n" + "=" * 28)
    check_repo_hygiene()
    print("\nEngine checks")
    check_engine_binaries()
    print("\nFrontend static checks")
    check_frontend_static_contracts()
    print("\nBackend live checks")
    check_backend_contracts()

    passed = sum(1 for _, ok, _ in CHECKS if ok)
    total = len(CHECKS)
    score = 10.0 * passed / max(total, 1)
    print("\nSummary")
    print(f"Passed {passed}/{total} checks")
    print(f"Quality-gate score: {score:.2f}/10")

    if score >= 9.5:
        print("RESULT: 9.5+ gate PASSED")
        return 0
    print("RESULT: gate FAILED — fix failed checks above")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
