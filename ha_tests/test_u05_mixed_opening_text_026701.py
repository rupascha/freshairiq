"""U05 (0.26.7.1): the hint about the tilt model names the model really used.

One window fully open plus one tilted (two three-state contacts in the same room) is evaluated with the general
ventilation model – a specialist model needs one uniform, proven mode – and the session never teaches the tilt model
(``session_opening_mode_mixed``). Before, the room still said "evaluated with the separate tilt model".
"""
from __future__ import annotations

from custom_components.freshairiq.coordinator_room_model import MIXED_OPENING_REASON
from custom_components.freshairiq.localize import to_english as translate_text
from ha_tests.test_cov_coordinator_b import HUM, _cleanup_coordinators, _data, _make, _rooms, _with  # noqa: F401

LAGE = {"options": ["closed", "tilted", "open"], "device_class": "enum"}
TILT = "Drei-Zustands-Sensor meldet Kipplüftung; die gewählte Lüftungsart wird mit dem separaten Kippmodell bewertet"
A, B = "sensor.schlaf_fenster_lage", "sensor.schlaf_fenster2_lage"


def _texts(room):
    reasons = list(room.get("recommendation_reasons") or [])
    return {"tilt": any(r in (TILT, translate_text(TILT)) for r in reasons),
            "mixed": any(r in (MIXED_OPENING_REASON, translate_text(MIXED_OPENING_REASON)) for r in reasons)}


async def _room(hass, freezer, extra_contacts=()):
    contacts = [A, B, *extra_contacts]
    rooms = _with(_rooms(), "schlaf", contacts=contacts, contact_delays={c: 0 for c in contacts},
                  contact_orientations={c: "east" for c in contacts})
    initial = {A: ("closed", LAGE), B: ("closed", LAGE), "sensor.schlaf_h": (68.0, HUM)}
    for c in extra_contacts:
        initial[c] = "off"
    return await _make(hass, freezer, data=_data(rooms), initial=initial)


async def test_only_tilted_keeps_the_tilt_model_hint(hass, freezer) -> None:
    d = await _room(hass, freezer)
    await d.step(60, **{A.replace(".", "__"): ("tilted", LAGE)})
    await d.step(5)
    room = d.room("schlaf")
    assert d.mem("schlaf")["session_specialist_opening_mode"] == "tilted"
    assert room["action"] not in {"Close", "Check sensor"}
    assert _texts(room) == {"tilt": True, "mixed": False}


async def test_only_open_has_no_tilt_hint(hass, freezer) -> None:
    d = await _room(hass, freezer)
    await d.step(60, **{A.replace(".", "__"): ("open", LAGE)})
    await d.step(5)
    assert _texts(d.room("schlaf")) == {"tilt": False, "mixed": False}


async def test_open_plus_tilted_is_explained_as_mixed_and_never_teaches_the_tilt_model(hass, freezer) -> None:
    d = await _room(hass, freezer)
    tilted_before = dict((d.mem("schlaf").get("opening_learning") or {}).get("tilted") or {})
    await d.step(60, **{A.replace(".", "__"): ("open", LAGE), B.replace(".", "__"): ("tilted", LAGE)})
    await d.step(5)
    room = d.room("schlaf")
    assert room["action"] not in {"Close", "Check sensor"}
    assert _texts(room) == {"tilt": False, "mixed": True}
    assert translate_text(MIXED_OPENING_REASON).startswith("Windows open and tilted at the same time")
    for i in range(6):
        await d.step(60, sensor__schlaf_h=round(68 - 0.8 * (i + 1), 1))
    await d.step(60, **{A.replace(".", "__"): ("closed", LAGE), B.replace(".", "__"): ("closed", LAGE)})
    await d.finish(sensor__schlaf_h=62.5)
    mem = d.mem("schlaf")
    assert mem["session_active"] is False
    assert dict((mem.get("opening_learning") or {}).get("tilted") or {}) == tilted_before


async def test_mode_change_during_the_session_switches_the_hint(hass, freezer) -> None:
    d = await _room(hass, freezer)
    await d.step(60, **{A.replace(".", "__"): ("tilted", LAGE)})
    await d.step(5)
    assert _texts(d.room("schlaf"))["tilt"] is True
    await d.step(60, **{B.replace(".", "__"): ("open", LAGE)})
    await d.step(5)
    assert _texts(d.room("schlaf")) == {"tilt": False, "mixed": True}
    assert d.mem("schlaf")["session_opening_mode_mixed"] is True


async def test_tilted_three_state_plus_open_binary_contact_is_mixed(hass, freezer) -> None:
    d = await _room(hass, freezer, extra_contacts=("binary_sensor.schlaf_tuer_kontakt",))
    await d.step(60, **{A.replace(".", "__"): ("tilted", LAGE), "binary_sensor__schlaf_tuer_kontakt": "on"})
    await d.step(5)
    assert _texts(d.room("schlaf")) == {"tilt": False, "mixed": True}
