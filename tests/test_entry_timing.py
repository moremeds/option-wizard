"""Tests for scripts.entry_timing."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from scripts.entry_timing import THRESHOLDS, calibrate, decide


def _fresh_ts() -> str:
    """Helper: ISO timestamp ~30s ago (well within freshness gate)."""
    return (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()


BASE_SNAPSHOT = {
    "spot": 2300.0,
    "time_et": "10:00",
    "vix": 14.0,
    "vix1d": 13.5,
    "vix9d": 14.0,
    "premarket_gap": 0.003,
    "gex_flip": 2250.0,
    "net_dealer_gex": 1.0e9,
    "odte_put_premium": 4.0e6,
    "odte_call_premium": 4.0e6,
    "is_fomc_day": False,
    "is_monday_open": False,
    "is_opex_friday": False,
}


def _snap(**overrides):
    """Build a snapshot with fresh timestamp + overrides."""
    return {**BASE_SNAPSHOT, "snapshot_taken_at": _fresh_ts(), **overrides}


# --- Tasks 10+11 — decision tree branches ---


def test_thresholds_is_dict():
    assert isinstance(THRESHOLDS, dict)
    assert "vix_abort_high" in THRESHOLDS


def test_vix_event_backwardation_aborts():
    out = decide(_snap(vix=22.0, vix1d=24.0, vix9d=22.5), mode="csp")
    assert out["action"] == "abort"
    assert out["triggered_threshold"] == "vix_event_backwardation"


def test_vix_too_low_aborts():
    out = decide(_snap(vix=10.5, vrp_label="CHEAP"), mode="csp")
    assert out["action"] == "abort"
    assert out["triggered_threshold"] == "vix_too_low_cheap_vrp"


def test_premarket_gap_csp_waits():
    out = decide(_snap(premarket_gap=-0.015), mode="csp")
    assert out["action"] == "wait_minutes"
    assert out["triggered_threshold"] == "premarket_gap"


def test_premarket_gap_rut_uses_higher_threshold():
    # 1.2% < 1.5% RUT threshold → premarket gap does NOT fire
    out = decide(_snap(premarket_gap=-0.012), mode="rut_calendar")
    assert out["triggered_threshold"] != "premarket_gap"


def test_gex_short_gamma_with_flip_proximity_waits_eod():
    out = decide(_snap(net_dealer_gex=-2.0e9, gex_flip=2295.0, spot=2300.0), mode="csp")
    assert out["action"] == "wait_eod"
    assert out["triggered_threshold"] == "gex_short_flip_proximity"


def test_odte_whale_put_buyer_waits():
    out = decide(_snap(odte_put_premium=15.0e6, odte_call_premium=3.0e6), mode="csp")
    assert out["action"] == "wait_minutes"
    assert out["triggered_threshold"] == "odte_put_buyer_imbalance"


def test_csp_mode_morning_window_recommends_enter():
    out = decide(_snap(time_et="10:00"), mode="csp")
    assert out["action"] == "enter_now"
    assert out["triggered_threshold"] == "mode_window_morning"


def test_rut_calendar_mode_morning_says_wait_eod():
    out = decide(_snap(time_et="10:00"), mode="rut_calendar")
    assert out["action"] == "wait_eod"
    assert out["triggered_threshold"] == "mode_window_eod"


def test_rut_aggressive_vix_cap_blocks_above_25():
    out = decide(_snap(vix=27.0), mode="rut_aggressive")
    assert out["action"] == "abort"
    assert out["triggered_threshold"] == "aggressive_mode_vix_cap"


def test_fomc_day_override_waits_until_1430():
    out = decide(_snap(is_fomc_day=True, time_et="10:00"), mode="csp")
    assert out["action"] == "wait_minutes"
    assert out["triggered_threshold"] == "fomc_presser"


def test_monday_open_override():
    out = decide(_snap(is_monday_open=True, time_et="09:35"), mode="csp")
    assert out["action"] == "wait_minutes"
    assert out["triggered_threshold"] == "monday_open_unwind"


def test_opex_friday_csp_defers_to_eod():
    out = decide(_snap(is_opex_friday=True, time_et="13:30"), mode="csp")
    assert out["action"] == "wait_eod"
    assert out["triggered_threshold"] == "opex_friday_pin_csp"


def test_opex_friday_diagonal_anchors_max_pain():
    out = decide(_snap(is_opex_friday=True, time_et="13:30"), mode="rut_calendar")
    assert out["action"] == "enter_now"
    assert out["triggered_threshold"] == "opex_friday_anchor_max_pain"


# --- Freshness gate ---


def test_freshness_gate_rejects_stale_snapshot():
    stale = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
    snap = {**BASE_SNAPSHOT, "snapshot_taken_at": stale}
    out = decide(snap, mode="csp")
    assert out["action"] == "abort"
    assert out["triggered_threshold"] == "freshness_stale_snapshot"


def test_freshness_gate_rejects_missing_timestamp():
    # BASE_SNAPSHOT (no snapshot_taken_at)
    out = decide(BASE_SNAPSHOT, mode="csp")
    assert out["action"] == "abort"
    assert out["triggered_threshold"] == "freshness_missing_timestamp"


def test_freshness_gate_rejects_invalid_timestamp():
    snap = {**BASE_SNAPSHOT, "snapshot_taken_at": "not-an-iso-date"}
    out = decide(snap, mode="csp")
    assert out["action"] == "abort"
    assert out["triggered_threshold"] == "freshness_invalid_timestamp"


def test_freshness_gate_accepts_fresh_snapshot():
    out = decide(_snap(), mode="csp")
    assert out["triggered_threshold"] not in (
        "freshness_stale_snapshot",
        "freshness_missing_timestamp",
        "freshness_invalid_timestamp",
    )


# --- Task 12 — audit log + calibrate ---


def test_audit_log_writes_jsonl(tmp_path, monkeypatch):
    log_path = tmp_path / "log.jsonl"
    monkeypatch.setattr("scripts.entry_timing.AUDIT_LOG_PATH", str(log_path))
    decide(_snap(), mode="csp")
    assert log_path.exists()
    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["decision"] in ("enter_now", "wait_eod", "wait_minutes", "abort")
    assert parsed["mode"] == "csp"
    assert "triggered_threshold" in parsed


def test_audit_log_includes_snapshot_hash(tmp_path, monkeypatch):
    log_path = tmp_path / "log.jsonl"
    monkeypatch.setattr("scripts.entry_timing.AUDIT_LOG_PATH", str(log_path))
    decide(_snap(), mode="csp")
    parsed = json.loads(log_path.read_text().strip().splitlines()[0])
    assert "snapshot_hash" in parsed
    assert len(parsed["snapshot_hash"]) == 16  # 16 hex chars


def test_calibrate_aggregates(tmp_path, monkeypatch):
    log_path = tmp_path / "log.jsonl"
    monkeypatch.setattr("scripts.entry_timing.AUDIT_LOG_PATH", str(log_path))
    for trigger in [
        "vix_event_backwardation",
        "premarket_gap",
        "premarket_gap",
        "mode_window_morning",
        "mode_window_morning",
    ]:
        log_path.open("a").write(
            json.dumps(
                {
                    "timestamp": "2026-06-09T10:00:00Z",
                    "mode": "csp",
                    "decision": "abort" if "vix" in trigger else "enter_now",
                    "triggered_threshold": trigger,
                    "snapshot_hash": f"hash_{trigger}",
                }
            )
            + "\n"
        )
    stats = calibrate(log_path=str(log_path))
    assert stats["total_decisions"] == 5
    assert stats["per_threshold_fire_count"]["premarket_gap"] == 2
    assert "tuning_hints" in stats


def test_calibrate_reports_never_fired_thresholds(tmp_path, monkeypatch):
    """calibrate must report thresholds that never fired (count=0) with
    'never fired' hint, NOT just iterate triggers seen in log."""
    log_path = tmp_path / "log.jsonl"
    monkeypatch.setattr("scripts.entry_timing.AUDIT_LOG_PATH", str(log_path))
    for i in range(15):
        log_path.open("a").write(
            json.dumps(
                {
                    "timestamp": f"2026-06-09T{10 + i % 8:02d}:00:00Z",
                    "mode": "csp",
                    "decision": "abort",
                    "triggered_threshold": "vix_too_low_cheap_vrp",
                    "snapshot_hash": f"hash_{i}",
                }
            )
            + "\n"
        )
    stats = calibrate(log_path=str(log_path))
    assert stats["total_decisions"] == 15
    assert "freshness_stale_snapshot" in stats["per_threshold_fire_count"]
    assert stats["per_threshold_fire_count"]["freshness_stale_snapshot"] == 0
    never_fired_hints = [h for h in stats["tuning_hints"] if "NEVER FIRED" in h]
    assert len(never_fired_hints) > 5, (
        f"calibrate should flag never-fired thresholds; got {len(never_fired_hints)} "
        f"hints from {len(stats['per_threshold_fire_count'])} thresholds"
    )


def test_calibrate_no_log_returns_empty():
    """calibrate on a non-existent log path returns zero counts (no crash)."""
    stats = calibrate(log_path="/tmp/__nonexistent_log__.jsonl")
    assert stats["total_decisions"] == 0


def test_audit_log_path_resolves_within_skill_dir():
    """AUDIT_LOG_PATH must live under the skill's references/private/market/
    directory, not someone's hardcoded home path. Regression test for the
    P1 bug where the constant pinned ~/projects/option-wizard/... — broke
    audit logging for anyone not on that exact filesystem."""
    from scripts.entry_timing import AUDIT_LOG_PATH

    assert "/.worktrees/" in AUDIT_LOG_PATH or "/option-wizard/" in AUDIT_LOG_PATH
    assert AUDIT_LOG_PATH.endswith("references/private/market/entry-timing-log.jsonl")
    # The path must NOT contain ~/projects as a literal substring (i.e., must
    # have been resolved via __file__, not via os.path.expanduser on a hardcoded string)
    assert "~/projects" not in AUDIT_LOG_PATH


# --- Patch #1 — catalyst-clock event gate (live-run gap from 2026-06-09) ---


def test_event_clock_high_severity_tomorrow_aborts_csp():
    """Live-run regression: CPI tomorrow must abort, not silently pass.
    Pre-patch, only is_fomc_day was checked; today's CPI-tomorrow scenario
    proceeded through to mode_window where the morning slot green-lit entry.
    """
    out = decide(
        _snap(
            next_event_name="CPI",
            next_event_severity="HIGH",
            next_event_days_away=1,
        ),
        mode="csp",
    )
    assert out["action"] == "abort"
    assert out["triggered_threshold"] == "event_proximity_high_severity"
    assert "CPI" in out["reason"]
    assert "1d" in out["reason"]


def test_event_clock_high_severity_two_days_aborts_at_threshold_boundary():
    """event_proximity_days=2 — events 2d out must still abort."""
    out = decide(
        _snap(
            next_event_name="NFP",
            next_event_severity="HIGH",
            next_event_days_away=2,
        ),
        mode="rut_calendar",
    )
    assert out["action"] == "abort"
    assert out["triggered_threshold"] == "event_proximity_high_severity"


def test_event_clock_high_severity_three_days_passes():
    """Just outside the gate — should not abort here. Falls through to
    other gates; with default snapshot the morning window for CSP fires."""
    out = decide(
        _snap(
            next_event_name="FOMC",
            next_event_severity="HIGH",
            next_event_days_away=3,
        ),
        mode="csp",
    )
    assert out["triggered_threshold"] != "event_proximity_high_severity"


def test_event_clock_medium_severity_does_not_abort():
    """Only HIGH severity gates here. MEDIUM/LOW events flow through —
    trader's discretion via the broader catalyst check."""
    out = decide(
        _snap(
            next_event_name="Existing Home Sales",
            next_event_severity="MEDIUM",
            next_event_days_away=1,
        ),
        mode="csp",
    )
    assert out["triggered_threshold"] != "event_proximity_high_severity"


