"""Phase 1 auth diagnostics — run from PRISMFlow/apps/api."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

API = "http://127.0.0.1:8000"


def request(method: str, path: str, body: dict | None = None, token: str | None = None):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{API}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return e.code, payload


def main():
    checks = []

    status, _ = request("GET", "/health")
    checks.append(("health", status == 200))

    status, body = request("POST", "/auth/login", {"email": "demo@prismflow.com", "password": "demo123"})
    checks.append(("demo_login", status == 200 and "token" in body))
    token = body.get("token") if status == 200 else None

    if token:
        status, me = request("GET", "/auth/me", token=token)
        checks.append(("auth_me", status == 200 and me.get("email") == "demo@prismflow.com"))

        status, jobs = request("GET", "/jobs/", token=token)
        checks.append(("jobs_list", status == 200 and isinstance(jobs.get("jobs"), list)))

        status, _ = request("GET", "/jobs/", token="invalid-token-12345")
        checks.append(("invalid_token_401", status == 401))
    else:
        checks.extend([("auth_me", False), ("jobs_list", False), ("invalid_token_401", False)])

    email = f"diag_{__import__('uuid').uuid4().hex[:8]}@example.com"
    status, reg = request("POST", "/auth/register", {"email": email, "password": "testpass123", "name": "Diag"})
    checks.append(("register", status == 200 and "token" in reg))

    status, _ = request("POST", "/auth/login", {"email": "demo@prismflow.local", "password": "demo123"})
    checks.append(("invalid_email_rejected", status == 422))

    print("PRISMFlow Phase 1 Auth Diagnostics")
    print("=" * 40)
    passed = 0
    for name, ok in checks:
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {name}")
        if ok:
            passed += 1
    print("=" * 40)
    print(f"{passed}/{len(checks)} checks passed")
    if passed != len(checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
