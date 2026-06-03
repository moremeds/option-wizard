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


def build_email_message(
    to_addr: str,
    from_addr: str,
    report_body: str,
    rows: list[dict],
) -> MIMEMultipart:
    review_count = sum(1 for r in rows if r["action"] == "REVIEW")
    close_count = sum(1 for r in rows if r["action"] == "CLOSE")
    total = len(rows)
    today = datetime.utcnow().date().isoformat()

    if total == 0:
        subject = f"[option-wizard] {today} — no positions, no action"
    elif review_count > 0:
        subject = (
            f"[option-wizard]⚠ {today} — {total} positions, "
            f"{review_count} require review"
        )
    else:
        subject = (
            f"[option-wizard] {today} — {total} positions, "
            f"{close_count} to close, 0 require review"
        )

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


def send_daily_scan(
    report_body: str,
    rows: list[dict],
    to_addr: str = DEFAULT_RECIPIENT,
) -> bool:
    try:
        creds = load_credentials()
    except RuntimeError as e:
        _log_error(str(e))
        return False
    msg = build_email_message(
        to_addr=to_addr,
        from_addr=creds["sender"],
        report_body=report_body,
        rows=rows,
    )
    return send(msg, creds["password"], retries=1)


def send_test(to_addr: str = DEFAULT_RECIPIENT) -> bool:
    """Send a one-line test email. Exposed for the setup verification."""
    rows = []
    return send_daily_scan(
        "option-wizard SMTP test — if you can read this, delivery works.",
        rows=rows,
        to_addr=to_addr,
    )


if __name__ == "__main__":
    ok = send_test()
    print("sent" if ok else "FAILED — see ~/.config/option-wizard/email-errors.log")
    sys.exit(0 if ok else 1)
