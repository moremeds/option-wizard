from unittest.mock import MagicMock, patch

import pytest
from scripts._clients.uw import UWClient


def test_uw_client_sets_authorization_header(monkeypatch):
    monkeypatch.setenv("UW_API_KEY", "test_token_123")
    client = UWClient()
    assert client._headers["Authorization"] == "Bearer test_token_123"
    assert client._headers["UW-CLIENT-API-ID"] == "100001"


def test_uw_client_iv_rank_calls_correct_endpoint():
    with patch("scripts._clients.uw.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200, json=lambda: {"data": [{"iv_rank": 91}]}
        )
        client = UWClient(api_key="x")
        result = client.iv_rank("ORCL")
        called_url = mock_get.call_args[0][0]
        assert "/api/stock/ORCL/iv-rank" in called_url
        assert result == {"data": [{"iv_rank": 91}]}


def test_uw_client_missing_key_raises(monkeypatch):
    monkeypatch.delenv("UW_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="UW_API_KEY"):
        UWClient(api_key=None)
