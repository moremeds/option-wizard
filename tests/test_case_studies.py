"""Tests for scripts.case_studies — OKF case-study pattern matching.

Hermetic logic tests use tmp_path fixtures; one integration test loads the
real committed references/ticker bundle to validate the frontmatter added
during the OKF alignment actually parses and matches.
"""

from pathlib import Path

from scripts.case_studies import (
    CASE_STUDY_TYPE,
    find_case_studies,
    load_case_studies,
)


def _write(
    dir_: Path,
    name: str,
    *,
    type_=CASE_STUDY_TYPE,
    ticker="ORCL",
    structures="[fcn]",
    status="closed",
    date="2026-06",
    tags="[fcn]",
) -> Path:
    p = dir_ / name
    p.write_text(
        f"""---
type: {type_}
title: "{ticker} — {date} case"
description: a {ticker} case study
ticker: {ticker}
event: test event
date: {date}
status: {status}
result: framework insight
structures: {structures}
tags: {tags}
timestamp: 2026-06-03T06:03:28Z
---

# {ticker} — {date}

Body with no fabricated prices.
""",
        encoding="utf-8",
    )
    return p


def test_load_parses_extension_fields(tmp_path):
    _write(tmp_path, "orcl-2026-06-fcn.md", ticker="ORCL", structures="[fcn]")
    cases = load_case_studies(tmp_path)
    assert len(cases) == 1
    cs = cases[0]
    assert cs.ticker == "ORCL"
    assert cs.structures == ["fcn"]
    assert cs.status == "closed"
    assert cs.slug == "orcl-2026-06-fcn"


def test_load_skips_non_case_study_files(tmp_path):
    _write(tmp_path, "orcl-2026-06-fcn.md")
    # an Index, a Template, and a frontmatter-less README must all be skipped
    _write(tmp_path, "index.md", type_="Index")
    _write(tmp_path, "_template.md", type_="Template")
    (tmp_path / "README.md").write_text("# stub\nno frontmatter\n", encoding="utf-8")
    cases = load_case_studies(tmp_path)
    assert [c.slug for c in cases] == ["orcl-2026-06-fcn"]


def test_find_by_ticker_exact(tmp_path):
    _write(tmp_path, "orcl.md", ticker="ORCL", structures="[fcn]")
    _write(tmp_path, "nvda.md", ticker="NVDA", structures="[collar]")
    matches = find_case_studies(ticker="orcl", ticker_dir=tmp_path)  # case-insensitive
    assert [c.ticker for c in matches] == ["ORCL"]


def test_find_by_structure_overlap(tmp_path):
    _write(tmp_path, "orcl.md", ticker="ORCL", structures="[fcn]")
    _write(tmp_path, "nvda.md", ticker="NVDA", structures="[collar, protective-put]")
    assert [
        c.ticker for c in find_case_studies(structures=["collar"], ticker_dir=tmp_path)
    ] == ["NVDA"]
    assert [
        c.ticker for c in find_case_studies(structures=["fcn"], ticker_dir=tmp_path)
    ] == ["ORCL"]


def test_ticker_match_outranks_structure_match(tmp_path):
    # query ticker=ORCL + structure=collar: ORCL has fcn (ticker hit, 100),
    # NVDA has collar (structure hit, 10). Ticker hit must rank first.
    _write(tmp_path, "orcl.md", ticker="ORCL", structures="[fcn]")
    _write(tmp_path, "nvda.md", ticker="NVDA", structures="[collar]")
    matches = find_case_studies(
        ticker="ORCL", structures=["collar"], ticker_dir=tmp_path
    )
    assert [c.ticker for c in matches] == ["ORCL", "NVDA"]


def test_status_is_a_hard_filter(tmp_path):
    _write(tmp_path, "orcl.md", ticker="ORCL", status="closed")
    _write(tmp_path, "mega.md", ticker="MEGA-S", status="example")
    matches = find_case_studies(ticker="MEGA-S", status="closed", ticker_dir=tmp_path)
    assert matches == []
    matches = find_case_studies(status="example", ticker_dir=tmp_path)
    assert [c.ticker for c in matches] == ["MEGA-S"]


def test_no_query_returns_all_date_sorted(tmp_path):
    _write(tmp_path, "old.md", ticker="ORCL", date="2026-01")
    _write(tmp_path, "new.md", ticker="NVDA", date="2026-09")
    matches = find_case_studies(ticker_dir=tmp_path)
    assert [c.date for c in matches] == ["2026-09", "2026-01"]


def test_real_bundle_orcl_fcn_and_aq_example():
    """Integration: the real references/ticker bundle parses and matches."""
    orcl = find_case_studies(ticker="ORCL")
    assert any(c.slug == "orcl-2026-06-fcn" and "fcn" in c.structures for c in orcl)

    aq = find_case_studies(structures=["aq"])
    assert any(c.slug == "aq-example-case" for c in aq)

    # every real case parses with a non-empty ticker + at least one structure
    for c in load_case_studies():
        assert c.ticker, f"{c.slug} missing ticker"
        assert c.structures, f"{c.slug} missing structures"
