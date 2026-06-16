"""Backup QuantOS SQLite DB and outputs into backups/ as timestamped zip."""
from __future__ import annotations
import os, zipfile, datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BACKUPS = ROOT / "backups"
BACKUPS.mkdir(exist_ok=True)
ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
out = BACKUPS / f"quantos_backup_{ts}.zip"
paths = [ROOT / "apps" / "api" / "prismflow.db", ROOT / "outputs"]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for path in paths:
        if path.is_file():
            z.write(path, path.relative_to(ROOT))
        elif path.is_dir():
            for f in path.rglob("*"):
                if f.is_file():
                    z.write(f, f.relative_to(ROOT))
print(out)
