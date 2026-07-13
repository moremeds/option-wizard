"""Tests for scripts.archive_cold — TTL-based cold-storage migration."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

SKILL_ROOT = (
    Path(__file__).resolve().parent.parent
    / "plugins"
    / "option-wizard"
    / "skills"
    / "option-wizard"
)
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from scripts.archive_cold import (  # noqa: E402
    apply_plans,
    plan_migrations,
)


def _write(
    path: Path,
    name: str,
    *,
    ticker: str,
    date_iso: str,
    archive_eligible_after: str | None = None,
    body: str = "",
) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    fm_lines = [
        "---",
        f"ticker: {ticker}",
        f"date: {date_iso}",
        "structures: [csp]",
        "tags: [test]",
    ]
    if archive_eligible_after is not None:
        fm_lines.append(f"archive_eligible_after: {archive_eligible_after}")
    fm_lines.append("---")
    fm_lines.append("")
    fm_lines.append(body or "## Outcome / Lesson\n\n(empty)")
    full = path / name
    full.write_text("\n".join(fm_lines))
    return full


def test_plan_skips_when_default_ttl_not_reached(tmp_path: Path):
    """Default TTL: date + 30 days. If today < that, file stays active."""
    _write(
        tmp_path / "ticker",
        "2026-06-01-googl-long-eval.md",
        ticker="GOOGL",
        date_iso="2026-06-01",
    )
    # today = 2026-06-15 → only 14 days past source; TTL not reached
    plans, skips = plan_migrations(tmp_path, date(2026, 6, 15))
    assert plans == []
    assert skips == []


def test_plan_moves_when_default_ttl_reached(tmp_path: Path):
    """date=2026-06-01 + 30 = 2026-07-01. today=2026-07-01 → eligible."""
    src = _write(
        tmp_path / "ticker",
        "2026-06-01-googl-long-eval.md",
        ticker="GOOGL",
        date_iso="2026-06-01",
    )
    plans, skips = plan_migrations(tmp_path, date(2026, 7, 1))
    assert skips == []
    assert len(plans) == 1
    p = plans[0]
    assert p.source == src
    assert p.destination == (
        tmp_path / "archive" / "2026-06" / "ticker" / "2026-06-01-googl-long-eval.md"
    )
    assert p.eligibility_source == "default"
    assert p.archive_eligible_after == date(2026, 7, 1)


def test_frontmatter_archive_eligible_after_overrides_default(tmp_path: Path):
    """Trader-set archive_eligible_after wins over date+30 default."""
    _write(
        tmp_path / "ticker",
        "long-dated.md",
        ticker="NVDA",
        date_iso="2026-05-01",
        archive_eligible_after="2026-09-19",  # post-expiry, well past default
    )
    # today = 2026-07-01: default would have moved (2026-05-01 + 30 = 2026-05-31),
    # but trader override keeps it active.
    plans, skips = plan_migrations(tmp_path, date(2026, 7, 1))
    assert plans == []
    assert skips == []
    # today = 2026-09-19: trader's date reached → eligible
    plans2, _ = plan_migrations(tmp_path, date(2026, 9, 19))
    assert len(plans2) == 1
    assert plans2[0].eligibility_source == "frontmatter"


def test_subdir_routing_preserves_subdir_in_cold_path(tmp_path: Path):
    """ticker/ → archive/YYYY-MM/ticker/, market/ → archive/YYYY-MM/market/, etc."""
    _write(
        tmp_path / "ticker",
        "a.md",
        ticker="A",
        date_iso="2026-04-01",
    )
    _write(
        tmp_path / "market",
        "b.md",
        ticker="SPX",
        date_iso="2026-04-02",
    )
    _write(
        tmp_path / "review",
        "c.md",
        ticker="BOOK",
        date_iso="2026-04-03",
    )
    plans, _ = plan_migrations(tmp_path, date(2026, 6, 1))
    by_name = {p.source.name: p for p in plans}
    assert by_name["a.md"].destination.parent.name == "ticker"
    assert by_name["b.md"].destination.parent.name == "market"
    assert by_name["c.md"].destination.parent.name == "review"
    # All under archive/YYYY-MM/ matching source date's year-month
    assert by_name["a.md"].destination.parent.parent.name == "2026-04"
    assert by_name["b.md"].destination.parent.parent.name == "2026-04"


def test_apply_actually_moves_file(tmp_path: Path):
    """apply_plans moves the file; original is gone, destination exists."""
    src = _write(
        tmp_path / "ticker",
        "old.md",
        ticker="A",
        date_iso="2026-01-01",
    )
    plans, _ = plan_migrations(tmp_path, date(2026, 6, 1))
    assert len(plans) == 1
    moved = apply_plans(plans)
    assert moved[0].exists()
    assert not src.exists()


def test_apply_refuses_to_overwrite_existing_destination(tmp_path: Path):
    """If dest already exists, raise rather than silently clobber."""
    _write(
        tmp_path / "ticker",
        "dup.md",
        ticker="A",
        date_iso="2026-01-01",
    )
    plans, _ = plan_migrations(tmp_path, date(2026, 6, 1))
    # Pre-create the destination
    dest = plans[0].destination
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("already here")
    with pytest.raises(FileExistsError):
        apply_plans(plans)


def test_idempotent_after_apply(tmp_path: Path):
    """Second plan run finds nothing — file is now in cold storage, outside active subdirs."""
    _write(
        tmp_path / "ticker",
        "once.md",
        ticker="A",
        date_iso="2026-01-01",
    )
    plans, _ = plan_migrations(tmp_path, date(2026, 6, 1))
    apply_plans(plans)
    plans2, skips2 = plan_migrations(tmp_path, date(2026, 6, 1))
    assert plans2 == []
    assert skips2 == []


def test_skips_file_without_frontmatter(tmp_path: Path):
    (tmp_path / "ticker").mkdir(parents=True)
    (tmp_path / "ticker" / "broken.md").write_text("# no frontmatter\n")
    plans, skips = plan_migrations(tmp_path, date(2026, 6, 1))
    assert plans == []
    assert len(skips) == 1
    assert "no frontmatter" in skips[0].reason


def test_skips_file_with_bad_date(tmp_path: Path):
    _write(
        tmp_path / "ticker",
        "baddate.md",
        ticker="A",
        date_iso="not-a-date",
    )
    plans, skips = plan_migrations(tmp_path, date(2026, 6, 1))
    assert plans == []
    assert len(skips) == 1
    assert "date" in skips[0].reason.lower()


def test_readme_is_ignored(tmp_path: Path):
    (tmp_path / "ticker").mkdir(parents=True)
    (tmp_path / "ticker" / "README.md").write_text("# index")
    plans, skips = plan_migrations(tmp_path, date(2026, 6, 1))
    assert plans == []
    assert skips == []


def test_warns_when_archive_eligible_after_is_iso_timestamp(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """ISO timestamps with timezone (e.g., '2026-09-19T00:00:00Z') are
    common copy-paste from UW responses. They are NOT accepted by
    `date.fromisoformat`. Behavior: warn to stderr (so the trader sees their
    override was discarded) and fall back to the default TTL — never silently
    keep the file active past its intended override date.
    """
    _write(
        tmp_path / "ticker",
        "isots.md",
        ticker="NVDA",
        date_iso="2026-01-01",
        archive_eligible_after="2026-09-19T00:00:00Z",  # ISO timestamp, rejected
    )
    plans, skips = plan_migrations(tmp_path, date(2026, 6, 1))
    err = capsys.readouterr().err
    assert "archive_eligible_after" in err
    assert "2026-09-19T00:00:00Z" in err
    assert "isots.md" in err  # source path is identified
    # Override was ignored → default kicked in (2026-01-01 + 30 = 2026-01-31)
    # → today 2026-06-01 is well past, so file IS eligible via default.
    assert skips == []
    assert len(plans) == 1
    assert plans[0].eligibility_source == "default"


def test_warns_when_archive_eligible_after_is_garbage(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """Any unparseable string (typo, free-form prose) follows the same
    warn-and-fall-back path as the ISO-timestamp case.
    """
    _write(
        tmp_path / "ticker",
        "typo.md",
        ticker="A",
        date_iso="2026-01-01",
        archive_eligible_after="someday next month",
    )
    plans, skips = plan_migrations(tmp_path, date(2026, 6, 1))
    err = capsys.readouterr().err
    assert "archive_eligible_after" in err
    assert "someday next month" in err
    assert len(plans) == 1
    assert plans[0].eligibility_source == "default"


def test_no_warn_when_archive_eligible_after_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """Field absent (the common case) → silent default, no warn noise."""
    _write(
        tmp_path / "ticker",
        "ok.md",
        ticker="A",
        date_iso="2026-01-01",
    )
    plan_migrations(tmp_path, date(2026, 6, 1))
    assert capsys.readouterr().err == ""
