"""Tests for the 复盘 (review) framework — see scripts/retrospective.py.

Covers the pure-function core under hard rule #9 source separation:
frontmatter parsing, scope filter, call extraction, markout
(directional / vol regime / structure), trade markout, per-layer
aggregates (Layer A = call-only, Layer B = trade-only), pattern
analysis, action item generation, pitfall draft idempotency,
Outcome / Lesson writeback idempotency.

Live data fetchers (TV historical, IB executions, Futu CLI, UW IV
rank history) are NOT tested here — they're CLI orchestrator concerns.
Cross-stream join functions were removed in the source-separation
refactor; their tests are gone.
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
    aggregate_call_markout,
    aggregate_trade_markout,
    compute_call_markout,
    compute_trade_markout,
    detect_pattern_anomalies,
    extract_calls_from_archive,
    generate_action_items,
    generate_pitfall_drafts,
    parse_archive_frontmatter,
    parse_structured_calls,
    run_review,
    validate_archive_dir,
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


def test_vol_regime_markout_skips_only_t45():
    """D2: T+1d is now computed for vol regime (the 6/05 sell-off showed IV
    rank can jump 17 pts overnight). T+45d remains skipped — IV mean-reverts
    by then and the signal is too noisy."""
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
    # T+1d data is missing here, so it returns None — but with mark_source
    # "missing" rather than "skipped" (proves the design now tries to compute).
    assert cm.horizons[1] is None
    assert cm.mark_sources[1] == "missing"
    # T+45d is skipped by design (IV rank too noisy that far out).
    assert cm.horizons[45] is None
    assert cm.mark_sources[45] == "skipped"
    # T+5d had data → computed.
    assert cm.horizons[5] is not None


def test_d2_vol_regime_t1d_computes_when_iv_rank_jumps_overnight():
    """D2: regression test for the 2026-06-05 scenario — TSLA IV rank jumped
    16.57 → 33.07 overnight (+16.5 pts), confirming a CHEAP call from 6/04.
    T+1d should now catch this; pre-fix it was hard-coded to None.
    """
    call = Call(
        ticker="TSLA",
        analysis_date=date(2026, 6, 4),
        call_type="vol_regime",
        direction=+1,  # CHEAP — expects IV to expand
        structure=None,
        archive_path=Path("tsla.md"),
        notes="",
    )
    iv_ranks = {
        "TSLA": {
            date(2026, 6, 4): 16.57,
            _horizon_date(date(2026, 6, 4), 1): 33.07,
        }
    }
    cm = compute_call_markout(call, spot_history={}, iv_rank_history=iv_ranks)
    # +1 direction × (33.07 − 16.57) = +16.5 pts. CORRECT well past the ±5 band.
    assert cm.horizons[1] == pytest.approx(16.5)
    assert cm.mark_sources[1] == "uw_iv_rank"


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


# ----- Per-layer aggregate (Layer A / Layer B, never mixed) -----


def test_aggregate_call_markout_excludes_iv_rank_units():
    """Layer A: mixes raw_pct + normalized_pnl, never iv_rank_pts."""
    base = date(2026, 5, 1)
    spot = {"X": {base: 100.0, _horizon_date(base, 21): 110.0}}
    iv = {"X": {base: 75.0, _horizon_date(base, 21): 50.0}}
    c_dir = Call("X", base, "directional", +1, None, Path("d.md"), "")
    c_vol = Call("X", base, "vol_regime", -1, None, Path("v.md"), "")
    cms = [
        compute_call_markout(c_dir, spot_history=spot),
        compute_call_markout(c_vol, spot_history=spot, iv_rank_history=iv),
    ]
    agg = aggregate_call_markout(cms)
    assert agg[21]["n_calls"] == 1
    assert agg[21]["avg_call_markout"] == pytest.approx(0.10)
    assert "avg_trade_markout" not in agg[21]  # source separation: no trade fields


def test_aggregate_trade_markout_is_pure_layer_b():
    """Layer B: aggregates trade markouts only, no call fields."""
    base = date(2026, 5, 1)
    spot = {"X": {base: 100.0, _horizon_date(base, 1): 102.0}}
    trade = Trade("X", base, "BUY", 100, 100.0, "STK", None)
    tm = compute_trade_markout(trade, spot_history=spot)
    agg = aggregate_trade_markout([tm])
    assert agg[1]["n_trades"] == 1
    assert agg[1]["avg_trade_markout"] == pytest.approx(0.02)
    assert "avg_call_markout" not in agg[1]  # source separation: no call fields


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
        trade_sources=[],
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
        trade_sources=["IB", "Futu"],
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
        trade_sources=["IB", "Futu"],
        option_iv={"GOOGL": 0.30},
        drafts_dir=tmp_path / "drafts",
        write_back=False,
        generate_drafts=False,
    )
    # Layer A (archive): one call, verdict CORRECT.
    assert len(report_m.calls) == 1
    assert report_m.calls[0].verdict == "CORRECT"
    # Layer B (broker): one trade. NO scorecard joining the two layers (hard rule #9).
    assert len(report_m.trades) == 1
    assert report_m.trade_sources == ["IB", "Futu"]
    assert report_m.cross_cut_advisory == []  # no advisory passed in
    # Per-layer aggregates exist as independent dicts.
    assert "avg_call_markout" in report_m.call_aggregate[21]
    assert "avg_trade_markout" in report_m.trade_aggregate[21]


# ----- Horizon date helper -----


def test_horizon_date_uses_5_per_week_proxy():
    base = date(2026, 5, 1)  # Friday
    assert _horizon_date(base, 5) == base + timedelta(days=7)
    assert _horizon_date(base, 21) == base + timedelta(days=29)
    assert _horizon_date(base, 45) == base + timedelta(days=63)


# ----- Broker trade parsers (Layer B sources) -----


def test_parse_ib_trades_window_and_realized_pnl():
    from scripts.retrospective import parse_ib_trades

    resp = {
        "trades": [
            {
                "symbol": "QQQ",
                "sec_type": "OPT",
                "side": "SELL",
                "size": 1,
                "price": 177.11,
                "trade_time": "2026-06-03T14:14:16Z",
                "realized_pnl": 10226.53,
            },
            {
                "symbol": "QQQ",
                "sec_type": "OPT",
                "side": "BUY",
                "size": 1,
                "price": 72.67,
                "trade_time": "2026-06-05T14:46:19Z",
                "realized_pnl": 0,  # opening trade — should map to None
            },
            {
                "symbol": "QQQ",
                "sec_type": "OPT",
                "side": "SELL",
                "size": 1,
                "price": 9.09,
                "trade_time": "2026-05-22T17:34:11Z",  # outside window
                "realized_pnl": 0,
            },
        ]
    }
    out = parse_ib_trades(resp, date(2026, 5, 30), date(2026, 6, 6))
    assert len(out) == 2
    closer = next(t for t in out if t.trade_date == date(2026, 6, 3))
    opener = next(t for t in out if t.trade_date == date(2026, 6, 5))
    assert closer.realized_pnl == pytest.approx(10226.53)
    assert opener.realized_pnl is None  # zero realized_pnl normalized to None


def test_parse_futu_trades_matched_pair_attaches_realized_to_close_only():
    from scripts.retrospective import parse_futu_trades

    report = {
        "trades": {
            "matchedTrades": [
                {
                    "openTrade": {
                        "symbol": "FCX",
                        "instrumentType": "option",
                        "side": "buy",
                        "quantity": 6,
                        "price": 6.85,
                        "timestamp": "2026-06-01T15:44:26.048Z",
                        "optionDetails": {
                            "underlying": "FCX",
                            "expiry": "2026-09-18",
                            "strike": 70,
                            "putCall": "call",
                        },
                    },
                    "closeTrade": {
                        "symbol": "FCX",
                        "instrumentType": "option",
                        "side": "sell",
                        "quantity": 1,
                        "price": 9.4,
                        "timestamp": "2026-06-04T14:23:02.164Z",
                        "optionDetails": {
                            "underlying": "FCX",
                            "expiry": "2026-09-18",
                            "strike": 70,
                            "putCall": "call",
                        },
                    },
                    "realizedPnl": 255.0,
                }
            ],
            "unmatchedTrades": [
                {
                    "symbol": "MU",
                    "instrumentType": "option",
                    "side": "buy",
                    "quantity": 2,
                    "price": 4.27,
                    "timestamp": "2026-06-04T14:21:06.458Z",
                    "optionDetails": {
                        "underlying": "MU",
                        "expiry": "2026-06-12",
                        "strike": 750,
                        "putCall": "put",
                    },
                }
            ],
        }
    }
    out = parse_futu_trades(report, date(2026, 5, 30), date(2026, 6, 6))
    assert len(out) == 3
    open_leg = next(t for t in out if t.ticker == "FCX" and t.side == "BUY")
    close_leg = next(t for t in out if t.ticker == "FCX" and t.side == "SELL")
    unmatched = next(t for t in out if t.ticker == "MU")
    # Source separation invariant: realizedPnl lives on the CLOSE leg only.
    assert open_leg.realized_pnl is None
    assert close_leg.realized_pnl == pytest.approx(255.0)
    assert unmatched.realized_pnl is None
    # Option metadata propagated.
    assert close_leg.option_meta["right"] == "C"
    assert close_leg.option_meta["strike"] == 70.0
    assert unmatched.option_meta["right"] == "P"


def test_parse_futu_trades_filters_window():
    from scripts.retrospective import parse_futu_trades

    report = {
        "trades": {
            "dateRange": {
                "from": "2026-05-01T00:00:00.000Z",
                "to": "2026-06-06T15:59:59.000Z",  # fresh through Sat 6/06
            },
            "matchedTrades": [],
            "unmatchedTrades": [
                {
                    "symbol": "X",
                    "instrumentType": "stock",
                    "side": "buy",
                    "quantity": 10,
                    "price": 100.0,
                    "timestamp": "2026-05-15T15:00:00Z",  # outside window
                }
            ],
        }
    }
    out = parse_futu_trades(report, date(2026, 5, 30), date(2026, 6, 6))
    assert out == []


def test_parse_futu_trades_raises_when_stale():
    """Hard rule #7: Futu cache ending before the last trading day in window must error.

    The Futu CLI caches by ISO week, so re-runs without `--rerun` return data
    silently 1-2 trading days stale. This is more dangerous than missing data:
    the report appears to succeed but the most recent trading day's activity
    is dropped. (Observed in first v0.3 weekly run, where 26 trades on 6/05
    were missing from a cache that stopped at 6/04 EOD.)
    """
    from scripts.retrospective import parse_futu_trades

    report = {
        "trades": {
            "dateRange": {
                "from": "2026-05-01T00:00:00.000Z",
                "to": "2026-06-04T15:59:59.000Z",  # cache ends Thu
            },
            "matchedTrades": [],
            "unmatchedTrades": [],
        }
    }
    # window_end Sat 6/06 → last trading day = Fri 6/05. Cache to Thu 6/04 < 6/05 → stale.
    with pytest.raises(ValueError, match="Futu data stale"):
        parse_futu_trades(report, date(2026, 5, 30), date(2026, 6, 6))


def test_parse_futu_trades_allow_stale_overrides_freshness_gate():
    """`allow_stale=True` opt-out for deliberate backfills / historical reviews."""
    from scripts.retrospective import parse_futu_trades

    report = {
        "trades": {
            "dateRange": {
                "from": "2026-05-01T00:00:00.000Z",
                "to": "2026-06-04T15:59:59.000Z",  # would normally be stale
            },
            "matchedTrades": [],
            "unmatchedTrades": [],
        }
    }
    out = parse_futu_trades(
        report, date(2026, 5, 30), date(2026, 6, 6), allow_stale=True
    )
    assert out == []


def test_parse_futu_trades_fresh_through_friday_is_ok_when_window_ends_saturday():
    """Sat window_end + cache through Fri = NOT stale (Fri is the last trading day)."""
    from scripts.retrospective import parse_futu_trades

    report = {
        "trades": {
            "dateRange": {
                "from": "2026-05-01T00:00:00.000Z",
                "to": "2026-06-05T15:59:59.000Z",  # Friday EOD
            },
            "matchedTrades": [],
            "unmatchedTrades": [],
        }
    }
    out = parse_futu_trades(report, date(2026, 5, 30), date(2026, 6, 6))
    assert out == []  # no trades but no exception either


# ----- Hard rule #9: source separation invariants -----


def test_source_separation_no_reconcile_or_discipline_symbols_exported():
    """Regression guard for hard rule #9: cross-stream join API must stay deleted."""
    import scripts.retrospective as r

    for name in (
        "reconcile_calls_with_trades",
        "discipline_quadrant",
        "DisciplineQuadrant",
        "_trade_matches_call",
        "DISCIPLINE_MATCH_WINDOW_DAYS",
        "aggregate_markout",  # split into call/trade specific
    ):
        assert not hasattr(r, name), (
            f"{name} must remain removed per SKILL.md hard rule #9 "
            "(archive ≠ broker source separation)"
        )


