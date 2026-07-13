from __future__ import annotations

from datetime import date
from unittest.mock import patch

from scripts.grade_calls import (
    build_spot_history,
    iv_rank_history_from_regime_log,
    tickers_in_window,
)

# Frozen REAL RUT daily closes, pulled live 2026-07-13 from CBOE's public
# daily_prices CSV feed (same fixture as tests/test_cboe_client.py).
RUT_CLOSES = {
    date(2026, 7, 8): 2956.3887,
    date(2026, 7, 9): 2992.5414,
    date(2026, 7, 10): 2977.8052,
}


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


def test_build_spot_history_rut_falls_back_to_cboe():
    with (
        patch("scripts.grade_calls.XenonClient") as mock_xenon_cls,
        patch("scripts.grade_calls.CBOEClient") as mock_cboe_cls,
    ):
        mock_xenon_cls.return_value.daily_closes.return_value = {}
        mock_cboe_cls.return_value.daily_closes.return_value = RUT_CLOSES

        spot, failures = build_spot_history({"RUT"})

        assert spot["RUT"] == RUT_CLOSES
        assert failures == []
        mock_cboe_cls.return_value.daily_closes.assert_called_once_with("RUT")


def test_build_spot_history_rut_both_fail_is_honest_gap():
    with (
        patch("scripts.grade_calls.XenonClient") as mock_xenon_cls,
        patch("scripts.grade_calls.CBOEClient") as mock_cboe_cls,
    ):
        mock_xenon_cls.return_value.daily_closes.return_value = {}
        mock_cboe_cls.return_value.daily_closes.return_value = {}

        spot, failures = build_spot_history({"RUT"})

        assert "RUT" not in spot
        assert len(failures) == 1
        assert "RUT" in failures[0]
        assert "xenon" in failures[0].lower()
        assert "cboe" in failures[0].lower()


def test_build_spot_history_non_rut_unchanged():
    with (
        patch("scripts.grade_calls.XenonClient") as mock_xenon_cls,
        patch("scripts.grade_calls.CBOEClient") as mock_cboe_cls,
    ):
        mock_xenon_cls.return_value.daily_closes.return_value = {}

        spot, failures = build_spot_history({"SPX"})

        assert "SPX" not in spot
        assert len(failures) == 1
        assert "SPX" in failures[0]
        mock_cboe_cls.assert_not_called()
