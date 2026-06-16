"""Market data validation and metadata."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict

REQUIRED = {"open", "high", "low", "close"}


def validate_market_csv(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"valid": False, "error": "file_not_found", "path": str(path)}
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        fields = set(reader.fieldnames or [])
        missing = sorted(REQUIRED - fields)
        rows = 0
        bad = 0
        first_close = None
        last_close = None
        for row in reader:
            rows += 1
            try:
                close = float(row.get("close", ""))
                if first_close is None:
                    first_close = close
                last_close = close
            except Exception:
                bad += 1
        return {
            "valid": not missing and rows > 0 and bad == 0,
            "path": str(path),
            "rows": rows,
            "columns": sorted(fields),
            "missing_required_columns": missing,
            "bad_numeric_rows": bad,
            "first_close": first_close,
            "last_close": last_close,
        }
