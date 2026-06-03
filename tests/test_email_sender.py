import pytest
from scripts.email_sender import build_email_message, load_credentials


def test_build_email_message_includes_subject_with_counts():
    rows = [
        {"symbol": "ORCL", "action": "REVIEW", "dte": 20, "rationale": "..."},
        {"symbol": "AMD", "action": "HOLD", "dte": 50, "rationale": "..."},
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
