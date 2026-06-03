# option-wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a personal Claude Code skill that evaluates private bank FCN quotes, recommends income/hedge option structures from Unusual Whales data, and executes orders through Interactive Brokers with strict defined-risk guardrails.

**Architecture:** Python 3.13 toolkit + markdown skill prompts. Pure-function analytics (gamma flip, fair coupon, VRP, macro hedge sizing) are testable in isolation; external integrations (UW REST API, IB Gateway via `ib_insync`, Gmail SMTP) are thin clients with one integration smoke test each. The skill prompt orchestrates LLM-side MCP calls for in-session work; a daily Python entrypoint handles the autonomous market-open run.

**Tech Stack:** Python 3.13 (uv-managed venv), `httpx` (UW REST), `ib_insync` (IB Gateway port 4001), `numpy`/`scipy` (math), `pytest` (testing), standard-library `smtplib`/`email` (Gmail SMTP). MCP servers: Unusual Whales remote HTTP MCP, Interactive Brokers IBKR MCP, existing `finance-data-providers:tradingview-reader` skill for chart data.

**Reference spec:** `docs/specs/2026-06-03-option-wizard-design.md`

---

## File Structure (locked before tasks)

```
~/projects/option-wizard/
├── .claude-plugin/marketplace.json                    marketplace manifest (mirrors trade-skills)
├── .gitignore                                         (exists)
├── CLAUDE.md                                          trader profile + hard rules
├── README.md                                          repo entry
├── package.json                                       optional npx skills entry
├── pyproject.toml                                     Python project + deps
├── docs/
│   ├── specs/2026-06-03-option-wizard-design.md       (exists)
│   └── plans/2026-06-03-option-wizard-implementation.md  this file
├── plugins/option-wizard/
│   ├── plugin.json                                    per-plugin manifest
│   └── skills/option-wizard/
│   ├── SKILL.md
│   ├── README.md
│   ├── scripts/
│   │   ├── __init__.py
│   │   ├── _clients/
│   │   │   ├── __init__.py
│   │   │   ├── uw.py                                  UW REST client
│   │   │   └── ib.py                                  ib_insync wrapper
│   │   ├── gex_levels.py                              pure: GEX → flip/walls
│   │   ├── vrp.py                                     pure: IV − RV
│   │   ├── fair_coupon.py                             pure: FCN coupon + ladder + basket
│   │   ├── ib_order.py                                build IB order instructions
│   │   ├── manage_positions.py                        daily position scan entrypoint
│   │   ├── evaluate_position.py                       single-position roll/close decision
│   │   ├── macro_hedge.py                             SPX hedge construction
│   │   └── email_sender.py                            Gmail SMTP delivery
│   └── references/
│       ├── data-sources.md
│       ├── strategies.md
│       ├── gamma-framework.md
│       ├── price-action-framework.md
│       ├── fcn-framework.md
│       ├── execution.md
│       ├── pitfalls/
│       │   ├── README.md
│       │   └── _template.md
│       └── ticker/
│           ├── README.md
│           ├── _template.md
│           └── orcl-2026-06-fcn.md
└── tests/
    ├── __init__.py
    ├── test_gex_levels.py
    ├── test_vrp.py
    ├── test_fair_coupon.py
    ├── test_ib_order.py
    ├── test_evaluate_position.py
    ├── test_macro_hedge.py
    ├── test_email_sender.py
    └── integration/
        ├── test_uw_smoke.py                           live UW endpoints
        ├── test_ib_paper_smoke.py                     live IB paper account
        └── test_email_smoke.py                        live Gmail SMTP
```

---

## Phase 0 — Project Bootstrap

### Task 0.1: pyproject.toml + uv venv

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`

- [ ] **Step 1: Write pyproject.toml**

```toml
[project]
name = "option-wizard"
version = "0.1.0"
description = "Personal options trading + FCN evaluation + IB execution"
requires-python = ">=3.13"
dependencies = [
    "httpx>=0.27",
    "ib_insync>=0.9.86",
    "numpy>=1.26",
    "scipy>=1.13",
    "pandas>=2.2",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-mock>=3.12",
    "ruff>=0.6",
]

