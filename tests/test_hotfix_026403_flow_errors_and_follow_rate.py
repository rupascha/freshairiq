"""0.26.4.3: setup-flow exceptions become visible; follow rate is measured correctly."""
import asyncio
from datetime import datetime, timedelta, timezone

from custom_components.freshairiq.flow_error_signature import flow_error_message, flow_error_signature
from custom_components.freshairiq import flow_errors
from custom_components.freshairiq.intelligence import (
    mark_recommendation_followed, mark_recommendation_notified, sync_active_recommendation,
)

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)


def _schema(room, contact):
    if include_back:  # noqa: F821 - reproduces GitHub #12
        return {}


def _raise_issue_12():
    try:
        _schema({}, "binary_sensor.window")
    except NameError as err:
        import sys
        return err, sys.exc_info()[2]


def test_signature_has_type_and_code_locations_but_no_message():
    err, tb = _raise_issue_12()
    sig = flow_error_signature(err, tb, flow="room_flow", step="add_references")
    assert sig["error_type"] == "NameError" and sig["code"] == "FAIQ-CONFIG-FLOW-001"
    assert sig["locations"] == []  # frames outside the integration package are not exported
    assert "include_back" not in str(sig)
    assert flow_error_message(sig) == "NameError in room_flow.add_references at unknown location"


def test_signature_keeps_only_integration_frames(tmp_path):
    pkg = tmp_path / "custom_components" / "freshairiq"
    pkg.mkdir(parents=True)
    code = compile("def boom():\n    raise ValueError('secret sensor.kitchen')\n", str(pkg / "config_flow.py"), "exec")
    ns = {}
    exec(code, ns)
    try:
        ns["boom"]()
    except ValueError as err:
        import sys
        sig = flow_error_signature(err, sys.exc_info()[2], flow="options_flow", step="room_goals")
    assert sig["locations"] == ["config_flow:2 boom"]
    assert "secret" not in str(sig) and "kitchen" not in str(sig)
    assert flow_error_message(sig) == "ValueError in options_flow.room_goals at config_flow:2 boom"
    assert len(sig["fingerprint"]) == 24


class _Recorder:
    def __init__(self):
        self.events = []

    async def async_record_flow_error(self, event):
        self.events.append(event)
        return True


class _Telemetry:
    def __init__(self):
        self.reports = []

    async def async_report_client_error(self, **kw):
        self.reports.append(kw)
        return {}


class _Hass:
    def __init__(self):
        self.tasks = []

    def async_create_task(self, coro):
        self.tasks.append(coro)


def _flow(options, *, with_entry=True, raise_get_entry=False):
    coordinator = type("C", (), {})()
    coordinator.diagnostics = _Recorder()
    coordinator.telemetry = _Telemetry()
    entry = type("E", (), {"options": options, "runtime_data": coordinator})() if with_entry else None

    class Flow:
        hass = _Hass()

        def _get_entry(self):
            if raise_get_entry:
                raise RuntimeError("no entry")
            return entry

        async def async_step_room_goals(self, user_input=None):
            raise KeyError("goal")

        async def async_step_ok(self, user_input=None):
            return {"type": "form"}

        async def async_step_abort(self, user_input=None):
            raise type("AbortFlow", (Exception,), {})("already_configured")

    flow_errors.guard_flow_steps(Flow, "options_flow")
    flow_errors.guard_flow_steps(Flow, "options_flow")  # idempotent
    return Flow(), coordinator


def _run_step(flow, name):
    async def go():
        try:
            return await getattr(flow, name)()
        except Exception as err:  # the original error must still reach Home Assistant
            return err
    result = asyncio.run(go())
    for task in flow.hass.tasks:
        asyncio.run(task)
    flow.hass.tasks.clear()
    return result


def test_exception_is_recorded_reraised_and_reported_only_with_consent():
    flow, coord = _flow({"diagnostics_consent": "granted", "diagnostics_reporting_mode": "daily"})
    assert isinstance(_run_step(flow, "async_step_room_goals"), KeyError)
    assert coord.diagnostics.events[0]["step"] == "room_goals"
    assert coord.telemetry.reports[0]["component"] == "config_flow"
    assert coord.telemetry.reports[0]["operation"] == "options_flow.room_goals"

    flow, coord = _flow({"diagnostics_consent": "unset"})
    _run_step(flow, "async_step_room_goals")
    assert len(coord.diagnostics.events) == 1 and coord.telemetry.reports == []

    flow, coord = _flow({"diagnostics_consent": "granted", "diagnostics_reporting_mode": "off"})
    _run_step(flow, "async_step_room_goals")
    assert coord.telemetry.reports == []