def test_event_clock_missing_fields_does_not_crash():
    """If orchestrator didn't compute the next-event triple, fall through
    cleanly — don't crash and don't infer high severity."""
    out = decide(_snap(), mode="csp")
    assert out["triggered_threshold"] != "event_proximity_high_severity"


def test_event_clock_today_zero_days_aborts():
    """next_event_days_away=0 should also abort — defense in depth in case
    is_fomc_day wasn't computed."""
    out = decide(
        _snap(
            next_event_name="CPI",
            next_event_severity="HIGH",
            next_event_days_away=0,
        ),
        mode="csp",
    )
    assert out["action"] == "abort"
    assert out["triggered_threshold"] == "event_proximity_high_severity"


def test_event_clock_fires_before_day_specific_override():
    """Event gate sits above day-override in the pipeline. If both could
    fire (FOMC tomorrow + Monday open today), event gate wins because it's
    more conservative (defer entirely vs wait 30min)."""
    out = decide(
        _snap(
            next_event_name="FOMC Statement",
            next_event_severity="HIGH",
            next_event_days_away=1,
            is_monday_open=True,
            time_et="09:35",
        ),
        mode="csp",
    )
    assert out["triggered_threshold"] == "event_proximity_high_severity"


# --- Patch #2 — IV term inversion gate ---


