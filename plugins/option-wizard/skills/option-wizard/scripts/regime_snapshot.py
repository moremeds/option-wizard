"""Daily regime state vector — persisted so 复盘 can condition on regime.

Capability audit 2026-07-13 R1: regime was re-derived ad hoc per analysis and
discarded, making regime-conditioned learning structurally impossible and the
19 vol_regime calls ungradeable (UW keeps no IV-rank history). This script
archives the vector daily; the log IS the IV-rank history going forward.

Design: fetch_all() does I/O and NEVER raises on a single-source failure —
each miss becomes an entry in snapshot["gaps"] (honest-gap discipline, hard
rule #7). build_snapshot() is pure so tests run without network.

Known live-path gap (2026-07-13): UW `spot_gex_by_strike` rows do not carry
`gex` / `call_gex` / `put_gex` — they carry raw per-leg greek components
(`call_gamma_oi`, `put_gamma_oi`, `call_delta_oi`, ...). `gex_levels.compute_levels`
expects a `gex`/`call_gex`+`put_gex` shape, so against the real payload it
returns `gamma_flip`/`put_wall`/`call_wall` all `None` without raising. Rather
than fabricate a GEX-from-raw-greeks formula, `fetch_all` detects the
all-`None` result and records it as an honest gap instead of silently
shipping a snapshot that looks complete but carries a null GEX read.

Cron (after the 16:00 ET close, weekdays) — mirror the proven manage_positions
entry exactly: repo-root cd (the editable-install .pth resolves `scripts`),
`. ./.env` sourcing (UW_API_KEY/FRED_API_KEY live there — without it this
crashes on RuntimeError at UWClient()), crontab-wide TZ=America/New_York:
  35 16 * * 1-5  cd /Users/chenxi/projects/option-wizard && set -a && . ./.env && set +a && .venv/bin/python -m scripts.regime_snapshot >> /Users/chenxi/.config/option-wizard/regime.log 2>&1
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts._clients.uw import UWClient
from scripts.gex_levels import compute_levels
from scripts.term_curve import label_regime, summarize_regime

DEFAULT_TICKERS = ("SPX", "QQQ", "VIX", "NVDA", "TSLA", "SMH")
INDEXES_FOR_GEX = ("SPX", "QQQ")


def _default_log_path() -> Path:
    return (
        Path(__file__).resolve().parent.parent
        / "references"
        / "private"
        / "market"
        / "regime-log.jsonl"
    )


def fetch_all(tickers: tuple[str, ...] = DEFAULT_TICKERS) -> dict[str, Any]:
    """Pull every regime input; single-source failures land in ['_errors']."""
    uw = UWClient()
    out: dict[str, Any] = {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "iv_rank": {},
        "term_structure": {},
        "gex": {},
        "tide_eod": None,
        "hy_oas": None,
        "_errors": [],
    }
    for t in tickers:
        try:
            d = uw.iv_rank(t)["data"]
            row = d[-1] if isinstance(d, list) else d
            out["iv_rank"][t] = {
                "close": float(row["close"]) if row.get("close") else None,
                "iv_rank_1y": float(row["iv_rank_1y"])
                if row.get("iv_rank_1y")
                else None,
                "date": row.get("date"),
            }
        except Exception as e:
            out["_errors"].append(f"iv_rank {t}: {e}")
    for t in ("SPX", "QQQ"):
        try:
            rows = uw.iv_term_structure(t)["data"]
            expiries = [str(r["expiry"]) for r in rows if r.get("dte", 1) > 0][:8]
            ivs = {
                str(r["expiry"]): float(r["volatility"])
                for r in rows
                if str(r.get("expiry")) in expiries and r.get("volatility")
            }
            out["term_structure"][t] = ivs
        except Exception as e:
            out["_errors"].append(f"term_structure {t}: {e}")
    for t in INDEXES_FOR_GEX:
        try:
            rows = uw.spot_gex_by_strike(t)["data"]
            spot = out["iv_rank"].get(t, {}).get("close")
            if spot:
                lv = compute_levels(
                    rows, float(spot), call_wall_definition="oi_cluster"
                )
                levels = {k: lv[k] for k in ("gamma_flip", "put_wall", "call_wall")}
                if all(v is None for v in levels.values()):
                    # spot_gex_by_strike rows lack gex/call_gex/put_gex in the
                    # live UW payload (see module docstring) — compute_levels
                    # silently returns all-None rather than raising. Surface
                    # it as a gap instead of shipping a null-looking read.
                    out["_errors"].append(
                        f"gex {t}: compute_levels returned all-None "
                        f"(spot_gex_by_strike rows lack gex/call_gex/put_gex fields)"
                    )
                else:
                    out["gex"][t] = levels
        except Exception as e:
            out["_errors"].append(f"gex {t}: {e}")
    try:
        tide = uw.market_tide()["data"]
        if tide:
            last = tide[-1]
            out["tide_eod"] = {
                "net_call_premium": float(last.get("net_call_premium") or 0),
                "net_put_premium": float(last.get("net_put_premium") or 0),
                "as_of": last.get("timestamp"),
            }
    except Exception as e:
        out["_errors"].append(f"market_tide: {e}")
    try:
        from scripts._clients.fred import hy_oas_signal

        sig = hy_oas_signal()
        out["hy_oas"] = {
            k: sig[k]
            for k in ("hy_oas", "hy_oas_date", "hy_oas_30d_pct", "hy_oas_trend")
        }
    except Exception as e:
        out["_errors"].append(f"hy_oas: {e}")
        out["hy_oas"] = {"hy_oas": None, "error": str(e)}
    return out


def build_snapshot(fetched: dict[str, Any]) -> dict[str, Any]:
    """Pure assembly: label regimes, compute dispersion, collect gaps."""
    snap: dict[str, Any] = {
        "date": fetched["date"],
        "ts_utc": None,  # stamped in append_snapshot
        "iv_rank": fetched.get("iv_rank", {}),
        "gex": fetched.get("gex", {}),
        "tide_eod": fetched.get("tide_eod"),
        "hy_oas": fetched.get("hy_oas"),
        "term_regime": {},
        "dispersion": {},
        "gaps": list(fetched.get("_errors", [])),
    }
    for t, ivs in fetched.get("term_structure", {}).items():
        if len(ivs) >= 2:
            snap["term_regime"][t] = summarize_regime(label_regime(ivs))
        else:
            snap["gaps"].append(f"term_structure {t}: <2 expiries")
    ir = snap["iv_rank"]
    q, s = ir.get("QQQ", {}).get("iv_rank_1y"), ir.get("SPX", {}).get("iv_rank_1y")
    if q is not None and s is not None:
        snap["dispersion"]["qqq_minus_spx_iv_rank"] = q - s
    hy = fetched.get("hy_oas") or {}
    if hy.get("hy_oas") is None and "error" in hy:
        gap = f"hy_oas: {hy['error']}"
        if gap not in snap["gaps"]:  # fetch_all already logs it via _errors
            snap["gaps"].append(gap)
    return snap


def append_snapshot(snap: dict[str, Any], *, log_path: Path | None = None) -> Path:
    """One line per date — same-date re-run replaces (idempotent)."""
    path = log_path or _default_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    snap = {**snap, "ts_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    lines: list[dict[str, Any]] = []
    if path.exists():
        lines = [
            json.loads(x)
            for x in path.read_text(encoding="utf-8").splitlines()
            if x.strip()
        ]
    lines = [x for x in lines if x.get("date") != snap["date"]]
    lines.append(snap)
    path.write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in lines) + "\n",
        encoding="utf-8",
    )
    return path


def latest_regime(log_path: Path | None = None) -> dict[str, Any] | None:
    path = log_path or _default_log_path()
    if not path.exists():
        return None
    lines = [x for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    return json.loads(lines[-1]) if lines else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Persist today's regime state vector")
    parser.add_argument("--tickers", nargs="*", default=list(DEFAULT_TICKERS))
    parser.add_argument("--log-path", type=Path, default=None)
    args = parser.parse_args(argv)
    snap = build_snapshot(fetch_all(tuple(args.tickers)))
    path = append_snapshot(snap, log_path=args.log_path)
    print(
        f"regime snapshot {snap['date']} -> {path} "
        f"({len(snap['gaps'])} gaps: {snap['gaps'] or 'none'})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
