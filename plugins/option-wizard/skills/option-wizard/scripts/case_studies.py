"""Pattern-match prior public case studies by ticker / structure / status.

Reads the OKF frontmatter (`type: Trade Case Study`) that ships on every
`references/ticker/*.md` file and surfaces the cases that match a current
setup. This is the analysis-time complement to `scripts.retrospective`
(which scores the trader's *private* archive); here we query the *public*,
anonymized case-study bundle.

Reuses `parse_archive_frontmatter` from `scripts.retrospective` — the
skill's single YAML-ish parser — rather than adding a YAML dependency, the
same way `scripts.archive_cold` does.

Unlike the 复盘 review, this finder does NOT apply the PB-out-of-scope filter:
FCN / AQ / DQ cases are exactly what a "have I seen this structure before?"
lookup should return.

CLI:
    python -m scripts.case_studies --ticker ORCL
    python -m scripts.case_studies --structure fcn --status closed
    python -m scripts.case_studies --ticker NVDA --structure collar --json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from scripts.retrospective import parse_archive_frontmatter

CASE_STUDY_TYPE = "Trade Case Study"
# Non-concept files that live alongside case studies in references/ticker/.
_SKIP_NAMES = {"index.md", "readme.md", "_template.md"}


def _default_ticker_dir() -> Path:
    # scripts/case_studies.py → scripts/ → <skill root>/ → references/ticker
    return Path(__file__).resolve().parents[1] / "references" / "ticker"


@dataclass
class CaseStudy:
    path: Path
    ticker: str
    event: str
    date: str
    status: str
    result: str
    structures: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    title: str = ""
    description: str = ""

    @property
    def slug(self) -> str:
        return self.path.stem


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def load_case_studies(ticker_dir: Path | None = None) -> list[CaseStudy]:
    """Parse every `type: Trade Case Study` file in `ticker_dir`.

    Files without frontmatter, or whose `type` is not a case study
    (index.md, _template.md, README.md), are skipped silently.
    """
    ticker_dir = ticker_dir or _default_ticker_dir()
    out: list[CaseStudy] = []
    if not ticker_dir.exists():
        return out
    for md_path in sorted(ticker_dir.glob("*.md")):
        if md_path.name.lower() in _SKIP_NAMES:
            continue
        fm = parse_archive_frontmatter(md_path.read_text(encoding="utf-8"))
        if not fm or fm.get("type") != CASE_STUDY_TYPE:
            continue
        out.append(
            CaseStudy(
                path=md_path,
                ticker=str(fm.get("ticker", "")),
                event=str(fm.get("event", "")),
                date=str(fm.get("date", "")),
                status=str(fm.get("status", "")),
                result=str(fm.get("result", "")),
                structures=_as_list(fm.get("structures")),
                tags=_as_list(fm.get("tags")),
                title=str(fm.get("title", "")),
                description=str(fm.get("description", "")),
            )
        )
    return out


def _score(cs: CaseStudy, ticker: str | None, structures: list[str]) -> int:
    """Ticker match dominates (100); each shared structure adds 10."""
    score = 0
    if ticker and cs.ticker.upper() == ticker.upper():
        score += 100
    if structures:
        want = {s.lower() for s in structures}
        have = {s.lower() for s in cs.structures}
        score += 10 * len(want & have)
    return score


def find_case_studies(
    *,
    ticker: str | None = None,
    structures: list[str] | None = None,
    status: str | None = None,
    ticker_dir: Path | None = None,
) -> list[CaseStudy]:
    """Return case studies matching the query, best match first.

    - `ticker` exact-matches the frontmatter ticker (case-insensitive).
    - `structures` matches any overlap with the case's `structures` list.
    - `status` is a hard filter (e.g. only `closed` cases).
    - With no ticker/structures query, returns all cases (date-sorted),
      so the bare CLI doubles as a case-study listing.
    """
    structures = structures or []
    cases = load_case_studies(ticker_dir)
    if status:
        cases = [c for c in cases if c.status.lower() == status.lower()]

    if not ticker and not structures:
        return sorted(cases, key=lambda c: c.date, reverse=True)

    scored = [(c, _score(c, ticker, structures)) for c in cases]
    scored = [(c, s) for c, s in scored if s > 0]
    scored.sort(key=lambda cs_s: (cs_s[1], cs_s[0].date), reverse=True)
    return [c for c, _ in scored]


def format_matches(matches: list[CaseStudy]) -> str:
    if not matches:
        return "No matching case studies."
    lines = []
    for c in matches:
        structs = ",".join(c.structures) or "-"
        lines.append(
            f"{c.ticker:<8} {c.date:<10} {c.status:<10} [{structs}]  "
            f"{c.title}\n         {c.path.name}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Pattern-match prior public case studies (references/ticker/)."
    )
    ap.add_argument("--ticker", help="exact ticker to match (case-insensitive)")
    ap.add_argument(
        "--structure",
        action="append",
        dest="structures",
        help="structure to match (repeatable, e.g. --structure fcn --structure collar)",
    )
    ap.add_argument("--status", help="hard filter on status (e.g. closed, example)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    ap.add_argument(
        "--ticker-dir",
        type=Path,
        default=None,
        help="override the case-study directory (default: references/ticker)",
    )
    args = ap.parse_args(argv)

    matches = find_case_studies(
        ticker=args.ticker,
        structures=args.structures,
        status=args.status,
        ticker_dir=args.ticker_dir,
    )
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "slug": c.slug,
                        "ticker": c.ticker,
                        "event": c.event,
                        "date": c.date,
                        "status": c.status,
                        "structures": c.structures,
                        "title": c.title,
                        "description": c.description,
                        "path": str(c.path),
                    }
                    for c in matches
                ],
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print(format_matches(matches))
    return 0


if __name__ == "__main__":
    sys.exit(main())
