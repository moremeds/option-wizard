"""Tests for the decision ledger (scripts/ledger.py) — see
references/decision-doctrine.md §"Dynamic risk management".
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from scripts.ledger import (
    append_entry,
    default_ledger_path,
    load_ledger,
    open_items,
    overdue_items,
    render_ledger_section,
    render_open_items_block,
    set_status,
)


def test_default_ledger_path_resolves_under_references_private(tmp_path: Path):
    # Pass-2 codex-review coverage gap: the untested failure mode is
    # resolving to the wrong repo/private path. skill_root is two parents
    # up from scripts/ledger.py — assert the resolved path actually lands
    # in that skill's references/private/, not some other directory.
    path = default_ledger_path()
    assert path.name == "ledger.jsonl"
    assert path.parent.name == "private"
    assert path.parent.parent.name == "references"
    assert path.parent.parent.parent.name == "option-wizard"


def test_load_ledger_missing_file_returns_empty(tmp_path: Path):
    assert load_ledger(tmp_path / "nope.jsonl") == []


def test_append_entry_assigns_sequential_ids(tmp_path: Path):
    path = tmp_path / "ledger.jsonl"
    e1 = append_entry(
        path, entry_date=date(2026, 7, 2), ticker="nvda", action="close spread"
    )
    e2 = append_entry(
        path, entry_date=date(2026, 7, 2), ticker="SPX", action="build hedge"
    )
    assert e1["id"] == "L1" and e2["id"] == "L2"
    assert e1["ticker"] == "NVDA"  # normalized upper
    assert e1["status"] == "open"
    entries = load_ledger(path)
    assert len(entries) == 2
    assert entries[0]["id"] == "L1"


def test_append_entry_records_optional_fields(tmp_path: Path):
    path = tmp_path / "ledger.jsonl"
    e = append_entry(
        path,
        entry_date=date(2026, 7, 2),
        ticker="NVDA",
        action="roll down",
        tier="PROBE",
        due=date(2026, 7, 10),
        source_file="2026-07-02-nvda.md",
    )
    assert e["tier"] == "PROBE"
    assert e["due"] == "2026-07-10"
    assert e["source_file"] == "2026-07-02-nvda.md"


def test_open_items_filters_by_status(tmp_path: Path):
    path = tmp_path / "ledger.jsonl"
    append_entry(path, entry_date=date(2026, 7, 2), ticker="A", action="x")
    e2 = append_entry(path, entry_date=date(2026, 7, 2), ticker="B", action="y")
    set_status(path, e2["id"], "done")
    entries = load_ledger(path)
    open_ = open_items(entries)
    assert len(open_) == 1 and open_[0]["ticker"] == "A"


def test_set_status_unknown_raises(tmp_path: Path):
    path = tmp_path / "ledger.jsonl"
    e = append_entry(path, entry_date=date(2026, 7, 2), ticker="A", action="x")
    with pytest.raises(ValueError, match="unknown status"):
        set_status(path, e["id"], "yolo")


def test_set_status_missing_id_returns_false(tmp_path: Path):
    path = tmp_path / "ledger.jsonl"
    append_entry(path, entry_date=date(2026, 7, 2), ticker="A", action="x")
    assert set_status(path, "L99", "done") is False


def test_overdue_items_only_flags_open_past_due(tmp_path: Path):
    path = tmp_path / "ledger.jsonl"
    append_entry(
        path,
        entry_date=date(2026, 6, 22),
        ticker="TSLA",
        action="roll down 400/390 to 380/370",
        due=date(2026, 6, 25),
    )
    e_done = append_entry(
        path,
        entry_date=date(2026, 6, 22),
        ticker="QQQ",
        action="already closed",
        due=date(2026, 6, 25),
    )
    set_status(path, e_done["id"], "done")
    append_entry(
        path,
        entry_date=date(2026, 7, 2),
        ticker="SPX",
        action="not due yet",
        due=date(2026, 8, 1),
    )
    entries = load_ledger(path)
    overdue = overdue_items(entries, date(2026, 6, 29))
    assert [e["ticker"] for e in overdue] == ["TSLA"]  # QQQ done, SPX not due


def test_overdue_items_never_mutates(tmp_path: Path):
    path = tmp_path / "ledger.jsonl"
    append_entry(
        path,
        entry_date=date(2026, 6, 22),
        ticker="TSLA",
        action="roll down",
        due=date(2026, 6, 25),
    )
    overdue_items(load_ledger(path), date(2026, 6, 29))
    # status on disk is untouched — overdue_items is read-only
    assert load_ledger(path)[0]["status"] == "open"


def test_render_open_items_block_empty_when_no_open(tmp_path: Path):
    path = tmp_path / "ledger.jsonl"
    e = append_entry(path, entry_date=date(2026, 7, 2), ticker="A", action="x")
    set_status(path, e["id"], "done")
    assert render_open_items_block(load_ledger(path)) == ""


def test_render_open_items_block_sorts_by_due_undated_last(tmp_path: Path):
    path = tmp_path / "ledger.jsonl"
    append_entry(
        path,
        entry_date=date(2026, 7, 2),
        ticker="LATER",
        action="y",
        due=date(2026, 8, 1),
    )
    append_entry(path, entry_date=date(2026, 7, 2), ticker="UNDATED", action="z")
    append_entry(
        path,
        entry_date=date(2026, 7, 2),
        ticker="SOONEST",
        action="x",
        due=date(2026, 7, 3),
    )
    block = render_open_items_block(load_ledger(path))
    assert block.index("SOONEST") < block.index("LATER") < block.index("UNDATED")
    assert "Open decision-ledger items (3)" in block


def test_render_ledger_section_flags_overdue(tmp_path: Path):
    path = tmp_path / "ledger.jsonl"
    append_entry(
        path,
        entry_date=date(2026, 6, 22),
        ticker="TSLA",
        action="roll down 400/390",
        tier="NORMAL",
        due=date(2026, 6, 25),
    )
    section = render_ledger_section(load_ledger(path), date(2026, 7, 2))
    assert "## Decision ledger" in section
    assert "TSLA" in section and "OVERDUE" in section
    assert "[NORMAL]" in section


def test_render_ledger_section_no_open_items(tmp_path: Path):
    section = render_ledger_section([], date(2026, 7, 2))
    assert "(no open items)" in section


def test_load_ledger_malformed_line_raises_with_location(tmp_path: Path):
    # Pass-3 adversarial finding: a bare JSONDecodeError gave no line
    # number, unattributable in manage_positions.py's daily scan output.
    path = tmp_path / "ledger.jsonl"
    path.write_text('{"id": "L1", "status": "open"}\nnot valid json\n')
    with pytest.raises(ValueError, match=r"ledger\.jsonl:2: malformed"):
        load_ledger(path)