def test_iv_term_inverted_with_event_soon_aborts():
    """Inverted IV term + event within 5d = market explicitly pricing
    event vol; abort regardless of mode."""
    out = decide(
        _snap(
            iv_term_inverted=True,
            next_event_name="CPI",
            next_event_severity="MEDIUM",
            next_event_days_away=3,
        ),
        mode="csp",
    )
    assert out["action"] == "abort"
    assert out["triggered_threshold"] == "iv_term_inverted_event_pricing"


def test_iv_term_inverted_alone_downgrades_morning_csp_to_eod():
    """Inversion without near-term event: morning CSP downgrades to EOD."""
    out = decide(_snap(iv_term_inverted=True, time_et="10:00"), mode="csp")
    assert out["action"] == "wait_eod"
    assert out["triggered_threshold"] == "iv_term_inverted_morning_downgrade"


def test_iv_term_inverted_does_not_downgrade_eod_mode():
    """RUT calendar already targets EOD; no downgrade needed. The gate
    should let the existing EOD path own the decision."""
    out = decide(_snap(iv_term_inverted=True, time_et="10:00"), mode="rut_calendar")
    assert out["triggered_threshold"] != "iv_term_inverted_morning_downgrade"


def test_iv_term_inverted_no_effect_when_false():
    """Default snapshot has iv_term_inverted=False (missing key); pipeline
    flows through normally."""
    out = decide(_snap(time_et="10:00"), mode="csp")
    assert out["triggered_threshold"] not in (
        "iv_term_inverted_event_pricing",
        "iv_term_inverted_morning_downgrade",
    )


