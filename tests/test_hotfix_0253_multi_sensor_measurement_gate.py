from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from custom_components.freshairiq.climate_sources import (
    advance_climate_report_activity,
    climate_report_snapshot,
    logical_climate_sensor_groups,
)

class States:
    def __init__(self, values): self.values = values
    def get(self, entity_id): return self.values.get(entity_id)
class Hass:
    def __init__(self, values): self.states = States(values)

def state(value, stamp):
    return SimpleNamespace(state=str(value), last_reported=stamp, last_updated=stamp)

def test_legacy_single_sensor_pair_still_accepts_one_temperature_plus_one_humidity_report():
    start = datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc)
    old = {"0": {"reports": {"temperature": start.isoformat(), "humidity": start.isoformat()}}}
    current = {"0": {"available": True, "reports": {
        "temperature": (start + timedelta(minutes=1)).isoformat(),
        "humidity": (start + timedelta(minutes=2)).isoformat(),
    }}}
    _, counts, fresh = advance_climate_report_activity(old, {"0": 0}, current, window_start=start)
    assert counts == {"0": 2}
    assert fresh == 2

def test_secondary_sensor_does_not_block_gate_after_primary_has_two_reports():
    start = datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc)
    old = {str(i): {"reports": {"temperature": start.isoformat(), "humidity": start.isoformat()}} for i in range(2)}
    current = {
        "0": {"available": True, "reports": {"temperature": (start+timedelta(minutes=1)).isoformat(), "humidity": (start+timedelta(minutes=2)).isoformat()}},
        "1": {"available": True, "reports": {"temperature": (start+timedelta(minutes=1)).isoformat(), "humidity": start.isoformat()}},
    }
    nxt, counts, fresh = advance_climate_report_activity(old, {"0": 0, "1": 0}, current, window_start=start)
    assert counts == {"0": 2, "1": 1}
    assert fresh == 2
    current["1"]["reports"]["temperature"] = (start+timedelta(minutes=3)).isoformat()
    _, counts, fresh = advance_climate_report_activity(nxt, counts, current, window_start=start)
    assert counts["1"] == 2
    assert fresh == 2

def test_redundant_unavailable_sensor_does_not_block_remaining_sensor_or_gate():
    start = datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc)
    current = {
        "0": {"available": True, "reports": {"temperature": (start+timedelta(minutes=1)).isoformat(), "humidity": (start+timedelta(minutes=2)).isoformat()}},
        "1": {"available": False, "reports": {"temperature": start.isoformat(), "humidity": start.isoformat()}},
    }
    _, counts, fresh = advance_climate_report_activity({}, {}, current, window_start=start)
    assert counts["0"] == 2
    assert fresh == 2

def test_two_reports_may_both_come_from_same_measurement_type():
    start = datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc)
    old = {"0": {"reports": {"temperature": start.isoformat(), "humidity": start.isoformat()}}}
    first = {"0": {"available": True, "reports": {"temperature": (start+timedelta(minutes=1)).isoformat(), "humidity": start.isoformat()}}}
    nxt, counts, fresh = advance_climate_report_activity(old, {}, first, window_start=start)
    assert fresh == 1
    second = {"0": {"available": True, "reports": {"temperature": (start+timedelta(minutes=2)).isoformat(), "humidity": start.isoformat()}}}
    _, counts, fresh = advance_climate_report_activity(nxt, counts, second, window_start=start)
    assert counts["0"] == 2 and fresh == 2

def test_grouping_preserves_legacy_and_pairs_multi_sensor_selection_order():
    assert logical_climate_sensor_groups("sensor.t", "sensor.h") == [("sensor.t", "sensor.h")]
    assert logical_climate_sensor_groups(["sensor.t1", "sensor.t2"], ["sensor.h1", "sensor.h2"]) == [
        ("sensor.t1", "sensor.h1"), ("sensor.t2", "sensor.h2")]

def test_snapshot_marks_failed_secondary_pair_unavailable_without_removing_healthy_pair():
    now = datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc)
    hass = Hass({
        "sensor.t1": state(21, now), "sensor.h1": state(55, now),
        "sensor.t2": SimpleNamespace(state="unavailable", last_reported=now, last_updated=now),
        "sensor.h2": SimpleNamespace(state="unavailable", last_reported=now, last_updated=now),
    })
    snap = climate_report_snapshot(hass, ["sensor.t1", "sensor.t2"], ["sensor.h1", "sensor.h2"])
    assert snap["0"]["available"] is True
    assert snap["1"]["available"] is False

def test_snapshot_supports_unpaired_measurement_entities():
    now = datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc)
    hass = Hass({"sensor.t1": state(21, now), "sensor.t2": state(22, now), "sensor.h1": state(55, now)})
    snap = climate_report_snapshot(hass, ["sensor.t1", "sensor.t2"], ["sensor.h1"])
    assert snap["1"]["reports"] == {"temperature": now.isoformat()}
    assert snap["1"]["available"] is True

def test_invalid_report_timestamp_never_counts_as_fresh_activity():
    start = datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc)
    current = {"0": {"available": True, "reports": {"temperature": "not-a-timestamp"}}}
    _, counts, fresh = advance_climate_report_activity({}, {}, current, window_start=start)
    assert counts.get("0", 0) == 0
    assert fresh == 0

