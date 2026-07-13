"""build_snapshot is pure: it assembles pre-fetched payloads. Fetch fixtures
below are REAL UW response fragments frozen 2026-07-10 (from the 2026-07-13
capability audit pulls) — not invented values."""

import json

from scripts.regime_snapshot import append_snapshot, build_snapshot, latest_regime

# Frozen real values, as-of 2026-07-10 close (capability audit §Part B):
FETCHED = {
    "date": "2026-07-13",
    "iv_rank": {
        "SPX": {"close": 7575.39, "iv_rank_1y": 14.33, "date": "2026-07-10"},
        "QQQ": {"close": 725.51, "iv_rank_1y": 52.07, "date": "2026-07-10"},
        "VIX": {"close": 15.03, "iv_rank_1y": 12.93, "date": "2026-07-10"},
    },
    "term_structure": {
        "SPX": {"2026-07-17": 0.093, "2026-08-21": 0.132, "2026-12-18": 0.163},
    },
    "gex": {
        "SPX": {"gamma_flip": 7606.0, "put_wall": 7500.0, "call_wall": 7600.0},
    },
    "tide_eod": {
        "net_call_premium": -52.1e6,
        "net_put_premium": -106.3e6,
        "as_of": "2026-07-10T16:10:00-04:00",
    },
    "hy_oas": {"hy_oas": None, "error": "fetch failed"},
}


def test_build_snapshot_labels_term_regime_and_dispersion():
    snap = build_snapshot(FETCHED)
    assert snap["date"] == "2026-07-13"
    assert snap["term_regime"]["SPX"] == "all_contango"
    assert snap["dispersion"]["qqq_minus_spx_iv_rank"] == 52.07 - 14.33
    assert snap["gex"]["SPX"]["gamma_flip"] == 7606.0
    assert snap["gaps"] == ["hy_oas: fetch failed"]  # honest-gap, not silent


def test_append_snapshot_is_idempotent_per_date(tmp_path):
    log = tmp_path / "regime-log.jsonl"
    snap = build_snapshot(FETCHED)
    append_snapshot(snap, log_path=log)
    append_snapshot({**snap, "note": "rerun"}, log_path=log)
    lines = [json.loads(x) for x in log.read_text().splitlines()]
    assert len(lines) == 1 and lines[0].get("note") == "rerun"


def test_latest_regime_reads_last_line(tmp_path):
    log = tmp_path / "regime-log.jsonl"
    append_snapshot(build_snapshot(FETCHED), log_path=log)
    got = latest_regime(log_path=log)
    assert got["date"] == "2026-07-13"
    assert latest_regime(log_path=tmp_path / "missing.jsonl") is None