# ----- D1: closing-trade exclusion -----


def test_d1_closing_trade_excluded_from_markout():
    """D1: a BTC trade with realized_pnl != 0 has crystallized P/L.
    Re-marking via BSM produces nonsense (fake +95% markout on a deep ITM
    option closed near intrinsic) — exclude entirely.
    """
    trade = Trade(
        ticker="QQQ",
        trade_date=date(2026, 6, 3),
        side="BUY",  # BTC on a short put
        quantity=1,
        fill_price=1.84,
        contract_type="OPT",
        option_meta={"right": "P", "strike": 700.0, "expiry_iso": "2026-06-18"},
        realized_pnl=1273.0,  # P/L already realized
    )
    spot = {
        "QQQ": {
            date(2026, 6, 3): 744.21,
            _horizon_date(date(2026, 6, 3), 1): 740.61,
        }
    }
    tm = compute_trade_markout(trade, spot_history=spot, option_iv={"QQQ": 0.30})
    assert all(v is None for v in tm.horizons.values())
    assert all(src == "closing_trade_excluded" for src in tm.mark_sources.values())
    assert tm.closed_at_horizon == 0


def test_d1_opening_trade_still_computed():
    """D1 regression guard: realized_pnl=None or =0 → still compute markout."""
    trade = Trade(
        ticker="QQQ",
        trade_date=date(2026, 6, 4),
        side="BUY",
        quantity=1,
        fill_price=739.07,
        contract_type="STK",
        option_meta=None,
        realized_pnl=None,
    )
    spot = {
        "QQQ": {
            date(2026, 6, 4): 739.07,
            _horizon_date(date(2026, 6, 4), 1): 705.06,
        }
    }
    tm = compute_trade_markout(trade, spot_history=spot)
    assert tm.horizons[1] is not None
    assert tm.horizons[1] < 0  # spot dropped → BUY loss
    assert tm.mark_sources[1] == "tv_spot"


