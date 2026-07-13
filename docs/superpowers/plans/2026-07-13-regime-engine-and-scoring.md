# Regime Engine & Scoring Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement R1–R5 of `docs/audits/2026-07-13-capability-audit.md`: a daily persisted regime snapshot, σ-scaled horizon-matched verdicts, automated weekly call grading, and ledger escalation — so the co-pilot can measure its own edge and condition it on regime.

**Architecture:** Three new thin capabilities on existing clients (UW market-tide + per-expiry GEX, xenon historical bars), one new snapshot script appending JSONL to the private archive, surgical changes to `retrospective.py`'s verdict math, and a standalone weekly grading runner. No new dependencies; every fetcher stays in `_clients/`, every pure function stays testable without network.

**Tech Stack:** Python 3.13 / uv / httpx / pytest (mock `httpx.get`/`httpx.post` per `tests/test_xenon_client.py` convention).

## Global Constraints

- All file paths below relative to repo root; skill code lives under `plugins/option-wizard/skills/option-wizard/`.
- Personal data (regime log, graded reports) stays under `references/private/` (gitignored); only code + tests + docs are tracked.
- No fabricated API shapes: the two UW paths below were verified against UW's OpenAPI docs on 2026-07-13 (`GET /api/market/market-tide` — params `date`, `otm_only`, `interval_5m`; `GET /api/stock/{ticker}/greek-exposure/strike-expiry`). The xenon `POST /historical/bars` request body is from `/Users/chenxi/projects/xenon/docs/reference/readonly-query-api.md:251-267`; its **response** shape is undocumented — Task 2 probes it live and freezes a fixture before writing the parser.
- Tests use real tickers at real frozen prices (repo No-synthetic-data rule); fixtures record their as-of date.
- Never commit without explicit user request; one PR for the whole plan, branch `feat/regime-engine-and-scoring`.
- Run `.venv/bin/pytest tests/ -q` green before every commit.

---

### Task 1: UW client — market tide + per-expiry GEX

**Files:**
- Modify: `plugins/option-wizard/skills/option-wizard/scripts/_clients/uw.py` (append two methods after `dark_pool`, line 116)
- Test: `tests/test_uw_client_new_endpoints.py` (create)

**Interfaces:**
- Consumes: existing `UWClient._get(path, params)` (retry/backoff built in).
- Produces: `UWClient.market_tide(date: str | None = None, interval_5m: bool = True) -> dict` and `UWClient.gex_by_strike_expiry(ticker: str, date: str | None = None) -> dict`. Both return the raw `{"data": ...}` envelope (client convention: consumers unwrap `["data"]`). Task 4 consumes both.

- [ ] **Step 1: Write the failing test**

```python
"""New UW endpoints — paths verified against UW OpenAPI docs 2026-07-13:
GET /api/market/market-tide, GET /api/stock/{t}/greek-exposure/strike-expiry."""

from unittest.mock import MagicMock, patch

from scripts._clients.uw import UWClient


def _resp(payload):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = payload
    r.raise_for_status.return_value = None
    return r


def test_market_tide_path_and_params():
    with patch("scripts._clients.uw.httpx.get") as g:
        g.return_value = _resp({"data": [{"timestamp": "2026-07-10T09:30:00-04:00"}]})
        c = UWClient(api_key="k")
        out = c.market_tide(date="2026-07-10")
        assert g.call_args[0][0] == "https://api.unusualwhales.com/api/market/market-tide"
        assert g.call_args.kwargs["params"] == {"date": "2026-07-10", "interval_5m": "true"}
        assert out["data"][0]["timestamp"].startswith("2026-07-10")


def test_market_tide_no_date_omits_param():
    with patch("scripts._clients.uw.httpx.get") as g:
        g.return_value = _resp({"data": []})
        UWClient(api_key="k").market_tide()
        assert g.call_args.kwargs["params"] == {"interval_5m": "true"}


def test_gex_by_strike_expiry_path():
    with patch("scripts._clients.uw.httpx.get") as g:
        g.return_value = _resp({"data": [{"strike": "7500", "expiry": "2026-07-17"}]})
        c = UWClient(api_key="k")
        out = c.gex_by_strike_expiry("SPX")
        assert (
            g.call_args[0][0]
            == "https://api.unusualwhales.com/api/stock/SPX/greek-exposure/strike-expiry"
        )
        assert out["data"][0]["expiry"] == "2026-07-17"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_uw_client_new_endpoints.py -v`
Expected: FAIL — `AttributeError: 'UWClient' object has no attribute 'market_tide'`.

- [ ] **Step 3: Implement the two methods**

Append to `UWClient` (after `dark_pool`), matching the class's one-method-per-endpoint style:

```python
    def market_tide(
        self, date: str | None = None, interval_5m: bool = True
    ) -> dict[str, Any]:
        # Path verified against UW OpenAPI docs 2026-07-13 (get_public_api_docs).
        params: dict[str, Any] = {"interval_5m": "true" if interval_5m else "false"}
        if date:
            params["date"] = date
        return self._get("/api/market/market-tide", params=params)

    def gex_by_strike_expiry(
        self, ticker: str, date: str | None = None
    ) -> dict[str, Any]:
        # Per-expiry GEX — the all-expiry aggregate (spot_gex_by_strike) produces
        # far-OTM wall artifacts; per-expiry is the trade-relevant read.
        # Path verified against UW OpenAPI docs 2026-07-13.
        params = {"date": date} if date else None
        return self._get(f"/api/stock/{ticker}/greek-exposure/strike-expiry", params=params)
```

Also update the module docstring's observed-shapes list (lines 6-16) with the two new endpoints after the live smoke run in Step 5.

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/bin/pytest tests/test_uw_client_new_endpoints.py -v` — expected PASS.

- [ ] **Step 5: Live smoke + record shapes**

Run: `cd plugins/option-wizard/skills/option-wizard && set -a && source ../../../../.env && set +a && ../../../../.venv/bin/python -c "
from scripts._clients.uw import UWClient
c = UWClient()
t = c.market_tide()
g = c.gex_by_strike_expiry('QQQ')
print('tide keys:', list(t['data'][0].keys()) if t['data'] else 'EMPTY')
print('gex keys:', list(g['data'][0].keys()) if g['data'] else 'EMPTY')
"`
Expected: both print real field lists. Record them in the uw.py module docstring (convention at `uw.py:6-16`). Confirm the gex rows carry `strike`, `expiry`, and call/put gamma fields consumable by `gex_levels.compute_levels_per_expiry` (which needs `expiry` + either `gex` or `call_gex`+`put_gex`); if UW field names differ (e.g. `call_gamma_oi`), note the mapping — Task 4 owns the adapter.

