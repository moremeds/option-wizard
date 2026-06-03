"""Live Gmail SMTP smoke test. Requires GMAIL_APP_PASSWORD + GMAIL_SENDER_ADDRESS
set in the environment (or ~/.config/option-wizard/gmail.json). Skips otherwise.

Run manually before enabling the daily hook:
    .venv/bin/pytest tests/integration/test_email_smoke.py -v -s
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    "GMAIL_APP_PASSWORD" not in os.environ
    and not os.path.exists(os.path.expanduser("~/.config/option-wizard/gmail.json")),
    reason="no Gmail credentials configured",
)


def test_send_one_email_to_chenxi_outlook():
    from scripts.email_sender import send_test

    ok = send_test("chenxi.li08@outlook.com")
    assert ok, "send returned False — check ~/.config/option-wizard/email-errors.log"
