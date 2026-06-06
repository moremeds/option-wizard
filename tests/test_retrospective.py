"""Tests for the 复盘 (review) framework — see scripts/retrospective.py.

Covers the pure-function core: frontmatter parsing, scope filter, call
extraction, markout computation (directional / vol regime / structure),
trade markout, discipline reconciliation, aggregate side-by-side table,
pattern analysis, action item generation, pitfall draft idempotency,
Outcome / Lesson writeback idempotency.

Live data fetchers (TV historical, IB executions, UW IV rank history)
are NOT tested here — they're CLI orchestrator concerns.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from scripts.retrospective import (
    DIRECTIONAL_NOISE_BAND,
    MARKOUT_HORIZONS,
    VOL_REGIME_IV_RANK_BAND,
    Call,
    Trade,
    _horizon_date,
    _is_in_scope,
    _trade_matches_call,
    aggregate_markout,
    compute_call_markout,
    compute_trade_markout,
    detect_pattern_anomalies,
    discipline_quadrant,
    extract_calls_from_archive,
    generate_action_items,
    generate_pitfall_drafts,
    parse_archive_frontmatter,
    reconcile_calls_with_trades,
    run_review,
    write_back_outcome,
)

# ----- Frontmatter parsing -----


def test_frontmatter_parses_scalars_and_inline_list():
    text = (
        "---\n"
        "ticker: GOOGL\n"
        "date: 2026-05-15\n"
        "structures: [bull_put_spread, csp]\n"
        'event: "ER preview"\n'
        "---\n"
        "# body\n"
    )
    fm = parse_archive_frontmatter(text)
    assert fm == {
        "ticker": "GOOGL",
        "date": "2026-05-15",
        "structures": ["bull_put_spread", "csp"],
        "event": "ER preview",
    }


def test_frontmatter_returns_none_when_missing():
    assert parse_archive_frontmatter("no frontmatter here\n") is None


# ----- Scope filter -----


@pytest.mark.parametrize("structures", [["fcn"], ["aq"], ["dq"], ["accumulator"]])
def test_pb_products_are_out_of_scope(structures):
    in_scope, reason = _is_in_scope({"structures": structures})
    assert not in_scope
    assert "out of scope" in reason


def test_listed_options_are_in_scope():
    in_scope, _ = _is_in_scope({"structures": ["bull_put_spread", "csp"]})
    assert in_scope


def test_out_of_scope_via_tag():
    in_scope, reason = _is_in_scope({"structures": [], "tags": ["fcn", "defensive"]})
    assert not in_scope
    assert "fcn" in reason


# ----- Call extraction -----


def _write_archive(
    dir_: Path,
    *,
    name: str,
    ticker: str,
    date_iso: str,
    structures: list[str],
    body: str = "",
) -> Path:
    p = dir_ / name
    fm_lines = [
        "---",
        f"ticker: {ticker}",
        f"date: {date_iso}",
        f"structures: [{', '.join(structures)}]",
        "tags: []",
        "---",
    ]
    p.write_text("\n".join(fm_lines) + "\n" + body, encoding="utf-8")
    return p


def test_extract_calls_filters_window_and_pb_products(tmp_path: Path):
    _write_archive(
        tmp_path,
        name="googl-bull.md",
        ticker="GOOGL",
        date_iso="2026-05-15",
        structures=["bull_put_spread"],
    )
    _write_archive(
        tmp_path,
        name="msft-fcn.md",
        ticker="MSFT",
        date_iso="2026-05-16",
        structures=["fcn"],
    )
    _write_archive(
        tmp_path,
        name="aapl-old.md",
        ticker="AAPL",
        date_iso="2025-12-01",
        structures=["csp"],
    )
    calls, skipped = extract_calls_from_archive(
        tmp_path, date(2026, 5, 1), date(2026, 5, 31)
    )
    tickers = sorted(c.ticker for c in calls)
    assert tickers == ["GOOGL"]
    assert any("fcn" in s["reason"].lower() for s in skipped)


def test_extract_calls_classifies_structure_direction(tmp_path: Path):
    _write_archive(
        tmp_path,
        name="googl-bull.md",
        ticker="GOOGL",
        date_iso="2026-05-15",
        structures=["bull_put_spread"],
    )
    _write_archive(
        tmp_path,
        name="tsla-bear.md",
        ticker="TSLA",
        date_iso="2026-05-16",
        structures=["bear_call_spread"],
    )
    _write_archive(
        tmp_path,
        name="qqq-range.md",
        ticker="QQQ",
        date_iso="2026-05-17",
        structures=["iron_condor"],
    )
    calls, _ = extract_calls_from_archive(tmp_path, date(2026, 5, 1), date(2026, 5, 31))
    by_ticker = {c.ticker: c for c in calls}
    assert by_ticker["GOOGL"].direction == +1
    assert by_ticker["TSLA"].direction == -1
    assert by_ticker["QQQ"].direction == 0
    assert all(c.call_type == "structure" for c in calls)


def test_extract_falls_back_to_prose_when_no_structure(tmp_path: Path):
    _write_archive(
        tmp_path,
        name="nvda-bull.md",
        ticker="NVDA",
        date_iso="2026-05-15",
        structures=[],
        body=("## TL;DR\n\nBullish NVDA into ER — long delta via long call.\n"),
    )
    calls, _ = extract_calls_from_archive(tmp_path, date(2026, 5, 1), date(2026, 5, 31))
    assert len(calls) == 1
    assert calls[0].call_type == "directional"
    assert calls[0].direction == +1


# ----- Markout: directional -----


def test_directional_markout_correct_when_spot_rises_for_bullish_call():
    call = Call(
        ticker="GOOGL",
        analysis_date=date(2026, 5, 15),
        call_type="directional",
        direction=+1,
        structure=None,
        archive_path=Path("googl-bull.md"),
        notes="bullish",
    )
    spot = {
        "GOOGL": {
            date(2026, 5, 15): 175.0,
            _horizon_date(date(2026, 5, 15), 1): 176.0,
            _horizon_date(date(2026, 5, 15), 5): 178.0,
            _horizon_date(date(2026, 5, 15), 10): 180.0,
            _horizon_date(date(2026, 5, 15), 21): 185.0,
            _horizon_date(date(2026, 5, 15), 45): 195.0,
        }
    }
    cm = compute_call_markout(call, spot_history=spot)
    assert cm.verdict == "CORRECT"
    assert cm.horizons[21] == pytest.approx((185 - 175) / 175)


def test_directional_markout_neutral_in_noise_band():
    call = Call(
        ticker="X",
        analysis_date=date(2026, 5, 1),
        call_type="directional",
        direction=+1,
        structure=None,
        archive_path=Path("x.md"),
        notes="",
    )
    spot_0 = 100.0
    # +1% at T+21d — inside the ±2% noise band.
    spot_21 = spot_0 * 1.01
    spot = {
        "X": {date(2026, 5, 1): spot_0, _horizon_date(date(2026, 5, 1), 21): spot_21}
    }
    cm = compute_call_markout(call, spot_history=spot)
    assert cm.verdict == "NEUTRAL"
    assert abs(cm.horizons[21]) < DIRECTIONAL_NOISE_BAND


def test_directional_markout_wrong_signs_inverted():
    call = Call(
        ticker="X",
        analysis_date=date(2026, 5, 1),
        call_type="directional",
        direction=-1,  # bearish
        structure=None,
        archive_path=Path("x.md"),
        notes="",
    )
    spot = {
        "X": {
            date(2026, 5, 1): 100.0,
            _horizon_date(
                date(2026, 5, 1), 21
            ): 110.0,  # spot rose — bearish call WRONG
        }
    }
    cm = compute_call_markout(call, spot_history=spot)
    assert cm.verdict == "WRONG"
    assert cm.horizons[21] < 0


def test_directional_markout_unknown_when_data_missing():
    call = Call(
        ticker="X",
        analysis_date=date(2026, 5, 1),
        call_type="directional",
        direction=+1,
        structure=None,
        archive_path=Path("x.md"),
        notes="",
    )
    cm = compute_call_markout(call, spot_history={})
    assert cm.verdict == "UNKNOWN"
    assert all(v is None for v in cm.horizons.values())


# ----- Markout: vol regime -----


def test_vol_regime_markout_rich_correct_when_iv_rank_falls():
    call = Call(
        ticker="X",
        analysis_date=date(2026, 5, 1),
        call_type="vol_regime",
        direction=-1,  # RICH → expect IV decline
        structure=None,
        archive_path=Path("x.md"),
        notes="",
    )
    iv_ranks = {
        "X": {
            date(2026, 5, 1): 75.0,
            _horizon_date(date(2026, 5, 1), 5): 60.0,
            _horizon_date(date(2026, 5, 1), 10): 55.0,
            _horizon_date(date(2026, 5, 1), 21): 50.0,
        }
    }
    cm = compute_call_markout(call, spot_history={}, iv_rank_history=iv_ranks)
    # direction=-1, rank dropped 20 → markout = -1 × (55-75) = +20
    assert cm.horizons[10] == pytest.approx(20.0)
    assert cm.verdict == "CORRECT"


def test_vol_regime_markout_only_t5_t10_t21_have_values():
    call = Call(
        ticker="X",
        analysis_date=date(2026, 5, 1),
        call_type="vol_regime",
        direction=-1,
        structure=None,
        archive_path=Path("x.md"),
        notes="",
    )
    iv_ranks = {
        "X": {
            date(2026, 5, 1): 75.0,
            _horizon_date(date(2026, 5, 1), 5): 60.0,
        }
    }
    cm = compute_call_markout(call, spot_history={}, iv_rank_history=iv_ranks)
    assert cm.horizons[1] is None  # T+1d is skipped for vol regime
    assert cm.horizons[45] is None  # T+45d too
    assert cm.horizons[5] is not None


# ----- Markout: structure -----


def test_structure_markout_uses_delta1_proxy():
    call = Call(
        ticker="GOOGL",
        analysis_date=date(2026, 5, 1),
        call_type="structure",
        direction=+1,  # bull put spread
        structure="bull_put_spread",
        archive_path=Path("googl.md"),
        notes="",
    )
    spot = {
        "GOOGL": {
            date(2026, 5, 1): 175.0,
            _horizon_date(date(2026, 5, 1), 21): 180.0,
        }
    }
    cm = compute_call_markout(call, spot_history=spot)
    assert cm.verdict == "CORRECT"
    assert cm.mark_sources[21] == "model_delta1"


# ----- Trade markout -----


def test_stock_trade_markout_long():
    trade = Trade(
        ticker="GOOGL",
        trade_date=date(2026, 5, 1),
        side="BUY",
        quantity=100,
        fill_price=175.0,
        contract_type="STK",
        option_meta=None,
    )
    spot = {
        "GOOGL": {
            date(2026, 5, 1): 175.0,
            _horizon_date(date(2026, 5, 1), 21): 180.0,
        }
    }
    tm = compute_trade_markout(trade, spot_history=spot)
    assert tm.horizons[21] == pytest.approx((180 - 175) / 175)


def test_option_trade_markout_short_put_falls_with_spot_rise():
    trade = Trade(
        ticker="GOOGL",
        trade_date=date(2026, 5, 1),
        side="SELL",
        quantity=1,
        fill_price=5.0,  # received $5 premium
        contract_type="OPT",
        option_meta={
            "right": "P",
            "strike": 170.0,
            "expiry_iso": (date(2026, 5, 1) + timedelta(days=60)).isoformat(),
        },
    )
    spot = {
        "GOOGL": {
            date(2026, 5, 1): 175.0,
            _horizon_date(date(2026, 5, 1), 21): 185.0,  # spot up — short put gains
        }
    }
    tm = compute_trade_markout(trade, spot_history=spot, option_iv={"GOOGL": 0.30})
    # Short put: pnl = entry - mark; spot up → mark falls → pnl positive.
    assert tm.horizons[21] is not None and tm.horizons[21] > 0


# ----- Reconcile / discipline -----


def test_trade_matches_call_when_direction_aligns():
    call = Call(
        ticker="GOOGL",
        analysis_date=date(2026, 5, 1),
        call_type="directional",
        direction=+1,
        structure=None,
        archive_path=Path("g.md"),
        notes="",
    )
    long_call_trade = Trade(
        ticker="GOOGL",
        trade_date=date(2026, 5, 3),  # 2 days after — inside window
        side="BUY",
        quantity=1,
        fill_price=5.0,
        contract_type="OPT",
        option_meta={"right": "C", "strike": 180.0, "expiry_iso": "2026-06-15"},
    )
    assert _trade_matches_call(call, long_call_trade)


def test_trade_doesnt_match_when_wrong_direction():
    call = Call(
        ticker="GOOGL",
        analysis_date=date(2026, 5, 1),
        call_type="directional",
        direction=+1,
        structure=None,
        archive_path=Path("g.md"),
        notes="",
    )
    long_put_trade = Trade(
        ticker="GOOGL",
        trade_date=date(2026, 5, 2),
        side="BUY",
        quantity=1,
        fill_price=5.0,
        contract_type="OPT",
        option_meta={"right": "P", "strike": 170.0, "expiry_iso": "2026-06-15"},
    )
    assert not _trade_matches_call(call, long_put_trade)


def test_trade_doesnt_match_outside_window():
    call = Call(
        ticker="GOOGL",
        analysis_date=date(2026, 5, 1),
        call_type="directional",
        direction=+1,
        structure=None,
        archive_path=Path("g.md"),
        notes="",
    )
    trade = Trade(
        ticker="GOOGL",
        trade_date=date(2026, 5, 10),  # 9 days later — outside 3-day window
        side="BUY",
        quantity=100,
        fill_price=175.0,
        contract_type="STK",
        option_meta=None,
    )
    assert not _trade_matches_call(call, trade)


def test_discipline_quadrant_classifies_each_call():
    base = date(2026, 5, 1)
    spot = {
        "X": {base: 100.0, _horizon_date(base, 21): 110.0},  # bullish correct
        "Y": {base: 100.0, _horizon_date(base, 21): 90.0},  # bullish wrong
    }
    c_xx = Call("X", base, "directional", +1, None, Path("x.md"), "")
    c_yy = Call("Y", base, "directional", +1, None, Path("y.md"), "")
    cms = [
        compute_call_markout(c_xx, spot_history=spot),
        compute_call_markout(c_yy, spot_history=spot),
    ]
    followed = {c_xx: True, c_yy: False}  # followed correct X, ignored wrong Y
    q = discipline_quadrant(cms, followed)
    assert len(q.followed_correct) == 1
    assert len(q.ignored_wrong) == 1
    assert len(q.followed_wrong) == 0
    assert len(q.ignored_correct) == 0


# ----- Aggregate markout -----


def test_aggregate_markout_excludes_iv_rank_calls():
    base = date(2026, 5, 1)
    spot = {"X": {base: 100.0, _horizon_date(base, 21): 110.0}}
    iv = {"X": {base: 75.0, _horizon_date(base, 21): 50.0}}
    c_dir = Call("X", base, "directional", +1, None, Path("d.md"), "")
    c_vol = Call("X", base, "vol_regime", -1, None, Path("v.md"), "")
    cms = [
        compute_call_markout(c_dir, spot_history=spot),
        compute_call_markout(c_vol, spot_history=spot, iv_rank_history=iv),
    ]
    agg = aggregate_markout(cms, [])
    # Only directional contributes to T+21 average (vol_regime in iv_rank_pts units).
    assert agg[21]["n_calls"] == 1
    assert agg[21]["avg_call_markout"] == pytest.approx(0.10)


# ----- Pattern analysis (monthly) -----


def test_pattern_analysis_per_call_type_and_ticker():
    base = date(2026, 5, 1)
    spot = {
        "TSLA": {
            base: 100.0,
            _horizon_date(base, 21): 90.0,  # bullish call → WRONG
            base + timedelta(days=7): 100.0,
            _horizon_date(base + timedelta(days=7), 21): 88.0,
            base + timedelta(days=14): 100.0,
            _horizon_date(base + timedelta(days=14), 21): 85.0,
        }
    }
    # 3 directional bullish calls on TSLA — all wrong.
    calls = [
        Call("TSLA", base, "directional", +1, None, Path("t1.md"), ""),
        Call(
            "TSLA",
            base + timedelta(days=7),
            "directional",
            +1,
            None,
            Path("t2.md"),
            "",
        ),
        Call(
            "TSLA",
            base + timedelta(days=14),
            "directional",
            +1,
            None,
            Path("t3.md"),
            "",
        ),
    ]
    cms = [compute_call_markout(c, spot_history=spot) for c in calls]
    pat = detect_pattern_anomalies(cms)
    assert pat["by_call_type"]["directional"]["hit_rate"] == 0.0
    assert "TSLA" in pat["by_ticker_min3"]
    assert pat["by_ticker_min3"]["TSLA"]["hit_rate"] == 0.0


# ----- Action items -----


def test_action_items_proposes_skill_rule_for_low_hit_rate_ticker(tmp_path: Path):
    base = date(2026, 5, 1)
    spot = {
        "TSLA": {
            base: 100.0,
            _horizon_date(base, 21): 90.0,
            base + timedelta(days=7): 100.0,
            _horizon_date(base + timedelta(days=7), 21): 88.0,
            base + timedelta(days=14): 100.0,
            _horizon_date(base + timedelta(days=14), 21): 85.0,
        }
    }
    drafts_dir = tmp_path / "drafts"
    archive = tmp_path / "private"
    archive.mkdir()
    for i in range(3):
        _write_archive(
            archive,
            name=f"tsla-{i}.md",
            ticker="TSLA",
            date_iso=(base + timedelta(days=7 * i)).isoformat(),
            structures=["long_call"],
        )
    # today = base+14 puts the monthly window at [base-16, base+14], catching
    # all 3 archive dates (base, base+7d, base+14d).
    report = run_review(
        window="monthly",
        today=base + timedelta(days=14),
        archive_dir=archive,
        spot_history=spot,
        iv_rank_history=None,
        trades=[],
        drafts_dir=drafts_dir,
        write_back=False,
        generate_drafts=True,
    )
    assert len(report.calls) == 3
    assert all(cm.verdict == "WRONG" for cm in report.calls)
    s_items = [i for i in report.action_items if i["id"].startswith("S")]
    p_items = [i for i in report.action_items if i["id"].startswith("P")]
    assert len(s_items) == 1  # TSLA hit_rate 0% over 3 calls fires the S item
    assert "TSLA" in s_items[0]["desc"]
    assert len(p_items) == 3  # one pitfall candidate per WRONG call


# ----- Pitfall drafts -----


def test_pitfall_drafts_are_idempotent(tmp_path: Path):
    base = date(2026, 5, 1)
    call = Call("X", base, "directional", +1, None, Path("x-2026-05-01.md"), "bull X")
    spot = {"X": {base: 100.0, _horizon_date(base, 21): 90.0}}
    cm = compute_call_markout(call, spot_history=spot)
    assert cm.verdict == "WRONG"
    drafts_dir = tmp_path / "drafts"
    written1 = generate_pitfall_drafts([cm], drafts_dir, base + timedelta(days=30))
    written2 = generate_pitfall_drafts([cm], drafts_dir, base + timedelta(days=30))
    assert len(written1) == 1
    assert written2 == []  # second run skips because file exists
    assert written1[0].exists()
    content = written1[0].read_text()
    assert "WRONG" in content
    assert "T+21d:" in content


# ----- Writeback to source Outcome / Lesson -----


def test_writeback_appends_verdict_block_idempotently(tmp_path: Path):
    base = date(2026, 5, 1)
    archive = _write_archive(
        tmp_path,
        name="x-2026-05-01.md",
        ticker="X",
        date_iso=base.isoformat(),
        structures=["long_call"],
        body="\n## Outcome / Lesson\n\n(empty)\n",
    )
    call = Call("X", base, "structure", +1, "long_call", archive, "bull X")
    spot = {"X": {base: 100.0, _horizon_date(base, 21): 110.0}}
    cm = compute_call_markout(call, spot_history=spot)
    review_date = base + timedelta(days=30)
    n1 = write_back_outcome([cm], review_date)
    n2 = write_back_outcome([cm], review_date)  # second run is idempotent
    assert n1 == 1
    assert n2 == 0
    text = archive.read_text()
    assert "复盘" in text
    assert "CORRECT" in text


def test_writeback_skips_archives_without_outcome_section(tmp_path: Path):
    base = date(2026, 5, 1)
    archive = _write_archive(
        tmp_path,
        name="x.md",
        ticker="X",
        date_iso=base.isoformat(),
        structures=["long_call"],
        body="# body without outcome section\n",
    )
    call = Call("X", base, "structure", +1, "long_call", archive, "")
    spot = {"X": {base: 100.0, _horizon_date(base, 21): 110.0}}
    cm = compute_call_markout(call, spot_history=spot)
    n = write_back_outcome([cm], base + timedelta(days=30))
    assert n == 0


# ----- End-to-end pipeline -----


def test_run_review_end_to_end_smoke(tmp_path: Path):
    base = date(2026, 5, 15)
    archive = tmp_path / "private"
    archive.mkdir()
    _write_archive(
        archive,
        name="googl-bull.md",
        ticker="GOOGL",
        date_iso=base.isoformat(),
        structures=["bull_put_spread"],
        body="\n## Outcome / Lesson\n\n",
    )
    spot = {
        "GOOGL": {
            base: 175.0,
            _horizon_date(base, 1): 176.0,
            _horizon_date(base, 5): 178.0,
            _horizon_date(base, 10): 180.0,
            _horizon_date(base, 21): 185.0,
            _horizon_date(base, 45): 195.0,
        }
    }
    trades = [
        Trade(
            ticker="GOOGL",
            trade_date=base + timedelta(days=1),  # followed within 3 days
            side="SELL",
            quantity=1,
            fill_price=3.0,
            contract_type="OPT",
            option_meta={"right": "P", "strike": 170.0, "expiry_iso": "2026-07-15"},
        )
    ]
    report = run_review(
        window="weekly",
        today=base + timedelta(days=46),
        archive_dir=archive,
        spot_history=spot,
        iv_rank_history=None,
        trades=trades,
        option_iv={"GOOGL": 0.30},
        drafts_dir=tmp_path / "drafts",
        write_back=False,  # don't mutate fixture file content beyond appending
        generate_drafts=False,
    )
    # Weekly window: today - 7 days to today = [base+39, base+46]; base (analysis date)
    # is outside, so no calls inside window. Use monthly window instead.
    report_m = run_review(
        window="monthly",
        today=base + timedelta(days=29),
        archive_dir=archive,
        spot_history=spot,
        iv_rank_history=None,
        trades=trades,
        option_iv={"GOOGL": 0.30},
        drafts_dir=tmp_path / "drafts",
        write_back=False,
        generate_drafts=False,
    )
    assert len(report_m.calls) == 1
    assert report_m.calls[0].verdict == "CORRECT"
    assert len(report_m.trades) == 1
    # The trade was on the same direction → followed_correct.
    assert len(report_m.discipline.followed_correct) == 1


# ----- Horizon date helper -----


def test_horizon_date_uses_5_per_week_proxy():
    base = date(2026, 5, 1)  # Friday
    assert _horizon_date(base, 5) == base + timedelta(days=7)
    assert _horizon_date(base, 21) == base + timedelta(days=29)
    assert _horizon_date(base, 45) == base + timedelta(days=63)


# ----- Reconcile mapping -----


def test_reconcile_calls_with_trades_builds_full_map():
    base = date(2026, 5, 1)
    c1 = Call("X", base, "directional", +1, None, Path("x.md"), "")
    c2 = Call("Y", base, "directional", -1, None, Path("y.md"), "")
    trades = [
        Trade("X", base + timedelta(days=2), "BUY", 100, 100.0, "STK", None),
    ]
    out = reconcile_calls_with_trades([c1, c2], trades)
    assert out[c1] is True
    assert out[c2] is False