def test_one_confirmed_sensor_opens_gate_while_one_report_secondary_participates():
    start = datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc)
    old = {str(i): {"reports": {"temperature": start.isoformat(), "humidity": start.isoformat()}} for i in range(2)}
    current = {
        "0": {"available": True, "reports": {"temperature": (start+timedelta(minutes=1)).isoformat(), "humidity": (start+timedelta(minutes=2)).isoformat()}},
        "1": {"available": True, "reports": {"temperature": (start+timedelta(minutes=1)).isoformat(), "humidity": start.isoformat()}},
    }
    _, counts, fresh = advance_climate_report_activity(old, {"0": 0, "1": 0}, current, window_start=start)
    assert counts == {"0": 2, "1": 1}
    assert fresh == 2


def test_two_one_report_sensors_do_not_open_gate():
    start = datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc)
    old = {str(i): {"reports": {"temperature": start.isoformat(), "humidity": start.isoformat()}} for i in range(2)}
    current = {
        "0": {"available": True, "reports": {"temperature": (start+timedelta(minutes=1)).isoformat(), "humidity": start.isoformat()}},
        "1": {"available": True, "reports": {"temperature": start.isoformat(), "humidity": (start+timedelta(minutes=1)).isoformat()}},
    }
    _, counts, fresh = advance_climate_report_activity(old, {}, current, window_start=start)
    assert counts == {"0": 1, "1": 1}
    assert fresh == 1


def test_session_participation_requires_one_report_but_not_two():
    from custom_components.freshairiq.climate_sources import participating_climate_entities
    snapshot = {"0": {"available": True}, "1": {"available": True}, "2": {"available": True}}
    t, h = participating_climate_entities(
        ["sensor.t1", "sensor.t2", "sensor.t3"], ["sensor.h1", "sensor.h2", "sensor.h3"],
        snapshot, {"0": 2, "1": 1, "2": 0}
    )
    assert t == ["sensor.t1", "sensor.t2"]
    assert h == ["sensor.h1", "sensor.h2"]

def test_session_participation_skips_unavailable_and_malformed_counts():
    from custom_components.freshairiq.climate_sources import participating_climate_entities
    snapshot = {"0": {"available": False}, "1": {"available": True}}
    t, h = participating_climate_entities(
        ["sensor.t1", "sensor.t2"], ["sensor.h1", "sensor.h2"], snapshot, {"0": 5, "1": "bad"}
    )
    assert t == [] and h == []


def test_multisensor_release_contract_never_combines_single_reports_to_open_gate():
    """Hard contract: one sensor must independently reach two reports.

    Reports from different logical climate sensors must never be summed to
    satisfy the session measurement gate.
    """
    start = datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc)
    old = {
        "0": {"reports": {"temperature": start.isoformat(), "humidity": start.isoformat()}},
        "1": {"reports": {"temperature": start.isoformat(), "humidity": start.isoformat()}},
        "2": {"reports": {"temperature": start.isoformat(), "humidity": start.isoformat()}},
    }

    # Every sensor reports once: three reports exist globally, but no single
    # sensor satisfies the two-report base condition.
    current = {
        "0": {"available": True, "reports": {
            "temperature": (start + timedelta(minutes=1)).isoformat(),
            "humidity": start.isoformat(),
        }},
        "1": {"available": True, "reports": {
            "temperature": start.isoformat(),
            "humidity": (start + timedelta(minutes=1)).isoformat(),
        }},
        "2": {"available": True, "reports": {
            "temperature": (start + timedelta(minutes=1)).isoformat(),
            "humidity": start.isoformat(),
        }},
    }
    nxt, counts, gate = advance_climate_report_activity(old, {}, current, window_start=start)
    assert counts == {"0": 1, "1": 1, "2": 1}
    assert gate == 1
    assert not any(count >= 2 for count in counts.values())

    # Only after sensor 1 independently reaches two reports does the gate open.
    current["1"]["reports"]["temperature"] = (start + timedelta(minutes=2)).isoformat()
    _, counts, gate = advance_climate_report_activity(nxt, counts, current, window_start=start)
    assert counts == {"0": 1, "1": 2, "2": 1}
    assert gate == 2
    assert any(count >= 2 for count in counts.values())


def test_multisensor_release_contract_one_confirmed_sensor_allows_one_report_peers_only():
    """Hard contract: peers may participate only after one sensor opens the gate."""
    from custom_components.freshairiq.climate_sources import participating_climate_entities

    snapshot = {
        "0": {"available": True},
        "1": {"available": True},
        "2": {"available": True},
    }

    # Before any sensor reaches two reports, this participation set must not be
    # interpreted as a valid session measurement.
    counts_before_gate = {"0": 1, "1": 1, "2": 0}
    t, h = participating_climate_entities(
        ["sensor.t1", "sensor.t2", "sensor.t3"],
        ["sensor.h1", "sensor.h2", "sensor.h3"],
        snapshot,
        counts_before_gate,
    )
    assert t == ["sensor.t1", "sensor.t2"]
    assert h == ["sensor.h1", "sensor.h2"]
    assert not any(count >= 2 for count in counts_before_gate.values())

    # Once one sensor independently satisfies the base condition, peers with
    # one life-sign may participate; a zero-report peer remains excluded.
    counts_after_gate = {"0": 2, "1": 1, "2": 0}
    t, h = participating_climate_entities(
        ["sensor.t1", "sensor.t2", "sensor.t3"],
        ["sensor.h1", "sensor.h2", "sensor.h3"],
        snapshot,
        counts_after_gate,
    )
    assert any(count >= 2 for count in counts_after_gate.values())
    assert t == ["sensor.t1", "sensor.t2"]
    assert h == ["sensor.h1", "sensor.h2"]