# ----- S1: multi-ticker macro archives -----


def test_s1_multi_ticker_archive_emits_one_call_per_ticker(tmp_path: Path):
    """S1: previously archives with comma-separated tickers were skipped.
    Now: emit one Call per ticker, all sharing the same archive_path.
    """
    _write_archive(
        tmp_path,
        name="macro-2026-05-15.md",
        ticker="QQQ, SPY, IWM, DIA, VIX",
        date_iso="2026-05-15",
        structures=["observation", "vol-regime-call"],
        body=(
            "## TL;DR\n\nVol regime CHEAP across indices — IV ranks all "
            "below 40, buy premium bias.\n"
        ),
    )
    calls, skipped = extract_calls_from_archive(
        tmp_path, date(2026, 5, 1), date(2026, 5, 31)
    )
    tickers = sorted(c.ticker for c in calls)
    assert tickers == ["DIA", "IWM", "QQQ", "SPY", "VIX"]
    # All five share the same archive_path.
    assert len({c.archive_path for c in calls}) == 1
    # All five classified as vol_regime (prose says CHEAP).
    assert all(c.call_type == "vol_regime" for c in calls)
    assert all(c.direction == +1 for c in calls)
    assert not skipped  # nothing skipped


def test_s1_multi_ticker_forces_prose_classification_not_structure(tmp_path: Path):
    """S1: a multi-ticker book review with structures=[csp, bull_put_spread]
    must NOT emit a structure call per ticker — those structures apply to
    specific positions in the book, not every ticker uniformly.
    """
    _write_archive(
        tmp_path,
        name="book-2026-05-20.md",
        ticker="TSLA, NVDA, GOOGL",
        date_iso="2026-05-20",
        structures=["csp", "bull_put_spread"],
        body=("## TL;DR\n\nBullish into NFP — long delta theme across the book.\n"),
    )
    calls, _ = extract_calls_from_archive(tmp_path, date(2026, 5, 1), date(2026, 5, 31))
    # Should be 3 directional calls (one per ticker), not 3 structure calls.
    assert len(calls) == 3
    assert all(c.call_type == "directional" for c in calls)
    assert all(c.direction == +1 for c in calls)  # prose says bullish


