"""
Small API smoke test script for Flutter-style backend verification.

Usage examples:
1) Health-only checks:
   python smoke_test_api.py --base-url http://localhost:8000

2) With login and authenticated checks:
   python smoke_test_api.py --base-url http://localhost:8000 --username your_user --password your_pass
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Optional, Tuple


def request_json(
    method: str,
    url: str,
    body: Optional[Dict] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 15,
) -> Tuple[int, Dict]:
    payload = None
    req_headers = {"Accept": "application/json"}

    if headers:
        req_headers.update(headers)

    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, data=payload, headers=req_headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8")
            if text:
                return resp.status, json.loads(text)
            return resp.status, {}
    except urllib.error.HTTPError as err:
        raw = err.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return err.code, parsed


def print_result(label: str, ok: bool, status: int, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    line = f"[{mark}] {label} (status={status})"
    if detail:
        line = f"{line} - {detail}"
    print(line)


def main() -> int:
    parser = argparse.ArgumentParser(description="ROSCA FastAPI smoke test")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--username", default=None, help="Login username")
    parser.add_argument("--password", default=None, help="Login password")
    parser.add_argument("--year", type=int, default=2026, help="Metrics year")
    parser.add_argument("--month", type=int, default=4, help="Metrics month")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    failures = 0

    # 1) Health endpoint
    status, data = request_json("GET", f"{base}/health")
    ok = status == 200 and str(data.get("status", "")).lower() in {"ok", "healthy"}
    print_result("GET /health", ok, status, f"status={data.get('status')}")
    if not ok:
        failures += 1

    # 2) Dashboard metrics endpoint (no auth in current backend)
    metrics_url = f"{base}/api/dashboard/metrics?year={args.year}&month={args.month}"
    status, data = request_json("GET", metrics_url)
    ok = status == 200 and isinstance(data, dict) and "total_collection" in data
    print_result("GET /api/dashboard/metrics", ok, status)
    if not ok:
        failures += 1

    token = None
    if args.username and args.password:
        # 3) Login endpoint
        status, data = request_json(
            "POST",
            f"{base}/api/auth/login",
            body={"username": args.username, "password": args.password},
        )
        token = data.get("access_token") if isinstance(data, dict) else None
        ok = status == 200 and bool(token)
        print_result("POST /api/auth/login", ok, status)
        if not ok:
            failures += 1

        # 4) Authenticated profile endpoint
        if token:
            headers = {"Authorization": f"Bearer {token}"}
            status, data = request_json("GET", f"{base}/api/users/profile", headers=headers)
            ok = status == 200 and isinstance(data, dict) and "username" in data
            print_result("GET /api/users/profile", ok, status)
            if not ok:
                failures += 1

            # 5) Active loans endpoint
            status, data = request_json("GET", f"{base}/api/loans/active", headers=headers)
            ok = status == 200 and isinstance(data, dict) and "loans" in data
            print_result("GET /api/loans/active", ok, status)
            if not ok:
                failures += 1
    else:
        print("[INFO] Skipping auth checks. Provide --username and --password to test protected endpoints.")

    if failures:
        print(f"\nSmoke test completed with {failures} failure(s).")
        return 1

    print("\nSmoke test completed successfully.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        raise SystemExit(130)
