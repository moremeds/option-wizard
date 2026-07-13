"""Failure-alert path: any unhandled exception inside the scan must
(a) return exit code 1, (b) email the traceback even under --no-email."""

import scripts.manage_positions as mp


class _BoomClient:
    def __init__(self, *a, **k):
        pass

    def ib_portfolio(self):
        raise RuntimeError("xenon down (simulated)")


def test_scan_failure_emails_traceback_and_exits_1(monkeypatch, tmp_path):
    sent = {}

    def fake_alert(body):
        sent["body"] = body
        return True

    monkeypatch.setattr(mp, "XenonClient", _BoomClient)
    monkeypatch.setattr(mp, "LOCK_PATH", tmp_path / "test.lock")
    import scripts.email_sender as es

    monkeypatch.setattr(es, "send_failure_alert", fake_alert)

    rc = mp.main(["--no-email"])

    assert rc == 1
    assert "RuntimeError: xenon down (simulated)" in sent["body"]


def test_failure_alert_subject_is_not_the_no_action_subject():
    from scripts.email_sender import build_failure_message

    msg = build_failure_message("to@x.com", "from@x.com", "Traceback ...")
    assert "FAILED" in msg["Subject"]
    assert "no action" not in msg["Subject"]


def test_clean_run_unaffected(monkeypatch, tmp_path):
    # audit-only happy path with an empty book must still return 0
    class _EmptyClient:
        def __init__(self, *a, **k):
            pass

        def ib_portfolio(self):
            # Real xenon /portfolio shape (see tests/test_xenon_normalize.py
            # IB_PORTFOLIO fixture): account_summary key is "cash", positions
            # is a list of ticker dicts with legs.
            return {"positions": [], "account_summary": {"cash": 0.0}}

    monkeypatch.setattr(mp, "XenonClient", _EmptyClient)
    monkeypatch.setattr(mp, "LOCK_PATH", tmp_path / "test.lock")
    rc = mp.main(["--audit-only", "--no-email"])
    assert rc == 0
