from unittest.mock import MagicMock, patch

import pytest
from scripts._clients.fred import (
    FREDClient,
    add_fred_signals_to_snapshot,
    hy_oas_signal,
)


def test_fred_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="FRED_API_KEY"):
        FREDClient(api_key=None)


def test_fred_client_observations_calls_correct_url(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "test_key")
    with patch("scripts._clients.fred.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"observations": [{"date": "2026-06-01", "value": "2.50"}]},
        )
        client = FREDClient()
        result = client.observations("BAMLH0A0HYM2", observation_start="2026-05-01")
        called_url = mock_get.call_args[0][0]
        called_params = mock_get.call_args[1]["params"]
        assert called_url == "https://api.stlouisfed.org/fred/series/observations"
        assert called_params["series_id"] == "BAMLH0A0HYM2"
        assert called_params["api_key"] == "test_key"
        assert called_params["file_type"] == "json"
        assert called_params["observation_start"] == "2026-05-01"
        assert len(result) == 1


def _make_mock_obs(values: list[float], start_date: str = "2026-05-01") -> list[dict]:
    """Helper: build FRED-shape observations list from float values, one per day."""
    from datetime import date, timedelta

    start = date.fromisoformat(start_date)
    return [
        {"date": (start + timedelta(days=i)).isoformat(), "value": str(v)}
        for i, v in enumerate(values)
    ]


def test_hy_oas_signal_flat_when_steady(monkeypatch):
    """30 days of flat 3.0 → flat trend (mean_7 == mean_30 = 3.0, so
    neither rising nor falling regardless of percentile)."""
    monkeypatch.setenv("FRED_API_KEY", "test_key")
    values = [3.0] * 40
    mock_obs = _make_mock_obs(values)
    with patch.object(FREDClient, "observations", return_value=mock_obs):
        sig = hy_oas_signal(today="2026-06-10")
    assert sig["hy_oas_trend"] == "flat"
    assert sig["hy_oas"] == 3.0


def test_hy_oas_signal_rising_when_climbing_to_high_pct(monkeypatch):
    """Last 7 days clearly above 30d mean AND current at 100th percentile."""
    monkeypatch.setenv("FRED_API_KEY", "test_key")
    # 23 days at 2.5, then 7 days climbing 3.0 → 4.0
    values = [2.5] * 23 + [3.0, 3.2, 3.4, 3.6, 3.7, 3.8, 4.0]
    mock_obs = _make_mock_obs(values)
    with patch.object(FREDClient, "observations", return_value=mock_obs):
        sig = hy_oas_signal(today="2026-06-10")
    assert sig["hy_oas_trend"] == "rising"
    assert sig["hy_oas"] == 4.0
    assert sig["hy_oas_30d_pct"] >= 80.0


def test_hy_oas_signal_falling_when_declining_to_low_pct(monkeypatch):
    """Last 7 days clearly below 30d mean AND current at low percentile."""
    monkeypatch.setenv("FRED_API_KEY", "test_key")
    # 23 days at 4.0, then 7 days falling 3.5 → 2.0
    values = [4.0] * 23 + [3.5, 3.2, 2.9, 2.6, 2.4, 2.2, 2.0]
    mock_obs = _make_mock_obs(values)
    with patch.object(FREDClient, "observations", return_value=mock_obs):
        sig = hy_oas_signal(today="2026-06-10")
    assert sig["hy_oas_trend"] == "falling"
    assert sig["hy_oas"] == 2.0
    assert sig["hy_oas_30d_pct"] <= 20.0


def test_hy_oas_signal_skips_missing_values(monkeypatch):
    """FRED uses '.' for missing — must be filtered before computing."""
    monkeypatch.setenv("FRED_API_KEY", "test_key")
    obs = [
        {"date": "2026-05-01", "value": "3.0"},
        {"date": "2026-05-02", "value": "."},  # missing
        {"date": "2026-05-03", "value": "3.1"},
        {"date": "2026-05-04", "value": "3.05"},
    ] + _make_mock_obs([3.0] * 30, start_date="2026-05-11")
    with patch.object(FREDClient, "observations", return_value=obs):
        sig = hy_oas_signal(today="2026-06-10")
    # Should not crash, should not include "."
    assert sig["hy_oas"] == 3.0  # last valid
    assert all(isinstance(v, float) for _, v in sig["history"])


