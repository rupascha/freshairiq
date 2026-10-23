"""Regressions for work order 2026-10-14 package A (F01, F02, F05, F09, F10).

Fixtures are synthetic boundary cases derived from the documented evidence
(support export A 09.10. 09:16, 0.26.4.5: four rooms Continue -> Close within
10 s; A 11.10. 13:57, 0.26.5.0: house passive_open_monitor while a room reads
Close). No measured values are invented; only the decision-relevant fields.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from custom_components.freshairiq import automation_events as ev
from custom_components.freshairiq.consolidation import (
    AGGREGATE_CONTINUE_HYSTERESIS,
    stabilise_recommendation,
)
from custom_components.freshairiq.model import min_return_volume_factor
from custom_components.freshairiq.opening_strategy import (
    HOUSE_ALIGNED_STATES,
    house_aligned_room_actions,
    synchronize_room_presentation_actions,
)
from tests._source import module_source

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"
OPTIONS = {"min_return_next_5_min_ml": 25.0, "max_duration_min": 20.0, "close_delta": 0.4, "min_duration_min": 3.0}


def _active_rooms(combined_next5: float, *, elapsed: float = 12.0, temp_next5: float = -0.1) -> dict:
    base = dict(
        data_quality="ok", active=True, action="Close", close_recommended=True,
        session_elapsed_min=elapsed, temperature_change_c=-0.3, delta_g_m3=0.8,
        forecast_5_min_temperature_change_c=temp_next5, volume_m3=30.0, efficiency_ml_per_01c=50.0,
    )
    return {
        key: dict(base, key=key, name=key, forecast_5_min_moisture_effect_ml=combined_next5 / 2)
        for key in ("bad", "schlafzimmer")
    }


def _threshold() -> float:
    return 25.0 * min_return_volume_factor(60.0)


def _run(sequence, *, previous=None, **room_kw):
    seen = []
    for combined in sequence:
        rooms = _active_rooms(combined, **room_kw)
        rec = stabilise_recommendation({"kind": "close", "room_keys": list(rooms)}, rooms, OPTIONS, previous=previous)
        synchronize_room_presentation_actions(rec, rooms)
        previous = {"kind": rec["kind"], "room_keys": rec["room_keys"]}
        seen.append((rec["kind"], rooms["bad"]["action"], rooms["schlafzimmer"]["action"]))
    return seen


# --------------------------------------------------------------------------- F01
def test_f01_threshold_noise_no_longer_flips_house_and_room_actions():
    thr = _threshold()
    seen = _run([thr + 1, thr - 1, thr + 1, thr - 1, thr + 1])
    # First cycle: no published close yet -> unchanged aggregate behaviour.
    assert seen[0] == ("continue", "Continue ventilating", "Continue ventilating")
    # Once "close" was published, +-1 ml around the threshold keeps it.
    assert all(row == ("close", "Close", "Close") for row in seen[1:])


def test_f01_restart_keeps_previous_behaviour_without_memory():
    thr = _threshold()
    rooms = _active_rooms(thr + 1)
    assert stabilise_recommendation({"kind": "close", "room_keys": list(rooms)}, rooms, OPTIONS)["kind"] == "continue"


def test_f01_clearly_higher_return_still_reopens_continue():
    thr = _threshold()
    seen = _run([thr - 1, thr * AGGREGATE_CONTINUE_HYSTERESIS + 1])
    assert seen[0][0] == "close"
    assert seen[1][0] == "continue"


def test_f01_hard_close_is_never_held_back_by_hysteresis_or_return():
    thr = _threshold()
    # Maximum duration exceeded: hard close regardless of a large combined return.
    seen = _run([thr * 3, thr * 3], previous={"kind": "continue", "room_keys": ["bad", "schlafzimmer"]}, elapsed=25.0)
    assert seen == [("close", "Close", "Close"), ("close", "Close", "Close")]


def test_f01_hysteresis_only_applies_to_the_rooms_it_closed():
    thr = _threshold()
    rooms = _active_rooms(thr + 1)
    rec = stabilise_recommendation(
        {"kind": "close", "room_keys": list(rooms)}, rooms, OPTIONS,
        previous={"kind": "close", "room_keys": ["bad"]},  # schlafzimmer was not part of the close
    )
    assert rec["kind"] == "continue"


def test_f01_coordinator_feeds_last_final_recommendation():
    source = module_source("coordinator")
    assert 'previous=getattr(self, "_last_final_recommendation", None)' in source
    assert "self._last_final_recommendation = {" in source


# --------------------------------------------------------------------------- F02
def _passive_monitor_case():
    rooms = {
        "schlafzimmer": {"key": "schlafzimmer", "action": "Close", "active": True},
        "bad": {"key": "bad", "action": "Close", "active": True},
        "buero": {"key": "buero", "action": "Ventilate", "active": False},
    }
    rec = {"kind": "okay", "status": "passive_open_monitor", "room_keys": ["schlafzimmer"]}
    return rec, rooms


def test_f02_tolerated_long_opening_is_not_presented_as_close():
    rec, rooms = _passive_monitor_case()
    synchronize_room_presentation_actions(rec, rooms)
    house_aligned_room_actions(rec, rooms)
    assert rooms["schlafzimmer"]["action"] == "Close"  # physical room action kept
    assert rooms["schlafzimmer"]["house_aligned_action"] == "monitor_open"
    # A room the house did not put into monitor mode keeps its close.
    assert rooms["bad"]["house_aligned_action"] == "close"
    assert rooms["buero"]["house_aligned_action"] == "ventilate"
    assert "monitor_open" in HOUSE_ALIGNED_STATES


def test_f02_ordinary_close_decision_is_untouched():
    rooms = {"schlafzimmer": {"key": "schlafzimmer", "action": "Close", "active": True}}
    house_aligned_room_actions({"kind": "close", "status": "close_windows", "room_keys": ["schlafzimmer"]}, rooms)
    assert rooms["schlafzimmer"]["house_aligned_action"] == "close"


def test_f02_thermal_drop_is_not_tolerated_as_long_opening():
    rooms = _active_rooms(5.0, elapsed=40.0, temp_next5=-0.8)
    rec = stabilise_recommendation({"kind": "close", "room_keys": list(rooms)}, rooms, OPTIONS)
    assert rec["kind"] == "close"
    assert rec.get("status") != "passive_open_monitor"


def test_f02_all_surfaces_know_monitor_open():
    card = (COMP / "frontend/freshairiq-card.js").read_text(encoding="utf-8")
    assert 'houseMonitoredRoom(r) ? "Daueröffnung überwachen"' in card
    for name in ("translations/de.json", "translations/en.json", "strings.json"):
        data = json.loads((COMP / name).read_text(encoding="utf-8"))
        assert "monitor_open" in data["entity"]["sensor"]["house_aligned_action"]["state"], name
    for language in ("de", "en"):
        assert "monitor_open" in ev._LABELS[language]


# --------------------------------------------------------------------------- F05
def _room(action: str, aligned: str) -> dict:
    return {"key": "wohnen", "name": "Wohnen", "action": action, "house_aligned_action": aligned}


def test_f05_aligned_only_change_fires_recommendation_event_but_not_raw_event():
    fired = []
    emitter = ev.AutomationEventEmitter(lambda name, payload: fired.append((name, payload)), "entry")
    emitter.process({"rooms": {"wohnen": _room("Ventilate", "ventilate_later")}})
    assert fired == []  # start-up is silent
    emitter.process({"rooms": {"wohnen": _room("Ventilate", "ventilate")}})
    assert [name for name, _ in fired] == [ev.EVENT_ROOM_RECOMMENDATION]
    payload = fired[0][1]
    assert payload["recommendation"] == "ventilate"
    assert payload["previous_recommendation"] == "ventilate_later"
    assert payload["action"] == "ventilate"
    assert payload["message"] == "Wohnen: Bitte lüften."
    # Unchanged state: no duplicate.
    emitter.process({"rooms": {"wohnen": _room("Ventilate", "ventilate")}})
    assert len(fired) == 1


def test_f05_raw_action_contract_is_unchanged():
    fired = []
    emitter = ev.AutomationEventEmitter(lambda name, payload: fired.append(name), "entry")
    emitter.process({"rooms": {"wohnen": _room("Continue ventilating", "continue_ventilating")}})
    emitter.process({"rooms": {"wohnen": _room("Close", "close")}})
    assert fired.count(ev.EVENT_ROOM_ACTION) == 1
    assert fired.count(ev.EVENT_ROOM_RECOMMENDATION) == 1


def test_f05_rooms_without_aligned_value_do_not_fire():
    fired = []
    emitter = ev.AutomationEventEmitter(lambda name, payload: fired.append(name), "entry")
    emitter.process({"rooms": {"wohnen": {"key": "wohnen", "action": "Wait"}}})
    emitter.process({"rooms": {"wohnen": {"key": "wohnen", "action": "Wait"}}})
    assert fired == []


# --------------------------------------------------------------------------- F09 / F10
def _produced_actions() -> set[str]:
    """Every action literal the room engine and coordinator actually assign."""
    found: set[str] = set()
    pattern = re.compile(r'action(?:, reason)?\s*=\s*"([A-Z][A-Za-z ]+)"')
    for name in ("model.py", "coordinator.py"):
        found |= set(pattern.findall(module_source("coordinator") if name == "coordinator.py" else (COMP / name).read_text(encoding="utf-8")))
    return found


def _sensor_action_map() -> dict[str, str]:
    tree = ast.parse((COMP / "sensor.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "ACTION_STATE_MAP" for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("ACTION_STATE_MAP missing")


def test_f10_every_produced_action_has_sensor_event_frontend_and_translation():
    produced = _produced_actions()
    assert "Ventilate indirectly" in produced  # reachable: rooms without an opening contact
    sensor_map = _sensor_action_map()
    card = (COMP / "frontend/freshairiq-card.js").read_text(encoding="utf-8")
    action_de = re.search(r"const actionDE = v => \(\{(.*?)\}\[v\]", card).group(1)
    states = {
        name: json.loads((COMP / name).read_text(encoding="utf-8"))["entity"]["sensor"]["action"]["state"]
        for name in ("translations/de.json", "translations/en.json", "strings.json")
    }
    for action in sorted(produced):
        code = sensor_map.get(action)
        assert code, f"sensor maps {action!r} to unknown"
        assert ev.ACTION_CODES.get(action) == code, action
        assert f'"{action}":' in action_de, action
        for name, values in states.items():
            assert code in values, (name, code)
        for language in ("de", "en"):
            assert code in ev._LABELS[language], (language, code)


def test_f10_open_fully_is_mapped_consistently_although_not_produced():
    assert "Open fully" not in _produced_actions()  # documented as reserved
    assert _sensor_action_map()["Open fully"] == ev.ACTION_CODES["Open fully"] == "open_fully"


def test_f09_german_event_label_for_indirect_ventilation():
    payload = ev.room_payload({"key": "ulte_az", "name": "Ulte AZ", "action": "Ventilate indirectly"},
                              previous_action="Okay", language="de", entry_id="e")
    assert payload["action"] == "ventilate_indirectly"
    assert payload["action_label"] == "Über Nachbarraum lüften"
    assert "Ventilate indirectly" not in payload["message"]
    english = ev.room_payload({"key": "x", "name": "X", "action": "Ventilate indirectly"},
                              previous_action=None, language="en", entry_id="e")
    assert english["action_label"] == "Air via a connected room"
    en_pairs = (COMP / "frontend/freshairiq-card-i18n-en.js").read_text(encoding="utf-8")
    assert '["Über Nachbarraum lüften", "Ventilate via a connected room"]' in en_pairs
