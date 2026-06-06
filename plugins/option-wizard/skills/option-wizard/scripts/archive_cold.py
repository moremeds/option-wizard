"""Cold-storage migration for option-wizard archive files.

Hard rule #9 + 30-day TTL: analyses older than `archive_eligible_after`
(default = frontmatter `date:` + 30 days) move from the active subtree to a
frozen cold-storage subtree to prevent stale-thesis contamination of future
pattern-match lookups and default weekly / monthly reviews.

Active layout:  references/private/{ticker|market|review}/*.md
Cold layout:    references/private/archive/{YYYY-MM}/{ticker|market|review}/*.md
                (YYYY-MM = year-month of the source file's `date:` field, so
                 "show me everything from May 2026" → archive/2026-05/)

Run dry-run by default; pass --apply to actually move files. Idempotent: the
script only walks active subdirs, so re-running after `--apply` does nothing.

Usage:
  .venv/bin/python -m scripts.archive_cold                  # dry-run plan
  .venv/bin/python -m scripts.archive_cold --apply          # move eligible files
  .venv/bin/python -m scripts.archive_cold --today 2026-07-01  # override today
"""

from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from scripts.retrospective import parse_archive_frontmatter

ACTIVE_SUBDIRS = ("ticker", "market", "review")
COLD_SUBDIR = "archive"
TTL_DAYS = 30


@dataclass
class MigrationPlan:
    source: Path
    destination: Path
    archive_eligible_after: date
    source_date: date
    eligibility_source: str  # "frontmatter" or "default"


@dataclass
class Skip:
    source: Path
    reason: str


def _default_archive_root() -> Path:
    skill_root = Path(__file__).resolve().parent.parent
    return skill_root / "references" / "private"


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _eligible_after(
    fm: dict, source_date: date, *, source_path: Path | None = None
) -> tuple[date, str]:
    """Return (eligible_date, source) where source ∈ {"frontmatter", "default"}.

    Frontmatter `archive_eligible_after` wins if present and parseable as a
    plain `YYYY-MM-DD` date. If the field is missing → silent default. If the
    field is present but unparseable (e.g., ISO timestamp `2026-09-19T00:00:00Z`
    or garbage), warn to stderr and fall back to default — never silently
    discard a trader-set override.
    """
    raw = fm.get("archive_eligible_after")
    if raw is None:
        return source_date + timedelta(days=TTL_DAYS), "default"
    parsed = _parse_date(raw)
    if parsed is not None:
        return parsed, "frontmatter"
    location = f" in {source_path}" if source_path is not None else ""
    print(
        f"warning: archive_eligible_after={raw!r}{location} is not a plain "
        f"YYYY-MM-DD date — falling back to default (source date + {TTL_DAYS} "
        f"days). ISO timestamps and timezone suffixes are not accepted; strip "
        f"to the date portion (e.g., '2026-09-19') if you want the override to "
        f"take effect.",
        file=sys.stderr,
    )
    return source_date + timedelta(days=TTL_DAYS), "default"


def plan_migrations(
    archive_root: Path, today: date
) -> tuple[list[MigrationPlan], list[Skip]]:
    """Walk the active subtree and decide what to move. Pure function — no I/O writes."""
    plans: list[MigrationPlan] = []
    skips: list[Skip] = []
    for subdir in ACTIVE_SUBDIRS:
        sub = archive_root / subdir
        if not sub.exists():
            continue
        for md_path in sorted(sub.rglob("*.md")):
            if md_path.name.lower() == "readme.md":
                continue
            text = md_path.read_text(encoding="utf-8")
            fm = parse_archive_frontmatter(text)
            if fm is None:
                skips.append(Skip(md_path, "no frontmatter — fix or delete manually"))
                continue
            source_date = _parse_date(fm.get("date"))
            if source_date is None:
                skips.append(Skip(md_path, f"no/bad date field: {fm.get('date')!r}"))
                continue
            eligible, eligibility_source = _eligible_after(
                fm, source_date, source_path=md_path
            )
            if today < eligible:
                continue  # still active — silent skip
            dest_subdir = (
                archive_root
                / COLD_SUBDIR
                / f"{source_date.year:04d}-{source_date.month:02d}"
                / subdir
            )
            dest = dest_subdir / md_path.name
            plans.append(
                MigrationPlan(
                    source=md_path,
                    destination=dest,
                    archive_eligible_after=eligible,
                    source_date=source_date,
                    eligibility_source=eligibility_source,
                )
            )
    return plans, skips


def render_plan(
    plans: list[MigrationPlan],
    skips: list[Skip],
    archive_root: Path,
    today: date,
    apply: bool,
) -> str:
    head = "APPLYING" if apply else "DRY RUN"
    lines = [
        f"# archive_cold {head} — root={archive_root} today={today.isoformat()}",
        f"# eligible files: {len(plans)}    skipped: {len(skips)}",
        "",
    ]
    if plans:
        lines.append("## Moves")
        for p in plans:
            src_rel = _safe_relpath(p.source, archive_root)
            dest_rel = _safe_relpath(p.destination, archive_root)
            lines.append(f"  {src_rel}  →  {dest_rel}")
            lines.append(
                f"      eligible since {p.archive_eligible_after.isoformat()} "
                f"(from {p.eligibility_source}; source date {p.source_date.isoformat()})"
            )
        lines.append("")
    if skips:
        lines.append("## Skipped (cannot decide eligibility — fix or delete manually)")
        for s in skips:
            lines.append(f"  {_safe_relpath(s.source, archive_root)}: {s.reason}")
        lines.append("")
    if not plans and not skips:
        lines.append("nothing to do — active subtree is clean.")
    return "\n".join(lines)


def _safe_relpath(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return path


def apply_plans(plans: list[MigrationPlan]) -> list[Path]:
    """Move source → destination. Refuses to overwrite an existing destination.

    Returns the list of new (post-move) paths. Side-effect: creates parent
    directories and moves files. Caller is responsible for committing the move
    in git if the archive root is tracked.
    """
    moved: list[Path] = []
    for p in plans:
        if p.destination.exists():
            raise FileExistsError(
                f"destination already exists, refusing to overwrite: {p.destination}"
            )
        p.destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(p.source), str(p.destination))
        moved.append(p.destination)
    return moved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Move expired archive files from the active subtree to cold storage"
    )
    parser.add_argument(
        "--archive-root",
        type=Path,
        default=_default_archive_root(),
        help="Defaults to references/private/",
    )
    parser.add_argument(
        "--today",
        type=str,
        default=None,
        help="Override today (YYYY-MM-DD). Used for deterministic / test runs.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually move files. Default is dry-run (prints the plan only).",
    )
    args = parser.parse_args(argv)

    today = date.fromisoformat(args.today) if args.today else date.today()
    plans, skips = plan_migrations(args.archive_root, today)
    print(render_plan(plans, skips, args.archive_root, today, args.apply))

    if args.apply and plans:
        moved = apply_plans(plans)
        print(f"\n# applied: moved {len(moved)} file(s)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