def test_s1_single_ticker_still_uses_structure_branch(tmp_path: Path):
    """S1 regression guard: single-ticker archives unchanged behavior."""
    _write_archive(
        tmp_path,
        name="nvda.md",
        ticker="NVDA",
        date_iso="2026-05-20",
        structures=["csp"],
    )
    calls, _ = extract_calls_from_archive(tmp_path, date(2026, 5, 1), date(2026, 5, 31))
    assert len(calls) == 1
    assert calls[0].call_type == "structure"
    assert calls[0].structure == "csp"


# ----- S2: archive validator -----


def test_s2_validator_flags_missing_frontmatter(tmp_path: Path):
    """S2: a markdown file without YAML frontmatter is flagged."""
    p = tmp_path / "broken.md"
    p.write_text("# TSLA — runbook trace\n\nNo frontmatter here.\n")
    entries = validate_archive_dir(tmp_path)
    assert len(entries) == 1
    issues = entries[0]["issues"]
    assert any("missing YAML frontmatter" in i for i in issues)


def test_s2_validator_flags_missing_required_fields(tmp_path: Path):
    """S2: frontmatter missing ticker/date/structures/tags is flagged."""
    p = tmp_path / "thin.md"
    p.write_text("---\nticker: X\n---\n\n## Outcome / Lesson\n")
    entries = validate_archive_dir(tmp_path)
    issues = entries[0]["issues"]
    assert any("date" in i for i in issues)
    assert any("structures" in i for i in issues)
    assert any("tags" in i for i in issues)


def test_s2_validator_flags_unparseable_date(tmp_path: Path):
    p = tmp_path / "bad-date.md"
    p.write_text(
        "---\n"
        "ticker: X\n"
        "date: yesterday\n"
        "structures: []\n"
        "tags: []\n"
        "---\n\n"
        "## Outcome / Lesson\n"
    )
    entries = validate_archive_dir(tmp_path)
    assert any("unparseable date" in i for i in entries[0]["issues"])


def test_s2_validator_flags_missing_outcome_section(tmp_path: Path):
    p = tmp_path / "no-outcome.md"
    p.write_text(
        "---\n"
        "ticker: X\n"
        "date: 2026-05-15\n"
        "structures: []\n"
        "tags: []\n"
        "---\n\n"
        "# body without outcome section\n"
    )
    entries = validate_archive_dir(tmp_path)
    assert any("Outcome / Lesson" in i for i in entries[0]["issues"])


def test_s2_validator_clean_file_has_no_issues(tmp_path: Path):
    _write_archive(
        tmp_path,
        name="clean.md",
        ticker="X",
        date_iso="2026-05-15",
        structures=["csp"],
        body="\n## Outcome / Lesson\n\n(empty)\n",
    )
    entries = validate_archive_dir(tmp_path)
    assert entries[0]["issues"] == []


def test_s2_validator_skips_readme(tmp_path: Path):
    (tmp_path / "README.md").write_text("# index")
    entries = validate_archive_dir(tmp_path)
    assert entries == []


# ----- Cold-storage archive/ subtree exclusion -----


def test_extract_skips_cold_archive_subtree_by_default(tmp_path: Path):
    """Active files under ticker/ are scanned; cold files under archive/
    are excluded unless --include-archive is passed."""
    (tmp_path / "ticker").mkdir()
    (tmp_path / "archive" / "2026-04" / "ticker").mkdir(parents=True)
    _write_archive(
        tmp_path / "ticker",
        name="2026-05-15-googl-long-eval.md",
        ticker="GOOGL",
        date_iso="2026-05-15",
        structures=["bull_put_spread"],
    )
    _write_archive(
        tmp_path / "archive" / "2026-04" / "ticker",
        name="2026-04-10-aapl-long-eval.md",
        ticker="AAPL",
        date_iso="2026-04-10",
        structures=["bull_put_spread"],
    )
    # Default: only active GOOGL surfaces; AAPL stays frozen
    calls, _ = extract_calls_from_archive(tmp_path, date(2026, 4, 1), date(2026, 5, 31))
    assert sorted(c.ticker for c in calls) == ["GOOGL"]
    # Opt-in: both surface
    calls_all, _ = extract_calls_from_archive(
        tmp_path, date(2026, 4, 1), date(2026, 5, 31), include_archive=True
    )
    assert sorted(c.ticker for c in calls_all) == ["AAPL", "GOOGL"]


def test_validator_skips_cold_archive_subtree_by_default(tmp_path: Path):
    """Malformed file in cold archive/ should not noisy-up routine validation."""
    (tmp_path / "ticker").mkdir()
    (tmp_path / "archive" / "2026-04" / "ticker").mkdir(parents=True)
    # Clean active file
    _write_archive(
        tmp_path / "ticker",
        name="active.md",
        ticker="X",
        date_iso="2026-05-15",
        structures=["csp"],
        body="\n## Outcome / Lesson\n\n(empty)\n",
    )
    # Malformed cold file (no frontmatter)
    (tmp_path / "archive" / "2026-04" / "ticker" / "frozen.md").write_text(
        "# no frontmatter, but it's frozen\n"
    )
    # Default: only the active file is examined; cold file ignored
    entries = validate_archive_dir(tmp_path)
    assert [e["file"] for e in entries] == ["active.md"]
    # Opt-in: cold file surfaces with its issue
    entries_all = validate_archive_dir(tmp_path, include_archive=True)
    files = sorted(e["file"] for e in entries_all)
    assert files == ["active.md", "frozen.md"]


# --- parse_xenon_blotter (Layer-B trade flow from xenon /blotter) ---

from scripts.retrospective import parse_xenon_blotter  # noqa: E402

