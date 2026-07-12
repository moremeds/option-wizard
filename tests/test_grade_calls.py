from __future__ import annotations

from datetime import date

from scripts.grade_calls import iv_rank_history_from_regime_log, tickers_in_window


def test_tickers_in_window_reads_archive_calls(tmp_path):
    (tmp_path / "ticker").mkdir(parents=True)
    (tmp_path / "ticker" / "2026-07-08-nvda-test.md").write_text(
        "---\nticker: NVDA\ndate: 2026-07-08\nstatus: analysis-only\n"
        "result: pending\nstructures: []\n"
        'calls: ["NVDA|directional|+1||PROBE|0|false"]\n---\n\n# t\n',
        encoding="utf-8",
    )
    got = tickers_in_window(tmp_path, date(2026, 7, 1), date(2026, 7, 10))
    assert got == {"NVDA"}
    # outside the window → excluded
    assert tickers_in_window(tmp_path, date(2026, 6, 1), date(2026, 6, 30)) == set()


def test_iv_rank_history_from_regime_log(tmp_path):
    log = tmp_path / "regime-log.jsonl"
    log.write_text(
        '{"date": "2026-07-10", "iv_rank": {"QQQ": {"iv_rank_1y": 52.07}}}\n'
        '{"date": "2026-07-13", "iv_rank": {"QQQ": {"iv_rank_1y": 48.0}}}\n',
        encoding="utf-8",
    )
    hist = iv_rank_history_from_regime_log(log)
    assert hist["QQQ"][date(2026, 7, 10)] == 52.07
    assert hist["QQQ"][date(2026, 7, 13)] == 48.0
