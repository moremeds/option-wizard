from unittest.mock import MagicMock, patch

import pytest
from scripts.xenon import main


def test_cli_calls_get_with_path_and_params(capsys):
    fake = MagicMock()
    fake.get.return_value = {"symbol": "AAPL", "bids": []}
    with patch("scripts.xenon.XenonClient", return_value=fake):
        rc = main(["/market-depth", "-p", "symbol=AAPL", "-p", "num_rows=5"])
    assert rc == 0
    fake.get.assert_called_once_with(
        "/market-depth", {"symbol": "AAPL", "num_rows": "5"}
    )
    out = capsys.readouterr().out
    assert '"symbol": "AAPL"' in out


def test_cli_no_params(capsys):
    fake = MagicMock()
    fake.get.return_value = {"positions": []}
    with patch("scripts.xenon.XenonClient", return_value=fake):
        rc = main(["/portfolio"])
    assert rc == 0
    fake.get.assert_called_once_with("/portfolio", None)


def test_cli_bad_param_errors():
    with patch("scripts.xenon.XenonClient"):
        with pytest.raises(SystemExit):
            main(["/portfolio", "-p", "noequalssign"])