_BLOTTER = {
    "configured": True,
    "source": "postgres",
    "as_of": "2026-06-17T19:47:53+00:00",
    "summary": {"realized_pnl": -479.14},
    "open_trades": [],
    "closed_trades": [
        {
            "symbol": "GLD",
            "contract_desc": "Stock",
            "sec_type": "OPT",
            "is_closed": True,
            "net_quantity": 0,
            "realized_pnl": -479.14,
            "perm_id": None,
            "executions": [
                {
                    "exec_id": "a.1",
                    "time": "2026-06-12T03:40:00+08:00",
                    "side": "SELL",
                    "quantity": 1,
                    "price": 28.00,
                    "commission": 1.0,
                },
                {
                    "exec_id": "a.2",
                    "time": "2026-06-16T03:47:53+08:00",
                    "side": "BUY",
                    "quantity": 1,
                    "price": 22.69,
                    "commission": 1.0,
                },
            ],
        }
    ],
}


def test_parse_xenon_blotter_emits_per_fill_trades_with_realized_on_last():
    trades = parse_xenon_blotter(_BLOTTER, date(2026, 6, 1), date(2026, 6, 30))
    assert len(trades) == 2
    assert all(t.ticker == "GLD" and t.contract_type == "OPT" for t in trades)
    assert all(t.option_meta is None for t in trades)
    opener, closer = trades
    assert opener.side == "SELL" and opener.fill_price == 28.00
    assert opener.realized_pnl is None  # only the last (closing) fill carries it
    assert closer.side == "BUY" and closer.fill_price == 22.69
    assert closer.realized_pnl == -479.14


def test_parse_xenon_blotter_filters_to_window():
    trades = parse_xenon_blotter(_BLOTTER, date(2026, 6, 14), date(2026, 6, 30))
    # only the 6/16 fill is in-window
    assert len(trades) == 1 and trades[0].fill_price == 22.69


# ----- U1 fixes (2026-07-02 June review): R1-R4 -----


def test_r1_writeback_multi_ticker_archive_writes_all_verdicts(tmp_path: Path):
    """R1: marker carries ticker+type, so every call on a shared archive lands."""
    base = date(2026, 5, 1)
    archive = _write_archive(
        tmp_path,
        name="macro-2026-05-01.md",
        ticker="SPY, QQQ",
        date_iso=base.isoformat(),
        structures=[],
        body="\n## Outcome / Lesson\n\n(empty)\n",
    )
    spot = {
        "SPY": {base: 100.0, _horizon_date(base, 21): 110.0},
        "QQQ": {base: 100.0, _horizon_date(base, 21): 90.0},
    }
    cms = [
        compute_call_markout(
            Call(tk, base, "directional", +1, None, archive, "bull"),
            spot_history=spot,
        )
        for tk in ("SPY", "QQQ")
    ]
    review_date = base + timedelta(days=30)
    n1 = write_back_outcome(cms, review_date)
    assert n1 == 2  # both tickers written, not just the first
    text = archive.read_text()
    assert f"复盘 {review_date.isoformat()}, SPY directional):** CORRECT" in text
    assert f"复盘 {review_date.isoformat()}, QQQ directional):** WRONG" in text
    # idempotent per call on re-run
    assert write_back_outcome(cms, review_date) == 0


def test_r2_pitfall_drafts_unique_per_ticker(tmp_path: Path):
    """R2: two WRONG calls from the same archive emit two draft files."""
    base = date(2026, 5, 1)
    shared = Path("macro-2026-05-01.md")
    spot = {
        "SPY": {base: 100.0, _horizon_date(base, 21): 90.0},
        "QQQ": {base: 100.0, _horizon_date(base, 21): 90.0},
    }
    cms = [
        compute_call_markout(
            Call(tk, base, "directional", +1, None, shared, "bull"),
            spot_history=spot,
        )
        for tk in ("SPY", "QQQ")
    ]
    assert all(cm.verdict == "WRONG" for cm in cms)
    written = generate_pitfall_drafts(cms, tmp_path / "drafts", base)
    assert len(written) == 2
    names = {p.name for p in written}
    assert names == {
        "pitfall-macro-2026-05-01-spy-directional.md",
        "pitfall-macro-2026-05-01-qqq-directional.md",
    }


def test_r3_parse_futu_trades_min_lookback_guard():
    """R3: short-lookback report raises so cross-month realized isn't dropped."""
    from scripts.retrospective import parse_futu_trades

    report = {
        "trades": {
            "dateRange": {"from": "2026-06-01T00:00:00Z", "to": "2026-07-01T00:00:00Z"},
            "matchedTrades": [],
            "unmatchedTrades": [],
        }
    }
    with pytest.raises(ValueError, match="lookback too short"):
        parse_futu_trades(
            report, date(2026, 6, 1), date(2026, 6, 30), min_lookback_days=60
        )
    # default (0) preserves legacy behavior; long-enough lookback passes
    assert parse_futu_trades(report, date(2026, 6, 1), date(2026, 6, 30)) == []
    report["trades"]["dateRange"]["from"] = "2026-04-01T00:00:00Z"
    assert (
        parse_futu_trades(
            report, date(2026, 6, 1), date(2026, 6, 30), min_lookback_days=60
        )
        == []
    )


def test_r4_realized_pnl_by_currency_never_mixes():
    """R4: KRW closes group separately from USD — no cross-currency sum."""
    from scripts.retrospective import parse_ib_trades, realized_pnl_by_currency

    resp = {
        "trades": [
            {
                "symbol": "000660",
                "sec_type": "STK",
                "side": "SELL",
                "size": 9,
                "price": 2858000,
                "trade_time": "2026-06-22T05:30:00Z",
                "realized_pnl": -595618.2,
                "currency": "KRW",
            },
            {
                "symbol": "SPX",
                "sec_type": "OPT",
                "side": "SELL",
                "size": 1,
                "price": 21.7,
                "trade_time": "2026-06-23T15:30:00Z",
                "realized_pnl": 726.7185,
                "currency": "USD",
            },
            {
                # opening leg: no realized -> excluded from the P&L table
                "symbol": "QQQ",
                "sec_type": "OPT",
                "side": "BUY",
                "size": 1,
                "price": 5.52,
                "trade_time": "2026-06-30T15:30:00Z",
                "realized_pnl": 0,
                "currency": "USD",
            },
        ]
    }
    trades = parse_ib_trades(resp, date(2026, 6, 1), date(2026, 6, 30))
    assert [t.currency for t in trades] == ["KRW", "USD", "USD"]
    grouped = realized_pnl_by_currency(trades)
    assert grouped["KRW"] == {"realized": -595618.2, "n_closes": 1}
    assert grouped["USD"]["n_closes"] == 1
    assert grouped["USD"]["realized"] == pytest.approx(726.7185)
    assert set(grouped) == {"KRW", "USD"}