def test_iv_term_inverted_with_high_severity_event_event_clock_wins():
    """When BOTH event_clock fires (HIGH severity within 2d) AND IV inverted,
    event_clock takes priority (more conservative; runs earlier in pipeline)."""
    out = decide(
        _snap(
            iv_term_inverted=True,
            next_event_name="CPI",
            next_event_severity="HIGH",
            next_event_days_away=1,
        ),
        mode="csp",
    )
    assert out["triggered_threshold"] == "event_proximity_high_severity"


def test_iv_term_event_window_boundary():
    """iv_term_inversion_event_window_days=5 — event 5d out still triggers
    the event_pricing abort; 6d out does not."""
    out_5d = decide(
        _snap(
            iv_term_inverted=True,
            next_event_name="PPI",
            next_event_severity="MEDIUM",
            next_event_days_away=5,
        ),
        mode="csp",
    )
    assert out_5d["triggered_threshold"] == "iv_term_inverted_event_pricing"
    out_6d = decide(
        _snap(
            iv_term_inverted=True,
            next_event_name="PPI",
            next_event_severity="MEDIUM",
            next_event_days_away=6,
        ),
        mode="csp",
    )
    assert out_6d["triggered_threshold"] != "iv_term_inverted_event_pricing"


def test_event_clock_and_iv_inversion_registered_in_all_trigger_names():
    """calibrate() seeds with ALL_TRIGGER_NAMES; new triggers must be there
    or never-fired reporting will be misleading."""
    from scripts.entry_timing import ALL_TRIGGER_NAMES

    assert "event_proximity_high_severity" in ALL_TRIGGER_NAMES
    assert "iv_term_inverted_event_pricing" in ALL_TRIGGER_NAMES
    assert "iv_term_inverted_morning_downgrade" in ALL_TRIGGER_NAMES
