"""0.26.5.3 (community: message flood from the mould node).

* ``freshairiq_mould_risk`` carried the room action sentence as ``message``
  ("Büro: Bitte Lüfter ausschalten."); it now speaks about the mould risk and
  keeps the action sentence as ``action_message``.
* A surface humidity hovering around a level boundary fired an event every
  cycle; a lower level is now reported once it held 10 minutes.
* ``freshairiq_house_recommendation`` fired every minute while the countdown
  in its instruction ran ("noch ca. 19 min", "18 min", …).

The day test feeds 24 h of 30-second cycles with values that oscillate the
way real sensors do and caps the events per hour for every event type.
"""
from __future__ import annotations

from collections import Counter

from custom_components.freshairiq.automation_events import (
    EVENT_HOUSE_RECOMMENDATION,
    EVENT_MOULD_RISK,
    MOULD_FALL_HOLD_S,
    AutomationEventEmitter,
    house_signature,
    mould_message,
)


def _room(**extra) -> dict:
    room = {"key": "buero", "name": "Büro", "action": "Okay", "house_aligned_action": "okay",
            "mould_level": "Low", "surface_rh": 55.0, "humidity": 55.0, "temperature": 21.0}
    room.update(extra)
    return room


def _data(rooms, iq=None, language="de") -> dict:
    return {"rooms": {r["key"]: r for r in rooms}, "intelligent_recommendation": iq or {}, "output_language": language}


def _emitter():
    fired: list[tuple[str, dict]] = []
    clock = [0.0]
    emitter = AutomationEventEmitter(lambda t, p: fired.append((t, p)), "entry", clock=lambda: clock[0])
    return emitter, fired, clock


def test_mould_event_speaks_about_mould_and_keeps_the_action_sentence() -> None:
    emitter, fired, _clock = _emitter()
    emitter.process(_data([_room(action="Close", configured_actuators={"exhaust_fan": ["fan.buero"]})]))
    emitter.process(_data([_room(action="Close", mould_level="High", surface_rh=82.4)]))
    (event, payload), = fired[-1:]
    assert event == EVENT_MOULD_RISK
    assert payload["message"] == "Büro: Schimmelrisiko hoch · Oberflächenfeuchte 82 %."
    assert payload["action_message"] == "Büro: Bitte Fenster schließen."
    assert payload["rising"] is True and payload["mould_level"] == "high"


def test_mould_message_wording_in_both_languages() -> None:
    room = _room(surface_rh=None)
    assert mould_message(room, "Slightly elevated", rising=False, language="de") == "Büro: Schimmelrisiko gesunken auf leicht erhöht."
    assert mould_message(_room(), "Very high", rising=True, language="en") == "Büro: mould risk very high · surface humidity 55 %."
    assert mould_message(room, "Unknown level", rising=True, language="en") == "Büro: mould risk unknown level."


def test_a_level_hovering_at_a_boundary_is_reported_once() -> None:
    emitter, fired, clock = _emitter()
    emitter.process(_data([_room()]))
    for cycle in range(40):  # 20 minutes, flipping every 30 s
        clock[0] = cycle * 30.0
        emitter.process(_data([_room(mould_level="High" if cycle % 2 == 0 else "Elevated")]))
    assert [p["mould_level"] for t, p in fired if t == EVENT_MOULD_RISK] == ["high"]


def test_a_real_fall_is_reported_after_the_hold_time() -> None:
    emitter, fired, clock = _emitter()
    emitter.process(_data([_room()]))
    emitter.process(_data([_room(mould_level="High")]))
    for second in range(0, int(MOULD_FALL_HOLD_S) + 30, 30):
        clock[0] = 1000.0 + second
        emitter.process(_data([_room(mould_level="Slightly elevated")]))
    mould = [p for t, p in fired if t == EVENT_MOULD_RISK]
    assert [(p["mould_level"], p["rising"]) for p in mould] == [("high", True), ("slightly_elevated", False)]
    assert mould[-1]["message"] == "Büro: Schimmelrisiko gesunken auf leicht erhöht · Oberflächenfeuchte 55 %."


def test_the_house_countdown_is_not_a_new_recommendation() -> None:
    first = {"kind": "continue", "room_keys": ["wohnkueche"], "instruction": "Ziel etwa 19 min · noch ca. 19 min"}
    later = {**first, "instruction": "Ziel etwa 19 min · noch ca. 4 min"}
    other = {**first, "instruction": "Wohnküche offen lassen · Bad schließen"}
    assert house_signature(first) == house_signature(later)
    assert house_signature(first) != house_signature(other)
    assert house_signature({**first, "instruction": "Target about 19 min · about 2.5 min left"}) == house_signature(
        {**first, "instruction": "Target about 19 min · about 18 min left"})


def test_a_day_of_oscillating_values_stays_within_sane_event_rates() -> None:
    """24 h × 30 s cycles: sensor jitter around every threshold, a countdown, short state changes."""
    emitter, fired, clock = _emitter()
    hourly: Counter = Counter()
    mould_cycle = ["High", "Elevated", "High", "Very high", "High", "Elevated"]
    for cycle in range(24 * 120):
        clock[0] = cycle * 30.0
        minute = cycle // 2
        session = (minute // 60) % 3 != 2  # two hours airing, one hour quiet
        room = _room(
            mould_level=mould_cycle[cycle % len(mould_cycle)],
            surface_rh=79.5 + (cycle % 3) * 0.5,
            action="Continue ventilating" if session else "Okay",
            house_aligned_action="continue_ventilating" if session else "okay",
            moisture_source_active=False,
        )
        iq = ({"kind": "continue", "room_keys": ["buero"], "instruction": f"Ziel etwa 60 min · noch ca. {60 - minute % 60} min"}
              if session else {"kind": "okay", "room_keys": [], "instruction": "Keine Aktion erforderlich"})
        before = len(fired)
        emitter.process(_data([room], iq))
        for event, _payload in fired[before:]:
            hourly[(event, cycle // 120)] += 1
    worst = Counter()
    for (event, _hour), count in hourly.items():
        worst[event] = max(worst[event], count)
    # real changes only: a few per hour, never one per cycle or per minute
    assert worst[EVENT_HOUSE_RECOMMENDATION] <= 2
    assert worst[EVENT_MOULD_RISK] <= 2
    assert all(count <= 4 for count in worst.values()), worst