# ----- U2 (2026-07-02): structured `calls:` frontmatter -----


def _write_archive_with_calls(
    dir_: Path,
    *,
    name: str,
    ticker: str,
    date_iso: str,
    calls_line: str,
    body: str = "",
) -> Path:
    p = dir_ / name
    fm_lines = [
        "---",
        f"ticker: {ticker}",
        f"date: {date_iso}",
        "structures: []",
        "tags: []",
        calls_line,
        "---",
    ]
    p.write_text("\n".join(fm_lines) + "\n" + body, encoding="utf-8")
    return p


def test_structured_calls_take_precedence_over_prose(tmp_path: Path):
    archive = _write_archive_with_calls(
        tmp_path,
        name="nvda-2026-07-02.md",
        ticker="NVDA",
        date_iso="2026-07-02",
        calls_line=(
            'calls: ["NVDA|structure|-1|bull_put_spread|PROBE|3|true", '
            '"TSLA|directional|+1||NORMAL|0|false"]'
        ),
        # Body would classify bullish via prose keywords if it were read —
        # proves the structured branch short-circuits prose entirely.
        body="## TL;DR\n\nbullish 做多 buy the dip\n",
    )
    calls, skipped = extract_calls_from_archive(
        tmp_path, date(2026, 7, 1), date(2026, 7, 3)
    )
    assert skipped == []
    assert len(calls) == 2
    nvda, tsla = calls
    assert nvda.ticker == "NVDA" and nvda.call_type == "structure"
    assert nvda.direction == -1 and nvda.structure == "bull_put_spread"
    assert nvda.tier == "PROBE" and nvda.crowding_flags == 3
    assert nvda.opposite_case_first is True
    assert tsla.ticker == "TSLA" and tsla.call_type == "directional"
    assert tsla.direction == +1 and tsla.structure is None
    assert tsla.tier == "NORMAL" and tsla.crowding_flags == 0
    assert tsla.opposite_case_first is False
    assert calls[0].archive_path == archive


def test_structured_calls_empty_list_yields_no_calls_and_skips_prose(tmp_path: Path):
    _write_archive_with_calls(
        tmp_path,
        name="macro-2026-07-02.md",
        ticker="SPX",
        date_iso="2026-07-02",
        calls_line="calls: []",
        body="## TL;DR\n\nbullish 做多\n",
    )
    calls, skipped = extract_calls_from_archive(
        tmp_path, date(2026, 7, 1), date(2026, 7, 3)
    )
    assert calls == []
    assert skipped == []  # explicit empty calls is not an error


def test_structured_calls_malformed_entry_reported_not_silently_dropped(
    tmp_path: Path,
):
    _write_archive_with_calls(
        tmp_path,
        name="bad-2026-07-02.md",
        ticker="NVDA",
        date_iso="2026-07-02",
        calls_line='calls: ["NVDA|not_a_type|+1||PROBE|0|false"]',
    )
    calls, skipped = extract_calls_from_archive(
        tmp_path, date(2026, 7, 1), date(2026, 7, 3)
    )
    assert calls == []
    assert len(skipped) == 1
    assert "unknown call_type" in skipped[0]["reason"]


def test_structured_calls_reject_unknown_tier(tmp_path: Path):
    calls, reasons = parse_structured_calls(
        ["NVDA|directional|+1||MEGA_YOLO|0|false"],
        analysis_date=date(2026, 7, 2),
        archive_path=Path("x.md"),
        notes="",
    )
    assert calls == []
    assert len(reasons) == 1 and "unknown tier" in reasons[0]


def test_pattern_analysis_by_tier_only_counts_structured_calls():
    base = date(2026, 5, 1)
    spot = {
        "NVDA": {
            base: 100.0,
            _horizon_date(base, 21): 90.0,  # bullish -> WRONG
            base + timedelta(days=7): 100.0,
            _horizon_date(base + timedelta(days=7), 21): 88.0,
            base + timedelta(days=14): 100.0,
            _horizon_date(base + timedelta(days=14), 21): 85.0,
        }
    }
    tiered_calls = [
        Call(
            "NVDA",
            base + timedelta(days=7 * i),
            "directional",
            +1,
            None,
            Path(f"n{i}.md"),
            "",
            tier="PROBE",
        )
        for i in range(3)
    ]
    untiered_call = Call("NVDA", base, "directional", +1, None, Path("legacy.md"), "")
    cms = [compute_call_markout(c, spot_history=spot) for c in tiered_calls]
    cms.append(compute_call_markout(untiered_call, spot_history=spot))
    pat = detect_pattern_anomalies(cms)
    assert pat["by_tier"]["PROBE"]["n_scored"] == 3
    assert pat["by_tier"]["PROBE"]["hit_rate"] == 0.0
    assert None not in pat["by_tier"]  # untiered call excluded, no crash


