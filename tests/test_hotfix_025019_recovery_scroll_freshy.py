from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COORD = (ROOT / "custom_components/freshairiq/coordinator.py").read_text()
CARD = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text()

def test_sensor_recovery_guard_has_grace_and_two_valid_cycles():
    from datetime import datetime, timedelta, timezone
    from custom_components.freshairiq.sensor_recovery import advance_sensor_recovery

    t0 = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)

    started, cycles, active = advance_sensor_recovery(
        None, 0, required_unavailable=True, now=t0
    )
    assert (started, cycles, active) == (t0, 0, True)

    # Still unavailable immediately before the 90-second boundary: suppress
    # the transient outage.
    started, cycles, active = advance_sensor_recovery(
        started, cycles, required_unavailable=True, now=t0 + timedelta(seconds=89)
    )
    assert (started, cycles, active) == (t0, 0, True)

    # Persistent loss beyond the boundary must no longer be hidden.
    started, cycles, active = advance_sensor_recovery(
        started, cycles, required_unavailable=True, now=t0 + timedelta(seconds=91)
    )
    assert (started, cycles, active) == (t0, 0, False)

    # First valid cycle after recovery remains guarded.
    started, cycles, active = advance_sensor_recovery(
        started, cycles, required_unavailable=False, now=t0 + timedelta(seconds=92)
    )
    assert (started, cycles, active) == (t0, 1, True)

    # Second consecutive valid cycle clears recovery completely.
    started, cycles, active = advance_sensor_recovery(
        started, cycles, required_unavailable=False, now=t0 + timedelta(seconds=93)
    )
    assert started is None
    assert cycles == 0
    assert active is False

    # Healthy startup never enters recovery.
    started, cycles, active = advance_sensor_recovery(
        None, 0, required_unavailable=False, now=t0
    )
    assert (started, cycles, active) == (None, 0, False)

    required_block = COORD.split("def _required_source_groups", 1)[1].split("def _log_required_source_availability", 1)[0]
    assert "CONF_ROOM_TEMPERATURE" in required_block and "CONF_ROOM_HUMIDITY" in required_block
    assert "entity_ids(room.get(key))" in required_block
    assert "_contact_ids(room)" not in required_block

def test_scroll_restore_keeps_snapshot_through_delayed_ha_layout():
    assert "this._viewportRestoreToken" in CARD
    assert "[50, 150, 350].forEach" in CARD
    assert "setTimeout(() => { if (this._pageScrollSnapshot?.token === token) this._pageScrollSnapshot = null; }, 450)" in CARD
    assert "parentRoot.querySelectorAll('*').forEach(remember)" in CARD

def test_freshy_has_distinct_live_pre_night_and_night_states():
    assert 'active.length && passiveOpenMonitor ? "continuous"' in CARD
    assert ': active.length ? "live"' in CARD
    assert 'isNight ? "night"' in CARD
    assert 'isPreNight ? "pre-night"' in CARD
    assert "faiqSail" in CARD and "faiqBedtime" in CARD and "faiqSleep" in CARD
    assert "ai-sleepcap" in CARD and "ai-zzz" in CARD and "ai-airflow" in CARD