def test_hy_oas_30d_pct_uses_midrank_in_flat_market(monkeypatch):
    """Pass-2 C-MED2: percentile must use midrank so flat/clustered data
    doesn't return 100% (the old `v <= current` rank gave 100 for any tie).

    For 30 identical values: percentile should be 50 (median position),
    NOT 100. The trend logic still says "flat" either way (mean_7 ==
    mean_30), but the raw pct is exposed downstream via
    add_fred_signals_to_snapshot and the orchestrator's regime gates."""
    monkeypatch.setenv("FRED_API_KEY", "test_key")
    values = [3.0] * 40
    mock_obs = _make_mock_obs(values)
    with patch.object(FREDClient, "observations", return_value=mock_obs):
        sig = hy_oas_signal(today="2026-06-10")
    # Flat data → midrank gives pct = 50 (every tie is half-weight).
    assert sig["hy_oas_30d_pct"] == 50.0, (
        f"Flat-data percentile should be 50 (midrank), got {sig['hy_oas_30d_pct']}"
    )
    # Trend still "flat" because mean_7 == mean_30
    assert sig["hy_oas_trend"] == "flat"


def test_hy_oas_30d_pct_centers_at_50_when_current_is_median(monkeypatch):
    """Midrank: current at the median position of distinct values → pct ≈ 50."""
    monkeypatch.setenv("FRED_API_KEY", "test_key")
    # 30 values: 15 below current (2.5), current (3.0), 14 above (3.5)
    values = [2.5] * 15 + [3.5] * 14 + [3.0]
    mock_obs = _make_mock_obs(values)
    with patch.object(FREDClient, "observations", return_value=mock_obs):
        sig = hy_oas_signal(today="2026-06-10")
    # Current=3.0: below=15, equal=1, midrank = (15 + 0.5)/30 * 100 = 51.67
    assert 45 < sig["hy_oas_30d_pct"] < 55, (
        f"Median-position percentile should be ≈50, got {sig['hy_oas_30d_pct']}"
    )


def test_hy_oas_signal_raises_when_no_valid_data(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "test_key")
    with patch.object(FREDClient, "observations", return_value=[]):
        with pytest.raises(RuntimeError, match="No valid HY OAS"):
            hy_oas_signal(today="2026-06-10")


def test_add_fred_signals_to_snapshot_creates_regime_check(monkeypatch):
    """When snapshot has no regime_check, the helper creates it."""
    monkeypatch.setenv("FRED_API_KEY", "test_key")
    mock_obs = _make_mock_obs([3.0] * 35)
    with patch.object(FREDClient, "observations", return_value=mock_obs):
        snap = {"spot": 200.0, "iv_atm_90d": 0.32}
        result = add_fred_signals_to_snapshot(snap, today="2026-06-10")
    assert "regime_check" in result
    rc = result["regime_check"]
    assert "hy_oas" in rc
    assert "hy_oas_30d_pct" in rc
    assert "hy_oas_trend" in rc
    assert "hy_oas_date" in rc


def test_add_fred_signals_to_snapshot_preserves_existing_regime_check(monkeypatch):
    """When snapshot already has regime_check, the helper MERGES, doesn't replace."""
    monkeypatch.setenv("FRED_API_KEY", "test_key")
    mock_obs = _make_mock_obs([3.0] * 35)
    with patch.object(FREDClient, "observations", return_value=mock_obs):
        snap = {
            "spot": 200.0,
            "iv_atm_90d": 0.32,
            "regime_check": {"vix": 16.0, "vix9d": 17.5, "vvix": 145.0},
        }
        result = add_fred_signals_to_snapshot(snap, today="2026-06-10")
    rc = result["regime_check"]
    # Original keys preserved
    assert rc["vix"] == 16.0
    assert rc["vvix"] == 145.0
    # New keys added
    assert "hy_oas" in rc
    assert "hy_oas_trend" in rc