def test_k4_action_item_reports_scored_over_raw_not_raw_alone(tmp_path: Path):
    """K4 fix: 'TSLA: 0% over 7 calls' when only 1 was scored is the
    overfitting trap the 2026-07-02 June review flagged — S1 must show
    scored/raw, and the ≥3 threshold gates on SCORED count."""
    base = date(2026, 5, 1)
    # 1 scored (WRONG) + 2 UNKNOWN (missing spot at horizon) => below the
    # PATTERN_MIN_SCORED=3 gate, so no S-item should fire at all.
    spot = {"TSLA": {base: 100.0, _horizon_date(base, 21): 90.0}}
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
    report = run_review(
        window="monthly",
        today=base + timedelta(days=14),
        archive_dir=archive,
        spot_history=spot,  # only base has spot data -> other 2 calls UNKNOWN
        iv_rank_history=None,
        trades=[],
        trade_sources=[],
        write_back=False,
        generate_drafts=False,
    )
    s_items = [i for i in report.action_items if i["id"].startswith("S")]
    assert s_items == []  # 1 scored < PATTERN_MIN_SCORED=3 -> ticker excluded


# ----- U3 (2026-07-02): decision ledger section wiring -----


def test_ledger_section_included_in_render_report(tmp_path: Path):
    from scripts.retrospective import render_report

    archive = tmp_path / "private"
    archive.mkdir()
    report = run_review(
        window="weekly",
        today=date(2026, 7, 2),
        archive_dir=archive,
        spot_history={},
        iv_rank_history=None,
        trades=[],
        trade_sources=[],
        write_back=False,
        generate_drafts=False,
        ledger_section="## Decision ledger\n\n- **L1** TSLA: roll down [NORMAL] due 2026-06-25 ⚠ OVERDUE",
    )
    rendered = render_report(report)
    assert "## Decision ledger" in rendered
    assert "L1" in rendered and "OVERDUE" in rendered
    # Decision ledger section appears before Layer A in the rendered order.
    assert rendered.index("## Decision ledger") < rendered.index("## Layer A")


def test_ledger_section_omitted_when_empty(tmp_path: Path):
    from scripts.retrospective import render_report

    archive = tmp_path / "private"
    archive.mkdir()
    report = run_review(
        window="weekly",
        today=date(2026, 7, 2),
        archive_dir=archive,
        spot_history={},
        iv_rank_history=None,
        trades=[],
        trade_sources=[],
        write_back=False,
        generate_drafts=False,
    )
    assert "## Decision ledger" not in render_report(report)


# ----- U5 (2026-07-02): save_review_report auto-archive -----


def test_save_review_report_writes_expected_path_and_frontmatter(tmp_path: Path):
    from scripts.retrospective import render_report, save_review_report

    archive = tmp_path / "private"
    archive.mkdir()
    report = run_review(
        window="weekly",
        today=date(2026, 7, 2),
        archive_dir=archive,
        spot_history={},
        iv_rank_history=None,
        trades=[],
        trade_sources=[],
        write_back=False,
        generate_drafts=False,
    )
    rendered = render_report(report)
    saved = save_review_report(report, rendered, base_dir=archive)
    expected = archive / "review" / "2026-07-02-book-mixed-weekly-retrospective.md"
    assert saved == expected
    assert saved.exists()
    text = saved.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "ticker: BOOK" in text
    assert "date: 2026-07-02" in text
    assert "tags: [weekly-review, auto-archived]" in text
    assert "# 复盘 — Weekly review" in text  # rendered body preserved


def test_save_review_report_appends_outcome_section_when_missing(tmp_path: Path):
    from scripts.retrospective import render_report, save_review_report

    archive = tmp_path / "private"
    archive.mkdir()
    report = run_review(
        window="monthly",
        today=date(2026, 7, 2),
        archive_dir=archive,
        spot_history={},
        iv_rank_history=None,
        trades=[],
        trade_sources=[],
        write_back=False,
        generate_drafts=False,
    )
    rendered = render_report(report)
    assert "## Outcome / Lesson" not in rendered  # render_report never emits one
    saved = save_review_report(report, rendered, base_dir=archive)
    assert "## Outcome / Lesson" in saved.read_text(encoding="utf-8")


def test_save_review_report_overwrites_same_day_same_window(tmp_path: Path):
    from scripts.retrospective import save_review_report

    archive = tmp_path / "private"
    archive.mkdir()
    report = run_review(
        window="weekly",
        today=date(2026, 7, 2),
        archive_dir=archive,
        spot_history={},
        iv_rank_history=None,
        trades=[],
        trade_sources=[],
        write_back=False,
        generate_drafts=False,
    )
    saved1 = save_review_report(report, "first render", base_dir=archive)
    saved2 = save_review_report(report, "second render", base_dir=archive)
    assert saved1 == saved2
    assert "second render" in saved2.read_text(encoding="utf-8")
    assert "first render" not in saved2.read_text(encoding="utf-8")


# ----- U6 (2026-07-02): flag_hedge_cost_outliers (F3, reverse cost-cap) -----


def _opt_trade(
    *,
    ticker,
    side,
    right,
    strike,
    expiry_iso,
    fill_price,
    quantity=1,
    trade_date=date(2026, 6, 5),
):
    from scripts.retrospective import flag_hedge_cost_outliers  # noqa: F401 (import check)

    return Trade(
        ticker=ticker,
        trade_date=trade_date,
        side=side,
        quantity=quantity,
        fill_price=fill_price,
        contract_type="OPT",
        option_meta={"right": right, "strike": strike, "expiry_iso": expiry_iso},
    )


def test_flag_hedge_cost_outliers_catches_r1_vix_call_spread():
    """R1 case: manual VIX Aug 20/30 call spread ~8% NLV annualized, found
    only by hand-calculation weeks later per the 2026-07-01 skill audit."""
    from scripts.retrospective import flag_hedge_cost_outliers

    # BUY leg only (the SELL leg isn't hedge-like — filtered out by design,
    # see docstring: this overstates spread cost on purpose).
    trades = [
        _opt_trade(
            ticker="VIX",
            side="BUY",
            right="C",
            strike=20,
            expiry_iso="2026-08-21",
            fill_price=5.0,  # $500/contract
            quantity=25,
            trade_date=date(2026, 6, 5),
        )
    ]
    # 77 DTE (6/5 -> 8/21). cost = 500*25 = 12,500. NLV small enough to trip 1.5% cap.
    out = flag_hedge_cost_outliers(trades, nlv=100_000)
    assert len(out) == 1
    assert out[0]["ticker"] == "VIX"
    assert out[0]["annualized_cost_pct"] > 0.015


