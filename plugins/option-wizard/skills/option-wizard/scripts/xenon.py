"""Thin CLI over the xenon read-only Query API for ad-hoc agent use.

    python -m scripts.xenon /portfolio
    python -m scripts.xenon /market-depth -p symbol=AAPL -p num_rows=5
    python -m scripts.xenon /options/greeks -p symbol=QQQ -p expiry=20260717 \\
        -p strike=600 -p right=C

Prints the JSON response to stdout. Read-only — see scripts/_clients/xenon.py.
Equivalent raw curl: curl -H "X-API-Key: $XENON_KEY" "$XENON_BASE/portfolio".
"""

from __future__ import annotations

import argparse
import json
import sys

from scripts._clients.xenon import XenonClient


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="xenon read-only Query API CLI")
    parser.add_argument("path", help="API path, e.g. /portfolio or /market-depth")
    parser.add_argument(
        "-p",
        "--param",
        action="append",
        default=[],
        metavar="K=V",
        help="query param (repeatable), e.g. -p symbol=AAPL",
    )
    args = parser.parse_args(argv)

    params: dict[str, str] = {}
    for kv in args.param:
        if "=" not in kv:
            parser.error(f"bad --param {kv!r}; expected K=V")
        k, v = kv.split("=", 1)
        params[k] = v

    client = XenonClient()
    data = client.get(args.path, params or None)
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
