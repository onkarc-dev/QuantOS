import copy
import csv
import json
import time
from pathlib import Path
from typing import Any, Callable

_CACHE_TTL_SECONDS = 5.0
_READ_CACHE: dict[tuple[str, int, int, str], tuple[float, Any]] = {}


def _cache_key(path: Path, kind: str) -> tuple[str, int, int, str] | None:
    try:
        st = path.stat()
    except FileNotFoundError:
        return None
    return (str(path.resolve()), int(st.st_mtime_ns), int(st.st_size), kind)


def _cached_read(path: Path, kind: str, loader: Callable[[], Any], default: Any) -> Any:
    if not path.exists():
        return default
    key = _cache_key(path, kind)
    if key is None:
        return default
    now_ts = time.time()
    cached = _READ_CACHE.get(key)
    if cached and now_ts - cached[0] < _CACHE_TTL_SECONDS:
        return copy.deepcopy(cached[1])
    value = loader()
    _READ_CACHE[key] = (now_ts, value)
    if len(_READ_CACHE) > 256:
        oldest_key = min(_READ_CACHE, key=lambda k: _READ_CACHE[k][0])
        _READ_CACHE.pop(oldest_key, None)
    return copy.deepcopy(value)


def safe_read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def read_csv(path: Path):
    def loader():
        with path.open(newline="", encoding="utf-8", errors="replace") as f:
            return list(csv.DictReader(f))

    return _cached_read(path, "csv", loader, [])


def read_json(path: Path) -> Any:
    def loader():
        try:
            return json.loads(safe_read_text(path))
        except Exception as e:
            return {"error": str(e), "raw": safe_read_text(path)[:2000]}

    return _cached_read(path, "json", loader, {})


def read_jsonl(path: Path):
    def loader():
        out = []
        for line in safe_read_text(path).splitlines():
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                out.append({"raw": line})
        return out

    return _cached_read(path, "jsonl", loader, [])


def output_manifest(output_dir: str):
    d = Path(output_dir)
    files = []
    if d.exists():
        for p in sorted(d.iterdir()):
            if p.is_file():
                if p.is_file():
                    files.append({"name": p.name, "size": p.stat().st_size})
    return {"exists": d.exists(), "files": files}