def test_flag_hedge_cost_outliers_within_cap_not_flagged():
    from scripts.retrospective import flag_hedge_cost_outliers

    trades = [
        _opt_trade(
            ticker="QQQ",
            side="BUY",
            right="P",
            strike=600,
            expiry_iso="2026-12-18",  # ~196 DTE, standing hedge
            fill_price=2.0,
            quantity=5,
            trade_date=date(2026, 6, 5),
        )
    ]
    # cost = 200*5 = 1,000. NLV = 1,000,000 -> annualized well under 1.5%.
    out = flag_hedge_cost_outliers(trades, nlv=1_000_000)
    assert out == []


def test_flag_hedge_cost_outliers_ignores_non_hedge_shapes():
    from scripts.retrospective import flag_hedge_cost_outliers

    trades = [
        # SELL leg -> not a BUY, never flagged regardless of cost.
        _opt_trade(
            ticker="VIX", side="SELL", right="C", strike=30,
            expiry_iso="2026-08-21", fill_price=50.0, quantity=25,
        ),
        # long call on a non-VIX ticker -> not hedge-like.
        _opt_trade(
            ticker="NVDA", side="BUY", right="C", strike=200,
            expiry_iso="2026-07-17", fill_price=50.0, quantity=10,
        ),
        # stock trade -> not OPT, skipped.
        Trade(
            ticker="SPY", trade_date=date(2026, 6, 5), side="BUY",
            quantity=100, fill_price=700.0, contract_type="STK", option_meta=None,
        ),
    ]
    assert flag_hedge_cost_outliers(trades, nlv=100_000) == []


def test_flag_hedge_cost_outliers_skips_missing_option_meta():
    from scripts.retrospective import flag_hedge_cost_outliers

    trades = [
        Trade(
            ticker="VIX", trade_date=date(2026, 6, 5), side="BUY",
            quantity=25, fill_price=50.0, contract_type="OPT", option_meta=None,
        ),
    ]
    assert flag_hedge_cost_outliers(trades, nlv=100_000) == []


def test_flag_hedge_cost_outliers_skips_expired_or_unparseable_expiry():
    from scripts.retrospective import flag_hedge_cost_outliers

    trades = [
        _opt_trade(
            ticker="VIX", side="BUY", right="C", strike=20,
            expiry_iso="not-a-date", fill_price=50.0, quantity=25,
        ),
        _opt_trade(
            ticker="VIX", side="BUY", right="C", strike=20,
            expiry_iso="2026-06-01",  # before trade_date 2026-06-05 -> dte<=0
            fill_price=50.0, quantity=25, trade_date=date(2026, 6, 5),
        ),
    ]
    assert flag_hedge_cost_outliers(trades, nlv=100_000) == []


def test_flag_hedge_cost_outliers_raises_on_non_positive_nlv():
    from scripts.retrospective import flag_hedge_cost_outliers

    with pytest.raises(ValueError, match="positive"):
        flag_hedge_cost_outliers([], nlv=0)


# ----- U6 wiring: run_review(nlv=...) -> report.hedge_cost_outliers / R-items -----


def test_run_review_nlv_none_skips_hedge_check(tmp_path: Path):
    archive = tmp_path / "private"
    archive.mkdir()
    report = run_review(
        window="weekly",
        today=date(2026, 6, 5),
        archive_dir=archive,
        spot_history={},
        iv_rank_history=None,
        trades=[_opt_trade(ticker="VIX", side="BUY", right="C", strike=20,
                            expiry_iso="2026-08-21", fill_price=50.0, quantity=25)],
        trade_sources=["IB"],
        write_back=False,
        generate_drafts=False,
    )
    assert report.hedge_cost_outliers == []
    assert not any(i["id"].startswith("R") for i in report.action_items)


def test_run_review_nlv_supplied_flags_outlier_and_emits_r_item(tmp_path: Path):
    archive = tmp_path / "private"
    archive.mkdir()
    report = run_review(
        window="weekly",
        today=date(2026, 6, 5),
        archive_dir=archive,
        spot_history={},
        iv_rank_history=None,
        trades=[_opt_trade(ticker="VIX", side="BUY", right="C", strike=20,
                            expiry_iso="2026-08-21", fill_price=50.0, quantity=25)],
        trade_sources=["IB"],
        write_back=False,
        generate_drafts=False,
        nlv=100_000,
    )
    assert len(report.hedge_cost_outliers) == 1
    r_items = [i for i in report.action_items if i["id"].startswith("R")]
    assert len(r_items) == 1
    assert "VIX" in r_items[0]["desc"] and "annualized" in r_items[0]["desc"]


def test_render_report_shows_hedge_cost_outlier_table(tmp_path: Path):
    from scripts.retrospective import render_report

    archive = tmp_path / "private"
    archive.mkdir()
    report = run_review(
        window="weekly",
        today=date(2026, 6, 5),
        archive_dir=archive,
        spot_history={},
        iv_rank_history=None,
        trades=[_opt_trade(ticker="VIX", side="BUY", right="C", strike=20,
                            expiry_iso="2026-08-21", fill_price=50.0, quantity=25)],
        trade_sources=["IB"],
        write_back=False,
        generate_drafts=False,
        nlv=100_000,
    )
    rendered = render_report(report)
    assert "Hedge cost outliers (1" in rendered
    assert "VIX" in rendered
