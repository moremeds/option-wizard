"""Tests for the TV fallback client used when IB returns no quote."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import patch

from scripts._clients import tv


def _fake_run(stdout: str, returncode: int = 0):
    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0], returncode=returncode, stdout=stdout, stderr=""
        )

    return runner


def setup_function() -> None:
    tv.clear_cache()


def test_get_option_quote_returns_mid_and_delta_on_hit():
    chain = [
        {"strike": 696, "bid": 3.31, "ask": 3.56, "mid": 3.435, "delta": -0.129},
        {"strike": 700, "bid": 3.80, "ask": 4.10, "mid": 3.95, "delta": -0.150},
    ]
    with patch("subprocess.run", side_effect=_fake_run(json.dumps(chain))):
        q = tv.get_option_quote("QQQ", "20260626", 696, "P")
    assert q is not None
    assert q["mid"] == 3.435
    assert q["delta"] == -0.129
    assert q["source"] == "tv"


def test_get_option_quote_returns_none_when_strike_missing():
    chain = [{"strike": 700, "bid": 3.80, "ask": 4.10, "mid": 3.95, "delta": -0.15}]
    with patch("subprocess.run", side_effect=_fake_run(json.dumps(chain))):
        # Force the resolver to only try one exchange so the second probe
        # doesn't re-run with the same mock and look like a fresh chain.
        with patch.object(tv, "_resolve_exchange", return_value=["NASDAQ"]):
            q = tv.get_option_quote("QQQ", "20260626", 696, "P")
    assert q is None


def test_get_option_quote_handles_subprocess_failure():
    with patch("subprocess.run", side_effect=_fake_run("", returncode=1)):
        q = tv.get_option_quote("GLD", "20260702", 408, "P")
    assert q is None


def test_get_option_quote_handles_opencli_missing():
    with patch("subprocess.run", side_effect=FileNotFoundError):
        q = tv.get_option_quote("QQQ", "20260626", 696, "P")
    assert q is None


def test_call_right_translates_to_tv_call():
    chain = [{"strike": 595, "bid": 176.0, "ask": 179.7, "mid": 177.85, "delta": 0.86}]
    captured = {}

    def capturing_runner(*args, **kwargs):
        captured["cmd"] = args[0]
        return subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout=json.dumps(chain), stderr=""
        )

    with patch("subprocess.run", side_effect=capturing_runner):
        q = tv.get_option_quote("QQQ", "20270115", 595, "C")
    assert q is not None
    # Verify --type call was passed to opencli (not "C", not "put").
    assert "--type" in captured["cmd"]
    type_idx = captured["cmd"].index("--type")
    assert captured["cmd"][type_idx + 1] == "call"