def test_normal_steps_and_flow_control_are_untouched():
    flow, coord = _flow({"diagnostics_consent": "granted"})
    assert _run_step(flow, "async_step_ok") == {"type": "form"}
    assert type(_run_step(flow, "async_step_abort")).__name__ == "AbortFlow"
    assert coord.diagnostics.events == [] and coord.telemetry.reports == []


def test_flows_without_entry_still_raise_and_log():
    flow, coord = _flow({}, with_entry=False)
    assert isinstance(_run_step(flow, "async_step_room_goals"), KeyError)
    flow, coord = _flow({}, raise_get_entry=True)
    assert isinstance(_run_step(flow, "async_step_room_goals"), KeyError)
    assert coord.diagnostics.events == []


def test_reporting_failure_never_hides_the_original_error():
    flow, coord = _flow({"diagnostics_consent": "granted"})

    async def broken(**kw):
        raise RuntimeError("hub down")
    coord.telemetry.async_report_client_error = broken
    assert isinstance(_run_step(flow, "async_step_room_goals"), KeyError)


def test_flow_without_hass_skips_reporting():
    class Flow:
        hass = None

        async def async_step_x(self, user_input=None):
            raise ValueError("x")
    flow_errors.guard_flow_steps(Flow, "config_flow")
    assert isinstance(_run_step_plain(Flow()), ValueError)


def _run_step_plain(flow):
    async def go():
        try:
            await flow.async_step_x()
        except Exception as err:
            return err
    return asyncio.run(go())


def test_entry_lookup_falls_back_to_config_entry():
    class Flow:
        config_entry = "entry"
    assert flow_errors._entry_of(Flow()) == "entry"

    class Broken:
        @property
        def config_entry(self):
            raise RuntimeError("not set yet")
    assert flow_errors._entry_of(Broken()) is None


def _store(kind, keys=("bad",)):
    return {"rooms": {k: {} for k in keys}}


def test_keeping_windows_closed_counts_as_followed():
    store = _store("wait")
    sync_active_recommendation(store, {"kind": "wait", "room_keys": ["bad"]}, NOW)
    sync_active_recommendation(store, {"kind": "okay", "room_keys": []}, NOW + timedelta(minutes=30))
    room = store["rooms"]["bad"]
    assert (room["recommendation_followed"], room["recommendation_missed"]) == (1, 0)


def test_opening_during_wait_is_not_followed_and_notification_is_linked():
    store = _store("wait")
    sync_active_recommendation(store, {"kind": "wait", "room_keys": ["bad"]}, NOW)
    assert mark_recommendation_notified(store, NOW) is True
    assert mark_recommendation_notified(store, NOW) is False  # first delivery counts
    assert mark_recommendation_followed(store, store["rooms"]["bad"], "bad", NOW + timedelta(minutes=5)) is False
    sync_active_recommendation(store, {"kind": "okay", "room_keys": []}, NOW + timedelta(minutes=30))
    room = store["rooms"]["bad"]
    assert (room["recommendation_followed"], room["recommendation_missed"]) == (0, 1)
    assert (room["recommendation_notified"], room["recommendation_followed_notified"]) == (1, 0)


def test_ventilate_followed_after_notification_is_counted_as_such():
    store = _store("ventilate")
    sync_active_recommendation(store, {"kind": "ventilate", "room_keys": ["bad"]}, NOW)
    mark_recommendation_notified(store, NOW)
    assert mark_recommendation_followed(store, store["rooms"]["bad"], "bad", NOW + timedelta(minutes=3)) is True
    sync_active_recommendation(store, {"kind": "okay", "room_keys": []}, NOW + timedelta(minutes=20))
    room = store["rooms"]["bad"]
    assert (room["recommendation_followed"], room["recommendation_notified"], room["recommendation_followed_notified"]) == (1, 1, 1)
    assert mark_recommendation_notified({}, NOW) is False
