import csv, json
from pathlib import Path
from typing import Any


def safe_read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def read_csv(path: Path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))


def read_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        return json.loads(safe_read_text(path))
    except Exception as e:
        return {"error": str(e), "raw": safe_read_text(path)[:2000]}


def read_jsonl(path: Path):
    if not path.exists():
        return []
    out = []
    for line in safe_read_text(path).splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            out.append({"raw": line})
    return out


def output_manifest(output_dir: str):
    d = Path(output_dir)
    files = []
    if d.exists():
        for p in sorted(d.iterdir()):
            if p.is_file():
                files.append({"name": p.name, "size": p.stat().st_size})
    return {"exists": d.exists(), "files": files}
