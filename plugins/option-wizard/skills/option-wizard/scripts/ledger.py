"""Decision ledger — persistent state machine for open action items.

See `references/decision-doctrine.md` §"Dynamic risk management" and
`references/review-framework.md` for the trader-facing design. Motivation
(2026-07-02 June review): three separate archives found analysis-flagged
actions that never closed the loop (TSLA 6/22 "should roll down" still
open on 6/29, rescued only by a rally; 6/17 protective-put replacement
left a 1-2 day gap) — the 决策块's 我的行动 / 下一步触发器 lived only in
report prose, with no mechanism to resurface it in a later session.

Every 决策块 action item (or book-review Action item) that isn't executed
immediately becomes one ledger entry. Three surfacing points:
  1. Book review / 复盘 — opens with "what did I say to do last time?"
  2. `manage_positions` daily scan — open items block prepended to report
  3. 复盘's own report — a "Decision ledger" section (independent third
     source; never joined against Layer A/B per hard rule #9)

Storage: one JSON object per line (JSONL) at
`references/private/ledger.jsonl` (gitignored — trade journal data).
Pure functions operate on the loaded `list[dict]`; only `append_entry`
and `set_status` touch the filesystem, mirroring the retrospective.py
convention (pure core + thin IO/CLI shell).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

STATUSES: frozenset[str] = frozenset({"open", "done", "expired", "superseded"})


def default_ledger_path() -> Path:
    skill_root = Path(__file__).resolve().parent.parent
    return skill_root / "references" / "private" / "ledger.jsonl"


def load_ledger(path: Path) -> list[dict[str, Any]]:
    """Read all entries. Missing file returns []; blank lines are skipped."""
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as e:
            # Point at the exact bad line (Pass-3 adversarial finding,
            # 2026-07-02) — a bare JSONDecodeError from manage_positions.py's
            # daily scan would otherwise surface as an unattributed
            # traceback with no indication which of N ledger lines broke.
            raise ValueError(
                f"{path}:{lineno}: malformed ledger entry — {e}. "
                "Fix or remove this line; other entries are unaffected."
            ) from e
    return out


def _next_id(entries: list[dict[str, Any]]) -> str:
    nums = [
        int(e["id"][1:])
        for e in entries
        if e.get("id", "").startswith("L") and e["id"][1:].isdigit()
    ]
    return f"L{(max(nums) + 1) if nums else 1}"


def append_entry(
    path: Path,
    *,
    entry_date: date,
    ticker: str,
    action: str,
    tier: str | None = None,
    due: date | None = None,
    source_file: str | None = None,
) -> dict[str, Any]:
    """Create one open ledger entry and append it to `path`. Returns the entry.

    ponytail: unsynchronized read-modify-write — two concurrent callers
    can both read the same `entries` before either writes and compute the
    same next id, or `set_status`'s read-all/rewrite-all can clobber a
    line another process just appended. Acceptable for a single trader's
    single interactive session (this tool's only real usage pattern);
    add a file lock (e.g. `filelock`) if a second concurrent writer ever
    becomes real — flagged independently by Pass-2 codex-review,
    2026-07-02.
    """
    entries = load_ledger(path)
    entry = {
        "id": _next_id(entries),
        "date": entry_date.isoformat(),
        "ticker": ticker.upper(),
        "action": action,
        "tier": tier,
        "status": "open",
        "due": due.isoformat() if due else None,
        "source_file": source_file,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def set_status(path: Path, entry_id: str, new_status: str) -> bool:
    """Update one entry's status in place. Returns False if entry_id not found."""
    if new_status not in STATUSES:
        raise ValueError(f"unknown status {new_status!r}; must be one of {STATUSES}")
    entries = load_ledger(path)
    found = False
    for e in entries:
        if e.get("id") == entry_id:
            e["status"] = new_status
            found = True
            break
    if not found:
        return False
    with path.open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return True


def open_items(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [e for e in entries if e.get("status") == "open"]


def overdue_items(entries: list[dict[str, Any]], as_of: date) -> list[dict[str, Any]]:
    """Open entries whose `due` date has passed. Pure — caller decides
    whether to `set_status(..., "expired")`; this never mutates."""
    out = []
    for e in entries:
        if e.get("status") != "open" or not e.get("due"):
            continue
        if date.fromisoformat(e["due"]) < as_of:
            out.append(e)
    return out


def render_open_items_block(
    entries: list[dict[str, Any]], *, title: str = "Open decision-ledger items"
) -> str:
    """One line per open item, sorted by due date (undated last). Returns
    "" when there are none, so callers can omit the section entirely."""
    items = open_items(entries)
    if not items:
        return ""
    items = sorted(items, key=lambda e: e.get("due") or "9999-99-99")
    lines = [f"{title} ({len(items)}):"]
    for e in items:
        due_s = f" due {e['due']}" if e.get("due") else ""
        tier_s = f" [{e['tier']}]" if e.get("tier") else ""
        lines.append(f"  {e['id']} {e['ticker']}: {e['action']}{tier_s}{due_s}")
    return "\n".join(lines)


def render_ledger_section(entries: list[dict[str, Any]], as_of: date) -> str:
    """复盘 report section — open + expired-as-of-today, independent of
    Layer A/B (hard rule #9: never joined against archive or broker data)."""
    lines = ["## Decision ledger", ""]
    lines.append(
        "_Source: `references/private/ledger.jsonl` — action items from prior "
        "决策块 / book reviews that haven't closed the loop. Independent of "
        "Layer A/B; never cross-inferred._"
    )
    lines.append("")
    open_ = open_items(entries)
    overdue = overdue_items(entries, as_of)
    overdue_ids = {e["id"] for e in overdue}
    if not open_:
        lines.append("_(no open items)_")
        return "\n".join(lines)
    for e in sorted(open_, key=lambda e: e.get("due") or "9999-99-99"):
        flag = " ⚠ OVERDUE" if e["id"] in overdue_ids else ""
        due_s = f" due {e['due']}" if e.get("due") else ""
        tier_s = f" [{e['tier']}]" if e.get("tier") else ""
        lines.append(
            f"- **{e['id']}** {e['ticker']}: {e['action']}{tier_s}{due_s}{flag}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Decision ledger CLI")
    parser.add_argument("--path", type=Path, default=default_ledger_path())
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="add an open item")
    p_add.add_argument("--ticker", required=True)
    p_add.add_argument("--action", required=True)
    p_add.add_argument("--tier", default=None)
    p_add.add_argument("--due", default=None, help="YYYY-MM-DD")
    p_add.add_argument("--source", default=None, help="source archive filename")
    p_add.add_argument("--date", default=None, help="YYYY-MM-DD, default today")

    p_list = sub.add_parser("list", help="list entries")
    p_list.add_argument(
        "--status", choices=sorted(STATUSES), default=None, help="filter by status"
    )

    p_done = sub.add_parser("done", help="mark an entry done")
    p_done.add_argument("entry_id")

    p_expire = sub.add_parser("expire", help="mark all overdue open entries as expired")
    p_expire.add_argument("--today", default=None, help="YYYY-MM-DD, default today")

    p_supersede = sub.add_parser("supersede", help="mark an entry superseded")
    p_supersede.add_argument("entry_id")

    args = parser.parse_args(argv)

    if args.cmd == "add":
        entry_date = date.fromisoformat(args.date) if args.date else date.today()
        due = date.fromisoformat(args.due) if args.due else None
        entry = append_entry(
            args.path,
            entry_date=entry_date,
            ticker=args.ticker,
            action=args.action,
            tier=args.tier,
            due=due,
            source_file=args.source,
        )
        print(f"added {entry['id']}: {entry['ticker']} — {entry['action']}")
        return 0

    if args.cmd == "list":
        entries = load_ledger(args.path)
        if args.status:
            entries = [e for e in entries if e.get("status") == args.status]
        if not entries:
            print("(no entries)")
            return 0
        for e in entries:
            due_s = f" due {e['due']}" if e.get("due") else ""
            print(f"{e['id']} [{e['status']}] {e['ticker']}: {e['action']}{due_s}")
        return 0

    if args.cmd == "done":
        ok = set_status(args.path, args.entry_id, "done")
        if not ok:
            print(f"no entry {args.entry_id!r} found", file=sys.stderr)
            return 1
        print(f"{args.entry_id} marked done")
        return 0

    if args.cmd == "supersede":
        ok = set_status(args.path, args.entry_id, "superseded")
        if not ok:
            print(f"no entry {args.entry_id!r} found", file=sys.stderr)
            return 1
        print(f"{args.entry_id} marked superseded")
        return 0

    if args.cmd == "expire":
        today = date.fromisoformat(args.today) if args.today else date.today()
        entries = load_ledger(args.path)
        due = overdue_items(entries, today)
        for e in due:
            set_status(args.path, e["id"], "expired")
        print(f"expired {len(due)} overdue item(s)")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