- [ ] **Step 6: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/_clients/uw.py tests/test_uw_client_new_endpoints.py
git commit -m "feat(uw): market_tide + gex_by_strike_expiry client methods"
```

---

### Task 2: xenon client — historical daily closes

**Files:**
- Modify: `plugins/option-wizard/skills/option-wizard/scripts/_clients/xenon.py` (add `_post` + `historical_bars` + `daily_closes`)
- Test: `tests/test_xenon_historical_bars.py` (create)

**Interfaces:**
- Consumes: xenon `POST /historical/bars`, request body per `readonly-query-api.md:251-267`.
- Produces: `XenonClient.historical_bars(symbol: str, duration: str = "3 M", bar_size: str = "1 day", sec_type: str = "STK") -> Any` (raw response) and `daily_closes(symbol: str, duration: str = "3 M", sec_type: str = "STK") -> dict[datetime.date, float]` (parsed). Task 5 consumes `daily_closes` — its return type matches `run_review`'s `spot_history` inner dict exactly (keyed by `date` objects).

- [ ] **Step 1: Probe the live endpoint and freeze the response shape**

The request body is documented; the response is not. Probe before parsing (no-fabrication rule):

```bash
cd /Users/chenxi/projects/option-wizard && set -a && source .env && set +a && \
curl -s -X POST -H "X-API-Key: $XENON_KEY" -H "Content-Type: application/json" \
  "$XENON_BASE/historical/bars" -d '{
    "contract": {"sec_type": "STK", "symbol": "QQQ", "exchange": "SMART", "currency": "USD"},
    "end_date_time": "", "duration": "1 W", "bar_size": "1 day",
    "what_to_show": "TRADES", "use_rth": true
  }' | python3 -m json.tool | head -40
```

Expected: JSON containing a list of daily bars (ib_insync `BarData`-derived: fields like `date`, `open`, `high`, `low`, `close`, `volume`). Save the real first-two-bars output as the fixture in Step 2's test (with an as-of comment). If the endpoint errors, stop this task and record the failure — Tasks 4/5 then fall back to UW `iv_rank`-payload closes for indices (Task 4 already uses those) and this task is re-scoped.

- [ ] **Step 2: Write the failing test (using the frozen real fixture)**

```python
"""historical_bars/daily_closes — fixture frozen from live xenon probe.
REPLACE the two bar rows below with the real probe output from Task 2 Step 1
(real QQQ closes, as-of date in comment) before running. Shape shown here
follows ib_insync BarData; adjust field names to the probe if they differ."""

from datetime import date
from unittest.mock import MagicMock, patch

from scripts._clients.xenon import XenonClient

# Frozen from live probe 2026-07-XX (fill in):
BARS_FIXTURE = {
    "bars": [
        {"date": "2026-07-09", "open": 0.0, "high": 0.0, "low": 0.0, "close": 720.11, "volume": 0},
        {"date": "2026-07-10", "open": 0.0, "high": 0.0, "low": 0.0, "close": 725.51, "volume": 0},
    ]
}


def _resp(payload):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = payload
    r.raise_for_status.return_value = None
    return r


def test_historical_bars_posts_documented_body():
    with patch("scripts._clients.xenon.httpx.post") as p:
        p.return_value = _resp(BARS_FIXTURE)
        c = XenonClient(base_url="http://h:8321", api_key="x")
        c.historical_bars("QQQ", duration="1 W")
        assert p.call_args[0][0] == "http://h:8321/historical/bars"
        body = p.call_args.kwargs["json"]
        assert body["contract"] == {
            "sec_type": "STK", "symbol": "QQQ", "exchange": "SMART", "currency": "USD"
        }
        assert body["bar_size"] == "1 day"
        assert body["use_rth"] is True


def test_daily_closes_parses_to_date_float_map():
    with patch("scripts._clients.xenon.httpx.post") as p:
        p.return_value = _resp(BARS_FIXTURE)
        c = XenonClient(base_url="http://h:8321", api_key="x")
        closes = c.daily_closes("QQQ", duration="1 W")
        assert closes[date(2026, 7, 10)] == 725.51
        assert all(isinstance(k, date) for k in closes)
