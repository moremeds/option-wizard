from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from scripts._clients.cboe import CBOEClient

# Frozen REAL RUT daily closes, pulled live 2026-07-13 from CBOE's public
# daily_prices CSV feed (see cboe.py module docstring).
RUT_CSV = (
    "DATE,RUT\n07/08/2026,2956.388700\n07/09/2026,2992.541400\n07/10/2026,2977.805200\n"
)


def test_daily_closes_parses_csv():
    with patch("scripts._clients.cboe.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, text=RUT_CSV)
        result = CBOEClient().daily_closes("RUT")
        called_url = mock_get.call_args[0][0]
        assert "RUT_History.csv" in called_url
        assert result == {
            date(2026, 7, 8): pytest.approx(2956.3887),
            date(2026, 7, 9): pytest.approx(2992.5414),
            date(2026, 7, 10): pytest.approx(2977.8052),
        }


def test_daily_closes_skips_malformed_rows():
    csv_with_junk = (
        "DATE,RUT\n"
        "07/08/2026,2956.388700\n"
        "\n"
        "garbage\n"
        "07/09/2026,2992.541400\n"
        "07/10/2026,2977.805200\n"
    )
    with patch("scripts._clients.cboe.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, text=csv_with_junk)
        result = CBOEClient().daily_closes("RUT")
        assert result == {
            date(2026, 7, 8): pytest.approx(2956.3887),
            date(2026, 7, 9): pytest.approx(2992.5414),
            date(2026, 7, 10): pytest.approx(2977.8052),
        }
