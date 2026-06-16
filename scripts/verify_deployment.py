"""Lightweight deployment verification for local/Docker QuantOS."""
from __future__ import annotations
import sys, urllib.request
base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
for path in ["/health", "/system/readiness", "/metrics"]:
    url = base.rstrip('/') + path
    with urllib.request.urlopen(url, timeout=5) as r:
        print(url, r.status)
print("QuantOS deployment verification passed")
