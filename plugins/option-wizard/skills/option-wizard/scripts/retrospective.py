"""Weekly / monthly review (复盘) — markout scoring of past analyses + trades.

Sixth skill workflow. See `references/review-framework.md` for full design.

Scope (intentionally narrow):
  - Directional calls on individual stocks / indices
  - Vol regime calls (RICH / NEUTRAL / CHEAP)
  - Listed-options structure recommendations + their resulting trades
  - Stock outright trades

Out of scope: FCN / AQ / DQ. Archive files tagged `structures: [fcn]`,
`[aq]`, or `[dq]` are filtered out — those products audit separately
via Workflow 4 / 5 post-mortems.

Pure functions form the testable core. The CLI orchestrator below is
the second skill script with a CLI (after `manage_positions`) — it
fetches live data via `_clients/` and feeds it into the pure functions.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Literal

# BSM uses scipy.stats.norm same as macro_hedge / fair_aq_dq.
from scipy.stats import norm

# --- Constants -------------------------------------------------------

MARKOUT_HORIZONS: tuple[int, ...] = (1, 5, 10, 21, 45)
"""Trading-day horizons used for every markout computation."""

DIRECTIONAL_NOISE_BAND = 0.02
"""Raw % noise band for directional verdict at T+21d.

Phase 1: fixed ±2% (~2× SPX single-day median move). Phase 2 replaces
with vol-adjusted ±0.5σ once N ≥ 50 calls have been logged.
"""

VOL_REGIME_IV_RANK_BAND = 5.0
"""IV rank point band for vol regime verdict at T+10d."""

DEFAULT_DIRECTIONAL_VERDICT_HORIZON = 21
DEFAULT_VOL_REGIME_VERDICT_HORIZON = 10
DEFAULT_STRUCTURE_VERDICT_HORIZON = 21

# FCN / AQ / DQ markers in frontmatter — used to filter out of scope.
OUT_OF_SCOPE_STRUCTURE_TAGS: frozenset[str] = frozenset(
    {"fcn", "aq", "dq", "accumulator", "decumulator", "eln"}
)

# Structure → direction sign convention. +1 long delta / -1 short delta / 0 range.
STRUCTURE_DIRECTION: dict[str, int] = {
    "csp": +1,
    "cash_secured_put": +1,
    "bull_put_spread": +1,
    "bull_call_spread": +1,
    "long_call": +1,
    "covered_call": +1,
    "risk_reversal": +1,
    "long_stock": +1,
    "bear_call_spread": -1,
    "bear_put_spread": -1,
    "long_put": -1,
    "short_stock": -1,
    "protective_put": 0,
    "collar": 0,
    "put_spread_collar": 0,
    "iron_condor": 0,
    "jade_lizard": 0,
    "calendar": 0,
    "diagonal": 0,
}

DIRECTIONAL_BULLISH_KEYWORDS = (
    "bullish",
    "long delta",
    "做多",
    "upside",
    "long stock",
    "long call",
    "buy the dip",
)
DIRECTIONAL_BEARISH_KEYWORDS = (
    "bearish",
    "short delta",
    "做空",
    "downside",
    "long put",
    "hedge downside",
    "fade rally",
)
DIRECTIONAL_RANGE_KEYWORDS = (
    "range-bound",
    "rangebound",
    "consolidation",
    "iron condor",
    "jade lizard",
)
VOL_REGIME_RICH_KEYWORDS = ("rich", "sell premium", "short vol", "vol compression")
VOL_REGIME_CHEAP_KEYWORDS = ("cheap", "buy premium", "long vol", "vol expansion")


# --- Data classes ----------------------------------------------------


@dataclass(frozen=True)
class Call:
    """One falsifiable claim extracted from an archived analysis."""

    ticker: str
    analysis_date: date
    call_type: Literal["directional", "vol_regime", "structure"]
    direction: int  # +1 / -1 / 0
    structure: str | None  # e.g. "bull_put_spread"; None for non-structure types
    archive_path: Path
    notes: str  # excerpt from TL;DR / Decision for traceability

    @property
    def archive_stem(self) -> str:
        return self.archive_path.stem


@dataclass(frozen=True)
class Trade:
    """One execution within the review window."""

    ticker: str
    trade_date: date
    side: Literal["BUY", "SELL"]
    quantity: int  # signed; +qty BUY, -qty SELL (caller normalizes)
    fill_price: float
    contract_type: Literal["STK", "OPT"]
    option_meta: dict[str, Any] | None  # {right, strike, expiry_iso} for OPT
    realized_pnl: float | None = None
    group_key: str | None = (
        None  # legs entered same day with same group share one Trade
    )

    @property
    def signed_qty(self) -> int:
        return self.quantity if self.side == "BUY" else -abs(self.quantity)


@dataclass
class CallMarkout:
    call: Call
    horizons: dict[int, float | None]  # horizon_days -> raw % or normalized P/L
    horizon_units: Literal["raw_pct", "iv_rank_pts", "normalized_pnl"]
    verdict: Literal["CORRECT", "NEUTRAL", "WRONG", "UNKNOWN"]
    verdict_horizon: int
    mark_sources: dict[int, str] = field(default_factory=dict)
    notes: str = ""


@dataclass
class TradeMarkout:
    trade: Trade
    horizons: dict[int, float | None]  # horizon_days -> normalized P/L (frac of basis)
    closed_at_horizon: int | None  # if closed before max horizon
    mark_sources: dict[int, str] = field(
        default_factory=dict
    )  # per horizon: chain/model/realized_close


@dataclass
class ReviewReport:
    """Three independent layers per SKILL.md hard rule #9 (复盘 source separation).

    - Layer A (archive only): calls + call_aggregate. Directional verdict.
    - Layer B (broker only): trades + trade_aggregate. Execution markout.
    - Layer C (advisory): cross_cut_advisory. Judgment-only, no scorecard.

    Never cross-infer: archive presence ≠ trade evidence; trades don't follow calls.
    """

    window: Literal["weekly", "monthly"]
    window_start: date
    window_end: date
    archive_dir: Path
    # Layer A — analysis quality (archive)
    calls: list[CallMarkout]
    call_aggregate: dict[int, dict[str, Any]]
    # Layer B — trade flow (broker, IB + Futu)
    trades: list[TradeMarkout]
    trade_aggregate: dict[int, dict[str, Any]]
    trade_sources: list[str]  # which brokers were pulled (e.g., ["IB", "Futu"])
    # Layer C — cross-cut advisory (judgment-only)
    cross_cut_advisory: list[dict[str, str]]
    # Misc
    pattern_analysis: dict[str, Any] | None  # monthly only
    action_items: list[dict[str, str]]
    pitfall_candidates: list[dict[str, Any]]
    skipped_archives: list[dict[str, str]]  # filename + reason


# --- Frontmatter parsing --------------------------------------------


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_KEY_VALUE_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*):\s*(.*)$")
_LIST_INLINE_RE = re.compile(r"^\[(.*)\]$")


def parse_archive_frontmatter(md_text: str) -> dict[str, Any] | None:
    """Parse YAML-ish frontmatter. Supports scalars + inline lists only.

    Nested objects or block-style lists are not supported (the skill's
    archive convention doesn't use them). Returns None when no
    frontmatter block is present so caller can log it as skipped.
    """
    m = _FRONTMATTER_RE.match(md_text)
    if not m:
        return None
    out: dict[str, Any] = {}
    for raw_line in m.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        kv = _KEY_VALUE_RE.match(line)
        if not kv:
            continue
        key, value = kv.group(1), kv.group(2).strip()
        list_match = _LIST_INLINE_RE.match(value)
        if list_match:
            items = [
                p.strip().strip('"').strip("'")
                for p in list_match.group(1).split(",")
                if p.strip()
            ]
            out[key] = items
        else:
            out[key] = value.strip('"').strip("'")
    return out


# --- Call extraction ------------------------------------------------


def _is_in_scope(frontmatter: dict[str, Any]) -> tuple[bool, str]:
    """Return (in_scope, reason) — reason describes why if out-of-scope."""
    structures = frontmatter.get("structures", [])
    if isinstance(structures, str):
        structures = [structures]
    structures_lc = {s.lower() for s in structures}
    bad = structures_lc & OUT_OF_SCOPE_STRUCTURE_TAGS
    if bad:
        return False, f"structure {sorted(bad)} is out of scope (PB product)"
    tags = frontmatter.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]
    tags_lc = {t.lower() for t in tags}
    bad_tags = tags_lc & OUT_OF_SCOPE_STRUCTURE_TAGS
    if bad_tags:
        return False, f"tag {sorted(bad_tags)} is out of scope (PB product)"
    return True, ""


def _scan_keywords(text: str, keywords: Iterable[str]) -> bool:
    text_lc = text.lower()
    return any(kw.lower() in text_lc for kw in keywords)


def _classify_directional(body: str) -> int:
    """Return +1 / -1 / 0 from prose. Range wins ties — safest default."""
    body = body[:4000]  # only scan TL;DR + early sections
    bullish = _scan_keywords(body, DIRECTIONAL_BULLISH_KEYWORDS)
    bearish = _scan_keywords(body, DIRECTIONAL_BEARISH_KEYWORDS)
    range_ = _scan_keywords(body, DIRECTIONAL_RANGE_KEYWORDS)
    if range_:
        return 0
    if bullish and not bearish:
        return +1
    if bearish and not bullish:
        return -1
    return 0


def _classify_vol_regime(body: str) -> int:
    body = body[:4000]
    rich = _scan_keywords(body, VOL_REGIME_RICH_KEYWORDS)
    cheap = _scan_keywords(body, VOL_REGIME_CHEAP_KEYWORDS)
    if rich and not cheap:
        return -1  # sell-vol bias → IV expected to compress
    if cheap and not rich:
        return +1  # buy-vol bias → IV expected to expand
    return 0


def _extract_notes(body: str) -> str:
    """Return the first TL;DR-like section as a one-line excerpt."""
    for marker in ("## TL;DR", "## Decision", "## Analysis"):
        idx = body.find(marker)
        if idx >= 0:
            section = body[idx : idx + 800]
            line = section.split("\n", 2)[1] if "\n" in section else section
            return line.strip()
    first_para = body.strip().split("\n\n", 1)[0]
    return first_para.replace("\n", " ").strip()[:200]


# --- Active vs cold archive iteration -------------------------------
#
# Hard rule #9 + 30-day TTL: active subtree is `references/private/{ticker,
# market,review}/**/*.md`. Files older than 30 days (by frontmatter
# `archive_eligible_after`) get moved by `scripts.archive_cold` to a frozen
# `references/private/archive/YYYY-MM/...` cold-storage subtree. Default
# review only scans active to avoid stale-thesis contamination; monthly /
# quarterly reviews pass `include_archive=True` to also walk the cold subtree.


def _iter_archive_md(archive_dir: Path, *, include_archive: bool) -> list[Path]:
    """Sorted list of archive .md files. Excludes `<archive_dir>/archive/...`
    (cold storage) unless `include_archive=True`.
    """
    out: list[Path] = []
    for md_path in archive_dir.rglob("*.md"):
        if not include_archive:
            try:
                rel_parts = md_path.relative_to(archive_dir).parts
            except ValueError:
                rel_parts = md_path.parts
            if rel_parts and rel_parts[0] == "archive":
                continue
        out.append(md_path)
    return sorted(out)


def extract_calls_from_archive(
    archive_dir: Path,
    window_start: date,
    window_end: date,
    *,
    include_archive: bool = False,
) -> tuple[list[Call], list[dict[str, str]]]:
    """Scan archive dir for analyses in [window_start, window_end]. Return
    (calls, skipped) where skipped is a list of {file, reason} dicts.

    `include_archive=False` (default) skips the cold-storage `archive/`
    subtree — pass True for monthly / quarterly reviews that span the TTL.
    """
    calls: list[Call] = []
    skipped: list[dict[str, str]] = []
    if not archive_dir.exists():
        return calls, skipped
    for md_path in _iter_archive_md(archive_dir, include_archive=include_archive):
        if md_path.name.lower() == "readme.md":
            continue
        text = md_path.read_text(encoding="utf-8")
        fm = parse_archive_frontmatter(text)
        if fm is None:
            skipped.append({"file": md_path.name, "reason": "no frontmatter"})
            continue
        date_str = fm.get("date")
        if not date_str:
            skipped.append({"file": md_path.name, "reason": "no date in frontmatter"})
            continue
        try:
            analysis_date = date.fromisoformat(str(date_str))
        except ValueError:
            skipped.append(
                {"file": md_path.name, "reason": f"unparseable date {date_str!r}"}
            )
            continue
        if not (window_start <= analysis_date <= window_end):
            continue
        in_scope, reason = _is_in_scope(fm)
        if not in_scope:
            skipped.append({"file": md_path.name, "reason": reason})
            continue
        ticker_field = str(fm.get("ticker", "")).strip()
        tickers = [t.strip().upper() for t in ticker_field.split(",") if t.strip()]
        if not tickers:
            skipped.append({"file": md_path.name, "reason": "no ticker"})
            continue
        body = text[len(_FRONTMATTER_RE.match(text).group(0)) :]  # type: ignore[union-attr]
        notes = _extract_notes(body)
        structures = fm.get("structures", [])
        if isinstance(structures, str):
            structures = [structures]
        structures = [s.lower() for s in structures]
        # Multi-ticker archives (macro book reviews) force prose classification:
        # the structures list typically describes per-position picks scattered
        # across the book (e.g., "[BPS, BCS, long-call]" for a 17-name review),
        # not a single structure that applies to every ticker uniformly. Forcing
        # prose classification gives one directional/vol_regime call per ticker,
        # which is the only semantically clean interpretation.
        is_multi_ticker = len(tickers) > 1
        use_structure_branch = (
            not is_multi_ticker
            and structures
            and any(s in STRUCTURE_DIRECTION for s in structures)
        )
        for ticker in tickers:
            if use_structure_branch:
                for s in structures:
                    if s in STRUCTURE_DIRECTION:
                        calls.append(
                            Call(
                                ticker=ticker,
                                analysis_date=analysis_date,
                                call_type="structure",
                                direction=STRUCTURE_DIRECTION[s],
                                structure=s,
                                archive_path=md_path,
                                notes=notes,
                            )
                        )
                        break
                continue
            # No structure (or multi-ticker) → classify by prose.
            vol_dir = _classify_vol_regime(body)
            if vol_dir != 0:
                calls.append(
                    Call(
                        ticker=ticker,
                        analysis_date=analysis_date,
                        call_type="vol_regime",
                        direction=vol_dir,
                        structure=None,
                        archive_path=md_path,
                        notes=notes,
                    )
                )
                continue
            dir_dir = _classify_directional(body)
            # Even direction=0 (range) emits a directional call so it surfaces.
            calls.append(
                Call(
                    ticker=ticker,
                    analysis_date=analysis_date,
                    call_type="directional",
                    direction=dir_dir,
                    structure=None,
                    archive_path=md_path,
                    notes=notes,
                )
            )
    return calls, skipped


# --- Archive validator ----------------------------------------------


_REQUIRED_FRONTMATTER_FIELDS: tuple[str, ...] = ("ticker", "date", "structures", "tags")
_OUTCOME_SECTION_HEADER = "## Outcome / Lesson"


def validate_archive_dir(
    archive_dir: Path, *, include_archive: bool = False
) -> list[dict[str, Any]]:
    """Scan archive dir for format issues. Returns [{file, issues: [...]}].

    Checks per file: frontmatter present, required fields present, date
    parseable, Outcome/Lesson section present. Files with empty `issues`
    are clean. `include_archive=False` (default) skips the cold-storage
    `archive/` subtree.
    """
    out: list[dict[str, Any]] = []
    if not archive_dir.exists():
        return out
    for md_path in _iter_archive_md(archive_dir, include_archive=include_archive):
        if md_path.name.lower() == "readme.md":
            continue
        issues: list[str] = []
        text = md_path.read_text(encoding="utf-8")
        fm = parse_archive_frontmatter(text)
        if fm is None:
            issues.append("missing YAML frontmatter (file must start with `---` block)")
        else:
            for field_name in _REQUIRED_FRONTMATTER_FIELDS:
                if field_name not in fm:
                    issues.append(f"missing required frontmatter field: {field_name}")
            if "date" in fm:
                try:
                    date.fromisoformat(str(fm["date"]))
                except ValueError:
                    issues.append(
                        f"unparseable date: {fm['date']!r} (must be YYYY-MM-DD)"
                    )
        if _OUTCOME_SECTION_HEADER not in text:
            issues.append(
                f"missing `{_OUTCOME_SECTION_HEADER}` section (复盘 writeback target)"
            )
        out.append({"file": md_path.name, "issues": issues})
    return out


def render_validation_report(entries: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    clean = sum(1 for e in entries if not e["issues"])
    total = len(entries)
    lines.append(f"# Archive validation report")
    lines.append("")
    lines.append(
        f"**Scanned:** {total} files | **Clean:** {clean} | **Issues:** {total - clean}"
    )
    lines.append("")
    for entry in entries:
        if entry["issues"]:
            lines.append(f"⚠ **{entry['file']}**")
            for issue in entry["issues"]:
                lines.append(f"  - {issue}")
        else:
            lines.append(f"✓ {entry['file']}")
    return "\n".join(lines)


# --- BSM helpers (minimal — for option mark fallback) ---------------


def _bs_call(
    spot: float, strike: float, t_years: float, r: float, sigma: float
) -> float:
    if t_years <= 0 or sigma <= 0:
        return max(spot - strike, 0.0)
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma * sigma) * t_years) / (
        sigma * math.sqrt(t_years)
    )
    d2 = d1 - sigma * math.sqrt(t_years)
    return spot * norm.cdf(d1) - strike * math.exp(-r * t_years) * norm.cdf(d2)


def _bs_put(
    spot: float, strike: float, t_years: float, r: float, sigma: float
) -> float:
    if t_years <= 0 or sigma <= 0:
        return max(strike - spot, 0.0)
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma * sigma) * t_years) / (
        sigma * math.sqrt(t_years)
    )
    d2 = d1 - sigma * math.sqrt(t_years)
    return strike * math.exp(-r * t_years) * norm.cdf(-d2) - spot * norm.cdf(-d1)


def _option_mark_bsm(
    *,
    right: str,
    spot: float,
    strike: float,
    t_years: float,
    iv: float,
    r: float = 0.045,
) -> float:
    if right.upper() == "C":
        return _bs_call(spot, strike, t_years, r, iv)
    return _bs_put(spot, strike, t_years, r, iv)


# --- Markout computation --------------------------------------------


def _horizon_date(analysis_date: date, horizon_trading_days: int) -> date:
    """Approximate trading-day horizon → calendar date (5d/week).

    Phase 1 uses a simple 5-day-per-week approximation: 21 trading days ≈
    30 calendar days. Phase 2 should respect actual exchange holidays
    using a market calendar from `_clients/tv.py`.
    """
    cal_days = round(horizon_trading_days * 7 / 5)
    return analysis_date + timedelta(days=cal_days)


def compute_call_markout(
    call: Call,
    *,
    spot_history: dict[str, dict[date, float]],
    iv_rank_history: dict[str, dict[date, float]] | None = None,
    structure_iv_snapshot: dict[Call, dict[str, float]] | None = None,
) -> CallMarkout:
    """Compute markout per horizon for one call.

    For directional: signed (spot_T / spot_0 − 1).
    For vol_regime: signed (iv_rank_T − iv_rank_0).
    For structure: simulated mark vs entry credit/debit, normalized by max_loss.

    Inputs are pre-pulled price/IV series — keeping this function pure
    so tests don't hit live data.
    """
    horizons: dict[int, float | None] = {}
    mark_sources: dict[int, str] = {}
    ticker_spots = spot_history.get(call.ticker, {})
    spot_0 = ticker_spots.get(call.analysis_date)
    if call.call_type == "directional":
        for h in MARKOUT_HORIZONS:
            spot_t = ticker_spots.get(_horizon_date(call.analysis_date, h))
            if spot_0 is None or spot_t is None or spot_0 <= 0:
                horizons[h] = None
                mark_sources[h] = "missing"
                continue
            horizons[h] = call.direction * (spot_t / spot_0 - 1.0)
            mark_sources[h] = "tv_spot"
        units = "raw_pct"
        verdict_horizon = DEFAULT_DIRECTIONAL_VERDICT_HORIZON
        v_val = horizons.get(verdict_horizon)
        if v_val is None:
            verdict = "UNKNOWN"
        elif v_val > DIRECTIONAL_NOISE_BAND:
            verdict = "CORRECT"
        elif v_val < -DIRECTIONAL_NOISE_BAND:
            verdict = "WRONG"
        else:
            verdict = "NEUTRAL"
    elif call.call_type == "vol_regime":
        ranks = (iv_rank_history or {}).get(call.ticker, {})
        rank_0 = ranks.get(call.analysis_date)
        # Vol regime tracked at T+1/+5/+10/+21. T+1d added in v0.2 after the
        # 2026-06-05 sell-off showed IV rank can jump 17pts overnight when a
        # regime shift hits (TSLA 16.57→33.07). T+45 stays skipped — IV rank
        # has mean-reverted by then, the signal is too noisy.
        for h in MARKOUT_HORIZONS:
            if h == 45:
                horizons[h] = None
                mark_sources[h] = "skipped"
                continue
            rank_t = ranks.get(_horizon_date(call.analysis_date, h))
            if rank_0 is None or rank_t is None:
                horizons[h] = None
                mark_sources[h] = "missing"
                continue
            horizons[h] = call.direction * (rank_t - rank_0)
            mark_sources[h] = "uw_iv_rank"
        units = "iv_rank_pts"
        verdict_horizon = DEFAULT_VOL_REGIME_VERDICT_HORIZON
        v_val = horizons.get(verdict_horizon)
        if v_val is None:
            verdict = "UNKNOWN"
        elif v_val >= VOL_REGIME_IV_RANK_BAND:
            verdict = "CORRECT"
        elif v_val <= -VOL_REGIME_IV_RANK_BAND:
            verdict = "WRONG"
        else:
            verdict = "NEUTRAL"
    else:  # structure
        # Phase 1: use direction × spot move as a proxy for structure markout
        # (delta-1 approximation). Full BSM simulation requires per-leg meta
        # which isn't reliably parsed from the archive frontmatter today.
        # Mark source flagged "model_delta1" so trader sees the approximation.
        for h in MARKOUT_HORIZONS:
            spot_t = ticker_spots.get(_horizon_date(call.analysis_date, h))
            if spot_0 is None or spot_t is None or spot_0 <= 0:
                horizons[h] = None
                mark_sources[h] = "missing"
                continue
            move = spot_t / spot_0 - 1.0
            horizons[h] = call.direction * move
            mark_sources[h] = "model_delta1"
        units = "normalized_pnl"
        verdict_horizon = DEFAULT_STRUCTURE_VERDICT_HORIZON
        v_val = horizons.get(verdict_horizon)
        if v_val is None:
            verdict = "UNKNOWN"
        elif v_val > 0:
            verdict = "CORRECT"
        elif v_val < 0:
            verdict = "WRONG"
        else:
            verdict = "NEUTRAL"
    return CallMarkout(
        call=call,
        horizons=horizons,
        horizon_units=units,
        verdict=verdict,
        verdict_horizon=verdict_horizon,
        mark_sources=mark_sources,
    )


def compute_trade_markout(
    trade: Trade,
    *,
    spot_history: dict[str, dict[date, float]],
    option_iv: dict[str, float] | None = None,
    r: float = 0.045,
) -> TradeMarkout:
    """Compute P/L markout per horizon for one trade.

    Stock: (spot_T − entry) / entry × direction_sign.
    Option: BSM mark at horizon using TV spot + held IV; normalized by
      strike (margin proxy) for short, by debit for long.

    Closing trades (Trade.realized_pnl != 0) are excluded from markout —
    P/L is already crystallized at trade time and re-marking via BSM
    produces nonsense (this was the D1 gap surfaced by the first real
    run, where a BTC at $1.84 on a P700 with the underlying at $740
    showed a fake +95% T+1d markout).
    """
    if trade.realized_pnl is not None and trade.realized_pnl != 0:
        return TradeMarkout(
            trade=trade,
            horizons={h: None for h in MARKOUT_HORIZONS},
            closed_at_horizon=0,
            mark_sources={h: "closing_trade_excluded" for h in MARKOUT_HORIZONS},
        )
    horizons: dict[int, float | None] = {}
    mark_sources: dict[int, str] = {}
    ticker_spots = spot_history.get(trade.ticker, {})
    spot_0 = ticker_spots.get(trade.trade_date)
    direction_sign = 1 if trade.side == "BUY" else -1
    if trade.contract_type == "STK":
        for h in MARKOUT_HORIZONS:
            spot_t = ticker_spots.get(_horizon_date(trade.trade_date, h))
            if spot_t is None or spot_0 is None or spot_0 <= 0:
                horizons[h] = None
                mark_sources[h] = "missing"
                continue
            horizons[h] = direction_sign * (spot_t / spot_0 - 1.0)
            mark_sources[h] = "tv_spot"
    else:
        meta = trade.option_meta or {}
        strike = float(meta.get("strike", 0.0))
        right = str(meta.get("right", "C"))
        expiry_iso = str(meta.get("expiry_iso", ""))
        try:
            expiry_date = date.fromisoformat(expiry_iso)
        except ValueError:
            expiry_date = trade.trade_date + timedelta(days=45)
        iv = (option_iv or {}).get(trade.ticker, 0.35)
        entry_basis = trade.fill_price  # per-share
        for h in MARKOUT_HORIZONS:
            mark_date = _horizon_date(trade.trade_date, h)
            spot_t = ticker_spots.get(mark_date)
            if spot_t is None or strike <= 0:
                horizons[h] = None
                mark_sources[h] = "missing"
                continue
            t_years = max((expiry_date - mark_date).days, 1) / 365.0
            mark = _option_mark_bsm(
                right=right, spot=spot_t, strike=strike, t_years=t_years, iv=iv, r=r
            )
            # Short premium: pnl = entry - mark; normalize by strike (margin proxy).
            # Long premium: pnl = mark - entry; normalize by entry_basis.
            if trade.side == "SELL":
                pnl_per_share = entry_basis - mark
                denom = max(strike, 1.0)
            else:
                pnl_per_share = mark - entry_basis
                denom = max(entry_basis, 0.01)
            horizons[h] = pnl_per_share / denom
            mark_sources[h] = "model"
    return TradeMarkout(
        trade=trade,
        horizons=horizons,
        closed_at_horizon=None,
        mark_sources=mark_sources,
    )


# --- Reconcile calls with trades ------------------------------------


# --- Aggregate markout (per-layer, source-separated) ----------------


def _mean(values: list[float]) -> float | None:
    vs = [v for v in values if v is not None and not math.isnan(v)]
    if not vs:
        return None
    return sum(vs) / len(vs)


def aggregate_call_markout(
    call_markouts: list[CallMarkout],
) -> dict[int, dict[str, Any]]:
    """Layer A only — avg per-horizon call markout. Archive source.

    Mixes only `raw_pct` + `normalized_pnl` units (both percent-scale).
    `iv_rank_pts` calls are reported separately via pattern analysis.
    """
    out: dict[int, dict[str, Any]] = {}
    for h in MARKOUT_HORIZONS:
        vals = [
            cm.horizons.get(h)
            for cm in call_markouts
            if cm.horizon_units in ("raw_pct", "normalized_pnl")
        ]
        avg = _mean([v for v in vals if v is not None])
        out[h] = {
            "avg_call_markout": avg,
            "n_calls": sum(1 for v in vals if v is not None),
        }
    return out


def aggregate_trade_markout(
    trade_markouts: list[TradeMarkout],
) -> dict[int, dict[str, Any]]:
    """Layer B only — avg per-horizon trade markout. Broker source."""
    out: dict[int, dict[str, Any]] = {}
    for h in MARKOUT_HORIZONS:
        vals = [tm.horizons.get(h) for tm in trade_markouts]
        avg = _mean([v for v in vals if v is not None])
        out[h] = {
            "avg_trade_markout": avg,
            "n_trades": sum(1 for v in vals if v is not None),
        }
    return out


# --- Pattern analysis (monthly only) --------------------------------


def detect_pattern_anomalies(
    call_markouts: list[CallMarkout],
) -> dict[str, Any]:
    """Hit rate breakdowns by call type / ticker / direction. Monthly only."""

    def hit_rate(items: list[CallMarkout]) -> float | None:
        scored = [cm for cm in items if cm.verdict in ("CORRECT", "WRONG")]
        if not scored:
            return None
        return sum(1 for cm in scored if cm.verdict == "CORRECT") / len(scored)

    by_type: dict[str, dict[str, Any]] = {}
    for ct in ("directional", "vol_regime", "structure"):
        sub = [cm for cm in call_markouts if cm.call.call_type == ct]
        by_type[ct] = {"n": len(sub), "hit_rate": hit_rate(sub)}

    # By ticker (only tickers with ≥3 calls).
    by_ticker: dict[str, dict[str, Any]] = {}
    tickers = sorted({cm.call.ticker for cm in call_markouts})
    for tk in tickers:
        sub = [cm for cm in call_markouts if cm.call.ticker == tk]
        if len(sub) >= 3:
            by_ticker[tk] = {"n": len(sub), "hit_rate": hit_rate(sub)}

    return {"by_call_type": by_type, "by_ticker_min3": by_ticker}


# --- Action items + pitfall drafts ----------------------------------


def generate_action_items(report: ReviewReport) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    counter = {"S": 1, "P": 1, "T": 1, "D": 1}

    # S — skill rule suggestions from pattern outliers.
    if report.pattern_analysis:
        for tk, stats in report.pattern_analysis.get("by_ticker_min3", {}).items():
            hit = stats.get("hit_rate")
            if hit is not None and hit < 0.30:
                items.append(
                    {
                        "id": f"S{counter['S']}",
                        "desc": (
                            f"Ticker {tk}: hit rate {hit:.0%} over {stats['n']} calls — "
                            f"flag for skill-level downweight rule on directional signals for {tk}"
                        ),
                        "trigger": f"S{counter['S']} add",
                    }
                )
                counter["S"] += 1

    # P — pitfall candidates from WRONG calls.
    for cm in report.calls:
        if cm.verdict == "WRONG":
            items.append(
                {
                    "id": f"P{counter['P']}",
                    "desc": (
                        f"{cm.call.ticker} {cm.call.analysis_date.isoformat()}: "
                        f"{cm.call.call_type} call WRONG at T+{cm.verdict_horizon}d. "
                        f"Draft auto-emitted to _drafts/."
                    ),
                    "trigger": f"P{counter['P']} promote",
                }
            )
            counter["P"] += 1

    # D — data quality from mark sources.
    model_marks = 0
    total_marks = 0
    for cm in report.calls:
        for src in cm.mark_sources.values():
            total_marks += 1
            if src in ("model", "model_delta1"):
                model_marks += 1
    for tm in report.trades:
        for src in tm.mark_sources.values():
            total_marks += 1
            if src in ("model",):
                model_marks += 1
    if total_marks > 0 and model_marks / total_marks > 0.30:
        items.append(
            {
                "id": f"D{counter['D']}",
                "desc": (
                    f"{model_marks}/{total_marks} marks ({model_marks / total_marks:.0%}) "
                    f"used BSM/delta-1 fallback — getting IB historical chain or "
                    f"macmini DB online would tighten Layer 2 fidelity"
                ),
                "trigger": f"D{counter['D']} fix",
            }
        )
        counter["D"] += 1

    # T — trader profile items now come from cross_cut_advisory (judgment-only).
    # Per hard rule #9, no algorithmic followed/ignored quadrant can fire here;
    # only the trader (or LLM in advisory mode) can promote a Cross-cut observation
    # into a T-item, by adding it to report.cross_cut_advisory before action_items
    # generation. We surface each as a T-item without inferring source linkage.
    for obs in report.cross_cut_advisory:
        if obs.get("propose_action_item"):
            items.append(
                {
                    "id": f"T{counter['T']}",
                    "desc": obs.get("observation", "")
                    + " (cross-cut advisory; judgment-only)",
                    "trigger": f"T{counter['T']} review",
                }
            )
            counter["T"] += 1

    return items


def generate_pitfall_drafts(
    wrong_call_markouts: list[CallMarkout],
    drafts_dir: Path,
    review_date: date,
) -> list[Path]:
    """Write a draft pitfall file for each WRONG call. Idempotent on filename."""
    drafts_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for cm in wrong_call_markouts:
        if cm.verdict != "WRONG":
            continue
        slug = cm.call.archive_stem
        path = drafts_dir / f"pitfall-{slug}.md"
        if path.exists():
            continue  # idempotency: don't overwrite trader's in-progress edits
        markout_lines = [
            f"- T+{h}d: {v:+.2%}" if v is not None else f"- T+{h}d: n/a"
            for h, v in sorted(cm.horizons.items())
            if v is not None or cm.mark_sources.get(h) != "skipped"
        ]
        body = (
            f"# Pitfall draft: {cm.call.ticker} {cm.call.analysis_date.isoformat()}\n\n"
            f"**Source analysis:** [{cm.call.archive_path.name}]({cm.call.archive_path.name})\n"
            f"**Call type:** {cm.call.call_type}\n"
            f"**Direction:** {cm.call.direction:+d}\n"
            f"**Verdict horizon:** T+{cm.verdict_horizon}d\n"
            f"**Verdict:** {cm.verdict}\n"
            f"**Draft date:** {review_date.isoformat()}\n\n"
            f"## Original call notes\n\n"
            f"{cm.call.notes}\n\n"
            f"## Truth data (markout per horizon)\n\n"
            + "\n".join(markout_lines)
            + "\n\n"
            f"## What went wrong\n\n"
            f"(trader fills in)\n\n"
            f"## Rule going forward\n\n"
            f"(trader fills in — strip account-specific numbers before promoting "
            f"to references/pitfalls/NN-slug.md)\n"
        )
        path.write_text(body, encoding="utf-8")
        written.append(path)
    return written


# --- Writeback to source Outcome / Lesson section -------------------


_OUTCOME_HEADER_RE = re.compile(r"^## Outcome\s*/\s*Lesson\s*$", re.MULTILINE)


def write_back_outcome(call_markouts: list[CallMarkout], review_date: date) -> int:
    """Append verdict block to each source file's Outcome / Lesson section.

    Idempotent: skips files that already contain a 'Verdict (复盘 <review_date>'
    line. Returns count of files modified.
    """
    modified = 0
    for cm in call_markouts:
        if cm.verdict == "UNKNOWN":
            continue
        path = cm.call.archive_path
        text = path.read_text(encoding="utf-8")
        marker = f"**Verdict (复盘 {review_date.isoformat()},"
        if marker in text:
            continue
        match = _OUTCOME_HEADER_RE.search(text)
        if not match:
            continue  # archive doesn't have an Outcome section — leave it alone
        markout_lines = []
        for h in MARKOUT_HORIZONS:
            v = cm.horizons.get(h)
            tag = " ← verdict horizon" if h == cm.verdict_horizon else ""
            if v is None:
                markout_lines.append(f"- T+{h}d: n/a{tag}")
            else:
                if cm.horizon_units == "iv_rank_pts":
                    markout_lines.append(f"- T+{h}d: {v:+.1f} IV-rank pts{tag}")
                else:
                    markout_lines.append(f"- T+{h}d: {v:+.2%}{tag}")
        chain_count = sum(
            1
            for s in cm.mark_sources.values()
            if s in ("tv_spot", "uw_iv_rank", "chain")
        )
        model_count = sum(
            1 for s in cm.mark_sources.values() if s in ("model", "model_delta1")
        )
        block = (
            f"\n"
            f"**Verdict (复盘 {review_date.isoformat()}, {cm.call.call_type}):** "
            f"{cm.verdict}\n"
            f"**Markout:**\n"
            + "\n".join(markout_lines)
            + f"\n**Mark source:** chain {chain_count} / model {model_count}\n"
        )
        # Insert just after the Outcome / Lesson header line.
        header_end = match.end()
        new_text = text[:header_end] + block + text[header_end:]
        path.write_text(new_text, encoding="utf-8")
        modified += 1
    return modified


# --- Render report --------------------------------------------------


def _fmt_pct_or_na(v: float | None, units: str = "raw_pct") -> str:
    if v is None:
        return "n/a"
    if units == "iv_rank_pts":
        return f"{v:+.1f}"
    return f"{v:+.2%}"


def render_report(report: ReviewReport) -> str:
    lines: list[str] = []
    lines.append(f"# 复盘 — {report.window.title()} review")
    lines.append("")
    lines.append(
        f"**Window:** {report.window_start.isoformat()} → {report.window_end.isoformat()}"
    )
    lines.append(
        "**Source separation (hard rule #9):** Layer A = archive only · "
        "Layer B = broker only (IB + Futu) · Layer C = advisory (judgment-only)"
    )
    lines.append(f"**Archive dir:** `{report.archive_dir}`")
    lines.append(
        f"**Trade sources pulled:** {', '.join(report.trade_sources) or '(none)'}"
    )
    lines.append(f"**Calls scored:** {len(report.calls)}")
    lines.append(f"**Trades scored:** {len(report.trades)}")
    if report.skipped_archives:
        lines.append(f"**Skipped archives:** {len(report.skipped_archives)} (see end)")
    lines.append("")

    # ----- Layer A — Analysis quality (archive only) -----
    lines.append("## Layer A — Analysis quality (archive)")
    lines.append("")
    lines.append(
        "_Source: `references/private/{ticker,market,review}/**/*.md` (active subtree; `archive/` cold storage skipped unless `--include-archive`). Directional verdicts only — not trade records._"
    )
    lines.append("")
    lines.append(
        "| Ticker | Date | Type | Dir | T+1 | T+5 | T+10 | T+21 | T+45 | Verdict |"
    )
    lines.append(
        "|--------|------|------|-----|-----|-----|------|------|------|---------|"
    )
    for cm in sorted(report.calls, key=lambda x: x.call.analysis_date, reverse=True):
        h = cm.horizons
        u = cm.horizon_units
        lines.append(
            f"| {cm.call.ticker} "
            f"| {cm.call.analysis_date.isoformat()} "
            f"| {cm.call.call_type} "
            f"| {cm.call.direction:+d} "
            f"| {_fmt_pct_or_na(h.get(1), u)} "
            f"| {_fmt_pct_or_na(h.get(5), u)} "
            f"| {_fmt_pct_or_na(h.get(10), u)} "
            f"| {_fmt_pct_or_na(h.get(21), u)} "
            f"| {_fmt_pct_or_na(h.get(45), u)} "
            f"| {cm.verdict} |"
        )
    lines.append("")
    lines.append("**Aggregate call markout (Layer A):**")
    lines.append("")
    lines.append("| Horizon | Avg call markout | n_calls |")
    lines.append("|---------|------------------|---------|")
    for h in MARKOUT_HORIZONS:
        row = report.call_aggregate.get(h, {})
        lines.append(
            f"| T+{h}d | {_fmt_pct_or_na(row.get('avg_call_markout'))} | {row.get('n_calls', 0)} |"
        )
    lines.append("")

    # ----- Layer B — Trade flow (broker only) -----
    lines.append("## Layer B — Trade flow (broker)")
    lines.append("")
    lines.append(
        f"_Source: {' + '.join(report.trade_sources) or '(no brokers pulled)'}. "
        "Actual fills + execution markout — never inferred from archive._"
    )
    lines.append("")
    lines.append("**Aggregate trade markout (Layer B):**")
    lines.append("")
    lines.append("| Horizon | Avg trade markout | n_trades |")
    lines.append("|---------|-------------------|----------|")
    for h in MARKOUT_HORIZONS:
        row = report.trade_aggregate.get(h, {})
        lines.append(
            f"| T+{h}d | {_fmt_pct_or_na(row.get('avg_trade_markout'))} | {row.get('n_trades', 0)} |"
        )
    lines.append("")

    # ----- Layer C — Cross-cut advisory (judgment-only) -----
    lines.append("## Layer C — Cross-cut (advisory, judgment-only)")
    lines.append("")
    lines.append(
        "_Manual observations linking Layer A ↔ Layer B. No algorithmic scorecard; "
        "no `followed × correct` quadrant. Per hard rule #9._"
    )
    lines.append("")
    if not report.cross_cut_advisory:
        lines.append("_(none surfaced this window)_")
    else:
        for obs in report.cross_cut_advisory:
            lines.append(f"- {obs.get('observation', '')}")
            for ref in obs.get("layer_a_refs", []):
                lines.append(f"  - Layer A ref: `{ref}`")
            for ref in obs.get("layer_b_refs", []):
                lines.append(f"  - Layer B ref: `{ref}`")
    lines.append("")

    # Pattern analysis (monthly only).
    if report.pattern_analysis:
        lines.append("## Pattern analysis (monthly)")
        lines.append("")
        bt = report.pattern_analysis.get("by_call_type", {})
        lines.append("**By call type:**")
        for ct, stats in bt.items():
            hit = stats.get("hit_rate")
            hit_s = f"{hit:.0%}" if hit is not None else "n/a"
            lines.append(f"- {ct}: {stats['n']} calls, hit rate {hit_s}")
        lines.append("")
        bk = report.pattern_analysis.get("by_ticker_min3", {})
        if bk:
            lines.append("**By ticker (≥3 calls):**")
            for tk, stats in bk.items():
                hit = stats.get("hit_rate")
                hit_s = f"{hit:.0%}" if hit is not None else "n/a"
                lines.append(f"- {tk}: {stats['n']} calls, hit rate {hit_s}")
            lines.append("")

    # Action items.
    lines.append("## Action items")
    lines.append("")
    if not report.action_items:
        lines.append("_No items this window._")
    for item in report.action_items:
        lines.append(f"- **{item['id']}** {item['desc']} → `{item['trigger']}`")
    lines.append("")

    # Skipped archives footnote.
    if report.skipped_archives:
        lines.append("## Skipped archives")
        lines.append("")
        for s in report.skipped_archives:
            lines.append(f"- `{s['file']}` — {s['reason']}")
        lines.append("")

    return "\n".join(lines)


# --- Broker trade parsers (Layer B sources) -------------------------
# Per hard rule #9, ALL trade flow comes from these parsers — IB MCP and
# Futu CLI are the only legitimate sources. Both must be pulled each
# review (per `private/trader-profile.md`).


def _iso_to_date(iso_ts: str) -> date | None:
    """Parse an ISO 8601 timestamp into the trade date (UTC). Returns None on failure."""
    try:
        return date.fromisoformat(iso_ts[:10])
    except (ValueError, TypeError):
        return None


def parse_ib_trades(
    ib_response: dict[str, Any],
    window_start: date,
    window_end: date,
) -> list[Trade]:
    """Convert IB MCP `get_account_trades` response → Trade[].

    FALLBACK: prefer parse_xenon_blotter (xenon /blotter) — this path is the
    IB-MCP fallback.

    Filters to `[window_start, window_end]` inclusive. IB only exposes
    {symbol, sec_type, side, size, price, trade_time, realized_pnl} per
    leg — option strike/expiry require a separate `search_contracts` call,
    so `option_meta` is left None unless the caller pre-enriches.
    """
    out: list[Trade] = []
    for tr in ib_response.get("trades", []):
        d = _iso_to_date(str(tr.get("trade_time", "")))
        if d is None or not (window_start <= d <= window_end):
            continue
        sec = str(tr.get("sec_type", "STK")).upper()
        contract_type: Literal["STK", "OPT"] = "OPT" if sec == "OPT" else "STK"
        out.append(
            Trade(
                ticker=str(tr.get("symbol", "")).upper(),
                trade_date=d,
                side="BUY" if str(tr.get("side", "")).upper() == "BUY" else "SELL",
                quantity=tr.get("size", 0),
                fill_price=float(tr.get("price", 0.0)),
                contract_type=contract_type,
                option_meta=None,
                realized_pnl=(
                    float(tr["realized_pnl"]) if tr.get("realized_pnl") else None
                ),
            )
        )
    return out


def _futu_leg_to_trade(
    leg: dict[str, Any], realized_pnl: float | None = None
) -> Trade | None:
    """Map one Futu trade leg dict → Trade. Returns None if timestamp unparseable."""
    d = _iso_to_date(str(leg.get("timestamp", "")))
    if d is None:
        return None
    is_option = str(leg.get("instrumentType", "stock")).lower() == "option"
    opt = leg.get("optionDetails") or {}
    option_meta: dict[str, Any] | None = None
    ticker = str(leg.get("symbol", "")).upper()
    if is_option and opt:
        ticker = str(opt.get("underlying", ticker)).upper()
        put_call = str(opt.get("putCall", "")).lower()
        right = (
            "C" if put_call.startswith("c") else "P" if put_call.startswith("p") else ""
        )
        option_meta = {
            "right": right,
            "strike": float(opt.get("strike", 0.0)),
            "expiry_iso": str(opt.get("expiry", "")),
        }
    return Trade(
        ticker=ticker,
        trade_date=d,
        side="BUY" if str(leg.get("side", "")).lower() == "buy" else "SELL",
        quantity=leg.get("quantity", 0),
        fill_price=float(leg.get("price", 0.0)),
        contract_type="OPT" if is_option else "STK",
        option_meta=option_meta,
        realized_pnl=realized_pnl,
    )


def _last_trading_day_at_or_before(d: date) -> date:
    """Skip back over weekends (Sat=5, Sun=6). Used by the Futu staleness gate."""
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def parse_futu_trades(
    futu_report: dict[str, Any],
    window_start: date,
    window_end: date,
    *,
    allow_stale: bool = False,
) -> list[Trade]:
    """Convert portfolio-analyser JSON report → Trade[].

    FALLBACK: prefer parse_xenon_blotter (xenon /blotter, both brokers) —
    this path is the Futu-CLI fallback.

    Reads `trades.matchedTrades[]` and `trades.unmatchedTrades[]`. Each
    matched pair emits two Trade objects (open + close, with the pair's
    `realizedPnl` attached to the close leg). Unmatched legs emit one
    Trade each with `realized_pnl=None`. Filters to date window inclusive.

    Freshness gate (SKILL.md hard rule #7): the Futu CLI caches by ISO
    week, so a re-run without `--rerun` happily returns data 1-2 trading
    days stale. This silently breaks Layer B — the entire most recent
    trading day's activity gets dropped. We enforce: `dateRange.to`
    (from the report JSON) MUST be >= the last trading day at or before
    `window_end`. Raises `ValueError` if stale. Pass `allow_stale=True`
    to opt out (e.g., backfills, deliberate historical reviews).
    """
    trades_block = futu_report.get("trades", {})
    if not allow_stale:
        to_iso = str(trades_block.get("dateRange", {}).get("to", ""))
        to_date = _iso_to_date(to_iso)
        last_td = _last_trading_day_at_or_before(window_end)
        if to_date is not None and to_date < last_td:
            raise ValueError(
                f"Futu data stale: report dateRange.to is {to_date}, "
                f"but the last trading day at or before review window_end "
                f"({window_end}) is {last_td}. "
                "Re-pull with `cd ~/projects/portfolio-analyser && "
                "npx tsx src/cli.ts ft --range 1m --rerun` or pass "
                "`allow_stale=True` to override (per SKILL.md hard rule #7)."
            )
    out: list[Trade] = []
    for pair in trades_block.get("matchedTrades", []):
        realized = pair.get("realizedPnl")
        realized_f = float(realized) if realized is not None else None
        if open_leg := pair.get("openTrade"):
            t = _futu_leg_to_trade(open_leg, realized_pnl=None)
            if t and window_start <= t.trade_date <= window_end:
                out.append(t)
        if close_leg := pair.get("closeTrade"):
            t = _futu_leg_to_trade(close_leg, realized_pnl=realized_f)
            if t and window_start <= t.trade_date <= window_end:
                out.append(t)
    for leg in trades_block.get("unmatchedTrades", []):
        t = _futu_leg_to_trade(leg, realized_pnl=None)
        if t and window_start <= t.trade_date <= window_end:
            out.append(t)
    return out


def parse_xenon_blotter(
    blotter: dict[str, Any],
    window_start: date,
    window_end: date,
) -> list[Trade]:
    """Convert a xenon ``GET /blotter`` response → Trade[] (IB + Futu fills
    from Postgres). PRIMARY trade-flow source for Layer B (hard rule #9);
    parse_ib_trades (IB MCP) and parse_futu_trades (Futu CLI) are retained
    as documented fallbacks.

    Walks ``closed_trades[].executions[]`` + ``open_trades[].executions[]``;
    each execution → one Trade, filtered to [window_start, window_end]
    inclusive. The blotter carries no option strike/expiry/right at the
    execution level, so ``option_meta`` is None (same limitation as
    parse_ib_trades; the caller pre-enriches if needed). The trade-level
    ``realized_pnl`` is attached to the LAST in-window execution of each
    closed trade (mirrors parse_futu_trades attaching realizedPnl to the
    close leg) so it is not double-counted across fills.
    """
    out: list[Trade] = []
    groups = (blotter.get("closed_trades") or []) + (blotter.get("open_trades") or [])
    for tr in groups:
        sec = str(tr.get("sec_type", "STK")).upper()
        ctype: Literal["STK", "OPT"] = "OPT" if sec == "OPT" else "STK"
        ticker = str(tr.get("symbol", "")).upper()
        realized = tr.get("realized_pnl")
        realized_f = float(realized) if realized is not None else None
        is_closed = bool(tr.get("is_closed"))
        execs = tr.get("executions") or []
        last_idx = len(execs) - 1
        for i, ex in enumerate(execs):
            d = _iso_to_date(str(ex.get("time", "")))
            if d is None or not (window_start <= d <= window_end):
                continue
            attach_pnl = realized_f if (is_closed and i == last_idx) else None
            out.append(
                Trade(
                    ticker=ticker,
                    trade_date=d,
                    side="BUY" if str(ex.get("side", "")).upper() == "BUY" else "SELL",
                    quantity=int(abs(ex.get("quantity", 0))),
                    fill_price=float(ex.get("price", 0.0)),
                    contract_type=ctype,
                    option_meta=None,
                    realized_pnl=attach_pnl,
                )
            )
    return out


# --- Orchestrator CLI ------------------------------------------------


def _window_dates(window: str, today: date) -> tuple[date, date]:
    if window == "weekly":
        return today - timedelta(days=7), today
    if window == "monthly":
        return today - timedelta(days=30), today
    raise ValueError(f"unknown window {window!r}")


def run_review(
    *,
    window: Literal["weekly", "monthly"],
    today: date,
    archive_dir: Path,
    spot_history: dict[str, dict[date, float]],
    iv_rank_history: dict[str, dict[date, float]] | None,
    trades: list[Trade],
    trade_sources: list[str],
    option_iv: dict[str, float] | None = None,
    cross_cut_advisory: list[dict[str, str]] | None = None,
    drafts_dir: Path | None = None,
    write_back: bool = True,
    generate_drafts: bool = True,
    include_archive: bool = False,
) -> ReviewReport:
    """End-to-end pure-function pipeline (3-layer per hard rule #9).

    Layer A (archive) and Layer B (broker) are computed in isolation.
    Layer C (advisory) is passed in as `cross_cut_advisory` — judgment-only
    observations relating A↔B, never auto-derived. Caller is responsible
    for filling B's trades from ALL configured brokers (IB + Futu per
    `trader-profile.md`) and tagging `trade_sources` accordingly.

    `include_archive=False` (default) restricts Layer A to the active
    subtree (`references/private/{ticker,market,review}/`). Pass True for
    monthly / quarterly reviews that need to span the 30-day cold-storage
    TTL — adds files under `references/private/archive/YYYY-MM/...`.
    """
    window_start, window_end = _window_dates(window, today)
    calls, skipped = extract_calls_from_archive(
        archive_dir, window_start, window_end, include_archive=include_archive
    )
    # Layer A
    call_markouts = [
        compute_call_markout(
            c, spot_history=spot_history, iv_rank_history=iv_rank_history
        )
        for c in calls
    ]
    call_aggregate = aggregate_call_markout(call_markouts)
    # Layer B
    trade_markouts = [
        compute_trade_markout(t, spot_history=spot_history, option_iv=option_iv)
        for t in trades
    ]
    trade_aggregate = aggregate_trade_markout(trade_markouts)
    # Layer C (passed in)
    advisory = cross_cut_advisory or []

    pattern = detect_pattern_anomalies(call_markouts) if window == "monthly" else None
    report = ReviewReport(
        window=window,
        window_start=window_start,
        window_end=window_end,
        archive_dir=archive_dir,
        calls=call_markouts,
        call_aggregate=call_aggregate,
        trades=trade_markouts,
        trade_aggregate=trade_aggregate,
        trade_sources=trade_sources,
        cross_cut_advisory=advisory,
        pattern_analysis=pattern,
        action_items=[],
        pitfall_candidates=[],
        skipped_archives=skipped,
    )
    report.action_items = generate_action_items(report)
    if generate_drafts and drafts_dir is not None:
        wrong = [cm for cm in call_markouts if cm.verdict == "WRONG"]
        written = generate_pitfall_drafts(wrong, drafts_dir, today)
        report.pitfall_candidates = [{"path": str(p)} for p in written]
    if write_back:
        write_back_outcome(call_markouts, today)
    return report


def _default_archive_dir() -> Path:
    skill_root = Path(__file__).resolve().parent.parent
    return skill_root / "references" / "private"


def _default_drafts_dir() -> Path:
    skill_root = Path(__file__).resolve().parent.parent
    return skill_root / "references" / "pitfalls" / "_drafts"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Weekly / monthly review of past analyses + trades"
    )
    parser.add_argument(
        "--window",
        choices=["weekly", "monthly"],
        default=None,
        help="Required unless --validate-archive is passed",
    )
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=_default_archive_dir(),
        help="Defaults to references/private/ (recursively scans ticker/market/review/ subdirs; cold-storage archive/ subtree is skipped by default — pass --include-archive to opt in)",
    )
    parser.add_argument(
        "--include-archive",
        action="store_true",
        help="Also scan references/private/archive/YYYY-MM/... cold-storage subtree (default: active subdirs only). Use for monthly / quarterly reviews that span the 30-day TTL.",
    )
    parser.add_argument(
        "--drafts-dir",
        type=Path,
        default=_default_drafts_dir(),
        help="Defaults to references/pitfalls/_drafts/",
    )
    parser.add_argument("--no-writeback", action="store_true")
    parser.add_argument("--no-pitfall-drafts", action="store_true")
    parser.add_argument(
        "--validate-archive",
        action="store_true",
        help="Scan archive dir for frontmatter / Outcome-section format issues and exit",
    )
    parser.add_argument(
        "--today", type=str, default=None, help="Override today (YYYY-MM-DD)"
    )
    args = parser.parse_args(argv)

    if args.validate_archive:
        entries = validate_archive_dir(
            args.archive_dir, include_archive=args.include_archive
        )
        print(render_validation_report(entries))
        # Exit non-zero if any file had issues, so this can be wired into CI.
        return 1 if any(e["issues"] for e in entries) else 0

    if not args.window:
        parser.error("--window is required unless --validate-archive is passed")

    today = date.fromisoformat(args.today) if args.today else date.today()

    # Phase 1 CLI: data fetchers are stubs — the script is run as an orchestrator
    # entrypoint but live IB / TV / UW fetches need to be wired by the trader.
    # See `references/review-framework.md` §"Phase 1 limitations".
    print(
        "scripts.retrospective CLI is a Phase 1 scaffold — live data fetchers "
        "(TV historical spot, IB executions, UW IV rank history) need wiring. "
        "Run via python -c with pre-fetched data, or extend this CLI to call "
        "the matching _clients/ methods.",
        file=sys.stderr,
    )
    # Run with empty data so the trader sees the report structure + skipped archives.
    report = run_review(
        window=args.window,
        today=today,
        archive_dir=args.archive_dir,
        spot_history={},
        iv_rank_history=None,
        trades=[],
        trade_sources=[],
        cross_cut_advisory=[],
        drafts_dir=args.drafts_dir if not args.no_pitfall_drafts else None,
        write_back=not args.no_writeback,
        generate_drafts=not args.no_pitfall_drafts,
        include_archive=args.include_archive,
    )
    print(render_report(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
