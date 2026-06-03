#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27"]
# ///
"""
UW live smoke test — hits every endpoint plugin/option-wizard/scripts/_clients/uw.py
plans to consume, against ORCL, and prints the observed top-level JSON keys.

Run:
    uv run scripts/smoke/uw_smoke.py
    # or with a fresh key:
    UW_API_KEY=... uv run scripts/smoke/uw_smoke.py

Reads UW_API_KEY from env, falling back to .env in the project root.
Exits non-zero if any endpoint returns non-2xx.
"""

from __future__ import annotations

import os
import pathlib
import sys
import time

import httpx

BASE = "https://api.unusualwhales.com"
TICKER = "ORCL"

ENDPOINTS: list[tuple[str, str]] = [
    ("iv_rank", f"/api/stock/{TICKER}/iv-rank"),
    ("realized_volatility", f"/api/stock/{TICKER}/volatility/realized"),
    ("skew", f"/api/stock/{TICKER}/historical-risk-reversal-skew"),
    ("iv_term_structure", f"/api/stock/{TICKER}/volatility/term-structure"),
    ("max_pain", f"/api/stock/{TICKER}/max-pain"),
    ("spot_gex_by_strike", f"/api/stock/{TICKER}/spot-exposures/strike"),
    ("interpolated_iv", f"/api/stock/{TICKER}/interpolated-iv"),
    ("greeks_by_strike", f"/api/stock/{TICKER}/greeks"),
    ("dark_pool", f"/api/darkpool/{TICKER}"),
    ("technical_indicator_sma", f"/api/stock/{TICKER}/technical-indicator/sma"),
]


def load_env() -> None:
    if os.environ.get("UW_API_KEY"):
        return
    env_path = pathlib.Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def main() -> int:
    load_env()
    key = os.environ.get("UW_API_KEY")
    if not key:
        print("FAIL: UW_API_KEY not set (env or .env)", file=sys.stderr)
        return 2

    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json, text/plain",
        "User-Agent": "option-wizard-smoke/0.1",
    }

    failures: list[str] = []
    with httpx.Client(base_url=BASE, headers=headers, timeout=20.0) as client:
        for name, path in ENDPOINTS:
            try:
                t0 = time.time()
                resp = client.get(path)
                dt_ms = (time.time() - t0) * 1000
            except httpx.HTTPError as exc:
                print(f"  {name:28s} TRANSPORT FAIL: {exc}")
                failures.append(name)
                continue

            shape = ""
            if resp.headers.get("content-type", "").startswith("application/json"):
                try:
                    body = resp.json()
                    if isinstance(body, dict):
                        shape = "{" + ", ".join(sorted(body.keys())[:6]) + "}"
                    elif isinstance(body, list):
                        first_keys = ""
                        if body and isinstance(body[0], dict):
                            first_keys = (
                                "[0]={" + ", ".join(sorted(body[0].keys())[:6]) + "}"
                            )
                        shape = f"list len={len(body)} {first_keys}".strip()
                except Exception as exc:
                    shape = f"JSON decode error: {exc}"
            else:
                shape = f"non-json ({resp.headers.get('content-type', '?')})"

            mark = "OK " if 200 <= resp.status_code < 300 else "ERR"
            if resp.status_code >= 300:
                failures.append(name)
            print(f"  {name:28s} {mark} {resp.status_code} {dt_ms:6.0f}ms  {path}")
            print(f"    shape: {shape[:200]}")

    print()
    if failures:
        print(f"FAIL: {len(failures)} endpoint(s) failed: {', '.join(failures)}")
        return 1
    print(f"PASS: all {len(ENDPOINTS)} endpoints OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
