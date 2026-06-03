from unittest.mock import MagicMock, patch

from scripts._clients.ib import IBClient


def test_ib_client_default_port_is_live():
    with patch("scripts._clients.ib.IB"):
        client = IBClient()
        assert client.host == "127.0.0.1"
        assert client.port == 4001
        # client_id is derived from pid; just assert it's an int in the expected band
        assert isinstance(client.client_id, int)
        assert 99 <= client.client_id < 199


def test_ib_client_connects_with_explicit_settings():
    with patch("scripts._clients.ib.IB") as mock_ib_cls:
        mock_ib = MagicMock()
        mock_ib.isConnected.return_value = False
        mock_ib_cls.return_value = mock_ib
        client = IBClient(host="localhost", port=4002, client_id=77)
        client.connect()
        mock_ib.connect.assert_called_once_with(
            "localhost", 4002, clientId=77, timeout=10
        )


def test_ib_client_get_positions_returns_list():
    with patch("scripts._clients.ib.IB") as mock_ib_cls:
        mock_ib = MagicMock()
        mock_ib.isConnected.return_value = True
        mock_ib.positions.return_value = [
            MagicMock(contract=MagicMock(symbol="ORCL"), position=5)
        ]
        mock_ib_cls.return_value = mock_ib
        client = IBClient()
        result = client.get_positions()
        assert isinstance(result, list)