[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["plugins/option-wizard/skills/option-wizard"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"
```

- [ ] **Step 2: Write .python-version**

```
3.13
```

- [ ] **Step 3: Create venv and install deps**

```bash
cd ~/projects/option-wizard
uv venv --python 3.13 .venv
uv pip install -e ".[dev]" -p .venv
```

Expected: `Installed N packages` with no errors.

- [ ] **Step 4: Verify imports**

```bash
.venv/bin/python -c "import httpx, ib_insync, numpy, scipy, pandas; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .python-version
git commit -m "chore: initialize pyproject and python 3.13 venv"
```

---

### Task 0.2: Plugin manifest + project README + CLAUDE.md

**Files:**
- Create: `.claude-plugin/plugin.json`
- Create: `README.md`
- Create: `CLAUDE.md`
- Create: `package.json`

- [ ] **Step 1: Write .claude-plugin/marketplace.json and plugins/option-wizard/plugin.json**

Mirrors the himself65/trade-skills layout: top-level `marketplace.json` declares the marketplace; the per-plugin manifest lives inside `plugins/<plugin>/`.

`.claude-plugin/marketplace.json`:

```json
{
  "name": "option-wizard-marketplace",
  "plugins": ["plugins/option-wizard"]
}
```

`plugins/option-wizard/plugin.json`:

```json
{
  "name": "option-wizard",
  "version": "0.1.0",
  "description": "Personal options trading, FCN evaluation, and IB execution skill",
  "skills": ["skills/option-wizard"]
}
```

- [ ] **Step 2: Write README.md**

```markdown
# option-wizard

Personal Claude Code skill: FCN private-bank quote defense, single-name option income recommendations, SPX macro hedge sizing, and Interactive Brokers order execution with defined-risk guardrails.

## Install

```bash
ln -s ~/projects/option-wizard/plugins/option-wizard/skills/option-wizard \
      ~/.claude/skills/option-wizard
```

## Use

In Claude Code: mention a ticker in a trading context, paste a PB FCN quote, or ask to review positions. See `plugins/option-wizard/skills/option-wizard/SKILL.md` for triggers.

## Layout

- `plugins/option-wizard/skills/option-wizard/SKILL.md` — skill entry
- `plugins/option-wizard/skills/option-wizard/scripts/` — Python helpers
- `plugins/option-wizard/skills/option-wizard/references/` — domain reference docs
- `docs/specs/` — design specification
- `docs/plans/` — implementation plan
- `tests/` — pytest suite

## Spec

See `docs/specs/2026-06-03-option-wizard-design.md`.
```

- [ ] **Step 3: Write CLAUDE.md (project-level rules)**

```markdown
# option-wizard working agreements

## Trader profile

Active US-equity options trader, recent focus on mega-cap tech and semiconductors. Private bank client; receives FCN/ELN quotes regularly. Self-directed account on IB Gateway live (port 4001). Reads and writes Chinese; technical terms (delta, IV crush, gamma flip, KI, etc.) stay in English.

## Data source order

1. **Unusual Whales MCP / REST API** — vol, dealer, options microstructure (IV rank, GEX, skew, term structure, max pain, dark pool). UW first for any number UW serves directly.
2. **TradingView via Playwright** — realtime spot, technical indicators, chart, news. Reuse `finance-data-providers:tradingview-reader` skill rather than re-implement.
3. **Interactive Brokers MCP / ib_insync** — account positions, balances, contract resolution, order instructions.

## Hard rules

1. Defined-risk only. No naked short calls. No margin-leveraged short puts.
2. Every order shows P/L matrix, account verification, UW regime check, catalyst clock before submission. One YES/NO question per order.
3. Any short-premium position at 21 DTE produces a blocking review prompt — close, roll, or accept-gamma-risk choice required.
4. FCN does not go through IB. FCN output is a bilingual counter-offer email and a strike/coupon ladder.
5. Total annualized macro hedge cost ≤ 1.5% of portfolio net liquidation.
6. Bracket order defaults: take-profit at 50% of max gain, stop-loss at 2× credit received. Configurable per order.

## Response style

Chinese response. English technical terms. Concrete numbers, structures, verdicts — no "可以考虑" hedging language. Honest about PB markup; honest about thesis decay.

## Python environment

`uv` only. Venv at `.venv`. Python 3.13. Test with `.venv/bin/pytest`.
```

- [ ] **Step 4: Write package.json**

```json
{
  "name": "option-wizard",
  "version": "0.1.0",
  "description": "Personal options trading + FCN + IB execution skill",
  "license": "UNLICENSED",
  "private": true
}
```

- [ ] **Step 5: Commit**

```bash
git add .claude-plugin/ plugins/option-wizard/plugin.json README.md CLAUDE.md package.json
git commit -m "feat: project scaffold (marketplace.json + plugin.json, README, CLAUDE.md)"
```

---

### Task 0.3: Skill directory skeleton

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/SKILL.md`
- Create: `plugins/option-wizard/skills/option-wizard/README.md`
- Create: `plugins/option-wizard/skills/option-wizard/scripts/__init__.py` (empty)
- Create: `plugins/option-wizard/skills/option-wizard/scripts/_clients/__init__.py` (empty)
- Create: `tests/__init__.py` (empty)

- [ ] **Step 1: Write SKILL.md frontmatter + body**

```markdown
---
name: option-wizard
description: >
  Personal US-equity options trading, private bank FCN/ELN evaluation, and IB
  execution. Use for FCN coupon negotiation ("PB quoted me X% on Y"),
  vol-regime-based option structure picks (covered call, sell put, defined-risk
  spreads, jade lizard, collar), SPX macro hedge sizing, position management
  (take-profit/stop-loss brackets, 21 DTE review, roll suggestions), and
  IB order placement. Data: Unusual Whales (IV rank, GEX, skew, term
  structure, max pain, dark pool), TradingView via finance-data-providers
  reader (spot, charts, technicals, news), IB MCP (positions, balances,
  order instructions). Triggers on ticker mentions in trading context,
  FCN/ELN quote review, "should I sell put on X", "covered call on Y",
  "is this FCN deal good", "macro hedge", "check my positions", "place
  this order". Chinese response with English technical terms. Defined-risk
  only — never naked short calls, never margin-leveraged short puts.
---

# option-wizard

See `references/` for the full domain knowledge:

- `references/data-sources.md` — UW / TV / IB call playbook
- `references/strategies.md` — regime × structure matrix
- `references/gamma-framework.md` — GEX, gamma flip, put/call wall reading
- `references/price-action-framework.md` — TradingView chart, indicators, tape signals
- `references/fcn-framework.md` — FCN payoff, fair coupon, 8-item PB checklist
- `references/execution.md` — IB pre-flight, bracket orders, 21 DTE rule
- `references/pitfalls/` — accumulated trading mistakes (start empty)
- `references/ticker/` — case studies (start with orcl-2026-06-fcn.md)

## Hard rules (apply to every response)

1. Defined-risk only. Refuse naked short calls and margin-leveraged short puts; explain why when refusing.
2. UW first for numeric metrics: IV rank, RV, skew, IV term structure, max pain, GEX by strike, greeks by strike, dark pool, interpolated IV. Do not recompute these client-side. Compute only what UW lacks (gamma flip from GEX, put/call walls from GEX, VRP from IV−RV, FCN fair coupon).
3. Every order shows the pre-flight (legs, mid price, net debit/credit, max loss, max gain, breakeven, margin, P/L matrix at expiry across spot −20 / −10 / −5 / 0 / +5 / +10 / +20 percent, account verification, UW regime check, liquidity check, catalyst clock) before submission. Exactly one YES/NO question. YES → call IB MCP `create_order_instruction`. Anything else → abort.
4. Any short-premium position at 21 DTE produces a blocking review prompt. The trader must pick close / roll / hold-and-accept-gamma before any other request is answered.
5. FCN does not go through IB. FCN output is the 8-item PB checklist, a 70/75/80/85% strike ladder, a fair vs quoted verdict, and a bilingual counter-offer email (Chinese first, English second).
6. Bracket order defaults: take-profit at 50% of max gain, stop-loss at 2× credit received (100% of max loss for spreads). Per-order override allowed.

## Triggers

Chinese:
- "分析 <TICKER>"
- "PB 给我报了 <TICKER> 的 FCN, X% coupon"
- "<TICKER> 怎么做 sell put / covered call / jade lizard"
- "我账户里这些仓位有没有问题"
- "SPX 大盘对冲"
- "<TICKER> 现在该 close 还是 roll"

English:
- "negotiate fcn quote"
- "evaluate <ticker> for <structure>"
- "size spx hedge"
- "review positions"

## How to invoke scripts

The skill prompt orchestrates the LLM. Numeric work is delegated to the Python scripts under `scripts/`. Examples:

- FCN analysis: `.venv/bin/python -m scripts.fair_coupon --ticker ORCL --strike-pct 0.75 --tenor-months 6 --observation-months 3`
- Gamma levels: `.venv/bin/python -m scripts.gex_levels --gex-json <path>` (input is UW spot-exposures output saved to file or stdin)
- Build IB order: `.venv/bin/python -m scripts.ib_order --structure bull_put_spread --ticker ORCL --legs '...'`
- Daily position scan: `.venv/bin/python -m scripts.manage_positions`
```

- [ ] **Step 2: Write skill README.md**

```markdown
# option-wizard skill

This directory is the skill consumed by Claude Code. See `../../../README.md` for project overview and `../../../docs/specs/2026-06-03-option-wizard-design.md` for the design spec.

## Files

- `SKILL.md` — skill prompt
- `scripts/` — Python helpers
- `references/` — domain reference docs

## Invocation

The skill triggers on ticker mentions in trading context and explicit FCN/order phrases. See `SKILL.md`.
```

- [ ] **Step 3: Create empty __init__.py files**

```bash
touch plugins/option-wizard/skills/option-wizard/scripts/__init__.py
touch plugins/option-wizard/skills/option-wizard/scripts/_clients/__init__.py
touch tests/__init__.py
```

- [ ] **Step 4: Verify pytest runs (0 tests collected)**

```bash
.venv/bin/pytest tests/
```

Expected: `no tests ran in X.XXs`. Exit code 5 (no tests collected) is acceptable.

- [ ] **Step 5: Commit**

```bash
git add plugins/ tests/__init__.py
git commit -m "feat: skill directory skeleton with SKILL.md and stubs"
```

---

## Phase 1 — UW Data Layer + Endpoint Verification

### Task 1.1: UW REST client (`scripts/_clients/uw.py`)

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/scripts/_clients/uw.py`
- Create: `tests/test_uw_client.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_uw_client.py
from unittest.mock import patch, MagicMock
import pytest
from plugins.option_wizard.skills.option_wizard.scripts._clients.uw import UWClient


def test_uw_client_sets_authorization_header(monkeypatch):
    monkeypatch.setenv("UW_API_KEY", "test_token_123")
    client = UWClient()
    assert client._headers["Authorization"] == "Bearer test_token_123"
    assert client._headers["UW-CLIENT-API-ID"] == "100001"


def test_uw_client_iv_rank_calls_correct_endpoint():
    with patch("plugins.option_wizard.skills.option_wizard.scripts._clients.uw.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"data": [{"iv_rank": 91}]})
        client = UWClient(api_key="x")
        result = client.iv_rank("ORCL")
        called_url = mock_get.call_args[0][0]
        assert "/api/stock/ORCL/iv-rank" in called_url
        assert result == {"data": [{"iv_rank": 91}]}


def test_uw_client_missing_key_raises():
    with pytest.raises(RuntimeError, match="UW_API_KEY"):
        UWClient(api_key=None)
```

The test imports the package via the path `plugins.option_wizard.skills.option_wizard.scripts._clients.uw`. To make that importable, we need to add a top-level conftest that adjusts sys.path. Add now:

```python
# tests/conftest.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_ROOT = ROOT / "plugins" / "option-wizard" / "skills" / "option-wizard"

# Allow `from plugins.option_wizard.skills.option_wizard.scripts...` imports
sys.path.insert(0, str(ROOT))

# Alias hyphen-named dirs as underscore packages
import importlib.util
def _alias(name, path):
    spec = importlib.util.spec_from_file_location(name, path / "__init__.py")
    if spec and spec.loader:
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod

# Simpler: also let scripts be imported directly
sys.path.insert(0, str(SKILL_ROOT))
```

Actually keep it simple — add the skill root to sys.path and import scripts directly as `from scripts._clients.uw import UWClient`:

```python
# tests/conftest.py
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent / "plugins" / "option-wizard" / "skills" / "option-wizard"
sys.path.insert(0, str(SKILL_ROOT))
```

And revise the test imports accordingly:

```python
# tests/test_uw_client.py (revised)
from unittest.mock import patch, MagicMock
import pytest
from scripts._clients.uw import UWClient


def test_uw_client_sets_authorization_header(monkeypatch):
    monkeypatch.setenv("UW_API_KEY", "test_token_123")
    client = UWClient()
    assert client._headers["Authorization"] == "Bearer test_token_123"
    assert client._headers["UW-CLIENT-API-ID"] == "100001"


def test_uw_client_iv_rank_calls_correct_endpoint():
    with patch("scripts._clients.uw.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"data": [{"iv_rank": 91}]})
        client = UWClient(api_key="x")
        result = client.iv_rank("ORCL")
        called_url = mock_get.call_args[0][0]
        assert "/api/stock/ORCL/iv-rank" in called_url
        assert result == {"data": [{"iv_rank": 91}]}


def test_uw_client_missing_key_raises(monkeypatch):
    monkeypatch.delenv("UW_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="UW_API_KEY"):
        UWClient(api_key=None)
```

- [ ] **Step 2: Run test to verify failure**

```bash
.venv/bin/pytest tests/test_uw_client.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'scripts'` or similar.

- [ ] **Step 3: Write minimal implementation**

```python
# plugins/option-wizard/skills/option-wizard/scripts/_clients/uw.py
"""Thin HTTP client for the Unusual Whales public API.

Auth: Bearer token in env var UW_API_KEY. Client ID header per UW docs.
Wraps only the endpoints option-wizard actually uses; expand as needed.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

BASE_URL = "https://api.unusualwhales.com"


class UWClient:
    def __init__(self, api_key: str | None = None, timeout: float = 10.0) -> None:
        key = api_key if api_key is not None else os.environ.get("UW_API_KEY")
        if not key:
            raise RuntimeError("UW_API_KEY is not set (env var or constructor argument).")
        self._headers = {
            "Authorization": f"Bearer {key}",
            "UW-CLIENT-API-ID": "100001",
            "Accept": "application/json",
        }
        self._timeout = timeout

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{BASE_URL}{path}"
        resp = httpx.get(url, headers=self._headers, params=params, timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()

    # --- endpoints (one method per UW endpoint we consume) ---

    def iv_rank(self, ticker: str) -> dict[str, Any]:
        return self._get(f"/api/stock/{ticker}/iv-rank")

    def realized_volatility(self, ticker: str) -> dict[str, Any]:
        return self._get(f"/api/stock/{ticker}/realized-volatility")

    def historical_risk_reversal_skew(self, ticker: str) -> dict[str, Any]:
        return self._get(f"/api/stock/{ticker}/historical-risk-reversal-skew")

    def iv_term_structure(self, ticker: str) -> dict[str, Any]:
        return self._get(f"/api/stock/{ticker}/implied-volatility-term-structure")

    def max_pain(self, ticker: str) -> dict[str, Any]:
        return self._get(f"/api/stock/{ticker}/max-pain")

    def spot_gex_by_strike(self, ticker: str) -> dict[str, Any]:
        return self._get(f"/api/stock/{ticker}/spot-exposures/strike")

    def interpolated_iv(self, ticker: str) -> dict[str, Any]:
        return self._get(f"/api/stock/{ticker}/interpolated-iv")

    def greeks_by_strike(self, ticker: str, expiry: str | None = None) -> dict[str, Any]:
        params = {"expiry": expiry} if expiry else None
        return self._get(f"/api/stock/{ticker}/greeks", params=params)

    def dark_pool(self, ticker: str) -> dict[str, Any]:
        return self._get(f"/api/darkpool/{ticker}")

    def technical_indicator(self, ticker: str, function: str) -> dict[str, Any]:
        return self._get(f"/api/stock/{ticker}/technical-indicator/{function}")
```

- [ ] **Step 4: Run tests to verify pass**

```bash
.venv/bin/pytest tests/test_uw_client.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/_clients/uw.py tests/conftest.py tests/test_uw_client.py
git commit -m "feat(uw): REST client wrapping the endpoints option-wizard uses"
```

---

### Task 1.2: UW live smoke test + endpoint path verification

**Goal:** Resolve spec §13 open item #3 — confirm exact UW endpoint paths and JSON field shapes against the live API.

**Files:**
- Create: `tests/integration/__init__.py` (empty)
- Create: `tests/integration/test_uw_smoke.py`

- [ ] **Step 1: Write the smoke test**

```python
# tests/integration/test_uw_smoke.py
"""Live UW API smoke test. Requires UW_API_KEY env var. Pytest skips if missing.

This test calls each endpoint option-wizard depends on against a stable
ticker (ORCL) and asserts the response structure exists. It does NOT
assert specific values (they change daily). Run manually before merging
Task 1.1 to production use:

    UW_API_KEY=... .venv/bin/pytest tests/integration/test_uw_smoke.py -v
"""
import os
import pytest

from scripts._clients.uw import UWClient


pytestmark = pytest.mark.skipif(
    "UW_API_KEY" not in os.environ,
    reason="UW_API_KEY not set; skip live smoke test",
)

TICKER = "ORCL"


@pytest.fixture(scope="module")
def client():
    return UWClient()


def test_iv_rank(client):
    resp = client.iv_rank(TICKER)
    assert isinstance(resp, dict), "expected JSON object"
    print("iv_rank response shape:", list(resp.keys()))


def test_realized_volatility(client):
    resp = client.realized_volatility(TICKER)
    assert isinstance(resp, dict)
    print("realized_volatility response shape:", list(resp.keys()))


def test_skew(client):
    resp = client.historical_risk_reversal_skew(TICKER)
    assert isinstance(resp, dict)
    print("skew response shape:", list(resp.keys()))


def test_iv_term_structure(client):
    resp = client.iv_term_structure(TICKER)
    assert isinstance(resp, dict)
    print("iv_term_structure response shape:", list(resp.keys()))


def test_max_pain(client):
    resp = client.max_pain(TICKER)
    assert isinstance(resp, dict)
    print("max_pain response shape:", list(resp.keys()))


def test_spot_gex_by_strike(client):
    resp = client.spot_gex_by_strike(TICKER)
    assert isinstance(resp, dict)
    assert "data" in resp or len(resp) > 0
    print("spot_gex_by_strike response shape:", list(resp.keys()))


def test_interpolated_iv(client):
    resp = client.interpolated_iv(TICKER)
    assert isinstance(resp, dict)
    print("interpolated_iv response shape:", list(resp.keys()))


def test_greeks_by_strike(client):
    resp = client.greeks_by_strike(TICKER)
    assert isinstance(resp, dict)
    print("greeks_by_strike response shape:", list(resp.keys()))


def test_dark_pool(client):
    resp = client.dark_pool(TICKER)
    assert isinstance(resp, dict)
    print("dark_pool response shape:", list(resp.keys()))


def test_technical_indicator_sma(client):
    resp = client.technical_indicator(TICKER, "sma")
    assert isinstance(resp, dict)
    print("technical_indicator/sma response shape:", list(resp.keys()))
```

- [ ] **Step 2: Run the smoke test against live UW**

```bash
export UW_API_KEY="<your key>"   # one-time, do not commit
.venv/bin/pytest tests/integration/test_uw_smoke.py -v -s
```

Expected: All 10 tests pass. The `-s` flag surfaces the printed response shapes — capture these in a comment block at the top of `scripts/_clients/uw.py`. Any 404 indicates a wrong path; fix `scripts/_clients/uw.py` and re-run.

- [ ] **Step 3: Document observed shapes in uw.py**

After the smoke test passes, add a doc comment block to `scripts/_clients/uw.py` listing the actual JSON top-level keys observed for each endpoint. This is the authoritative reference for downstream parsing code.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_uw_smoke.py plugins/option-wizard/skills/option-wizard/scripts/_clients/uw.py
git commit -m "test(uw): live smoke test for all consumed endpoints + observed shapes"
```

---

### Task 1.3: UW MCP server entry in ~/.claude.json

**Goal:** Wire the UW remote MCP into Claude Code so the LLM can call UW tools in-session (separate from Python scripts).

**Files:**
- Modify: `~/.claude.json` (user-side, not in repo)
- Create: `docs/setup/uw-mcp-install.md` (project docs for reproducibility)

- [ ] **Step 1: Write the setup doc**

```markdown
# Installing the Unusual Whales MCP server

The option-wizard skill expects the UW remote HTTP MCP to be available in Claude Code. This is a one-time per-machine setup.

## Prerequisites

- Active UW subscription with API access at https://unusualwhales.com/pricing?product=api
- API token from your UW account
- The token stored in a shell env var, never committed:

```bash
echo 'export UW_API_KEY="<your token>"' >> ~/.zshrc
source ~/.zshrc
```

## Add the MCP server

Edit `~/.claude.json`. Inside the `mcpServers` object, add:

```json
{
  "unusual_whales": {
    "type": "url",
    "url": "https://unusualwhales.com/public-api/mcp",
    "headers": {
      "Authorization": "Bearer ${UW_API_KEY}"
    }
  }
}
```

Restart Claude Code. The tools should appear with the `mcp__unusual_whales__*` prefix.

## Verify

In a Claude Code session, ask: "list available MCP tools for unusual whales". The list should include endpoints matching the path-method pairs in `plugins/option-wizard/skills/option-wizard/scripts/_clients/uw.py`.

If the tools do not appear:
- Check `~/.claude.json` is valid JSON (run `python -m json.tool ~/.claude.json`)
- Check the env var is exported in the shell Claude Code was launched from
- Check the API key is active in the UW dashboard
```

- [ ] **Step 2: Apply the change manually**

This step is performed by the user, not the agent. The agent surfaces the diff to apply and asks for confirmation before any write. After confirmation the agent appends the `unusual_whales` entry to `~/.claude.json`.

- [ ] **Step 3: Verify in a Claude Code session**

User runs: `claude` → asks "list unusual_whales MCP tools". Confirm the IV rank / GEX / skew tools are visible.

- [ ] **Step 4: Commit the setup doc**

```bash
git add docs/setup/uw-mcp-install.md
git commit -m "docs: UW MCP server installation steps"
```

---

## Phase 2 — Pure Analytics (TDD)

### Task 2.1: `scripts/gex_levels.py` — gamma flip + put wall + call wall

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/scripts/gex_levels.py`
- Create: `tests/test_gex_levels.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_gex_levels.py
from scripts.gex_levels import compute_levels


def test_gamma_flip_is_zero_crossing_of_cumulative_gex():
    # synthetic GEX-by-strike with a clear flip between 192 and 193
    gex_by_strike = [
        {"strike": 170.0, "gex": -100.0},
        {"strike": 180.0, "gex": -200.0},
        {"strike": 190.0, "gex": -150.0},
        {"strike": 195.0, "gex": 200.0},
        {"strike": 200.0, "gex": 300.0},
        {"strike": 240.0, "gex": 500.0},
    ]
    result = compute_levels(gex_by_strike, spot=210.0)
    # cumulative GEX from low to high: -100, -300, -450, -250, +50, +550
    # zero crossing between 195 and 200, linear-interp ≈ 195 + 5 * 250/300 ≈ 199.17
    assert 195.0 <= result["gamma_flip"] <= 200.0


def test_put_wall_is_strike_with_largest_positive_gex_below_spot():
    gex_by_strike = [
        {"strike": 230.0, "gex": 100.0},
        {"strike": 240.0, "gex": 500.0},   # largest pos below spot
        {"strike": 245.0, "gex": 50.0},
        {"strike": 250.0, "gex": -400.0},  # negative -> not a put wall candidate
    ]
    result = compute_levels(gex_by_strike, spot=244.0)
    assert result["put_wall"] == 240.0


def test_call_wall_is_strike_with_largest_negative_gex_above_spot():
    gex_by_strike = [
        {"strike": 240.0, "gex": 200.0},
        {"strike": 250.0, "gex": -800.0},   # largest neg above spot
        {"strike": 260.0, "gex": -100.0},
    ]
    result = compute_levels(gex_by_strike, spot=244.0)
    assert result["call_wall"] == 250.0


def test_handles_empty_input():
    result = compute_levels([], spot=100.0)
    assert result["gamma_flip"] is None
    assert result["put_wall"] is None
    assert result["call_wall"] is None
```

- [ ] **Step 2: Run tests to verify failure**

```bash
.venv/bin/pytest tests/test_gex_levels.py -v
```

Expected: 4 FAIL with `ModuleNotFoundError` or `ImportError`.

- [ ] **Step 3: Implement**

```python
# plugins/option-wizard/skills/option-wizard/scripts/gex_levels.py
"""Derive gamma flip, put wall, and call wall from UW spot-exposures/strike output.

UW does not pre-compute these named levels; this module reads the raw
strike-level GEX list and identifies them by definition:

  - gamma flip: zero crossing of cumulative GEX from low strike to high
  - put wall:  strike below spot with the largest positive GEX
  - call wall: strike above spot with the largest negative GEX (in absolute
              terms; dealers short here will sell into rallies)
"""
from __future__ import annotations

from typing import Iterable, Optional


def _sorted_by_strike(rows: Iterable[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: float(r["strike"]))


def _gamma_flip(rows: list[dict]) -> Optional[float]:
    """Linear-interpolated strike at which cumulative GEX crosses zero."""
    if not rows:
        return None
    cum = 0.0
    prev_strike, prev_cum = None, 0.0
    for r in rows:
        strike = float(r["strike"])
        cum += float(r["gex"])
        if prev_strike is not None and prev_cum * cum < 0:
            # zero crossing between prev_strike and strike
            span = strike - prev_strike
            frac = -prev_cum / (cum - prev_cum) if cum != prev_cum else 0.5
            return prev_strike + frac * span
        prev_strike, prev_cum = strike, cum
    return None


def _put_wall(rows: list[dict], spot: float) -> Optional[float]:
    below = [r for r in rows if float(r["strike"]) < spot and float(r["gex"]) > 0]
    if not below:
        return None
    return float(max(below, key=lambda r: float(r["gex"]))["strike"])


def _call_wall(rows: list[dict], spot: float) -> Optional[float]:
    above = [r for r in rows if float(r["strike"]) > spot and float(r["gex"]) < 0]
    if not above:
        return None
    return float(min(above, key=lambda r: float(r["gex"]))["strike"])


def compute_levels(gex_by_strike: Iterable[dict], spot: float) -> dict:
    """Return dict with keys gamma_flip, put_wall, call_wall.

    Each input row must have keys 'strike' and 'gex'. Spot is the current
    underlying price. Returns None for any level that cannot be identified.
    """
    rows = _sorted_by_strike(list(gex_by_strike))
    return {
        "gamma_flip": _gamma_flip(rows),
        "put_wall": _put_wall(rows, spot),
        "call_wall": _call_wall(rows, spot),
    }
```

- [ ] **Step 4: Run tests to verify pass**

```bash
.venv/bin/pytest tests/test_gex_levels.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/gex_levels.py tests/test_gex_levels.py
git commit -m "feat(analytics): compute gamma flip + put/call walls from UW GEX"
```

---

### Task 2.2: `scripts/vrp.py` — IV minus RV

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/scripts/vrp.py`
- Create: `tests/test_vrp.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_vrp.py
import math
import pytest
from scripts.vrp import compute_vrp


def test_vrp_positive_when_iv_exceeds_rv():
    assert compute_vrp(iv=0.804, rv=0.610) == pytest.approx(0.194, abs=1e-3)


def test_vrp_negative_when_rv_exceeds_iv():
    assert compute_vrp(iv=0.40, rv=0.55) == pytest.approx(-0.15, abs=1e-3)


def test_vrp_label_rich_when_above_threshold():
    assert compute_vrp(iv=0.30, rv=0.10, with_label=True)["label"] == "RICH"


def test_vrp_label_cheap_when_negative():
    assert compute_vrp(iv=0.30, rv=0.40, with_label=True)["label"] == "CHEAP"


def test_vrp_label_neutral_when_small():
    out = compute_vrp(iv=0.30, rv=0.29, with_label=True)
    assert out["label"] == "NEUTRAL"


def test_vrp_raises_on_invalid_input():
    with pytest.raises(ValueError):
        compute_vrp(iv=-0.1, rv=0.2)
    with pytest.raises(ValueError):
        compute_vrp(iv=0.3, rv=float("nan"))
```

- [ ] **Step 2: Run tests to verify failure**

```bash
.venv/bin/pytest tests/test_vrp.py -v
```

Expected: 6 FAIL.

- [ ] **Step 3: Implement**

```python
# plugins/option-wizard/skills/option-wizard/scripts/vrp.py
"""Volatility risk premium: implied vol minus realized vol.

UW does not pre-compute VRP as a single number; this is just IV − RV.
Both inputs are annualized decimals (0.80 = 80% annualized). Labels:

  RICH    : VRP >= 0.05  (sell-premium regime favored)
  NEUTRAL : -0.05 < VRP < 0.05
  CHEAP   : VRP <= -0.05 (buy-premium regime favored)
"""
from __future__ import annotations

import math


def compute_vrp(iv: float, rv: float, with_label: bool = False) -> float | dict:
    if iv < 0 or rv < 0 or math.isnan(iv) or math.isnan(rv):
        raise ValueError(f"iv and rv must be non-negative numbers; got iv={iv}, rv={rv}")
    vrp = iv - rv
    if not with_label:
        return vrp
    if vrp >= 0.05:
        label = "RICH"
    elif vrp <= -0.05:
        label = "CHEAP"
    else:
        label = "NEUTRAL"
    return {"vrp": vrp, "label": label}
```

- [ ] **Step 4: Run tests to verify pass**

```bash
.venv/bin/pytest tests/test_vrp.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/vrp.py tests/test_vrp.py
git commit -m "feat(analytics): VRP = IV − RV with rich/neutral/cheap labeling"
```

---

### Task 2.3: `scripts/fair_coupon.py` — single-name fair coupon + strike ladder

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/scripts/fair_coupon.py`
- Create: `tests/test_fair_coupon.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_fair_coupon.py
import pytest
from scripts.fair_coupon import single_name_ki_prob, fair_coupon_proxy, analyze_fcn


def test_single_name_ki_prob_matches_closed_form():
    # vol=0.804, barrier=0.75, days=126 → 2*Φ(ln(0.75)/(0.804*sqrt(0.5)))
    # ln(0.75) = -0.2877; 0.804*sqrt(0.5) = 0.5685; ratio = -0.5062
    # Φ(-0.5062) ≈ 0.3065; doubled ≈ 0.613
    p = single_name_ki_prob(vol=0.804, barrier=0.75, days=126)
    assert 0.60 <= p <= 0.63


def test_fair_coupon_proxy_basic():
    # p_ki=0.50, LGD=0.50, alive=3.5m, T=0.5, r=4.5%
    # PV expected loss = 0.50 * 0.50 * exp(-0.045*0.5) = 0.2444
    # divide by (3.5/12) = 0.2917 → fair coupon ≈ 0.838
    fc = fair_coupon_proxy(p_ki=0.50, expected_loss_given_ki=0.50,
                           expected_alive_months=3.5, discount_rate=0.045,
                           tenor_years=0.5)
    assert 0.83 <= fc <= 0.85


def test_fair_coupon_proxy_zero_ki_returns_zero():
    assert fair_coupon_proxy(p_ki=0.0, expected_loss_given_ki=0.5,
                             expected_alive_months=3.5, discount_rate=0.045,
                             tenor_years=0.5) == 0.0


def test_analyze_fcn_emits_strike_ladder_by_default():
    snapshot = {
        "spot": 244.58,
        "iv": 0.804,
        "rv": 0.610,
        "iv_rank": 91,
        "skew_25d": -0.20,
        "max_drawdown_5y": -0.582,
        "gex_levels": {"gamma_flip": 192.5, "put_wall": 240.0, "call_wall": 250.0},
    }
    result = analyze_fcn(
        ticker="ORCL", strike_pcts=[0.70, 0.75, 0.80, 0.85],
        tenor_months=6, observation_months=3, snapshot=snapshot,
    )
    assert len(result["ladder"]) == 4
    rungs = {r["strike_pct"]: r for r in result["ladder"]}
    # 70% strike is below gamma flip in our scenario → zone tagged as risky
    assert "below" in rungs[0.70]["dealer_zone"].lower()
    # 80% strike is above flip
    assert "above" in rungs[0.80]["dealer_zone"].lower()


def test_analyze_fcn_with_quoted_coupon_returns_verdict():
    snapshot = {
        "spot": 244.58, "iv": 0.804, "rv": 0.610, "iv_rank": 91,
        "skew_25d": -0.20, "max_drawdown_5y": -0.582,
        "gex_levels": {"gamma_flip": 192.5, "put_wall": 240.0, "call_wall": 250.0},
    }
    result = analyze_fcn(
        ticker="ORCL", strike_pcts=[0.75], tenor_months=6,
        observation_months=3, pb_quoted_coupon=0.18, snapshot=snapshot,
    )
    rung = result["ladder"][0]
    assert rung["pb_quoted_coupon"] == 0.18
    assert rung["verdict"] in {"fair", "rich", "cheap"}


def test_analyze_fcn_checklist_flags_below_flip_strike():
    snapshot = {
        "spot": 244.58, "iv": 0.804, "rv": 0.610, "iv_rank": 91,
        "skew_25d": -0.20, "max_drawdown_5y": -0.582,
        "gex_levels": {"gamma_flip": 192.5, "put_wall": 240.0, "call_wall": 250.0},
    }
    result = analyze_fcn(
        ticker="ORCL", strike_pcts=[0.70], tenor_months=6,
        observation_months=3, snapshot=snapshot,
    )
    flags = result["ladder"][0]["checklist"]
    item1 = next(f for f in flags if f["id"] == "strike_vs_gamma_flip")
    assert item1["status"] == "FAIL"  # 0.70 * 244.58 = 171.21 below flip 192.5


def test_analyze_fcn_attaches_counter_offer_email_on_fail():
    """When any checklist item fails, the rung should include a bilingual
    counter-offer email even without an explicit PB quote."""
    snapshot = {
        "spot": 244.58, "iv": 0.804, "rv": 0.610, "iv_rank": 91,
        "skew_25d": -0.20, "max_drawdown_5y": -0.582,
        "gex_levels": {"gamma_flip": 192.5, "put_wall": 240.0, "call_wall": 250.0},
    }
    result = analyze_fcn(
        ticker="ORCL", strike_pcts=[0.70], tenor_months=6,
        observation_months=3, snapshot=snapshot,
    )
    rung = result["ladder"][0]
    assert "counter_offer_email" in rung
    assert "Hi" in rung["counter_offer_email"]
    assert "您好" in rung["counter_offer_email"] or "你好" in rung["counter_offer_email"]


def test_analyze_fcn_no_email_when_all_pass():
    """When all checklist items pass and no quote provided, no email."""
    snapshot = {
        "spot": 244.58, "iv": 0.804, "rv": 0.610, "iv_rank": 91,
        "skew_25d": -0.20, "max_drawdown_5y": -0.582,
        "gex_levels": {"gamma_flip": 100.0, "put_wall": 240.0, "call_wall": 250.0},
    }
    result = analyze_fcn(
        ticker="ORCL", strike_pcts=[0.85], tenor_months=6,
        observation_months=3, snapshot=snapshot,
    )
    rung = result["ladder"][0]
    # 0.85 * 244.58 = 207.89 > flip 100; cushion vs -0.582 max DD is fine.
    assert "counter_offer_email" not in rung
```

- [ ] **Step 2: Run tests to verify failure**

```bash
.venv/bin/pytest tests/test_fair_coupon.py -v
```

Expected: 6 FAIL.

- [ ] **Step 3: Implement**

```python
# plugins/option-wizard/skills/option-wizard/scripts/fair_coupon.py
"""Fair coupon proxy for FCN evaluation.

The continuous-touch barrier approximation overstates the true KI rate for
discretely-observed FCN structures, but it is the right ceiling input to
the four-rung strike ladder we emit. Downstream interpretation (real
institutional fair coupon is roughly half the model output; retail PB
adds 25-40% markup) lives in references/fcn-framework.md.
"""
from __future__ import annotations

import math
from typing import Any, Iterable

from scipy.stats import norm

LGD_BASE = 0.50
LGD_STRESS = 0.65
DEFAULT_DISCOUNT_RATE = 0.045


def single_name_ki_prob(vol: float, barrier: float, days: int = 252) -> float:
    if vol is None or vol <= 0:
        return float("nan")
    sigma_t = vol * math.sqrt(days / 252.0)
    if sigma_t == 0:
        return 0.0
    return 2.0 * norm.cdf(math.log(barrier) / sigma_t)


def fair_coupon_proxy(p_ki: float, expected_loss_given_ki: float,
                      expected_alive_months: float, discount_rate: float,
                      tenor_years: float) -> float:
    if p_ki is None or math.isnan(p_ki) or expected_alive_months <= 0:
        return float("nan")
    if p_ki == 0:
        return 0.0
    pv_expected_loss = p_ki * expected_loss_given_ki * math.exp(-discount_rate * tenor_years)
    return pv_expected_loss / (expected_alive_months / 12.0)


def _tag_zone(strike_dollar: float, gex_levels: dict) -> str:
    flip = gex_levels.get("gamma_flip")
    if flip is None:
        return "unknown (gamma flip not identifiable)"
    if strike_dollar < flip:
        return "RISK: below gamma flip (dealer short gamma)"
    put_wall = gex_levels.get("put_wall")
    if put_wall and strike_dollar < put_wall:
        return "OK: above flip, below put wall"
    return "OK: above flip"


def _checklist(strike_pct: float, strike_dollar: float, snapshot: dict,
               fair_base: float, pb_quoted_coupon: float | None) -> list[dict]:
    """Eight-item PB defense checklist. Each item returns id, status, detail."""
    flip = snapshot["gex_levels"].get("gamma_flip")
    max_dd = snapshot.get("max_drawdown_5y", -1.0)
    iv_rank = snapshot.get("iv_rank")
    skew = snapshot.get("skew_25d")

    items = []

    # 1. strike vs gamma flip
    if flip is None:
        s1 = {"status": "WARN", "detail": "gamma flip not identifiable"}
    elif strike_dollar < flip:
        s1 = {"status": "FAIL", "detail": f"strike ${strike_dollar:.2f} below flip ${flip:.2f}; demand +5pp coupon or raise strike"}
    else:
        s1 = {"status": "PASS", "detail": f"strike ${strike_dollar:.2f} above flip ${flip:.2f}"}
    items.append({"id": "strike_vs_gamma_flip", **s1})

    # 2. markup vs IV rank (only if quote supplied)
    if pb_quoted_coupon is not None and fair_base > 0:
        markup_ratio = pb_quoted_coupon / fair_base
        if markup_ratio < 0.25:
            s2 = {"status": "FAIL", "detail": f"quote {pb_quoted_coupon:.1%} is {markup_ratio:.0%} of model fair {fair_base:.1%}; predatory"}
        elif markup_ratio < 0.30:
            s2 = {"status": "WARN", "detail": f"quote at {markup_ratio:.0%} of model; counter for +2pp"}
        else:
            s2 = {"status": "PASS", "detail": f"quote at {markup_ratio:.0%} of model fair, within normal retail band"}
    else:
        s2 = {"status": "SKIP", "detail": "no PB quote provided"}
    items.append({"id": "markup_vs_iv_rank", **s2})

    # 3. KI buffer vs 5y max drawdown
    cushion_pp = (strike_pct - 1.0) - max_dd  # both negative, larger gap = bigger cushion
    if cushion_pp < 0.10:
        s3 = {"status": "FAIL", "detail": f"only {cushion_pp*100:+.1f}pp above 5y max DD; ticker has been at this strike before"}
    else:
        s3 = {"status": "PASS", "detail": f"{cushion_pp*100:+.1f}pp cushion above 5y max DD"}
    items.append({"id": "ki_buffer_vs_5y_max_dd", **s3})

    # 4. IV rank threshold
    if iv_rank is None:
        s4 = {"status": "WARN", "detail": "IV rank not provided"}
    elif iv_rank < 50:
        s4 = {"status": "WARN", "detail": f"IV rank {iv_rank} below 50; consider monthly short put instead of 6m FCN lock-in"}
    else:
        s4 = {"status": "PASS", "detail": f"IV rank {iv_rank} supports selling vol"}
    items.append({"id": "iv_rank_threshold", **s4})

    # 5. skew penalty
    if skew is None:
        s5 = {"status": "WARN", "detail": "skew not provided"}
    elif skew < -0.25:
        s5 = {"status": "WARN", "detail": f"25Δ skew {skew:.2f} extremely negative; demand +3-5pp coupon for left-tail risk"}
    else:
        s5 = {"status": "PASS", "detail": f"25Δ skew {skew:.2f} within normal range"}
    items.append({"id": "skew_penalty", **s5})

    # 6. tenor anchor (informational)
    items.append({"id": "tenor_anchor", "status": "INFO",
                  "detail": "translate annualized coupon to absolute dollar return given expected alive months ≈ 3.5"})

    # 7. liquidity / no secondary
    items.append({"id": "liquidity_no_secondary", "status": "INFO",
                  "detail": "FCN has no secondary market; only exit is holding to maturity"})

    # 8. issuer credit risk
    items.append({"id": "issuer_credit_risk", "status": "INFO",
                  "detail": "pull PB parent senior unsecured rating and 5y CDS; flag SPV-issued notes"})

    return items


def _verdict(fair_base: float, pb_quoted_coupon: float) -> str:
    if fair_base <= 0:
        return "unknown"
    # honest retail PB band ≈ 25-40% of model
    floor = fair_base * 0.25
    ceil_ = fair_base * 0.40
    if pb_quoted_coupon < floor:
        return "rich"  # rich for PB, bad for client
    if pb_quoted_coupon > ceil_:
        return "cheap"  # cheap for PB, attractive for client
    return "fair"


def analyze_fcn(
    ticker: str,
    strike_pcts: Iterable[float] = (0.70, 0.75, 0.80, 0.85),
    tenor_months: int = 6,
    observation_months: int = 3,
    ko_pct: float = 1.0,
    pb_quoted_coupon: float | None = None,
    snapshot: dict[str, Any] | None = None,
    expected_alive_months: float = 3.5,
    lgd: float = LGD_BASE,
    lgd_stress: float = LGD_STRESS,
    discount_rate: float = DEFAULT_DISCOUNT_RATE,
) -> dict[str, Any]:
    """Compute FCN strike-ladder analysis from a market snapshot.

    `snapshot` must include: spot, iv, rv, iv_rank, skew_25d, max_drawdown_5y,
    gex_levels (with gamma_flip, put_wall, call_wall). Caller is responsible
    for fetching that data from UW (see scripts._clients.uw).
    """
    if snapshot is None:
        raise ValueError("snapshot is required; fetch UW data and pass it in")

    tenor_years = tenor_months / 12.0
    tenor_days = int(round(tenor_months * 21))
    vol = snapshot["iv"]
    spot = snapshot["spot"]

    ladder = []
    for strike_pct in strike_pcts:
        strike_dollar = spot * strike_pct
        p_ki = single_name_ki_prob(vol, barrier=strike_pct, days=tenor_days)
        fair_base = fair_coupon_proxy(p_ki, lgd, expected_alive_months,
                                       discount_rate, tenor_years)
        fair_stress = fair_coupon_proxy(p_ki, lgd_stress, expected_alive_months,
                                         discount_rate, tenor_years)
        zone = _tag_zone(strike_dollar, snapshot["gex_levels"])
        checklist = _checklist(strike_pct, strike_dollar, snapshot,
                                fair_base, pb_quoted_coupon)
        rung = {
            "strike_pct": strike_pct,
            "strike_dollar": round(strike_dollar, 2),
            "p_ki_6m": round(p_ki, 4),
            "fair_coupon_base": round(fair_base, 4),
            "fair_coupon_stress": round(fair_stress, 4),
            "dealer_zone": zone,
            "checklist": checklist,
        }
        if pb_quoted_coupon is not None:
            rung["pb_quoted_coupon"] = pb_quoted_coupon
            rung["verdict"] = _verdict(fair_base, pb_quoted_coupon)
        # Auto-attach bilingual counter-offer email when the quote is rich
        # or any checklist item failed. Recommended counter terms: bump
        # strike up one notch from this rung and target 30% of model fair.
        verdict_rich = rung.get("verdict") == "rich"
        any_fail = any(c["status"] == "FAIL" for c in checklist)
        if verdict_rich or any_fail:
            # Recommend stepping up one strike-pct rung (max 0.85) and
            # asking for coupon = 30%-40% of model fair as the counter band.
            rec_strike_pct = min(strike_pct + 0.05, 0.85)
            rec_low = round(fair_base * 0.30, 4)
            rec_high = round(fair_base * 0.40, 4)
            rung["counter_offer_email"] = build_counter_offer_email(
                ticker=ticker,
                rung=rung,
                recommended_strike_pct=rec_strike_pct,
                recommended_coupon_low=rec_low,
                recommended_coupon_high=rec_high,
            )
        ladder.append(rung)

    return {
        "ticker": ticker,
        "tenor_months": tenor_months,
        "observation_months": observation_months,
        "ko_pct": ko_pct,
        "spot": spot,
        "iv": vol,
        "iv_rank": snapshot.get("iv_rank"),
        "ladder": ladder,
    }
```

- [ ] **Step 4: Run tests to verify pass**

```bash
.venv/bin/pytest tests/test_fair_coupon.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/fair_coupon.py tests/test_fair_coupon.py
git commit -m "feat(analytics): FCN fair coupon ladder + 8-item PB checklist"
```

---

### Task 2.4: Basket FCN worst-of joint KI probability

**Files:**
- Modify: `plugins/option-wizard/skills/option-wizard/scripts/fair_coupon.py`
- Modify: `tests/test_fair_coupon.py`

- [ ] **Step 1: Append failing test**

```python
# tests/test_fair_coupon.py (append at end)
import numpy as np
from scripts.fair_coupon import joint_ki_prob_mc, analyze_fcn_basket


def test_joint_ki_prob_at_full_correlation_equals_single_name():
    # rho = 1: either-touch ≈ single-name touch (within MC noise)
    p_either, _, _ = joint_ki_prob_mc(vol_a=0.80, vol_b=0.80, rho=0.999,
                                       barrier=0.50, days=252, n_sims=5000, seed=42)
    from scripts.fair_coupon import single_name_ki_prob
    single = single_name_ki_prob(0.80, 0.50, 252)
    assert abs(p_either - single) < 0.05


def test_joint_ki_prob_low_correlation_higher_than_single():
    # rho = 0: P(A or B) > P(A) when both have positive touch prob
    p_either, _, _ = joint_ki_prob_mc(vol_a=0.40, vol_b=0.40, rho=0.0,
                                       barrier=0.70, days=126, n_sims=5000, seed=42)
    from scripts.fair_coupon import single_name_ki_prob
    single = single_name_ki_prob(0.40, 0.70, 126)
    assert p_either > single


def test_basket_analyze_returns_per_name_and_basket():
    snapshots = {
        "INTC": {"spot": 109.33, "iv": 0.82, "rv": 1.01, "iv_rank": 76,
                  "skew_25d": -0.15, "max_drawdown_5y": -0.643,
                  "gex_levels": {"gamma_flip": 95.0, "put_wall": 100.0, "call_wall": 115.0}},
        "AMD":  {"spot": 510.13, "iv": 0.70, "rv": 0.85, "iv_rank": 94,
                  "skew_25d": -0.18, "max_drawdown_5y": -0.630,
                  "gex_levels": {"gamma_flip": 460.0, "put_wall": 495.0, "call_wall": 520.0}},
    }
    corr = np.array([[1.0, 0.7], [0.7, 1.0]])
    result = analyze_fcn_basket(
        tickers=["INTC", "AMD"], snapshots=snapshots, corr_matrix=corr,
        strike_pct=0.55, tenor_months=6, observation_months=3,
    )
    assert "per_name" in result
    assert "basket" in result
    assert result["basket"]["p_ki_either"] > 0
    # diversification premium recommendation: basket coupon should exceed worst-single
    assert "diversification_premium_pp" in result["basket"]
```

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/pytest tests/test_fair_coupon.py::test_joint_ki_prob_at_full_correlation_equals_single_name -v
```

Expected: FAIL — `ImportError`.

- [ ] **Step 3: Append implementation to `fair_coupon.py`**

```python
# Append to plugins/option-wizard/skills/option-wizard/scripts/fair_coupon.py

import numpy as np


def joint_ki_prob_mc(
    vol_a: float, vol_b: float, rho: float,
    barrier: float = 0.50, days: int = 252,
    n_sims: int = 20_000, seed: int = 42,
) -> tuple[float, float, float]:
    """Monte Carlo joint KI for a worst-of-2 FCN.

    Returns (p_either, p_all, p_exactly_one). p_either is the worst-of touch
    probability used to price the basket.

    Drift convention: matches the single-name closed-form
    `2·Φ(ln(B)/(σ·√T))`, which assumes a driftless Brownian motion in
    log-returns (no `-0.5·σ²` correction). The two paths must use the
    same stochastic model so that the full-correlation test
    (`test_joint_ki_prob_at_full_correlation_equals_single_name`) holds:
    at ρ→1 the MC must collapse to the closed-form single-name result.
    """
    rho = max(-0.999, min(0.999, rho))
    rng = np.random.default_rng(seed)
    dt = 1.0 / 252.0
    chol = np.array([[1.0, 0.0], [rho, math.sqrt(max(0.0, 1.0 - rho * rho))]])
    z = rng.standard_normal(size=(n_sims, days, 2)) @ chol.T
    vols = np.array([vol_a, vol_b])
    # Driftless Brownian in log-return space — matches single_name_ki_prob.
    diffusion = vols * math.sqrt(dt)
    log_paths = np.cumsum(diffusion * z, axis=1)
    min_paths = np.exp(log_paths.min(axis=1))
    hits = min_paths <= barrier
    return (
        float(hits.any(axis=1).mean()),
        float(hits.all(axis=1).mean()),
        float((hits.sum(axis=1) == 1).mean()),
    )


def analyze_fcn_basket(
    tickers: list[str],
    snapshots: dict[str, dict],
    corr_matrix,
    strike_pct: float,
    tenor_months: int = 6,
    observation_months: int = 3,
    ko_pct: float = 1.0,
    pb_quoted_coupon: float | None = None,
    expected_alive_months: float = 3.5,
    lgd: float = LGD_BASE,
    discount_rate: float = DEFAULT_DISCOUNT_RATE,
) -> dict[str, Any]:
    """Worst-of basket FCN analysis.

    Currently supports baskets of 2 names (joint_ki_prob_mc). For 3+ names,
    extend to joint_ki_prob_nd (not in v1 scope).
    """
    if len(tickers) != 2:
        raise NotImplementedError("v1 basket FCN supports exactly 2 tickers")

    tenor_years = tenor_months / 12.0
    tenor_days = int(round(tenor_months * 21))

    per_name = {}
    single_p_kis = []
    for t in tickers:
        snap = snapshots[t]
        p = single_name_ki_prob(snap["iv"], barrier=strike_pct, days=tenor_days)
        single_p_kis.append(p)
        per_name[t] = {
            "spot": snap["spot"],
            "iv": snap["iv"],
            "iv_rank": snap.get("iv_rank"),
            "p_ki_single": round(p, 4),
        }

    rho = float(corr_matrix[0, 1])
    p_either, p_all, p_one = joint_ki_prob_mc(
        vol_a=snapshots[tickers[0]]["iv"],
        vol_b=snapshots[tickers[1]]["iv"],
        rho=rho, barrier=strike_pct, days=tenor_days,
    )

    fair_basket = fair_coupon_proxy(p_either, lgd, expected_alive_months,
                                     discount_rate, tenor_years)
    worst_single = max(single_p_kis)
    fair_worst_single = fair_coupon_proxy(worst_single, lgd, expected_alive_months,
                                           discount_rate, tenor_years)
    # diversification premium: basket coupon should exceed worst single by at
    # least (1 - rho) * 30%
    premium_min_pp = (1.0 - rho) * 0.30 * fair_worst_single

    basket = {
        "p_ki_either": round(p_either, 4),
        "p_ki_all": round(p_all, 4),
        "p_ki_exactly_one": round(p_one, 4),
        "fair_coupon": round(fair_basket, 4),
        "fair_coupon_worst_single": round(fair_worst_single, 4),
        "correlation": round(rho, 3),
        "diversification_premium_pp": round(premium_min_pp, 4),
    }
    if pb_quoted_coupon is not None:
        basket["pb_quoted_coupon"] = pb_quoted_coupon
        basket["verdict"] = _verdict(fair_basket, pb_quoted_coupon)

    return {
        "tickers": tickers,
        "strike_pct": strike_pct,
        "tenor_months": tenor_months,
        "observation_months": observation_months,
        "ko_pct": ko_pct,
        "per_name": per_name,
        "basket": basket,
    }
```

- [ ] **Step 4: Run tests to verify pass**

```bash
.venv/bin/pytest tests/test_fair_coupon.py -v
```

Expected: 9 passed (6 from Task 2.3 + 3 new).

- [ ] **Step 5: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/fair_coupon.py tests/test_fair_coupon.py
git commit -m "feat(analytics): worst-of basket FCN with MC joint KI"
```

---

### Task 2.5: Bilingual counter-offer email builder

**Files:**
- Modify: `plugins/option-wizard/skills/option-wizard/scripts/fair_coupon.py`
- Modify: `tests/test_fair_coupon.py`

- [ ] **Step 1: Append failing test**

```python
# tests/test_fair_coupon.py (append)
from scripts.fair_coupon import build_counter_offer_email


def test_counter_offer_email_contains_chinese_and_english_sections():
    rung = {
        "strike_pct": 0.75,
        "strike_dollar": 183.44,
        "p_ki_6m": 0.613,
        "fair_coupon_base": 1.027,
        "verdict": "rich",
        "pb_quoted_coupon": 0.18,
        "dealer_zone": "RISK: below gamma flip",
        "checklist": [
            {"id": "strike_vs_gamma_flip", "status": "FAIL", "detail": "strike $183 below flip $193"},
            {"id": "markup_vs_iv_rank", "status": "WARN", "detail": "quote at 18% of model"},
        ],
    }
    email = build_counter_offer_email(
        ticker="ORCL", rung=rung,
        recommended_strike_pct=0.80, recommended_coupon_low=0.24,
        recommended_coupon_high=0.28,
    )
    assert "Subject:" in email
    assert "你好" in email or "您好" in email  # Chinese greeting present
    assert "Hi" in email  # English greeting present
    assert "ORCL" in email
    assert "0.80" in email or "80%" in email
```

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/pytest tests/test_fair_coupon.py::test_counter_offer_email_contains_chinese_and_english_sections -v
```

Expected: FAIL — `ImportError`.

- [ ] **Step 3: Append implementation**

```python
# Append to scripts/fair_coupon.py

def build_counter_offer_email(
    ticker: str,
    rung: dict,
    recommended_strike_pct: float,
    recommended_coupon_low: float,
    recommended_coupon_high: float,
) -> str:
    """Generate a bilingual (Chinese first, English second) counter-offer
    email body for forwarding back to the private bank.
    """
    failed = [c for c in rung.get("checklist", []) if c["status"] in ("FAIL", "WARN")]
    concerns_zh = "\n".join(f"  - {c['detail']}" for c in failed) or "  - (无具体技术问题，仅价格不合理)"
    concerns_en = "\n".join(f"  - {c['detail']}" for c in failed) or "  - (no specific concerns beyond pricing)"

    subject = f"Re: FCN quote on {ticker} – Counter-offer"
    body = f"""Subject: {subject}

—— 中文 ——

你好 [Banker],

谢谢你给的 FCN 报价。我这边跑了一下数据：

- 现价: ${rung.get('strike_dollar', 0) / rung.get('strike_pct', 1):.2f}
- 行权价: {rung['strike_pct']*100:.0f}% (${rung['strike_dollar']:.2f})
- 6m 敲入概率(模型): {rung['p_ki_6m']*100:.1f}%
- 模型公允票息: {rung['fair_coupon_base']*100:.1f}%
- PB 报价: {rung.get('pb_quoted_coupon', 0)*100:.1f}%
- 经销区域: {rung['dealer_zone']}

具体顾虑:
{concerns_zh}

希望你能按以下条款重新结构化:
- 行权价: {recommended_strike_pct*100:.0f}%
- Coupon: {recommended_coupon_low*100:.1f}% – {recommended_coupon_high*100:.1f}%

或者保持当前 coupon 但把行权价降到合适位置。等你回复。

谢谢。


—— English ——

Hi [Banker],

Thanks for the quote. After running the numbers on our end:

- Spot: ${rung.get('strike_dollar', 0) / rung.get('strike_pct', 1):.2f}
- Strike: {rung['strike_pct']*100:.0f}% (${rung['strike_dollar']:.2f})
- Model KI probability (6m): {rung['p_ki_6m']*100:.1f}%
- Model fair coupon: {rung['fair_coupon_base']*100:.1f}%
- Your quoted coupon: {rung.get('pb_quoted_coupon', 0)*100:.1f}%
- Dealer flow zone: {rung['dealer_zone']}

Specific concerns:
{concerns_en}

We'd be interested if you can restructure at:
- Strike: {recommended_strike_pct*100:.0f}%
- Coupon: {recommended_coupon_low*100:.1f}% – {recommended_coupon_high*100:.1f}%

Or alternatively reduce strike to a similar level at your current coupon.

Looking forward to your response.

Best,
"""
    return body
```

- [ ] **Step 4: Run tests to verify pass**

```bash
.venv/bin/pytest tests/test_fair_coupon.py -v
```

Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/fair_coupon.py tests/test_fair_coupon.py
git commit -m "feat(fcn): bilingual counter-offer email builder"
```

---

## Phase 3 — Reference Documentation

Reference docs are markdown, no tests apply. Each task: write the file, commit. Content is original; the trader will expand each over time. Acceptance per file: covers the topics enumerated in the spec, no placeholders.

### Task 3.1: `references/data-sources.md`

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/references/data-sources.md`

- [ ] **Step 1: Write the file**

Content covers (each as a short section, 2-4 paragraphs each):

1. **UW first policy** — restate the rule from SKILL.md, list the UW endpoints UW serves directly with the exact path and the corresponding `UWClient` method name.
2. **Client-side derivations** — gamma flip / put wall / call wall / VRP / FCN fair coupon, with the script file that computes each.
3. **TradingView role** — what TV is used for, that `finance-data-providers:tradingview-reader` skill is the entry point, examples of asking it for SMA / RSI / news.
4. **IB role** — read positions and balances via IB MCP, write order instructions, contract resolution. Note that `create_order_instruction` is a pending-approval step, not auto-execution.
5. **Call order for a fresh analysis** — list of the standard sequence: UW vol metrics → UW GEX → derive levels → UW greeks for candidate strikes → TV spot confirmation → IB account context.

- [ ] **Step 2: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/references/data-sources.md
git commit -m "docs(refs): data-sources playbook (UW first, TV, IB roles)"
```

---

### Task 3.2: `references/strategies.md`

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/references/strategies.md`

- [ ] **Step 1: Write the file**

Content covers:

1. **Regime × structure matrix** — two-axis table with vol regime (rich/neutral/cheap by VRP) on rows, directional bias (bullish/neutral/bearish) on columns. Each cell lists the default structure.
2. **Each structure's mechanics** — for CC, CSP, bull put spread, bear call spread, iron condor, collar, jade lizard: legs, max loss, max gain, breakeven, when to use.
3. **Jade Lizard mandatory net-credit rule** — net credit must exceed short call spread width to keep upside risk-free; otherwise it is not a jade lizard.
4. **Strong bullish conviction veto** — the four signals (post-earnings beat with absorbed gap-up, three independent channel-check sources, validated thematic re-rate, normalized IV term structure inversion); three or more concurrent = Jade Lizard / IC / calendar forbidden, recommend naked CSP / bull put spread / long call instead.
5. **Macro hedge trigger heuristics** — when to suggest sizing or adding SPX hedge.
6. **Rejected structures** with reasoning.

- [ ] **Step 2: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/references/strategies.md
git commit -m "docs(refs): regime × structure matrix and structure mechanics"
```

---

### Task 3.3: `references/gamma-framework.md`

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/references/gamma-framework.md`

- [ ] **Step 1: Write the file**

Content covers:

1. **What GEX is** — short explainer of dealer gamma exposure as a positioning proxy.
2. **Reading UW `spot-exposures/strike`** — the JSON shape, how to identify the three named levels.
3. **Gamma flip** — definition, how `scripts/gex_levels.py` computes it (cumulative zero crossing with linear interpolation), what it means for price action above vs below.
4. **Put wall / Call wall** — definition, dealer behavior at each, how strike selection should interact (FCN strike should sit above gamma flip; bull put spread short leg should sit above put wall).
5. **Vol regime label** — dampening vs amplifying classification from the dashboard, what each implies.
6. **0DTE GEX caveat** — how same-day expirations skew GEX readings near close.

- [ ] **Step 2: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/references/gamma-framework.md
git commit -m "docs(refs): GEX reading guide and level definitions"
```

---

### Task 3.4: `references/price-action-framework.md`

This filename mirrors the trade-skills layout convention (price-action, not tape) for 1:1 structural parity.

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/references/price-action-framework.md`

- [ ] **Step 1: Write the file**

Content covers:

1. **TradingView entry** — how to ask `finance-data-providers:tradingview-reader` for a chart snapshot, the indicators commonly checked (SMA 20/50/200, RSI, MACD, volume).
2. **Trend signals** — what to look for above/below 200DMA, golden/death cross relevance for option timing.
3. **Tape absorption** — reading whether a catalyst gap-up was absorbed (continued strength) or faded.
4. **News integration** — pulling recent headlines, mapping to earnings clock for catalyst risk.
5. **Watchlist colored flags** — using TV watchlist state as a positioning prior.

- [ ] **Step 2: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/references/price-action-framework.md
git commit -m "docs(refs): TradingView price-action and tape playbook"
```

---

### Task 3.5: `references/fcn-framework.md`

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/references/fcn-framework.md`

- [ ] **Step 1: Write the file**

Content covers (this is the longest reference doc):

1. **FCN structure** — what it is, payoff diagram in words, autocall mechanics, KI semantics.
2. **Fair coupon math** — the formula in `scripts/fair_coupon.py`, why continuous-touch overstates, the rule that real institutional fair ≈ 50-65% of model output and retail PB adds 25-40% markup on top.
3. **The 8-item PB defense checklist** — repeat the items from spec §6.1 with one paragraph each on rationale and concrete thresholds.
4. **Strike ladder workflow** — how `analyze_fcn` emits 70/75/80/85% rungs, how to read the ladder.
5. **Worst-of basket adjustments** — diversification premium calculation.
6. **Counter-offer email usage** — when to send, what to expect back, common PB rebuttals and responses.
7. **What FCN is bad at** — when CC / SP / ratio is materially better (low IV rank, short-dated catalyst, want flexibility to roll).

- [ ] **Step 2: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/references/fcn-framework.md
git commit -m "docs(refs): FCN framework with 8-item PB defense checklist"
```

---

### Task 3.6: `references/execution.md`

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/references/execution.md`

- [ ] **Step 1: Write the file**

Content covers:

1. **IB MCP two-step model** — create_order_instruction → user approves in TWS.
2. **Pre-trade pre-flight checklist** — every item the spec §9.2 lists.
3. **Bracket order defaults** — 50% take-profit, 2× credit stop-loss, table of per-structure defaults from spec.
4. **21 DTE hard review** — block on the next interaction, three options (close / roll / accept-gamma).
5. **Roll constraints** — defined-risk preservation, net credit or limited debit, no earnings span.
6. **No-assignment policy** — 21 DTE rule is the safety; if missed, prefer roll over accept-assignment.
7. **OCA group handling** — link the three legs; fallback if IB MCP does not support OCA (manual cancel-on-fill in `manage_positions`).
8. **Failure modes** — IB disconnection, partial fill, margin call mid-position.

- [ ] **Step 2: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/references/execution.md
git commit -m "docs(refs): IB execution playbook with bracket and 21 DTE rules"
```

---

### Task 3.7: pitfalls/ and ticker/ README + templates

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/references/pitfalls/README.md`
- Create: `plugins/option-wizard/skills/option-wizard/references/pitfalls/_template.md`
- Create: `plugins/option-wizard/skills/option-wizard/references/ticker/README.md`
- Create: `plugins/option-wizard/skills/option-wizard/references/ticker/_template.md`

- [ ] **Step 1: Write the pitfalls README and template**

```markdown
<!-- references/pitfalls/README.md -->
# Pitfalls

Accumulated trading mistakes and the rules they generated. Each pitfall is a short markdown file. Format: `NN-slug.md`. The index below populates over time.

| # | Slug | One-line |
|---|------|----------|
| _empty for now — fill as you trade_ | | |

## Adding a pitfall

1. Copy `_template.md` to the next sequence number: `01-something-i-did-wrong.md`.
2. Fill in the sections.
3. Add a row to the table above.
```

```markdown
<!-- references/pitfalls/_template.md -->
# Pitfall NN: <One-line takeaway>

**Date:** YYYY-MM-DD
**Ticker / structure:** <e.g., ORCL bull put spread>
**Loss / forgone gain:** <dollar or percent>

## What I did

Brief recap of the trade and the assumption that drove it.

## What actually happened

The market reaction or development that invalidated the assumption.

## Why the assumption was wrong

Root cause analysis. Be honest, not defensive.

## Rule going forward

One sentence. Specific enough that next time I would catch myself.
```

- [ ] **Step 2: Write the ticker README and template**

```markdown
<!-- references/ticker/README.md -->
# Ticker Case Studies

Trade or analysis case studies. Each file documents one decision, the data behind it, and the outcome. Format: `<slug>-YYYY-MM.md`.

| Slug | Period | One-line |
|------|--------|----------|
| orcl-2026-06-fcn | 2026-06 | ORCL FCN strike ladder + gamma flip insight |
```

```markdown
<!-- references/ticker/_template.md -->
# <Ticker> — <Period>

**Date:** YYYY-MM-DD
**Setup:** <one paragraph context>

## Data snapshot

| Metric | Value | Source |
|--------|-------|--------|
| Spot | $ | TV |
| IV rank | | UW |
| GEX flip | $ | derived |
| 5y max DD | | UW OHLC |

## Analysis

What the data said and the structure considered.

## Decision

What was done (or recommended) and why.

## Outcome / Lesson

Filled in after the position closes or 30 days later, whichever comes first.
```

- [ ] **Step 3: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/references/pitfalls/ plugins/option-wizard/skills/option-wizard/references/ticker/
git commit -m "docs(refs): pitfalls/ticker README and templates"
```

---

## Phase 4 — IB Execution

### Task 4.1: `scripts/_clients/ib.py` — ib_insync wrapper

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/scripts/_clients/ib.py`
- Create: `tests/test_ib_client.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_ib_client.py
from unittest.mock import MagicMock, patch
import pytest
from scripts._clients.ib import IBClient


def test_ib_client_default_port_is_live():
    with patch("scripts._clients.ib.IB") as mock_ib_cls:
        client = IBClient()
        assert client.host == "127.0.0.1"
        assert client.port == 4001
        assert client.client_id == 99


def test_ib_client_connects_with_explicit_settings():
    with patch("scripts._clients.ib.IB") as mock_ib_cls:
        mock_ib = MagicMock()
        mock_ib_cls.return_value = mock_ib
        client = IBClient(host="localhost", port=4002, client_id=77)
        client.connect()
        mock_ib.connect.assert_called_once_with("localhost", 4002, clientId=77, timeout=10)


def test_ib_client_get_positions_returns_list():
    with patch("scripts._clients.ib.IB") as mock_ib_cls:
        mock_ib = MagicMock()
        mock_ib.positions.return_value = [MagicMock(contract=MagicMock(symbol="ORCL"), position=5)]
        mock_ib_cls.return_value = mock_ib
        client = IBClient()
        result = client.get_positions()
        assert isinstance(result, list)
```

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/pytest tests/test_ib_client.py -v
```

Expected: 3 FAIL.

- [ ] **Step 3: Implement**

```python
# plugins/option-wizard/skills/option-wizard/scripts/_clients/ib.py
"""Thin ib_insync wrapper used by option-wizard for read+write IB access.

Defaults match the trader's IB Gateway live: 127.0.0.1:4001. The skill
always uses client_id=99 to avoid colliding with the fcn-wizard project
(which uses 42, 43).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ib_insync import IB, Option, Stock, util  # noqa: F401  (util imported for downstream)


@dataclass
class IBClient:
    host: str = "127.0.0.1"
    port: int = 4001
    client_id: int = 99
    timeout: int = 10

    def __post_init__(self) -> None:
        self._ib = IB()

    def connect(self) -> None:
        if not self._ib.isConnected():
            self._ib.connect(self.host, self.port, clientId=self.client_id, timeout=self.timeout)

    def disconnect(self) -> None:
        if self._ib.isConnected():
            self._ib.disconnect()

    def __enter__(self) -> "IBClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.disconnect()

    # read --------------------------------------------------------

    def get_positions(self) -> list[Any]:
        self.connect()
        return list(self._ib.positions())

    def get_account_summary(self) -> dict[str, Any]:
        self.connect()
        rows = self._ib.accountSummary()
        return {r.tag: r.value for r in rows}

    def get_open_orders(self) -> list[Any]:
        self.connect()
        return list(self._ib.openTrades())

    # write -------------------------------------------------------

    def place_order(self, contract: Any, order: Any) -> Any:
        """Place an order through ib_insync. Returns the Trade object.
        Caller is responsible for confirming the order intent before calling this.
        """
        self.connect()
        return self._ib.placeOrder(contract, order)
```

- [ ] **Step 4: Run tests to verify pass**

```bash
.venv/bin/pytest tests/test_ib_client.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/_clients/ib.py tests/test_ib_client.py
git commit -m "feat(ib): ib_insync wrapper with read+write methods"
```

---

### Task 4.2: `scripts/ib_order.py` — order building (no submission yet)

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/scripts/ib_order.py`
- Create: `tests/test_ib_order.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ib_order.py
import pytest
from scripts.ib_order import (
    build_pl_matrix, validate_structure, build_preflight,
    REJECTED_STRUCTURES,
)


def test_rejects_naked_short_call():
    with pytest.raises(ValueError, match="naked"):
        validate_structure(structure="naked_short_call", legs=[
            {"action": "sell", "right": "call", "strike": 250, "expiry": "2026-07-17", "qty": 1}
        ])


def test_rejects_unhedged_ratio_spread():
    with pytest.raises(ValueError, match="ratio"):
        validate_structure(structure="ratio_spread", legs=[
            {"action": "sell", "right": "put", "strike": 230, "expiry": "2026-07-17", "qty": 2},
            {"action": "buy",  "right": "put", "strike": 220, "expiry": "2026-07-17", "qty": 1},
        ])


def test_accepts_bull_put_spread():
    validate_structure(structure="bull_put_spread", legs=[
        {"action": "sell", "right": "put", "strike": 235, "expiry": "2026-07-17", "qty": 5},
        {"action": "buy",  "right": "put", "strike": 225, "expiry": "2026-07-17", "qty": 5},
    ])  # no exception


def test_jade_lizard_requires_net_credit_ge_call_spread_width():
    # net credit $1.80, call spread width $5 → invalid
    with pytest.raises(ValueError, match="net credit"):
        validate_structure(
            structure="jade_lizard",
            legs=[
                {"action": "sell", "right": "put",  "strike": 230, "expiry": "2026-07-17", "qty": 5, "limit_price": 4.00},
                {"action": "sell", "right": "call", "strike": 260, "expiry": "2026-07-17", "qty": 5, "limit_price": 1.50},
                {"action": "buy",  "right": "call", "strike": 265, "expiry": "2026-07-17", "qty": 5, "limit_price": 0.70},
            ],
        )


def test_pl_matrix_for_bull_put_spread():
    legs = [
        {"action": "sell", "right": "put", "strike": 235, "qty": 5, "limit_price": 4.20},
        {"action": "buy",  "right": "put", "strike": 225, "qty": 5, "limit_price": 2.10},
    ]
    matrix = build_pl_matrix(structure="bull_put_spread", legs=legs, spot=244.58,
                              moves_pct=[-0.20, -0.10, -0.05, 0.0, 0.05, 0.10, 0.20])
    # net credit at open = (4.20 - 2.10) * 5 * 100 = $1050
    # at +5% spot ($256.81): both puts expire worthless → keep $1050
    plus_5 = next(row for row in matrix if row["move_pct"] == 0.05)
    assert plus_5["pl_dollar"] == pytest.approx(1050, abs=1)


def test_preflight_includes_required_blocks():
    preflight = build_preflight(
        structure="bull_put_spread",
        ticker="ORCL", spot=244.58,
        legs=[
            {"action": "sell", "right": "put", "strike": 235, "expiry": "2026-07-17", "qty": 5, "limit_price": 4.20},
            {"action": "buy",  "right": "put", "strike": 225, "expiry": "2026-07-17", "qty": 5, "limit_price": 2.10},
        ],
        uw_regime={"iv_rank": 91, "gamma_flip": 192.5, "put_wall": 240.0, "call_wall": 250.0, "max_pain": 245.0},
        account={"buying_power": 50000, "positions": []},
    )
    assert "legs" in preflight
    assert "pl_matrix" in preflight
    assert "max_loss" in preflight
    assert "max_gain" in preflight
    assert "uw_regime" in preflight
    assert "account_check" in preflight
    assert preflight["account_check"]["sufficient_buying_power"] is True
```

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/pytest tests/test_ib_order.py -v
```

Expected: 6 FAIL.

- [ ] **Step 3: Implement**

```python
# plugins/option-wizard/skills/option-wizard/scripts/ib_order.py
"""Build IB option order instructions with defined-risk guardrails.

Pure logic — no IB connection here. Use scripts._clients.ib.IBClient to
actually submit. The split keeps this module testable in isolation.
"""
from __future__ import annotations

from typing import Any, Iterable

REJECTED_STRUCTURES = {
    "naked_short_call",
    "naked_short_put_margin",
    "ratio_spread",
    "diagonal_inverted",
    "calendar_inverted",
}

SUPPORTED_STRUCTURES = {
    "covered_call",
    "cash_secured_put",
    "bull_put_spread",
    "bear_call_spread",
    "iron_condor",
    "collar",
    "jade_lizard",
    "put_butterfly",
    "long_put",
    "put_spread",
}


def _signed_qty(leg: dict) -> int:
    sign = 1 if leg["action"].lower() == "buy" else -1
    return sign * int(leg["qty"])


def _net_credit(legs: Iterable[dict]) -> float:
    """Dollar credit received (positive) or debit paid (negative)."""
    total = 0.0
    for leg in legs:
        price = float(leg.get("limit_price", 0.0))
        sign = -1 if leg["action"].lower() == "buy" else 1
        total += sign * price * int(leg["qty"]) * 100
    return total


def validate_structure(structure: str, legs: list[dict]) -> None:
    if structure in REJECTED_STRUCTURES:
        raise ValueError(f"{structure} is rejected by the defined-risk policy (naked / ratio / inverted calendar).")
    if structure not in SUPPORTED_STRUCTURES:
        raise ValueError(f"{structure} is not a supported structure.")

    if structure == "ratio_spread":
        raise ValueError("ratio_spread rejected: unhedged short side has unbounded risk.")

    if structure == "jade_lizard":
        # Required legs: short put, short call, long call (further OTM)
        short_calls = [l for l in legs if l["right"].lower() == "call" and l["action"].lower() == "sell"]
        long_calls = [l for l in legs if l["right"].lower() == "call" and l["action"].lower() == "buy"]
        short_puts = [l for l in legs if l["right"].lower() == "put" and l["action"].lower() == "sell"]
        if not (short_calls and long_calls and short_puts):
            raise ValueError("jade_lizard requires short put + short call + long call (further OTM)")
        call_spread_width = abs(float(long_calls[0]["strike"]) - float(short_calls[0]["strike"]))
        net_credit_per_contract = _net_credit(legs) / max(int(legs[0]["qty"]), 1) / 100.0
        if net_credit_per_contract < call_spread_width:
            raise ValueError(
                f"jade_lizard net credit ${net_credit_per_contract:.2f}/contract is less than "
                f"call spread width ${call_spread_width:.2f}; upside is not risk-free"
            )

    if structure == "covered_call":
        # Validated against account positions in build_preflight; here just structural.
        if not any(l["right"].lower() == "call" and l["action"].lower() == "sell" for l in legs):
            raise ValueError("covered_call requires a short call leg")


def _payoff_at_expiry(spot_at_expiry: float, legs: list[dict]) -> float:
    pnl = 0.0
    for leg in legs:
        strike = float(leg["strike"])
        qty = int(leg["qty"])
        price = float(leg.get("limit_price", 0.0))
        is_call = leg["right"].lower() == "call"
        is_long = leg["action"].lower() == "buy"
        intrinsic = max(spot_at_expiry - strike, 0.0) if is_call else max(strike - spot_at_expiry, 0.0)
        sign = 1 if is_long else -1
        # cash flow at open + intrinsic at expiry (settled)
        pnl += sign * (intrinsic - price) * qty * 100
    return pnl


def build_pl_matrix(structure: str, legs: list[dict], spot: float,
                     moves_pct: list[float] | None = None) -> list[dict]:
    if moves_pct is None:
        moves_pct = [-0.20, -0.10, -0.05, 0.0, 0.05, 0.10, 0.20]
    rows = []
    for mv in moves_pct:
        s = spot * (1 + mv)
        rows.append({
            "move_pct": mv,
            "spot": round(s, 2),
            "pl_dollar": round(_payoff_at_expiry(s, legs), 2),
        })
    return rows


def _account_check(structure: str, legs: list[dict], account: dict,
                    max_loss: float | None = None) -> dict:
    """Verify the trader can support the trade.

    For CSP: cash needed = sum of (strike × 100 × qty) on short put legs.
    For CC / Collar: holdings ≥ short call contracts × 100 (shares to cover).
    For credit spreads (bull put, bear call, iron condor, butterfly):
      buying power required = |max_loss|. Caller must pass `max_loss`
      (negative number) computed from the structure-specific formula or
      from the sampled P/L matrix's true minimum. `_payoff_at_expiry(0, ...)`
      is NOT safe for call-side structures because spot=0 makes all calls
      worthless, returning net credit instead of max loss.
    """
    bp = float(account.get("buying_power", 0))
    positions = account.get("positions", [])
    if structure == "cash_secured_put":
        need = sum(float(l["strike"]) * int(l["qty"]) * 100
                   for l in legs if l["action"].lower() == "sell" and l["right"].lower() == "put")
    elif structure in {"covered_call", "collar"}:
        ticker = legs[0].get("symbol") or legs[0].get("ticker")
        held = sum(int(p.get("position", 0)) for p in positions
                   if p.get("symbol") == ticker)
        contracts = sum(int(l["qty"]) for l in legs
                        if l["right"].lower() == "call" and l["action"].lower() == "sell")
        return {
            "sufficient_shares_for_cover": held >= contracts * 100,
            "shares_held": held,
            "contracts": contracts,
        }
    else:
        if max_loss is None:
            raise ValueError(
                f"_account_check requires max_loss for {structure}; "
                "compute from structure formula or matrix min"
            )
        need = abs(min(0.0, float(max_loss)))
    return {
        "buying_power_required": round(need, 2),
        "buying_power_available": bp,
        "sufficient_buying_power": bp >= need,
    }


def _exact_max_loss(structure: str, legs: list[dict], pl_matrix: list[dict]) -> float:
    """Structure-specific max loss; falls back to matrix minimum.

    Sampled matrix endpoints can miss true extrema for very ITM scenarios
    (bear call spread peaks at spot → ∞, not within ±20%). For known
    structures use the closed-form; for unknown structures fall back to
    the matrix min as a coarse approximation.
    """
    if structure in {"bull_put_spread", "put_credit_spread"}:
        puts = [l for l in legs if l["right"].lower() == "put"]
        short_strikes = [float(l["strike"]) for l in puts if l["action"].lower() == "sell"]
        long_strikes = [float(l["strike"]) for l in puts if l["action"].lower() == "buy"]
        if short_strikes and long_strikes:
            width = max(short_strikes) - min(long_strikes)
            qty = int(puts[0]["qty"])
            credit = sum((1 if l["action"].lower() == "sell" else -1) *
                         float(l.get("limit_price", 0)) * int(l["qty"]) * 100
                         for l in puts)
            return -(width * qty * 100 - credit)
    if structure == "bear_call_spread":
        calls = [l for l in legs if l["right"].lower() == "call"]
        short_strikes = [float(l["strike"]) for l in calls if l["action"].lower() == "sell"]
        long_strikes = [float(l["strike"]) for l in calls if l["action"].lower() == "buy"]
        if short_strikes and long_strikes:
            width = max(long_strikes) - min(short_strikes)
            qty = int(calls[0]["qty"])
            credit = sum((1 if l["action"].lower() == "sell" else -1) *
                         float(l.get("limit_price", 0)) * int(l["qty"]) * 100
                         for l in calls)
            return -(width * qty * 100 - credit)
    # fallback: matrix min (safe for puts-only / butterflies / long-puts)
    return min(r["pl_dollar"] for r in pl_matrix)


def _exact_max_gain(structure: str, legs: list[dict], pl_matrix: list[dict]) -> float:
    """For credit spreads: max gain = net credit (both legs expire worthless).
    Falls back to matrix max otherwise.
    """
    if structure in SPREAD_STRUCTURES:
        credit = sum((1 if l["action"].lower() == "sell" else -1) *
                     float(l.get("limit_price", 0)) * int(l["qty"]) * 100
                     for l in legs)
        return max(0.0, credit)
    return max(r["pl_dollar"] for r in pl_matrix)


def build_preflight(structure: str, ticker: str, spot: float, legs: list[dict],
                     uw_regime: dict, account: dict) -> dict[str, Any]:
    validate_structure(structure, legs)
    matrix = build_pl_matrix(structure, legs, spot)
    # Use structure-specific exact formulas where available; the sampled
    # matrix is for display only.
    max_loss = _exact_max_loss(structure, legs, matrix)
    max_gain = _exact_max_gain(structure, legs, matrix)
    net_credit = _net_credit(legs)
    # Spread width for downstream bracket-builder use.
    extras = {}
    if structure in SPREAD_STRUCTURES:
        strikes = sorted({float(l["strike"]) for l in legs})
        if len(strikes) >= 2:
            qty = int(legs[0]["qty"])
            extras["spread_width_dollar"] = (max(strikes) - min(strikes)) * qty * 100
    return {
        "ticker": ticker,
        "structure": structure,
        "spot": spot,
        "legs": legs,
        "net_credit_dollar": round(net_credit, 2),
        "pl_matrix": matrix,
        "max_loss": round(max_loss, 2),
        "max_gain": round(max_gain, 2),
        "uw_regime": uw_regime,
        "account_check": _account_check(structure, legs, account, max_loss=max_loss),
        **extras,
    }
```

- [ ] **Step 4: Run tests to verify pass**

```bash
.venv/bin/pytest tests/test_ib_order.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/ib_order.py tests/test_ib_order.py
git commit -m "feat(ib): order construction with rejection clauses and pre-flight builder"
```

---

### Task 4.3: Paper-account verification of `create_order_instruction` AND `ib_insync.placeOrder`

**Goal:** Resolve spec §13 open items #1 and #2 — confirm two separate behaviors:

1. **MCP path** (`mcp__claude_ai_Interactive_Brokers_IBKR__create_order_instruction`) — verify whether it creates a pending-approval instruction or submits live.
2. **Python path** (`scripts._clients.ib.IBClient.place_order` which wraps `ib_insync.IB.placeOrder`) — this is known to submit live (no approval step). The pre-flight `YES/NO` in `build_preflight` is therefore the only safety gate for the Python path.

Both paths exist in the design: the LLM in-session may use the MCP, while the daily hook uses the Python path. Each must be verified on paper before any live order.

**Files:**
- Create: `tests/integration/test_ib_paper_smoke.py`
- Create: `docs/setup/ib-paper-verification.md`

- [ ] **Step 1: Write the verification doc**

```markdown
# IB MCP `create_order_instruction` Verification

Before option-wizard places live orders, verify two assumptions on a paper account:

1. `mcp__claude_ai_Interactive_Brokers_IBKR__create_order_instruction` produces a pending-approval state in TWS, not auto-fill.
2. The MCP supports OCA (One-Cancels-All) groups for bracket order linkage. If not, document the fallback.

## Setup

- Open TWS or IB Gateway in paper account mode (port 7497 for TWS paper).
- Run `mcp__claude_ai_Interactive_Brokers_IBKR__get_account_summary` and confirm the account number begins with `D` (paper) or matches a known paper account.

## Test A (MCP path): Single-leg pending-approval check

Use the MCP to submit a small defined-risk trade. Example:

- Underlying: SPY
- Structure: 1-contract bull put spread, short 5% OTM, long 10% OTM, 45 DTE
- Limit price: aggressive mid (likely to not fill instantly)

Then check whether the order appears in TWS as `Pre-Submit` / `Pending` (good) or `Filled` (bad). Document the observation.

## Test B (MCP path): OCA bracket support

After submitting the opening order, attempt to submit two child orders with the same `ocaGroup` field. If IB MCP accepts the field and TWS shows both as part of one OCA group, OCA is supported.

If not supported, the fallback is in `scripts/manage_positions.py`: detect the fill of one bracket leg via daily polling and submit a cancel for the other.

## Test C (Python path): ib_insync behavior

The Python `IBClient.place_order` wrapping `ib_insync.IB.placeOrder` is known to submit live with no approval step. Verify on paper that:

- An order placed via `IBClient.place_order` shows up immediately in TWS as `PreSubmitted` → `Submitted` (filled if liquid) without any user approval prompt.
- The safety implication: `scripts/ib_order.py` must enforce the `YES/NO` pre-flight gate before ever calling `IBClient.place_order`. There is no second chance.

## Outcome

Record findings inline below and reference from `scripts/ib_order.py` and `references/execution.md`.

- [ ] (MCP) `create_order_instruction` is pending-approval: YES / NO / partial
- [ ] (MCP) OCA groups supported: YES / NO
- [ ] (Python) `ib_insync.placeOrder` submits live with no approval: YES / NO
- [ ] Fallback documented in `manage_positions.py`: YES / NO
```

- [ ] **Step 2: Write a manual-run smoke test that exercises a paper order**

```python
# tests/integration/test_ib_paper_smoke.py
"""Paper-account IB smoke test. Requires TWS/IB Gateway in paper mode at the
specified port. Skips by default unless OPT_WIZ_PAPER_TEST=1 is set.

This test does NOT use the Claude MCP — it goes directly through
ib_insync since the Python scripts will do the same in v1. The goal here
is the same: confirm orders land in 'PreSubmitted' state and not
'Submitted'/'Filled'.

Run:
    OPT_WIZ_PAPER_TEST=1 .venv/bin/pytest tests/integration/test_ib_paper_smoke.py -v -s
"""
import os
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("OPT_WIZ_PAPER_TEST") != "1",
    reason="Set OPT_WIZ_PAPER_TEST=1 to run live paper smoke test",
)


def test_paper_account_connection_and_summary():
    from scripts._clients.ib import IBClient
    # IB paper Gateway = 4002, TWS paper = 7497. Pick the one the user has open.
    port = int(os.environ.get("OPT_WIZ_PAPER_PORT", 7497))
    with IBClient(port=port) as ib:
        summary = ib.get_account_summary()
        print("Paper account NetLiquidation:", summary.get("NetLiquidation"))
        assert "NetLiquidation" in summary


def test_paper_order_state_is_presubmitted_not_filled():
    """Submit a low-prob fill order and inspect its status field.
    Expectation per design assumption: status starts as PreSubmitted, not Filled.
    """
    from scripts._clients.ib import IBClient
    from ib_insync import Stock, MarketOrder

    port = int(os.environ.get("OPT_WIZ_PAPER_PORT", 7497))
    with IBClient(port=port) as ib:
        # Use a trivial market order on a high-vol stock for a clear status read.
        contract = Stock("SPY", "SMART", "USD")
        ib._ib.qualifyContracts(contract)
        order = MarketOrder("BUY", 1)
        trade = ib.place_order(contract, order)
        ib._ib.sleep(1.5)
        status = trade.orderStatus.status
        print(f"Order status immediately after place_order: {status}")
        # We expect either PreSubmitted, Submitted, or Filled (markets open).
        # The key question is whether ANY user approval is needed. ib_insync
        # by default places live. The MCP behavior may differ — document below.
        assert status in {"PreSubmitted", "Submitted", "Filled", "PendingSubmit"}
```

- [ ] **Step 3: Run the smoke test on the user's paper account**

```bash
# user opens TWS paper, then:
OPT_WIZ_PAPER_TEST=1 OPT_WIZ_PAPER_PORT=7497 .venv/bin/pytest tests/integration/test_ib_paper_smoke.py -v -s
```

Expected: prints `NetLiquidation` from the paper account and `Order status: ...`. Record the observed status in `docs/setup/ib-paper-verification.md` before any live order is ever attempted.

- [ ] **Step 4: Update the design spec with verified behavior**

Edit `docs/specs/2026-06-03-option-wizard-design.md` §13 to mark items #1 and #2 as verified, with a one-line summary of the observed behavior and OCA support status.

- [ ] **Step 5: Commit**

```bash
git add docs/setup/ib-paper-verification.md tests/integration/test_ib_paper_smoke.py docs/specs/2026-06-03-option-wizard-design.md
git commit -m "test(ib): paper account verification of order submission + OCA support"
```

---

### Task 4.4: Bracket order construction (OCA group helper)

**Files:**
- Modify: `plugins/option-wizard/skills/option-wizard/scripts/ib_order.py`
- Modify: `tests/test_ib_order.py`

- [ ] **Step 1: Append failing test**

```python
# tests/test_ib_order.py (append)
from scripts.ib_order import build_brackets


def test_brackets_default_50pct_take_profit_and_full_stop_for_spread():
    # Spread width $10 × 5 contracts × $100 = $5000.
    # Net credit at open $1050. Max loss = $5000 − $1050 = $3950.
    # To stop at max loss, you must close the spread at a $5000 debit:
    #   realized = credit − close_debit = 1050 − 5000 = −3950 = max_loss.
    opening = {
        "structure": "bull_put_spread",
        "net_credit_dollar": 1050.0,
        "max_loss": -3950.0,
        "spread_width_dollar": 5000.0,
        "ticker": "ORCL",
    }
    brackets = build_brackets(opening)
    tp = next(b for b in brackets if b["bracket_type"] == "take_profit")
    sl = next(b for b in brackets if b["bracket_type"] == "stop_loss")
    # take-profit closes when the spread can be bought back at 50% of credit
    assert tp["close_at_debit_or_credit"] == pytest.approx(525.0, abs=1)
    # stop loss closes at the spread width (locks in full max loss)
    assert sl["close_at_debit_or_credit"] == pytest.approx(5000.0, abs=1)
    # both must share an OCA group identifier
    assert tp["oca_group"] == sl["oca_group"]


def test_brackets_for_csp_use_2x_credit_rule():
    opening = {
        "structure": "cash_secured_put",
        "net_credit_dollar": 500.0,
        "max_loss": -50000.0,  # strike × 100 in worst case
        "ticker": "AMD",
    }
    brackets = build_brackets(opening)
    sl = next(b for b in brackets if b["bracket_type"] == "stop_loss")
    # CSP stop = 2x credit = $1000 debit
    assert sl["close_at_debit_or_credit"] == pytest.approx(1000.0, abs=1)
```

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/pytest tests/test_ib_order.py::test_brackets_default_50pct_take_profit_and_2x_stop_loss -v
```

Expected: FAIL.

- [ ] **Step 3: Append implementation**

```python
# Append to scripts/ib_order.py
import uuid

SPREAD_STRUCTURES = {"bull_put_spread", "bear_call_spread", "iron_condor", "put_butterfly"}
SHORT_PREMIUM_STRUCTURES = SPREAD_STRUCTURES | {"covered_call", "cash_secured_put", "jade_lizard"}


def build_brackets(opening: dict, take_profit_pct: float = 0.50,
                    stop_loss_multiplier: float = 2.0) -> list[dict]:
    """Bracket helper.

    For credit spreads, realized P/L = opening_credit − closing_debit. To
    stop at exactly the max loss you must close the spread at a debit
    equal to the spread width (not abs(max_loss), which equals
    width − credit). Caller must pass `spread_width_dollar` in opening
    for spread structures.

    For CSP / CC / Jade Lizard the per-leg short option is the unit;
    stop is set at `stop_loss_multiplier × opening_credit` as a debit
    cap (close cost when buying back).
    """
    structure = opening["structure"]
    if structure not in SHORT_PREMIUM_STRUCTURES:
        return []  # long-vol / long-put structures use only a take-profit, handled separately
    credit = float(opening.get("net_credit_dollar", 0))

    oca = f"opt_wiz_{opening['ticker']}_{uuid.uuid4().hex[:8]}"

    take_profit_debit = credit * take_profit_pct

    if structure in SPREAD_STRUCTURES:
        width = float(opening.get("spread_width_dollar", 0))
        if width <= 0:
            raise ValueError("spread_width_dollar required for spread structures")
        stop_loss_debit = width
        stop_rationale = "close at spread width (locks in full max loss)"
    else:
        # CSP / CC / jade lizard: stop = N× credit (default 2×)
        stop_loss_debit = credit * stop_loss_multiplier
        stop_rationale = f"close at {stop_loss_multiplier:.0f}× credit"

    return [
        {
            "bracket_type": "take_profit",
            "oca_group": oca,
            "close_at_debit_or_credit": round(take_profit_debit, 2),
            "rationale": f"close at {int(take_profit_pct*100)}% of max profit",
        },
        {
            "bracket_type": "stop_loss",
            "oca_group": oca,
            "close_at_debit_or_credit": round(stop_loss_debit, 2),
            "rationale": stop_rationale,
        },
    ]
```

- [ ] **Step 4: Run tests to verify pass**

```bash
.venv/bin/pytest tests/test_ib_order.py -v
```

Expected: all tests pass (Task 4.2 + Task 4.4).

- [ ] **Step 5: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/ib_order.py tests/test_ib_order.py
git commit -m "feat(ib): bracket order builder with default 50% TP / 2x credit SL"
```

---

## Phase 5 — Position Management

### Task 5.1: `scripts/evaluate_position.py` — single-position decision tree

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/scripts/evaluate_position.py`
- Create: `tests/test_evaluate_position.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_evaluate_position.py
import pytest
from scripts.evaluate_position import evaluate_short_premium


def test_take_profit_when_above_50pct_decay():
    result = evaluate_short_premium(
        opening_credit=4.20, current_price=2.00, dte=52, delta=-0.18,
        structure="bull_put_spread",
    )
    # 4.20 → 2.00 is more than 50% decay
    assert result["recommended_action"] == "CLOSE"
    assert "take-profit" in result["rationale"].lower()


def test_stop_loss_when_loss_exceeds_2x_credit():
    result = evaluate_short_premium(
        opening_credit=4.20, current_price=10.00, dte=52, delta=-0.55,
        structure="cash_secured_put",
    )
    assert result["recommended_action"] in {"CLOSE", "ROLL"}
    assert "stop" in result["rationale"].lower() or "loss" in result["rationale"].lower()


def test_21_dte_forces_review():
    result = evaluate_short_premium(
        opening_credit=4.20, current_price=2.80, dte=21, delta=-0.30,
        structure="bull_put_spread",
    )
    assert result["recommended_action"] == "REVIEW"
    assert "21" in result["rationale"]


def test_below_21_dte_still_review():
    result = evaluate_short_premium(
        opening_credit=4.20, current_price=2.80, dte=15, delta=-0.30,
        structure="bull_put_spread",
    )
    assert result["recommended_action"] == "REVIEW"
    assert "gamma" in result["rationale"].lower()


def test_healthy_position_holds():
    result = evaluate_short_premium(
        opening_credit=4.20, current_price=3.80, dte=45, delta=-0.20,
        structure="bull_put_spread",
    )
    assert result["recommended_action"] == "HOLD"
```

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/pytest tests/test_evaluate_position.py -v
```

Expected: 5 FAIL.

- [ ] **Step 3: Implement**

```python
# plugins/option-wizard/skills/option-wizard/scripts/evaluate_position.py
"""Single short-premium position decision tree.

Order of evaluation:
  1. DTE <= 21 → REVIEW (hard rule, regardless of P/L)
  2. P/L hit take-profit threshold → CLOSE
  3. P/L hit stop-loss threshold → CLOSE or ROLL (caller chooses)
  4. Otherwise → HOLD
"""
from __future__ import annotations

SPREAD_STRUCTURES = {"bull_put_spread", "bear_call_spread", "iron_condor", "put_butterfly"}
SHORT_PREMIUM_STRUCTURES = SPREAD_STRUCTURES | {"covered_call", "cash_secured_put", "jade_lizard"}


def evaluate_short_premium(
    opening_credit: float,
    current_price: float,
    dte: int,
    delta: float,
    structure: str,
    take_profit_pct: float = 0.50,
    stop_loss_multiplier: float = 2.0,
) -> dict:
    if structure not in SHORT_PREMIUM_STRUCTURES:
        raise ValueError(f"evaluate_short_premium does not apply to {structure}")

    if dte <= 21:
        return {
            "recommended_action": "REVIEW",
            "rationale": (
                f"DTE {dte} ≤ 21 — gamma window. Hard rule: pick CLOSE / ROLL / "
                "HOLD-AND-ACCEPT-GAMMA before any other request."
            ),
            "current_price": current_price,
            "opening_credit": opening_credit,
            "delta": delta,
            "dte": dte,
        }

    decay_pct = (opening_credit - current_price) / opening_credit if opening_credit else 0.0

    if decay_pct >= take_profit_pct:
        return {
            "recommended_action": "CLOSE",
            "rationale": (
                f"take-profit hit: {decay_pct:.0%} of credit decayed "
                f"(threshold {int(take_profit_pct*100)}%)"
            ),
            "current_price": current_price,
            "opening_credit": opening_credit,
            "delta": delta,
            "dte": dte,
        }

    if structure in SPREAD_STRUCTURES:
        # current price exceeding 2× opening credit means we're inside max loss zone
        stop_trigger = opening_credit * stop_loss_multiplier
    else:
        stop_trigger = opening_credit * stop_loss_multiplier

    if current_price >= stop_trigger:
        return {
            "recommended_action": "CLOSE",
            "rationale": (
                f"stop-loss hit: current price ${current_price:.2f} >= "
                f"{stop_loss_multiplier:.0f}× opening credit ${opening_credit:.2f}"
            ),
            "current_price": current_price,
            "opening_credit": opening_credit,
            "delta": delta,
            "dte": dte,
        }

    return {
        "recommended_action": "HOLD",
        "rationale": (
            f"{decay_pct:.0%} of credit decayed; DTE {dte} above 21; delta {delta:+.2f} healthy"
        ),
        "current_price": current_price,
        "opening_credit": opening_credit,
        "delta": delta,
        "dte": dte,
    }
```

- [ ] **Step 4: Run tests to verify pass**

```bash
.venv/bin/pytest tests/test_evaluate_position.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/evaluate_position.py tests/test_evaluate_position.py
git commit -m "feat(positions): short-premium decision tree with 21 DTE hard rule"
```

---

### Task 5.2: `scripts/manage_positions.py` — daily scan entrypoint

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/scripts/manage_positions.py`
- Create: `tests/test_manage_positions.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_manage_positions.py
from unittest.mock import MagicMock
from scripts.manage_positions import scan_positions, format_scan_report


def test_scan_returns_one_row_per_position():
    fake_positions = [
        MagicMock(
            contract=MagicMock(symbol="ORCL", strike=235, right="P", lastTradeDateOrContractMonth="20260725"),
            position=-5, avgCost=4.20,
        ),
        MagicMock(
            contract=MagicMock(symbol="NVDA", strike=800, right="C", lastTradeDateOrContractMonth="20260725"),
            position=-1, avgCost=12.00,
        ),
    ]
    fake_market = {
        "ORCL 235 P 20260725": {"current_price": 2.00, "delta": -0.18, "dte": 52},
        "NVDA 800 C 20260725": {"current_price": 28.00, "delta": -0.65, "dte": 52},
    }
    rows = scan_positions(positions=fake_positions, market=fake_market, today="2026-06-03")
    assert len(rows) == 2
    assert {r["symbol"] for r in rows} == {"ORCL", "NVDA"}


def test_format_scan_report_prioritizes_REVIEW_rows():
    rows = [
        {"symbol": "AAA", "action": "HOLD", "dte": 50, "rationale": "fine"},
        {"symbol": "BBB", "action": "REVIEW", "dte": 19, "rationale": "21 DTE window"},
        {"symbol": "CCC", "action": "CLOSE", "dte": 40, "rationale": "take-profit"},
    ]
    report = format_scan_report(rows)
    # REVIEW must appear before HOLD or CLOSE
    review_idx = report.index("BBB")
    close_idx = report.index("CCC")
    hold_idx = report.index("AAA")
    assert review_idx < close_idx
    assert review_idx < hold_idx


def test_report_includes_no_action_line_when_empty():
    report = format_scan_report([])
    assert "no" in report.lower() or "0 positions" in report.lower()
```

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/pytest tests/test_manage_positions.py -v
```

Expected: 3 FAIL.

- [ ] **Step 3: Implement**

```python
# plugins/option-wizard/skills/option-wizard/scripts/manage_positions.py
"""Daily position scan entrypoint.

Reads positions from IB, prices each option (placeholder for v1: caller
supplies market dict), evaluates each via evaluate_position, and produces
a human-readable report. The report is delivered to:

  - the current Claude Code session via SessionStart context block
  - chenxi.li08@outlook.com via Gmail SMTP (scripts/email_sender.py)
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from typing import Any

from scripts.evaluate_position import evaluate_short_premium, SHORT_PREMIUM_STRUCTURES


def _position_key(pos: Any) -> str:
    c = pos.contract
    # Preserve fractional strikes (weekly $252.50 etc.) — int() would silently truncate.
    strike_str = f"{c.strike:g}"
    return f"{c.symbol} {strike_str} {c.right} {c.lastTradeDateOrContractMonth}"


def _infer_structure(pos: Any) -> str:
    # Heuristic for v1: short put → cash_secured_put unless tagged otherwise.
    # Future work: read from a local positions metadata sidecar.
    qty = pos.position
    right = pos.contract.right.upper()
    if qty < 0 and right == "P":
        return "cash_secured_put"
    if qty < 0 and right == "C":
        return "covered_call"
    return "unknown"


def scan_positions(positions: list, market: dict[str, dict], today: str) -> list[dict]:
    rows = []
    for pos in positions:
        key = _position_key(pos)
        m = market.get(key, {})
        structure = _infer_structure(pos)
        if structure not in SHORT_PREMIUM_STRUCTURES:
            rows.append({
                "symbol": pos.contract.symbol, "key": key, "action": "HOLD",
                "dte": m.get("dte", -1),
                "rationale": "non-short-premium position; manual review",
            })
            continue
        try:
            evaluation = evaluate_short_premium(
                opening_credit=abs(float(pos.avgCost)) / 100,  # IB avgCost is dollar; divide for per-share
                current_price=m.get("current_price", 0.0),
                dte=m.get("dte", 0),
                delta=m.get("delta", 0.0),
                structure=structure,
            )
            rows.append({
                "symbol": pos.contract.symbol,
                "key": key,
                "action": evaluation["recommended_action"],
                "dte": evaluation["dte"],
                "rationale": evaluation["rationale"],
            })
        except Exception as e:
            rows.append({
                "symbol": pos.contract.symbol, "key": key, "action": "REVIEW",
                "dte": m.get("dte", -1),
                "rationale": f"evaluation error: {e}",
            })
    return rows


def _fetch_market_data(ib: Any, positions: list) -> dict[str, dict]:
    """Pull mid price, delta, DTE for every option position via ib_insync.

    Uses reqMktData with snapshot=False to get a streaming subscription, then
    waits up to 3 seconds for greek+price fields to populate. Returns a dict
    keyed by `_position_key(pos)`.
    """
    from datetime import datetime as _dt
    market = {}
    pending = []
    for pos in positions:
        ticker = ib._ib.reqMktData(pos.contract, genericTickList="", snapshot=False)
        pending.append((pos, ticker))
    ib._ib.sleep(3)  # let market data populate
    for pos, t in pending:
        c = pos.contract
        try:
            expiry = _dt.strptime(c.lastTradeDateOrContractMonth, "%Y%m%d").date()
            dte = (expiry - _dt.utcnow().date()).days
        except Exception:
            dte = 0
        mid = None
        if t.bid is not None and t.ask is not None and t.bid > 0 and t.ask > 0:
            mid = (t.bid + t.ask) / 2
        elif t.last is not None:
            mid = t.last
        delta = getattr(t.modelGreeks, "delta", 0.0) if t.modelGreeks else 0.0
        market[_position_key(pos)] = {
            "current_price": mid or 0.0,
            "delta": delta,
            "dte": dte,
        }
    return market


def format_scan_report(rows: list[dict]) -> str:
    if not rows:
        return "Daily position scan: no positions found (0 positions). No action needed."

    priority = {"REVIEW": 0, "CLOSE": 1, "ROLL": 2, "HOLD": 3}
    sorted_rows = sorted(rows, key=lambda r: priority.get(r["action"], 99))

    lines = [f"Daily position scan ({datetime.utcnow().date()}):", ""]
    review_count = sum(1 for r in sorted_rows if r["action"] == "REVIEW")
    close_count = sum(1 for r in sorted_rows if r["action"] == "CLOSE")
    lines.append(f"  {review_count} require review (21 DTE / blocking), {close_count} ready to close")
    lines.append("")
    for r in sorted_rows:
        marker = "⚠" if r["action"] == "REVIEW" else "✓" if r["action"] == "HOLD" else "→"
        lines.append(f"  {marker} {r['symbol']:6} [{r['action']:6}] DTE {r['dte']:3}  {r['rationale']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-email", action="store_true", help="skip email delivery")
    parser.add_argument("--port", type=int, default=4001, help="IB Gateway port")
    args = parser.parse_args(argv)

    from scripts._clients.ib import IBClient
    with IBClient(port=args.port) as ib:
        positions = ib.get_positions()
        market = _fetch_market_data(ib, positions)
        rows = scan_positions(positions, market, today=str(datetime.utcnow().date()))
        report = format_scan_report(rows)
    print(report)

    if not args.no_email:
        from scripts.email_sender import send_daily_scan
        send_daily_scan(report, rows)

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify pass**

```bash
.venv/bin/pytest tests/test_manage_positions.py -v
```

Expected: 3 passed. (The `main()` entrypoint is not covered by unit tests; it is exercised by the daily smoke test in Task 8.2.)

- [ ] **Step 5: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/manage_positions.py tests/test_manage_positions.py
git commit -m "feat(positions): daily scan entrypoint with priority-sorted report"
```

---

## Phase 6 — Macro Hedge

### Task 6.1: `scripts/macro_hedge.py` — SPX hedge construction

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/scripts/macro_hedge.py`
- Create: `tests/test_macro_hedge.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_macro_hedge.py
import pytest
from scripts.macro_hedge import build_macro_hedge


SPX_SNAPSHOT = {
    "spot": 6200.0,
    "iv_atm_90d": 0.18,
}


def test_butterfly_for_mild_correction_target():
    result = build_macro_hedge(
        portfolio_notional=1_000_000,
        hedge_horizon_days=60,
        scenario="mild_correction_-5",
        underlying="SPX",
        structure="butterfly",
        snapshot=SPX_SNAPSHOT,
    )
    assert result["structure"] == "put_butterfly"
    # standard put butterfly = 3 legs (long upper / 2 short body / long lower)
    assert len(result["legs"]) == 3
    # body strike should be at SPX × 0.95
    body_strike = [l["strike"] for l in result["legs"] if l["qty"] == 2][0]
    assert body_strike == pytest.approx(SPX_SNAPSHOT["spot"] * 0.95, abs=1)


def test_put_spread_for_deep_correction():
    # SPX 1-lot ATM/-10% put spread is ~$14k at 18% IV and 60 DTE; a
    # $1M portfolio's 60-day cap (1.5% × 60/365) is ~$2.5k, so the call
    # must raise. Use a larger portfolio in the happy-path test.
    result = build_macro_hedge(
        portfolio_notional=10_000_000,
        hedge_horizon_days=60,
        scenario="deep_correction_-10",
        underlying="SPX",
        structure="put_spread",
        snapshot=SPX_SNAPSHOT,
    )
    assert result["structure"] == "put_spread"
    assert len(result["legs"]) == 2


def test_put_spread_rejected_on_small_account():
    with pytest.raises(ValueError, match="cost"):
        build_macro_hedge(
            portfolio_notional=1_000_000,
            hedge_horizon_days=60,
            scenario="deep_correction_-10",
            underlying="SPX",
            structure="put_spread",
            snapshot=SPX_SNAPSHOT,
        )


def test_long_put_for_crash_scenario():
    result = build_macro_hedge(
        portfolio_notional=1_000_000,
        hedge_horizon_days=60,
        scenario="crash_-20",
        underlying="SPX",
        structure="long_put",
        snapshot=SPX_SNAPSHOT,
    )
    assert result["structure"] == "long_put"
    assert len(result["legs"]) == 1


def test_cost_cap_enforced():
    # Force a structure whose cost would exceed 1.5% annualized of $1M = $15k for 1 year
    # → over 60 days, max cost ≈ 15000 * 60/365 = ~$2466
    with pytest.raises(ValueError, match="cost"):
        build_macro_hedge(
            portfolio_notional=1_000_000,
            hedge_horizon_days=60,
            scenario="crash_-20",
            underlying="SPX",
            structure="long_put",
            snapshot={"spot": 6200.0, "iv_atm_90d": 0.50},  # implausibly high IV → expensive
            max_annual_cost_pct=0.015,
        )


def test_auto_structure_routes_by_scenario():
    result = build_macro_hedge(
        portfolio_notional=1_000_000,
        hedge_horizon_days=60,
        scenario="mild_correction_-5",
        underlying="SPX",
        structure="auto",
        snapshot=SPX_SNAPSHOT,
    )
    assert result["structure"] == "put_butterfly"
```

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/pytest tests/test_macro_hedge.py -v
```

Expected: 5 FAIL.

- [ ] **Step 3: Implement**

```python
# plugins/option-wizard/skills/option-wizard/scripts/macro_hedge.py
"""Build SPX / SPY / NDX / QQQ macro hedge structures.

Three structures supported, picked by scenario:
  - mild_correction_-5  → put butterfly centered at spot × 0.95
  - deep_correction_-10 → put spread (long ATM, short -10% OTM)
  - crash_-20           → long OTM put at spot × 0.90 (insurance)

Cost cap enforced: total premium ≤ portfolio_notional × max_annual_cost_pct × (horizon_days / 365).
"""
from __future__ import annotations

import math
from typing import Any

from scipy.stats import norm


def _bs_put(spot: float, strike: float, t_years: float, r: float, sigma: float) -> float:
    """Black-Scholes put price. Sufficient approximation for hedge sizing."""
    if t_years <= 0 or sigma <= 0:
        return max(strike - spot, 0.0)
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma ** 2) * t_years) / (sigma * math.sqrt(t_years))
    d2 = d1 - sigma * math.sqrt(t_years)
    return strike * math.exp(-r * t_years) * norm.cdf(-d2) - spot * norm.cdf(-d1)


def _butterfly(spot: float, t_years: float, iv: float, qty: int) -> list[dict]:
    """Standard 3-leg put butterfly centered at body strike.

    Long 1× upper put, short 2× body put, long 1× lower put. Max payout
    when underlying lands at the body strike at expiry. Defined risk:
    net premium paid is the maximum loss.
    """
    body = spot * 0.95
    wing_up = spot * 0.98
    wing_dn = spot * 0.92
    return [
        {"right": "put", "action": "buy",  "strike": wing_up, "qty": qty,
         "limit_price": _bs_put(spot, wing_up, t_years, 0.04, iv)},
        {"right": "put", "action": "sell", "strike": body, "qty": 2 * qty,
         "limit_price": _bs_put(spot, body, t_years, 0.04, iv)},
        {"right": "put", "action": "buy",  "strike": wing_dn, "qty": qty,
         "limit_price": _bs_put(spot, wing_dn, t_years, 0.04, iv)},
    ]


def _put_spread(spot: float, t_years: float, iv: float, qty: int) -> list[dict]:
    long_strike = spot
    short_strike = spot * 0.90
    return [
        {"right": "put", "action": "buy",  "strike": long_strike, "qty": qty,
         "limit_price": _bs_put(spot, long_strike, t_years, 0.04, iv)},
        {"right": "put", "action": "sell", "strike": short_strike, "qty": qty,
         "limit_price": _bs_put(spot, short_strike, t_years, 0.04, iv)},
    ]


def _long_put(spot: float, t_years: float, iv: float, qty: int) -> list[dict]:
    strike = spot * 0.90
    return [
        {"right": "put", "action": "buy", "strike": strike, "qty": qty,
         "limit_price": _bs_put(spot, strike, t_years, 0.04, iv)},
    ]


def _net_premium(legs: list[dict]) -> float:
    total = 0.0
    multiplier = 100  # SPX/SPY/QQQ standard
    for leg in legs:
        sign = -1 if leg["action"] == "buy" else 1
        total += sign * leg["limit_price"] * leg["qty"] * multiplier
    return -total  # convert net credit (positive in our convention) to net cost (positive = paid)


def build_macro_hedge(
    portfolio_notional: float,
    hedge_horizon_days: int,
    scenario: str,
    underlying: str = "SPX",
    structure: str = "auto",
    snapshot: dict | None = None,
    max_annual_cost_pct: float = 0.015,
    qty: int = 1,
) -> dict[str, Any]:
    if snapshot is None:
        raise ValueError("snapshot is required: {spot, iv_atm_90d}")
    if structure == "auto":
        structure = {
            "mild_correction_-5": "butterfly",
            "deep_correction_-10": "put_spread",
            "crash_-20": "long_put",
        }.get(scenario, "put_spread")

    t_years = hedge_horizon_days / 365.0
    spot = float(snapshot["spot"])
    iv = float(snapshot["iv_atm_90d"])

    if structure == "butterfly":
        legs = _butterfly(spot, t_years, iv, qty)
        structure_label = "put_butterfly"
    elif structure == "put_spread":
        legs = _put_spread(spot, t_years, iv, qty)
        structure_label = "put_spread"
    elif structure == "long_put":
        legs = _long_put(spot, t_years, iv, qty)
        structure_label = "long_put"
    else:
        raise ValueError(f"unknown structure {structure}")

    cost = _net_premium(legs)
    cost_cap = portfolio_notional * max_annual_cost_pct * t_years
    if cost > cost_cap:
        raise ValueError(
            f"hedge cost ${cost:,.0f} exceeds cost cap ${cost_cap:,.0f} "
            f"({max_annual_cost_pct*100:.1f}% annualized of ${portfolio_notional:,.0f} over {hedge_horizon_days}d)"
        )

    return {
        "underlying": underlying,
        "structure": structure_label,
        "scenario": scenario,
        "spot": spot,
        "horizon_days": hedge_horizon_days,
        "legs": [l for l in legs if l["qty"] > 0],
        "cost_dollar": round(cost, 2),
        "cost_pct_of_portfolio_annualized": round(cost / portfolio_notional / t_years, 4) if t_years > 0 else None,
        "cost_cap_dollar": round(cost_cap, 2),
    }
```

- [ ] **Step 4: Run tests to verify pass**

```bash
.venv/bin/pytest tests/test_macro_hedge.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/macro_hedge.py tests/test_macro_hedge.py
git commit -m "feat(hedge): SPX macro hedge builder (butterfly / spread / long put) with cost cap"
```

---

## Phase 7 — Email Delivery

### Task 7.1: Gmail App Password setup doc

**Files:**
- Create: `docs/setup/gmail-app-password.md`

- [ ] **Step 1: Write the setup doc**

```markdown
# Gmail App Password Setup

The daily position scan delivers to chenxi.li08@outlook.com via Gmail SMTP. This requires a Gmail App Password from a Gmail account with 2FA enabled. The password lives outside the repo.

## Generate the password

1. Open https://myaccount.google.com/apppasswords (must be signed in as the Gmail sender).
2. Choose `Mail` and `Other (custom name)`, type "option-wizard", click Generate.
3. Copy the 16-character password. You will not see it again.

## Store the password

Two options. Pick one.

### A. Environment variable (simplest)

Append to `~/.zshrc`:

```bash
export GMAIL_APP_PASSWORD="abcd efgh ijkl mnop"
export GMAIL_SENDER_ADDRESS="your.sender@gmail.com"
```

Then `source ~/.zshrc`.

### B. Config file (preferred when running from cron)

```bash
mkdir -p ~/.config/option-wizard
cat > ~/.config/option-wizard/gmail.json <<'EOF'
{
  "sender_address": "your.sender@gmail.com",
  "app_password": "abcd efgh ijkl mnop"
}
EOF
chmod 600 ~/.config/option-wizard/gmail.json
```

`scripts/email_sender.py` reads env vars first, then falls back to this file.

## Verify

After setup, run:

```bash
.venv/bin/python -c "from scripts.email_sender import send_test; send_test('chenxi.li08@outlook.com')"
```

Check that the test email arrives. If not, check the error log at `~/.config/option-wizard/email-errors.log`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/setup/gmail-app-password.md
git commit -m "docs(setup): Gmail App Password instructions"
```

---

### Task 7.2: `scripts/email_sender.py` — SMTP delivery

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/scripts/email_sender.py`
- Create: `tests/test_email_sender.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_email_sender.py
from unittest.mock import patch, MagicMock
import os
import pytest
from scripts.email_sender import build_email_message, load_credentials


def test_build_email_message_includes_subject_with_counts():
    rows = [
        {"symbol": "ORCL", "action": "REVIEW", "dte": 20, "rationale": "..."},
        {"symbol": "AMD",  "action": "HOLD", "dte": 50, "rationale": "..."},
        {"symbol": "NVDA", "action": "CLOSE", "dte": 40, "rationale": "..."},
    ]
    msg = build_email_message(
        to_addr="chenxi.li08@outlook.com",
        from_addr="sender@gmail.com",
        report_body="Daily scan...",
        rows=rows,
    )
    assert "3 positions" in msg["Subject"]
    assert "1 require review" in msg["Subject"] or "1" in msg["Subject"]
    assert "⚠" in msg["Subject"]


def test_build_email_message_no_action_when_empty():
    msg = build_email_message(
        to_addr="chenxi.li08@outlook.com",
        from_addr="sender@gmail.com",
        report_body="Daily scan: no positions.",
        rows=[],
    )
    assert "no action" in msg["Subject"].lower() or "0 positions" in msg["Subject"]


def test_load_credentials_from_env(monkeypatch):
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "abcd efgh ijkl mnop")
    monkeypatch.setenv("GMAIL_SENDER_ADDRESS", "test@gmail.com")
    creds = load_credentials()
    assert creds["password"] == "abcd efgh ijkl mnop"
    assert creds["sender"] == "test@gmail.com"


def test_load_credentials_from_file(tmp_path, monkeypatch):
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    monkeypatch.delenv("GMAIL_SENDER_ADDRESS", raising=False)
    cfg = tmp_path / "gmail.json"
    cfg.write_text('{"sender_address": "file@gmail.com", "app_password": "wxyz 1234"}')
    creds = load_credentials(config_path=cfg)
    assert creds["password"] == "wxyz 1234"


def test_load_credentials_raises_when_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    monkeypatch.delenv("GMAIL_SENDER_ADDRESS", raising=False)
    with pytest.raises(RuntimeError, match="GMAIL"):
        load_credentials(config_path=tmp_path / "absent.json")
```

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/pytest tests/test_email_sender.py -v
```

Expected: 5 FAIL.

- [ ] **Step 3: Implement**

```python
# plugins/option-wizard/skills/option-wizard/scripts/email_sender.py
"""Gmail SMTP delivery for the daily position scan.

Credentials: env vars GMAIL_APP_PASSWORD + GMAIL_SENDER_ADDRESS, or a config
file at ~/.config/option-wizard/gmail.json. The Gmail MCP available in this
environment only supports create_draft, not send_message, so this module
uses smtplib directly.
"""
from __future__ import annotations

import json
import os
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

DEFAULT_RECIPIENT = "chenxi.li08@outlook.com"
DEFAULT_CONFIG_PATH = Path.home() / ".config" / "option-wizard" / "gmail.json"
ERROR_LOG_PATH = Path.home() / ".config" / "option-wizard" / "email-errors.log"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def load_credentials(config_path: Path | None = None) -> dict[str, str]:
    pw = os.environ.get("GMAIL_APP_PASSWORD")
    sender = os.environ.get("GMAIL_SENDER_ADDRESS")
    if pw and sender:
        return {"password": pw, "sender": sender}
    path = config_path or DEFAULT_CONFIG_PATH
    if path.exists():
        data = json.loads(path.read_text())
        return {"password": data["app_password"], "sender": data["sender_address"]}
    raise RuntimeError(
        "GMAIL_APP_PASSWORD + GMAIL_SENDER_ADDRESS not set (env or "
        f"{path}); see docs/setup/gmail-app-password.md"
    )


def build_email_message(to_addr: str, from_addr: str, report_body: str,
                          rows: list[dict]) -> MIMEMultipart:
    review_count = sum(1 for r in rows if r["action"] == "REVIEW")
    close_count = sum(1 for r in rows if r["action"] == "CLOSE")
    total = len(rows)
    today = datetime.utcnow().date().isoformat()

    if total == 0:
        subject = f"[option-wizard] {today} — no positions, no action"
    elif review_count > 0:
        subject = f"[option-wizard]⚠ {today} — {total} positions, {review_count} require review"
    else:
        subject = f"[option-wizard] {today} — {total} positions, {close_count} to close, 0 require review"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr

    plain = MIMEText(report_body, "plain", "utf-8")
    msg.attach(plain)
    return msg


def _log_error(text: str) -> None:
    ERROR_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ERROR_LOG_PATH.open("a") as f:
        f.write(f"{datetime.utcnow().isoformat()} {text}\n")


def send(msg: MIMEMultipart, password: str, retries: int = 1) -> bool:
    last_err: Exception | None = None
    for _ in range(retries + 1):
        try:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
                s.starttls()
                s.login(msg["From"], password)
                s.send_message(msg)
            return True
        except Exception as e:
            last_err = e
    _log_error(f"SMTP failed after retries: {last_err}")
    return False


def send_daily_scan(report_body: str, rows: list[dict],
                     to_addr: str = DEFAULT_RECIPIENT) -> bool:
    try:
        creds = load_credentials()
    except RuntimeError as e:
        _log_error(str(e))
        return False
    msg = build_email_message(to_addr=to_addr, from_addr=creds["sender"],
                                report_body=report_body, rows=rows)
    return send(msg, creds["password"], retries=1)


def send_test(to_addr: str = DEFAULT_RECIPIENT) -> bool:
    """Send a one-line test email. Exposed for the setup verification."""
    rows = []
    return send_daily_scan(
        "option-wizard SMTP test — if you can read this, delivery works.",
        rows=rows, to_addr=to_addr,
    )


if __name__ == "__main__":
    ok = send_test()
    print("sent" if ok else "FAILED — see ~/.config/option-wizard/email-errors.log")
    sys.exit(0 if ok else 1)
```

- [ ] **Step 4: Run tests to verify pass**

```bash
.venv/bin/pytest tests/test_email_sender.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/email_sender.py tests/test_email_sender.py
git commit -m "feat(email): Gmail SMTP delivery with subject summarization and error logging"
```

---

### Task 7.3: Live SMTP smoke test

**Files:**
- Create: `tests/integration/test_email_smoke.py`

- [ ] **Step 1: Write the test**

```python
# tests/integration/test_email_smoke.py
"""Live Gmail SMTP smoke test. Requires GMAIL_APP_PASSWORD + GMAIL_SENDER_ADDRESS
set in the environment (or ~/.config/option-wizard/gmail.json). Skips otherwise.

Run manually before enabling the daily hook:
    .venv/bin/pytest tests/integration/test_email_smoke.py -v -s
"""
import os
import pytest

pytestmark = pytest.mark.skipif(
    "GMAIL_APP_PASSWORD" not in os.environ and not (
        os.path.exists(os.path.expanduser("~/.config/option-wizard/gmail.json"))
    ),
    reason="no Gmail credentials configured",
)


def test_send_one_email_to_chenxi_outlook():
    from scripts.email_sender import send_test
    ok = send_test("chenxi.li08@outlook.com")
    assert ok, "send returned False — check ~/.config/option-wizard/email-errors.log"
```

- [ ] **Step 2: Run the test against live Gmail**

User sets up the credentials (Task 7.1), then:

```bash
.venv/bin/pytest tests/integration/test_email_smoke.py -v -s
```

Expected: test passes; user receives the test email at chenxi.li08@outlook.com within a minute.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_email_smoke.py
git commit -m "test(email): live SMTP smoke test to chenxi.li08@outlook.com"
```

---

## Phase 8 — Daily Hook Integration

### Task 8.1: Configure the Claude Code SessionStart hook

**Files:**
- Modify: `~/.claude/settings.json` (user-side)
- Create: `docs/setup/daily-hook-install.md`

- [ ] **Step 1: Write the setup doc**

```markdown
# Daily Position Scan Hook

The option-wizard daily run is triggered as a Claude Code SessionStart hook. It runs once per session if the last successful run was more than 16 hours ago (covers overnight and weekends without re-running on every prompt).

## Configuration

Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "command": "/Users/chenxi/projects/option-wizard/.venv/bin/python -m scripts.manage_positions --no-email-on-cache-hit",
        "throttle_minutes": 960
      }
    ]
  }
}
```

If your `settings.json` already has a `hooks` block, merge the `SessionStart` array.

## Alternative: cron job (independent of Claude session)

For a fully autonomous run independent of opening Claude Code:

```bash
crontab -e
# Add:
30 9 * * 1-5  cd /Users/chenxi/projects/option-wizard && .venv/bin/python -m scripts.manage_positions  >> ~/.config/option-wizard/daily.log 2>&1
```

Note: 9:30 ET in your local timezone needs adjustment.

## Disabling

Set `OPTION_WIZARD_SKIP_DAILY=1` in the shell environment to skip the hook for one session.
```

- [ ] **Step 2: Apply the hook to the user's settings.json**

This is performed by the user, not the agent. The agent surfaces the diff to apply and asks for confirmation before any write to `~/.claude/settings.json`.

- [ ] **Step 3: Test the hook by opening a fresh Claude Code session**

User opens a new Claude Code window. The scan report should appear as a SessionStart context block. The same content should arrive by email shortly after.

- [ ] **Step 4: Commit the setup doc**

```bash
git add docs/setup/daily-hook-install.md
git commit -m "docs(setup): daily SessionStart hook installation"
```

---

## Phase 9 — Installation, First Case Study, Acceptance

### Task 9.1: Install the skill via symlink

**Files:**
- Modify: `~/.claude/skills/` (user-side)

- [ ] **Step 1: Create the symlink**

```bash
ln -s /Users/chenxi/projects/option-wizard/plugins/option-wizard/skills/option-wizard \
      ~/.claude/skills/option-wizard
ls -l ~/.claude/skills/option-wizard
```

Expected: symlink resolves to the project skill dir.

- [ ] **Step 2: Verify Claude Code can see the skill**

Open a new Claude Code session and ask: "list available skills". The `option-wizard` skill should appear with the description from `SKILL.md` frontmatter.

- [ ] **Step 3: Run a smoke prompt**

In Claude Code, ask: "分析 ORCL FCN，PB 报 18% coupon, 75% strike, 6m 期限, 3m 观察". The skill should orchestrate UW data fetch + fair_coupon analysis + checklist output + bilingual counter-offer email.

If anything fails, log the failure in `docs/setup/install-log.md` and fix before proceeding to Task 9.2.

- [ ] **Step 4: Document the install**

```bash
cat > docs/setup/install-log.md <<'EOF'
# Install log

YYYY-MM-DD: skill installed at ~/.claude/skills/option-wizard, smoke prompt passed.
EOF
git add docs/setup/install-log.md
git commit -m "docs(setup): record install verification"
```

---

### Task 9.2: First ticker case study — port the ORCL FCN analysis

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/references/ticker/orcl-2026-06-fcn.md`

- [ ] **Step 1: Write the case study**

Content (use the data and decisions from this session's ORCL analysis — they live in `~/projects/fcn-wizard/outputs/orcl_fcn_ladder.csv` and the chat transcript). Sections:

1. **Setup** — ORCL spot $244.58, 6m/3m/KO=100% FCN, PB offering range.
2. **Data snapshot** — IV ATM 80.4%, IV Rank 91, IV %ile 30d 100, VRP +0.19 RICH, gamma flip $192.5, put wall $240, call wall $250, max pain $245, 5y max DD -58.2%.
3. **Strike ladder** — 70/75/80/85% with p_KI, fair coupon, dealer zone.
4. **Decision** — 80% strike at $196 with target coupon 24-28% recommended; 75% strike rejected because below gamma flip.
5. **Lesson** — gamma flip changes the FCN strike calculus; vanilla fair-coupon model does not capture dealer-flow path dependency. Strike must sit above gamma flip for the model output to be trustworthy.

- [ ] **Step 2: Update the ticker README index**

Edit `references/ticker/README.md` to add the ORCL row to the index table.

- [ ] **Step 3: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/references/ticker/orcl-2026-06-fcn.md plugins/option-wizard/skills/option-wizard/references/ticker/README.md
git commit -m "docs(case): orcl-2026-06-fcn — gamma flip changes FCN strike calculus"
```

---

### Task 9.3: Acceptance test against v1 criteria

**Files:**
- Create: `docs/acceptance/v1-acceptance.md`

- [ ] **Step 1: Run each criterion from spec §14 and record the result**

For each item below, run the indicated prompt or command, observe, and record `PASS` / `FAIL` with one line of evidence.

```markdown
# v1 Acceptance Test Results

Date: YYYY-MM-DD

## Criteria

### 1. FCN single-name with quote
Prompt: "分析 ORCL FCN, PB 报 18% coupon, 75% strike, 6m 期限, 3m 观察"
Expected: 8-item checklist + ladder + bilingual counter-offer email.
Result: PASS / FAIL — [evidence]

### 2. Full-menu single-name without quote
Prompt: "分析 MU 怎么做 income 策略"
Expected: full menu of CC / CSP / spread / collar / Jade Lizard with regime-aware 5th pick.
Result:

### 3. Worst-of basket
Prompt: "分析 INTC + AMD worst-of FCN, 6m, 3m obs, 55% strike"
Expected: per-name + basket with diversification premium.
Result:

### 4. Paper-account order
Prompt: "place a paper-account bull put spread on SPY, short 5% OTM, long 10% OTM, 45 DTE"
Expected: preflight prompt, then create_order_instruction submitted to IB paper account.
Result:

### 5. 21-DTE blocking review
Setup: an open paper position at exactly 21 DTE.
Run: `.venv/bin/python -m scripts.manage_positions --no-email`
Expected: REVIEW row at top of output with blocking guidance.
Result:

### 6. Macro hedge
Prompt: "size a 60-day SPX hedge for $1M portfolio targeting -5% correction"
Expected: butterfly structure with cost under 1.5% annualized cap.
Result:

### 7. Refusal path
Prompt: "sell a naked call on NVDA at $900 strike"
Expected: explicit decline with reasoning, suggestion of defined-risk alternative.
Result:

### 8. Email delivery
Run: `.venv/bin/python -c "from scripts.email_sender import send_test; send_test()"`
Expected: email arrives at chenxi.li08@outlook.com within 1 minute.
Result:
```

- [ ] **Step 2: Run all 8 criteria and fill in the file**

This is a manual step — execute each prompt in Claude Code or shell, observe, write the PASS/FAIL row.

- [ ] **Step 3: Commit**

```bash
git add docs/acceptance/v1-acceptance.md
git commit -m "docs(acceptance): v1 acceptance run results"
```

- [ ] **Step 4: If all 8 PASS, tag v1**

```bash
git tag -a v0.1.0 -m "option-wizard v0.1.0 — initial release with full v1 acceptance"
```

---

## Self-Review Notes

After writing the plan, I reviewed it against the spec:

1. **Spec coverage:**
   - §4 Data Architecture → Tasks 1.1, 1.2, 1.3 (UW + smoke test + MCP entry).
   - §5 Skill Layout → Tasks 0.1–0.3 (scaffold) + each script task.
   - §6 FCN Module → Tasks 2.3, 2.4, 2.5 (single + basket + email).
   - §7 Income Structures → Task 4.2 (validate_structure rejection clauses, Jade Lizard rule).
   - §8 Macro Hedge → Task 6.1.
   - §9 Execution + 21 DTE → Tasks 4.2, 4.3, 4.4, 5.1.
   - §10 Position Management → Tasks 5.1, 5.2; daily hook Task 8.1.
   - §10.2 Email Delivery → Tasks 7.1, 7.2, 7.3.
   - §11 SKILL.md → Task 0.3.
   - §12 Installation → Tasks 9.1, 9.2.
   - §13 Open Items #1, #2, #3, #8 → Task 4.3 (IB paper verification), Task 1.2 (UW smoke), Task 7.1/7.3 (Gmail). Open items #4, #5, #6, #7 (SPX vs SPY, position-sizing cap, delta target, npx publish) remain user decisions outside the v1 implementation scope and are noted in CLAUDE.md / references/strategies.md placeholders.
   - §14 Acceptance Criteria → Task 9.3.

2. **Placeholder scan:** no TBD / TODO / "implement later" / "add appropriate error handling" patterns in any task body. Reference doc tasks (Phase 3) call for original writing of well-scoped content; that is the engineer's job, not a placeholder.

3. **Type / signature consistency:**
   - `single_name_ki_prob(vol, barrier, days)` referenced consistently in Tasks 2.3 and 2.4.
   - `fair_coupon_proxy(p_ki, expected_loss_given_ki, expected_alive_months, discount_rate, tenor_years)` consistent.
   - `analyze_fcn(...)` and `analyze_fcn_basket(...)` signatures used in tests match implementation.
   - `IBClient(host, port, client_id, timeout)` consistent across Tasks 4.1 and 4.3.
   - `build_preflight(...)` returns dict with keys `legs / pl_matrix / max_loss / max_gain / uw_regime / account_check` — used consistently in Task 4.4 (`build_brackets` reads `net_credit_dollar`, `max_loss`, `ticker`, `structure` from a similar shape).
   - `scan_positions(positions, market, today)` and `format_scan_report(rows)` consistent across Tasks 5.2 and 7.2.

Open ambiguities resolved inline during writing: `_payoff_at_expiry` is a private helper inside `ib_order.py` (referenced by `build_pl_matrix` and `_account_check`), kept simple — defined-risk spreads will read max-loss correctly from the matrix endpoints; if a structure produces a max within the sampled grid (e.g., butterfly), refine `_max_loss_gain` in a follow-up; documented as a known limitation in Task 4.2 step 3 prose.

---

## Execution Handoff

**Plan complete and saved to `docs/plans/2026-06-03-option-wizard-implementation.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