```

- [ ] **Step 3: Run to verify failure** — `.venv/bin/pytest tests/test_xenon_historical_bars.py -v` → `AttributeError`.

- [ ] **Step 4: Implement**

Add to `XenonClient` (after `_get`/`get`; the class currently has no POST helper — this adds the only one):

```python
    def _post(self, path: str, body: dict[str, Any]) -> Any:
        url = f"{self._base}{path}"
        resp = httpx.post(url, headers=self._headers, json=body, timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()

    def historical_bars(
        self,
        symbol: str,
        duration: str = "3 M",
        bar_size: str = "1 day",
        sec_type: str = "STK",
    ) -> Any:
        """POST /historical/bars — body per xenon readonly-query-api.md."""
        return self._post(
            "/historical/bars",
            {
                "contract": {
                    "sec_type": sec_type,
                    "symbol": symbol.upper(),
                    "exchange": "SMART",
                    "currency": "USD",
                },
                "end_date_time": "",
                "duration": duration,
                "bar_size": bar_size,
                "what_to_show": "TRADES",
                "use_rth": True,
            },
        )

    def daily_closes(
        self, symbol: str, duration: str = "3 M", sec_type: str = "STK"
    ) -> dict[Any, float]:
        """Daily close series parsed to {datetime.date: close} — the exact
        inner shape run_review's spot_history expects. Adjust the envelope
        key ('bars' below) to the live probe from Task 2 Step 1."""
        from datetime import date as _date

        raw = self.historical_bars(symbol, duration=duration, sec_type=sec_type)
        rows = raw["bars"] if isinstance(raw, dict) else raw
        out: dict[Any, float] = {}
        for b in rows:
            d = _date.fromisoformat(str(b["date"])[:10])
            out[d] = float(b["close"])
        return out
```

Index note: for SPX/VIX use `sec_type="IND"` (IB index contracts; exchange stays SMART unless the probe shows xenon requires CBOE — if the IND probe 4xxes, record it and use QQQ/SPY proxies in Task 4 instead of index closes).

- [ ] **Step 5: Run tests + live smoke, then commit**

`.venv/bin/pytest tests/test_xenon_historical_bars.py tests/test_xenon_client.py -v` → PASS.
Live: `... python -c "from scripts._clients.xenon import XenonClient; print(list(XenonClient().daily_closes('QQQ', duration='1 W').items())[-2:])"` → two real (date, close) pairs.

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/_clients/xenon.py tests/test_xenon_historical_bars.py
git commit -m "feat(xenon): historical_bars + daily_closes (POST /historical/bars)"
```

---

### Task 3: σ-scaled, horizon-matched verdicts in retrospective.py

Evidence basis: capability audit §1.2 (±2% = 0.08σ on VIX vs 0.99σ on DIA) and §1.3 (50% T+1↔T+21 verdict flips). This replaces the "wait for N ≥ 50" plan — the miscalibration is already proven.

**Files:**
- Modify: `plugins/option-wizard/skills/option-wizard/scripts/retrospective.py` — constants (~line 39), `Call` (~131), `CallMarkout` (~181), `_parse_one_structured_call` (~364), `compute_call_markout` (~711)
- Modify: `plugins/option-wizard/skills/option-wizard/references/review-framework.md` (Phase-1 limitations §701-729: mark items 1-band and horizon DONE with date + audit link)
- Test: extend `tests/test_retrospective.py`

**Interfaces:**
- Consumes: existing `spot_history: dict[str, dict[date, float]]`.
- Produces: `Call.horizon_days: int | None` (new optional 8th `calls:` frontmatter field), `CallMarkout.band_used: float | None`, new module functions `_trailing_sigma(ticker_spots: dict[date, float], asof: date, lookback: int = 20) -> float | None` and `_nearest_horizon(h: int) -> int`. Verdict semantics unchanged (CORRECT/WRONG/NEUTRAL/UNKNOWN).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_retrospective.py` (reuse its `_horizon_date` import and fixture style):

```python
# --- σ-scaled band + per-call horizon (2026-07-13 capability audit R2) ---

def _flat_then_move_spots(base: float, daily_vol: float, move_at_21: float):
    """25 pre-dates alternating ±daily_vol (so sample σ ≈ daily_vol — a
    CONSTANT drift would have zero return variance and a zero band) +
    horizon dates carrying move_at_21 from T+21 on."""
    d0 = date(2026, 5, 15)
    spots = {}
    px = base
    for i in range(25, 0, -1):
        spots[d0 - timedelta(days=i)] = px
        px *= 1 + (daily_vol if i % 2 else -daily_vol)
    spots[d0] = px
    for h in (1, 5, 10, 21, 45):
        spots[_horizon_date(d0, h)] = px * (1 + (move_at_21 if h >= 21 else 0))
    return d0, spots


def test_sigma_band_neutralizes_submarginal_move_on_volatile_ticker():
    # ±1.5% move on a ticker with ~2%/day σ: old fixed 2% band would say
    # nothing; new 0.5σ√21 band (~4.6%) must say NEUTRAL, not WRONG/CORRECT.
    # Base = real TSLA close 423.74 (2026-06-02, UW — no-synthetic-data rule).
    d0, spots = _flat_then_move_spots(423.74, 0.02, 0.015)
    call = Call(ticker="TSLA", analysis_date=d0, call_type="directional",
                direction=+1, structure=None, archive_path=Path("t.md"), notes="")
    cm = compute_call_markout(call, spot_history={"TSLA": spots})
    assert cm.verdict == "NEUTRAL"
    assert cm.band_used is not None and cm.band_used > 0.02


def test_sigma_band_falls_back_to_fixed_when_history_short():
    call = Call(ticker="GOOGL", analysis_date=date(2026, 5, 15),
                call_type="directional", direction=+1, structure=None,
                archive_path=Path("g.md"), notes="")
    spots = {"GOOGL": {date(2026, 5, 15): 175.0,
                       _horizon_date(date(2026, 5, 15), 21): 185.0}}
    cm = compute_call_markout(call, spot_history=spots)
    assert cm.verdict == "CORRECT"          # +5.7% > fallback 2%
    assert cm.band_used == pytest.approx(0.02)


def test_call_horizon_days_selects_nearest_markout_horizon():
    # Base = real NVDA close 222.82 (2026-06-02, UW).
    d0, spots = _flat_then_move_spots(222.82, 0.0, 0.10)
    call = Call(ticker="NVDA", analysis_date=d0, call_type="directional",
                direction=+1, structure=None, archive_path=Path("n.md"),
                notes="", horizon_days=7)
    cm = compute_call_markout(call, spot_history={"NVDA": spots})
    assert cm.verdict_horizon == 5           # nearest of (1,5,10,21,45) to 7


def test_structured_calls_parse_optional_8th_field_horizon():
    calls, bad = parse_structured_calls(
        ["NVDA|directional|+1||PROBE|0|false|21"],
        analysis_date=date(2026, 7, 1), archive_path=Path("x.md"), notes="")
    assert not bad and calls[0].horizon_days == 21
    # 7-field legacy entries stay valid, horizon_days None
    calls7, bad7 = parse_structured_calls(
        ["NVDA|directional|+1||PROBE|0|false"],
        analysis_date=date(2026, 7, 1), archive_path=Path("x.md"), notes="")
    assert not bad7 and calls7[0].horizon_days is None
```

(Add `from datetime import timedelta` to the test file imports if absent.)

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest tests/test_retrospective.py -k "sigma or horizon_days or 8th" -v` → FAIL (`unexpected keyword 'horizon_days'`, missing `band_used`).

- [ ] **Step 3: Implement**

3a. `Call`: add field after `opposite_case_first` — `horizon_days: int | None = None  # explicit call horizon (trading days); verdict scores at the nearest MARKOUT_HORIZON`.

3b. `CallMarkout`: add `band_used: float | None = None` after `notes`.

3c. `_parse_one_structured_call`: replace the strict length check to accept an optional 8th field:

```python
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) not in (7, 8):
        return (
            None,
            f"malformed calls entry (want 7 or 8 |-separated fields, got {len(parts)}): {raw!r}",
        )
    horizon_s = parts[7] if len(parts) == 8 else ""
    ticker, call_type, direction_s, structure_s, tier, flags_s, opp_s = parts[:7]
```

and before the `return`:

```python
    try:
        horizon_days = int(horizon_s) if horizon_s else None
    except ValueError:
        return None, f"calls entry unparseable horizon_days {horizon_s!r}: {raw!r}"
    if horizon_days is not None and horizon_days <= 0:
        return None, f"calls entry horizon_days must be positive: {raw!r}"
```

pass `horizon_days=horizon_days` into the `Call(...)` constructor. Update the field-order comment at lines 355-361 to `...|opposite_case_first|horizon_days?`.

3d. New helpers (place above `compute_call_markout`):

```python
def _trailing_sigma(
    ticker_spots: dict[date, float], asof: date, lookback: int = 20
) -> float | None:
    """Daily close-to-close σ over the last `lookback` returns at/before asof.
    None when fewer than 6 returns are available (fall back to fixed band)."""
    closes = [v for d, v in sorted(ticker_spots.items()) if d <= asof]
    closes = closes[-(lookback + 1):]
    if len(closes) < 7:
        return None
    rets = [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return var**0.5


def _nearest_horizon(h: int) -> int:
    return min(MARKOUT_HORIZONS, key=lambda x: abs(x - h))
```

3e. `compute_call_markout` directional branch — replace lines 741-750:

```python
        verdict_horizon = (
            _nearest_horizon(call.horizon_days)
            if call.horizon_days
            else DEFAULT_DIRECTIONAL_VERDICT_HORIZON
        )
        sigma = _trailing_sigma(ticker_spots, call.analysis_date)
        # σ-scaled band (2026-07-13 capability audit §1.2): the fixed ±2% is
        # 0.08σ on VIX and 0.99σ on DIA — provably miscalibrated, so the
        # N≥50 gate documented in review-framework Phase-1 was retired early.
        band = (
            0.5 * sigma * (verdict_horizon**0.5)
            if sigma  # None (short history) AND 0.0 (degenerate constant series) both fall back
            else DIRECTIONAL_NOISE_BAND
        )
        v_val = horizons.get(verdict_horizon)
        if v_val is None:
            verdict = "UNKNOWN"
        elif v_val > band:
            verdict = "CORRECT"
        elif v_val < -band:
            verdict = "WRONG"
        else:
            verdict = "NEUTRAL"
```

and pass `band_used=band` in the directional `CallMarkout(...)` return (`band_used=None` for the other two branches). `call.horizon_days` must be honored in ALL three branches, not just directional — the explicit lines:

- structure branch (replace line 796):
  ```python
        verdict_horizon = (
            _nearest_horizon(call.horizon_days)
            if call.horizon_days
            else DEFAULT_STRUCTURE_VERDICT_HORIZON
        )
  ```
  (sign-only verdict logic unchanged)
- vol_regime branch (replace line 771) — T+45 is skipped for vol calls, so clamp the choices:
  ```python
        verdict_horizon = (
            min((1, 5, 10, 21), key=lambda x: abs(x - call.horizon_days))
            if call.horizon_days
            else DEFAULT_VOL_REGIME_VERDICT_HORIZON
        )
  ```

Update `DIRECTIONAL_NOISE_BAND`'s docstring (line 40-44): it is now the *fallback* when <7 returns of history exist.

3f. `review-framework.md` Phase-1 limitations: mark the fixed-band item DONE (2026-07-13, link `docs/audits/2026-07-13-capability-audit.md` §1.2-1.3), note the ±2% is retained only as short-history fallback, and document the 8th `calls:` field.

- [ ] **Step 4: Run the full suite**

`.venv/bin/pytest tests/test_retrospective.py -q` — expected: new tests PASS. Two known breakage classes: (a) any test asserting the exact malformed-entry message "want 7 |-separated fields" — update to the new "want 7 or 8" text; (b) pre-existing tests asserting fixed-band verdicts on rich histories may legitimately flip (e.g. a +5.7% GOOGL move stays CORRECT under both bands, but any test that hand-built ≥25 days of history AND a sub-σ move will change) — inspect each failure: if the new verdict is the σ-correct one, update the test's expected value with a comment citing the audit; never weaken the band to satisfy an old fixture.

- [ ] **Step 5: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/retrospective.py plugins/option-wizard/skills/option-wizard/references/review-framework.md tests/test_retrospective.py
git commit -m "feat(retro): sigma-scaled horizon-matched verdict bands (audit R2)"
```

---

### Task 4: `regime_snapshot.py` — daily persisted regime state vector

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/scripts/regime_snapshot.py`
- Test: `tests/test_regime_snapshot.py`
- Modify: `docs/setup/daily-cron-install.md` (add the second cron line)

**Interfaces:**
- Consumes: `UWClient.iv_rank/iv_term_structure/spot_gex_by_strike/market_tide`, `FREDClient`+`hy_oas_signal`, `term_curve.label_regime/summarize_regime`, `gex_levels.compute_levels`. (Per-expiry GEX — `gex_by_strike_expiry` + `compute_levels_per_expiry` — is deliberately NOT consumed in v1; see Deferred. Task 1 builds the client method so the one-line addition is ready when its row shapes are confirmed.)
- Produces: `build_snapshot(fetched: dict) -> dict` (pure), `latest_regime(log_path: Path | None = None) -> dict | None` (reader used by Task 7's frontmatter convention and future 复盘 regime-conditioning), CLI `python -m scripts.regime_snapshot [--tickers ...] [--log-path ...]`. JSONL log at `references/private/market/regime-log.jsonl`, one object per line, `date` field unique (re-run same day replaces the line).

- [ ] **Step 1: Write the failing tests (pure assembly — no network)**

```python
"""build_snapshot is pure: it assembles pre-fetched payloads. Fetch fixtures
below are REAL UW response fragments frozen 2026-07-10 (from the 2026-07-13
capability audit pulls) — not invented values."""

import json

from scripts.regime_snapshot import append_snapshot, build_snapshot, latest_regime

# Frozen real values, as-of 2026-07-10 close (capability audit §Part B):
FETCHED = {
    "date": "2026-07-13",
    "iv_rank": {
        "SPX": {"close": 7575.39, "iv_rank_1y": 14.33, "date": "2026-07-10"},
        "QQQ": {"close": 725.51, "iv_rank_1y": 52.07, "date": "2026-07-10"},
        "VIX": {"close": 15.03, "iv_rank_1y": 12.93, "date": "2026-07-10"},
    },
    "term_structure": {
        "SPX": {"2026-07-17": 0.093, "2026-08-21": 0.132, "2026-12-18": 0.163},
    },
    "gex": {
        "SPX": {"gamma_flip": 7606.0, "put_wall": 7500.0, "call_wall": 7600.0},
    },
    "tide_eod": {"net_call_premium": -52.1e6, "net_put_premium": -106.3e6,
                 "as_of": "2026-07-10T16:10:00-04:00"},
    "hy_oas": {"hy_oas": None, "error": "fetch failed"},
}


def test_build_snapshot_labels_term_regime_and_dispersion():
    snap = build_snapshot(FETCHED)
    assert snap["date"] == "2026-07-13"
    assert snap["term_regime"]["SPX"] == "all_contango"
    assert snap["dispersion"]["qqq_minus_spx_iv_rank"] == 52.07 - 14.33
    assert snap["gex"]["SPX"]["gamma_flip"] == 7606.0
    assert snap["gaps"] == ["hy_oas: fetch failed"]  # honest-gap, not silent


def test_append_snapshot_is_idempotent_per_date(tmp_path):
    log = tmp_path / "regime-log.jsonl"
    snap = build_snapshot(FETCHED)
    append_snapshot(snap, log_path=log)
    append_snapshot({**snap, "note": "rerun"}, log_path=log)
    lines = [json.loads(x) for x in log.read_text().splitlines()]
    assert len(lines) == 1 and lines[0].get("note") == "rerun"


def test_latest_regime_reads_last_line(tmp_path):
    log = tmp_path / "regime-log.jsonl"
    append_snapshot(build_snapshot(FETCHED), log_path=log)
    got = latest_regime(log_path=log)
    assert got["date"] == "2026-07-13"
    assert latest_regime(log_path=tmp_path / "missing.jsonl") is None
```

- [ ] **Step 2: Run to verify failure** — `ModuleNotFoundError: scripts.regime_snapshot`.

- [ ] **Step 3: Implement `regime_snapshot.py`**

```python
"""Daily regime state vector — persisted so 复盘 can condition on regime.

Capability audit 2026-07-13 R1: regime was re-derived ad hoc per analysis and
discarded, making regime-conditioned learning structurally impossible and the
19 vol_regime calls ungradeable (UW keeps no IV-rank history). This script
archives the vector daily; the log IS the IV-rank history going forward.

Design: fetch_all() does I/O and NEVER raises on a single-source failure —
each miss becomes an entry in snapshot["gaps"] (honest-gap discipline, hard
rule #7). build_snapshot() is pure so tests run without network.

Cron (after the 16:00 ET close, weekdays) — mirror the proven manage_positions
entry exactly: repo-root cd (the editable-install .pth resolves `scripts`),
`. ./.env` sourcing (UW_API_KEY/FRED_API_KEY live there — without it this
crashes on RuntimeError at UWClient()), crontab-wide TZ=America/New_York:
  35 16 * * 1-5  cd /Users/chenxi/projects/option-wizard && set -a && . ./.env && set +a && .venv/bin/python -m scripts.regime_snapshot >> /Users/chenxi/.config/option-wizard/regime.log 2>&1
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts._clients.uw import UWClient
from scripts.gex_levels import compute_levels
from scripts.term_curve import label_regime, summarize_regime

DEFAULT_TICKERS = ("SPX", "QQQ", "VIX", "NVDA", "TSLA", "SMH")
INDEXES_FOR_GEX = ("SPX", "QQQ")


def _default_log_path() -> Path:
    return (
        Path(__file__).resolve().parent.parent
        / "references" / "private" / "market" / "regime-log.jsonl"
    )


def fetch_all(tickers: tuple[str, ...] = DEFAULT_TICKERS) -> dict[str, Any]:
    """Pull every regime input; single-source failures land in ['_errors']."""
    uw = UWClient()
    out: dict[str, Any] = {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "iv_rank": {}, "term_structure": {}, "gex": {},
        "tide_eod": None, "hy_oas": None, "_errors": [],
    }
    for t in tickers:
        try:
            d = uw.iv_rank(t)["data"]
            row = d[-1] if isinstance(d, list) else d
            out["iv_rank"][t] = {
                "close": float(row["close"]) if row.get("close") else None,
                "iv_rank_1y": float(row["iv_rank_1y"]) if row.get("iv_rank_1y") else None,
                "date": row.get("date"),
            }
        except Exception as e:
            out["_errors"].append(f"iv_rank {t}: {e}")
    for t in ("SPX", "QQQ"):
        try:
            rows = uw.iv_term_structure(t)["data"]
            expiries = [str(r["expiry"]) for r in rows if r.get("dte", 1) > 0][:8]
            ivs = {str(r["expiry"]): float(r["volatility"]) for r in rows
                   if str(r.get("expiry")) in expiries and r.get("volatility")}
            out["term_structure"][t] = ivs
        except Exception as e:
            out["_errors"].append(f"term_structure {t}: {e}")
    for t in INDEXES_FOR_GEX:
        try:
            rows = uw.spot_gex_by_strike(t)["data"]
            spot = out["iv_rank"].get(t, {}).get("close")
            if spot:
                lv = compute_levels(rows, float(spot), call_wall_definition="oi_cluster")
                out["gex"][t] = {k: lv[k] for k in ("gamma_flip", "put_wall", "call_wall")}
        except Exception as e:
            out["_errors"].append(f"gex {t}: {e}")
    try:
        tide = uw.market_tide()["data"]
        if tide:
            last = tide[-1]
            out["tide_eod"] = {
                "net_call_premium": float(last.get("net_call_premium") or 0),
                "net_put_premium": float(last.get("net_put_premium") or 0),
                "as_of": last.get("timestamp"),
            }
    except Exception as e:
        out["_errors"].append(f"market_tide: {e}")
    try:
        from scripts._clients.fred import hy_oas_signal

        sig = hy_oas_signal()
        out["hy_oas"] = {k: sig[k] for k in
                         ("hy_oas", "hy_oas_date", "hy_oas_30d_pct", "hy_oas_trend")}
    except Exception as e:
        out["_errors"].append(f"hy_oas: {e}")
        out["hy_oas"] = {"hy_oas": None, "error": str(e)}
    return out


def build_snapshot(fetched: dict[str, Any]) -> dict[str, Any]:
    """Pure assembly: label regimes, compute dispersion, collect gaps."""
    snap: dict[str, Any] = {
        "date": fetched["date"],
        "ts_utc": None,  # stamped in append_snapshot
        "iv_rank": fetched.get("iv_rank", {}),
        "gex": fetched.get("gex", {}),
        "tide_eod": fetched.get("tide_eod"),
        "hy_oas": fetched.get("hy_oas"),
        "term_regime": {},
        "dispersion": {},
        "gaps": list(fetched.get("_errors", [])),
    }
    for t, ivs in fetched.get("term_structure", {}).items():
        if len(ivs) >= 2:
            snap["term_regime"][t] = summarize_regime(label_regime(ivs))
        else:
            snap["gaps"].append(f"term_structure {t}: <2 expiries")
    ir = snap["iv_rank"]
    q, s = ir.get("QQQ", {}).get("iv_rank_1y"), ir.get("SPX", {}).get("iv_rank_1y")
    if q is not None and s is not None:
        snap["dispersion"]["qqq_minus_spx_iv_rank"] = q - s
    hy = fetched.get("hy_oas") or {}
    if hy.get("hy_oas") is None and "error" in hy:
        gap = f"hy_oas: {hy['error']}"
        if gap not in snap["gaps"]:  # fetch_all already logs it via _errors
            snap["gaps"].append(gap)
    return snap


def append_snapshot(snap: dict[str, Any], *, log_path: Path | None = None) -> Path:
    """One line per date — same-date re-run replaces (idempotent)."""
    path = log_path or _default_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    snap = {**snap, "ts_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    lines: list[dict[str, Any]] = []
    if path.exists():
        lines = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    lines = [x for x in lines if x.get("date") != snap["date"]]
    lines.append(snap)
    path.write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in lines) + "\n",
        encoding="utf-8",
    )
    return path


def latest_regime(log_path: Path | None = None) -> dict[str, Any] | None:
    path = log_path or _default_log_path()
    if not path.exists():
        return None
    lines = [x for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    return json.loads(lines[-1]) if lines else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Persist today's regime state vector")
    parser.add_argument("--tickers", nargs="*", default=list(DEFAULT_TICKERS))
    parser.add_argument("--log-path", type=Path, default=None)
    args = parser.parse_args(argv)
    snap = build_snapshot(fetch_all(tuple(args.tickers)))
    path = append_snapshot(snap, log_path=args.log_path)
    print(f"regime snapshot {snap['date']} -> {path} "
          f"({len(snap['gaps'])} gaps: {snap['gaps'] or 'none'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Note on `fetch_all` field names (`iv_rank_1y`, `close`, `volatility`, `net_call_premium`): these match the shapes observed live 2026-07-10/13 (capability audit + Task 1 Step 5 smoke). Re-verify against the Task 1 smoke output and adjust the accessors if UW renamed anything — then freeze the corrected names into the test fixture too. Per-expiry GEX (`gex_by_strike_expiry` → `compute_levels_per_expiry`) joins `fetch_all` as a follow-up once Task 1 Step 5 confirms its row field names; keep v1 to the all-expiry levels already proven.

- [ ] **Step 4: Run tests** — `.venv/bin/pytest tests/test_regime_snapshot.py -v` → PASS.

- [ ] **Step 5: Live run + install cron**

`cd /Users/chenxi/projects/option-wizard && set -a && source .env && set +a && .venv/bin/python -m scripts.regime_snapshot` (repo root works — the editable-install `.pth` puts the skill dir on sys.path, same mechanism the live manage_positions cron relies on). Expected: one new line in `references/private/market/regime-log.jsonl`, gaps listed honestly. Then `crontab -e`: add the cron line from the module docstring; append the same line to `docs/setup/daily-cron-install.md`.

- [ ] **Step 6: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/regime_snapshot.py tests/test_regime_snapshot.py docs/setup/daily-cron-install.md
git commit -m "feat(regime): daily persisted regime state vector (audit R1)"
```

---

### Task 5: `grade_calls.py` — weekly automated Layer-A grading

Closes the 46/52-ungraded hole (audit §1.4). Layer A only in v1: spot-driven directional/structure verdicts + write-back + pitfall drafts. Layer B (broker trades) stays with the interactive 复盘 flow; iv_rank_history comes from the Task 4 regime log (so vol calls become gradeable for calls made after the log starts).

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/scripts/grade_calls.py`
- Modify: `plugins/option-wizard/skills/option-wizard/scripts/retrospective.py:1787-1830` (add optional `window_dates` override to `run_review`)
- Modify: `docs/setup/daily-cron-install.md` (Friday cron line)
- Test: `tests/test_grade_calls.py`

**Blocked by:** Task 2's live probe succeeding (xenon `/historical/bars` is the price source). If the probe failed and Task 2 was re-scoped, do NOT install this cron — re-scope grading to the UW-MCP-assisted interactive flow instead.

**Maturity window (why not the plain weekly window):** a call graded at its T+21 horizon has no data until ~4 weeks after it was made; a 7-day extraction window would scan it once (immature → UNKNOWN) and never revisit. The grader therefore always extracts over a 70-calendar-day lookback (≈45 trading days + buffer, covering the longest MARKOUT_HORIZON) and relies on `write_back_outcome`'s idempotent append-per-review-date design: matured calls get their verdict on a later run, already-graded ones are refreshed, nothing is double-counted.

**Interfaces:**
- Consumes: `retrospective.extract_calls_from_archive`, `run_review` (with new `window_dates`), `render_report`, `save_review_report`, `_default_archive_dir`, `_default_drafts_dir`; `XenonClient.daily_closes` (Task 2); the Task 4 regime log for IV-rank history.
- Produces: CLI `python -m scripts.grade_calls --window weekly [--today YYYY-MM-DD] [--dry-run]`; pure helpers `tickers_in_window(archive_dir, start: date, end: date, *, include_archive: bool = False) -> set[str]` and `iv_rank_history_from_regime_log(log_path) -> dict[str, dict[date, float]]`; `run_review(..., window_dates: tuple[date, date] | None = None)` (None preserves existing behavior exactly).

- [ ] **Step 1: Write the failing tests**

```python
from datetime import date

from scripts.grade_calls import iv_rank_history_from_regime_log, tickers_in_window


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
```

- [ ] **Step 2: Run to verify failure** — `ModuleNotFoundError: scripts.grade_calls`.

- [ ] **Step 3: Implement**

3a. `retrospective.py` — add the extraction-window override to `run_review` (signature at line 1787; two-line change, default preserves every existing caller):

```python
    window_dates: tuple[date, date] | None = None,   # new kwarg, after max_annual_cost_pct
```

and replace line 1830:

```python
    window_start, window_end = window_dates or _window_dates(window, today)
```

3b. Create `grade_calls.py`:

```python
"""Weekly automated call grading — Layer A of 复盘, unattended.

Wires the live fetchers the retrospective CLI scaffold never had (audit R3):
spot_history from xenon daily bars, iv_rank_history from the regime log.
Layer B (broker trades) intentionally stays with the interactive 复盘 flow —
this runner grades CALLS, writes verdicts back to archives, and emits pitfall
drafts, so the loop closes even when the trader skips a week.

Cron (Friday evening, after regime_snapshot; same proven pattern — repo-root
cd + .env sourcing, TZ set crontab-wide):
  0 18 * * 5  cd /Users/chenxi/projects/option-wizard && set -a && . ./.env && set +a && .venv/bin/python -m scripts.grade_calls --window weekly >> /Users/chenxi/.config/option-wizard/grade.log 2>&1
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from scripts._clients.xenon import XenonClient
from scripts.retrospective import (
    _default_archive_dir,
    _default_drafts_dir,
    extract_calls_from_archive,
    render_report,
    run_review,
    save_review_report,
)

INDEX_SEC_TYPES = {"SPX": "IND", "VIX": "IND", "NDX": "IND", "RUT": "IND"}

# ≈45 trading days + buffer — covers the longest MARKOUT_HORIZON so calls are
# re-scanned until their verdict horizon matures (see "Maturity window" above).
LOOKBACK_DAYS = 70


def _default_regime_log() -> Path:
    return _default_archive_dir() / "market" / "regime-log.jsonl"


def tickers_in_window(
    archive_dir: Path, start: date, end: date, *, include_archive: bool = False
) -> set[str]:
    calls, _ = extract_calls_from_archive(
        archive_dir, start, end, include_archive=include_archive
    )
    return {c.ticker for c in calls}


def iv_rank_history_from_regime_log(log_path: Path) -> dict[str, dict[date, float]]:
    hist: dict[str, dict[date, float]] = {}
    if not log_path.exists():
        return hist
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        snap = json.loads(line)
        d = date.fromisoformat(snap["date"])
        for t, row in (snap.get("iv_rank") or {}).items():
            r = row.get("iv_rank_1y")
            if r is not None:
                hist.setdefault(t, {})[d] = float(r)
    return hist


def build_spot_history(tickers: set[str]) -> tuple[dict[str, dict[date, float]], list[str]]:
    """xenon daily bars per ticker; failures reported, never fabricated."""
    client = XenonClient()
    spot: dict[str, dict[date, float]] = {}
    failures: list[str] = []
    for t in sorted(tickers):
        try:
            spot[t] = client.daily_closes(
                t, duration="3 M", sec_type=INDEX_SEC_TYPES.get(t, "STK")
            )
        except Exception as e:
            failures.append(f"{t}: {e}")
    return spot, failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Automated Layer-A call grading")
    parser.add_argument("--window", choices=["weekly", "monthly"], required=True)
    parser.add_argument("--today", type=str, default=None)
    parser.add_argument("--archive-dir", type=Path, default=_default_archive_dir())
    parser.add_argument("--regime-log", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help="no write-back, no drafts, no report archive")
    args = parser.parse_args(argv)
    today = date.fromisoformat(args.today) if args.today else date.today()

    # Maturity lookback, not the report window: extraction always spans
    # LOOKBACK_DAYS so T+21/T+45 verdicts get written once they mature.
    start = today - timedelta(days=LOOKBACK_DAYS)
    include_archive = True  # lookback crosses the 30-day cold-storage TTL
    tickers = tickers_in_window(
        args.archive_dir, start, today, include_archive=include_archive
    )
    spot_history, failures = build_spot_history(tickers)
    iv_hist = iv_rank_history_from_regime_log(args.regime_log or _default_regime_log())

    report = run_review(
        window=args.window,   # labels the report; extraction uses window_dates
        today=today,
        archive_dir=args.archive_dir,
        spot_history=spot_history,
        iv_rank_history=iv_hist or None,
        trades=[],            # Layer B stays interactive — see module docstring
        trade_sources=[],
        # run_review only writes drafts when drafts_dir is non-None
        # (retrospective.py:1878) — generate_drafts alone is not enough.
        drafts_dir=None if args.dry_run else _default_drafts_dir(),
        write_back=not args.dry_run,
        generate_drafts=not args.dry_run,
        include_archive=include_archive,
        window_dates=(start, today),
    )
    rendered = render_report(report)
    if failures:
        rendered += "\n\n## Grading data gaps\n\n" + "\n".join(f"- {f}" for f in failures)
    print(rendered)
    if not args.dry_run:
        path = save_review_report(report, rendered, base_dir=args.archive_dir)
        print(f"\n[graded report archived to {path}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Tests + live dry-run**

`.venv/bin/pytest tests/test_grade_calls.py -v` → PASS.
Live: `cd plugins/option-wizard/skills/option-wizard && ... python -m scripts.grade_calls --window weekly --dry-run` → real report over the current week's archives with real verdicts, gaps listed. Inspect one write-back diff with a non-dry run on a `--archive-dir` copy in the scratchpad before trusting it on the real archive.

- [ ] **Step 5: Install cron + commit**

Add the Friday cron line (module docstring) via `crontab -e`; document in `docs/setup/daily-cron-install.md`.

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/grade_calls.py plugins/option-wizard/skills/option-wizard/scripts/retrospective.py tests/test_grade_calls.py docs/setup/daily-cron-install.md
git commit -m "feat(retro): weekly automated Layer-A call grading (audit R3)"
```

---

### Task 6: Ledger escalation — kill the advice treadmill

Audit weakness #4: the same concentration action item resurfaced weekly for a month without execution. Age-based escalation, no new state (ponytail: the `date` field already exists on every entry).

**Files:**
- Modify: `plugins/option-wizard/skills/option-wizard/scripts/ledger.py` (`render_open_items_block`, lines 147-161)
- Test: extend `tests/test_ledger.py`

**Interfaces:**
- Consumes: entry dict shape `{id, date, ticker, action, tier, status, due, source_file}`.
- Produces: `render_open_items_block(entries, *, title=..., as_of: date | None = None)` — items open ≥ `ESCALATE_AFTER_DAYS` (module constant, 14) gain a `⚠ ESCALATED (open Nd) — execute or retire with reason` suffix and sort first.

- [ ] **Step 1: Write the failing test**

```python
def test_open_items_escalate_after_14_days(tmp_path):
    from datetime import date

    path = tmp_path / "ledger.jsonl"
    append_entry(path, entry_date=date(2026, 6, 20), ticker="TSLA",
                 action="hedge 400/390 conflict", tier="NORMAL")
    append_entry(path, entry_date=date(2026, 7, 10), ticker="NVDA",
                 action="roll 21DTE", tier="PROBE")
    block = render_open_items_block(load_ledger(path), as_of=date(2026, 7, 13))
    lines = block.splitlines()
    assert "ESCALATED (open 23d)" in block
    assert "execute or retire" in block
    assert "TSLA" in lines[1]          # escalated item sorts first
    assert "ESCALATED" not in [l for l in lines if "NVDA" in l][0]


def test_render_without_as_of_never_escalates(tmp_path):
    from datetime import date

    path = tmp_path / "ledger.jsonl"
    append_entry(path, entry_date=date(2026, 1, 1), ticker="QQQ", action="x")
    assert "ESCALATED" not in render_open_items_block(load_ledger(path))
```

- [ ] **Step 2: Run to verify failure** — `TypeError: unexpected keyword 'as_of'`.

- [ ] **Step 3: Implement**

Add module constant `ESCALATE_AFTER_DAYS = 14` next to `STATUSES`; replace `render_open_items_block`:

```python
def render_open_items_block(
    entries: list[dict[str, Any]],
    *,
    title: str = "Open decision-ledger items",
    as_of: date | None = None,
) -> str:
    """One line per open item. With `as_of`, items open >= ESCALATE_AFTER_DAYS
    are flagged ESCALATED and sorted first — an action item that survives two
    weekly scans unexecuted is a decision being avoided, not a reminder
    (2026-07-13 capability audit, weakness #4: same concentration item
    re-flagged for a month while the hedge slipped 5x over budget)."""
    items = open_items(entries)
    if not items:
        return ""

    def _age(e: dict[str, Any]) -> int:
        if as_of is None or not e.get("date"):
            return 0
        return (as_of - date.fromisoformat(e["date"])).days

    def _key(e: dict[str, Any]):
        escalated = _age(e) >= ESCALATE_AFTER_DAYS
        return (0 if escalated else 1, e.get("due") or "9999-99-99")

    lines = [f"{title} ({len(items)}):"]
    for e in sorted(items, key=_key):
        due_s = f" due {e['due']}" if e.get("due") else ""
        tier_s = f" [{e['tier']}]" if e.get("tier") else ""
        age = _age(e)
        esc = (
            f" ⚠ ESCALATED (open {age}d) — execute or retire with reason"
            if age >= ESCALATE_AFTER_DAYS
            else ""
        )
        lines.append(f"  {e['id']} {e['ticker']}: {e['action']}{tier_s}{due_s}{esc}")
    return "\n".join(lines)
```

Then in `manage_positions.py:269` pass the clock: `render_open_items_block(load_ledger(default_ledger_path()), as_of=datetime.utcnow().date())`.

- [ ] **Step 4: Run** — `.venv/bin/pytest tests/test_ledger.py tests/test_manage_positions*.py -q` → PASS (existing callers without `as_of` keep old behavior).

- [ ] **Step 5: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/ledger.py plugins/option-wizard/skills/option-wizard/scripts/manage_positions.py tests/test_ledger.py
git commit -m "feat(ledger): escalate items open >=14d (audit R5)"
```

---

### Task 7: Doctrine red-line + regime frontmatter convention

**Files:**
- Modify: `plugins/option-wizard/skills/option-wizard/references/decision-doctrine.md` (crowding-check section)
- Modify: `plugins/option-wizard/skills/option-wizard/SKILL.md` (archive conventions section, ~line 197-230)
- Modify: `plugins/option-wizard/skills/option-wizard/references/data-sources.md` (add regime-log row)

- [ ] **Step 1: Doctrine red-line**

In `decision-doctrine.md`'s crowding-check section, add (adjusting heading level to context):

```markdown
**Red line — falling IV rank never downgrades a fired crowding flag.**
A falling IV rank into a known binary event is NOT "the event is priced in /
safe" — crowded positioning with cheap options is the textbook sell-the-news
precondition (TSLA 2026-07-02: crowding check fired, falling IV rank
36.3→25.7 was read as a green light, delivery beat every estimate and the
stock fell −7.5%; see pitfalls/06 and the 2026-07-13 capability audit,
weakness #2). Once the crowding check fires, only positioning evidence
(flow/OI actually thinning) may downgrade it — never an IV-level argument.
```

- [ ] **Step 2: `regime:` frontmatter convention**

In `SKILL.md`'s archive-conventions section add one bullet:

```markdown
- Every archived analysis adds `regime: <summary>` frontmatter, copied from
  the latest `references/private/market/regime-log.jsonl` line
  (`scripts.regime_snapshot.latest_regime()` — e.g.
  `regime: SPX all_contango | QQQ-SPX ivr +37.7 | gamma_flip 7606 | hy_oas flat`).
  This is what lets 复盘 answer "in which regimes do my calls actually work"
  — an unanswerable question before 2026-07-13 because regime was never
  persisted at call time.
```

In `data-sources.md`, add a row to the source table: regime state history → `references/private/market/regime-log.jsonl` (written daily by `scripts.regime_snapshot` cron; the ONLY IV-rank history that exists — UW serves snapshots only).

Enforcement note (a convention nobody checks is a convention that decays): this task is
docs-only, so add the check where checking already happens — the capability-audit
runbook's Phase 5 counts archives dated after the regime-log start that lack `regime:`
frontmatter (done in this plan's companion runbook edit). Extending
`retrospective.py --validate-archive` to warn on missing `regime:` is a good follow-up
once the convention has a few weeks of usage — deferred, not forgotten.

- [ ] **Step 3: Verify + commit**

`grep -rn "regime-log" plugins/option-wizard/skills/option-wizard/{SKILL.md,references/data-sources.md}` → both hit. `.venv/bin/pytest tests/ -q` → green.

```bash
git add plugins/option-wizard/skills/option-wizard/SKILL.md plugins/option-wizard/skills/option-wizard/references/decision-doctrine.md plugins/option-wizard/skills/option-wizard/references/data-sources.md
git commit -m "docs(doctrine): crowding red-line + regime frontmatter convention (audit R4)"
```

---

## Deferred (do NOT build in this plan — triggers listed)

- **R6 flow/positioning layer + screener candidate generation** — separate plan once R1–R3 have ≥2 weeks of regime-log + graded data; needs UW flow-alerts/screener REST path discovery first (same `get_public_api_docs` method used above).
- **R7 real entry-timing logging** — wire when the next real index-premium entry decision happens; current log is synthetic fixtures.
- **Closing-trade pairing (gap-audit P2.2, review-framework Phase 2)** — attribute realized P/L back to the opening decision; build with the Layer-B extension of grade_calls once the trader wants automated trade markout (needs `parse_xenon_blotter` wiring + open/close matching design).
- **Per-expiry GEX in the snapshot** — one-line addition to `fetch_all` once Task 1 Step 5 confirms row field names.
- **xenon `/attribution` + `/ws-ticket` streaming** — server response undocumented (`readonly-query-api.md` has only the table row); needs a xenon-repo doc first.
- **Cross-vendor spot sanity band (R4b)** — fold into `fundamental-analysis` skill's fetch layer where the MU $1,064 bug actually lives; out of this repo's plan.

## Execution wrap-up

**Pre-flight blocker (verified 2026-07-13):** xenon (`$XENON_BASE`, Tailscale) is
unreachable — `/health` times out, consistent with the daily-scan cron failing since
07-10. Bring the xenon service/Tailscale link back BEFORE starting Task 2's probe or any
Task 4/5 live step. Tasks 1 and 3 (UW client, σ-band) don't touch xenon and can proceed
regardless.

Branch `feat/regime-engine-and-scoring`, single PR, body links `docs/audits/2026-07-13-capability-audit.md`. Task order matters: 1 → 2 → (3, 4 parallel) → 5 → 6 → 7. Post-merge verification: next weekday check `regime-log.jsonl` gained a line; next Friday check a graded report landed in `references/private/review/` with real verdicts written back.
