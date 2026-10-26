"""0.26.5.4 support case (laundry room with exhaust fan, bedroom, open rooms).

Reproduces the reported sequence in a real Home Assistant: a laundry room
without window contact but with an exhaust fan, a hallway as its reference
room and a bedroom with an open window. When the fan started, the house
counted the fan as an opened window: the fan room was told to close ("switch
off the fan") and the bedroom flipped between "Close" and "Continue
ventilating" every ten seconds although no value changed.
"""
from __future__ import annotations

from custom_components.freshairiq.open_connections import OPTION as OPEN_CONNECTIONS
from ha_tests.test_cov_coordinator_b import HUM, OPTIONS, TEMP, _cleanup_coordinators, _make, _room  # noqa: F401

_OPTIONS = {**OPTIONS, "operating_profile": "comfort", "co2_warn": 1200, "co2_critical": 1450,
            "start_rh": 62, "high_rh": 68, "target_rh": 58, "min_delta": 2.5, "min_delta_high_rh": 1.5}
_STEADY = {"sensor__schlaf_t": (22.7, TEMP), "sensor__schlaf_h": (48.0, HUM),
           "sensor__wk_t": (24.4, TEMP), "sensor__wk_h": (62.0, HUM)}
_INIT = {
    "sensor.aussen_t": (12.0, TEMP), "sensor.aussen_h": (84.0, HUM), "sensor.wk_t": (24.4, TEMP), "sensor.wk_h": (62.0, HUM),
    "sensor.flur_t": (24.2, TEMP), "sensor.flur_h": (9.6, HUM), "switch.wk_luefter": ("off", {}),
    "binary_sensor.haustuer": ("off", {"device_class": "door"}), "sensor.schlaf_t": (22.7, TEMP),
    "sensor.schlaf_h": (48.0, HUM), "binary_sensor.schlaf_fenster": ("on", {"device_class": "window"}),
    "sensor.ab_t": (21.0, TEMP), "sensor.ab_h": (70.0, HUM), "sensor.kammer_t": (21.0, TEMP), "sensor.kammer_h": (70.0, HUM),
}


def _data(*, fan: bool = True) -> dict:
    wk = _room("waschkuche", "Waschküche", "ground_floor", temp=["sensor.wk_t"], hum=["sensor.wk_h"], volume=9,
               exhaust="switch.wk_luefter" if fan else "",
               extra={"exhaust_fan_reference_temperature": "sensor.flur_t", "exhaust_fan_reference_humidity": "sensor.flur_h",
                      "moisture_sources": ["washing_machine"]} if fan else None)
    flur = _room("flur", "Flur", "ground_floor", temp=["sensor.flur_t"], hum=["sensor.flur_h"], contacts=["binary_sensor.haustuer"], volume=43)
    schlaf = _room("schlaf", "Schlafzimmer", "ground_floor", temp=["sensor.schlaf_t"], hum=["sensor.schlaf_h"],
                   contacts=["binary_sensor.schlaf_fenster"], volume=36)
    abstell = _room("abstell", "Abstellraum", "ground_floor", temp=["sensor.ab_t"], hum=["sensor.ab_h"], volume=9)
    kammer = _room("kammer", "Kammer", "ground_floor", temp=["sensor.kammer_t"], hum=["sensor.kammer_h"], volume=6)
    return {"outdoor_temperature": "sensor.aussen_t", "outdoor_humidity": "sensor.aussen_h",
            "rooms": [wk, flur, schlaf, abstell, kammer], "levels": ["ground_floor"]}


async def test_running_fan_is_no_opened_window_for_the_house(hass, freezer) -> None:
    d = await _make(hass, freezer, data=_data(), options=_OPTIONS, initial=_INIT)
    for _ in range(50):
        await d.step(30, **_STEADY)
    before = d.room("waschkuche")
    # no window, an exhaust fan: the task is the fan, not "air via a connected room"
    assert before["action"] == "Ventilate indirectly" and before["contact_count"] == 0
    assert before["action_hint"] in {"Ablüfter einschalten", "Switch on the exhaust fan"}
    assert "exhaust fan" in before["reason"] and "connected room" not in before["reason"]

    await d.step(5, switch__wk_luefter="on")
    rows = []
    for i in range(40):  # ten-second steps, values unchanged (the reported 12:55 sequence)
        await d.step(10, **(_STEADY if i % 3 == 0 else {}))
        iq = d.data["intelligent_recommendation"]
        rows.append((d.room("schlaf")["action"], d.room("waschkuche")["action"], iq["kind"], list(iq.get("room_keys") or []),
                     list(iq.get("room_names") or [])))
        names = {k: d.room(k)["name"] for k in iq.get("room_keys") or []}
        # the names belong to the selected keys (record 1278: keys of three rooms, name of a fourth)
        assert list(iq.get("room_names") or []) == [names[k] for k in iq.get("room_keys") or []]
    bedroom = [r[0] for r in rows]
    assert len(set(bedroom)) == 1, bedroom  # no Close/Continue flip without a changed value
    assert all(r[1] != "Close" for r in rows)  # the drying fan is not told to stop by the house
    assert not any("waschkuche" in r[3] for r in rows)  # a fan alone is judged by its own room model
    assert "action_hint" not in d.room("waschkuche")  # fan runs: nothing to switch on


async def test_rooms_without_window_name_only_known_air_paths(hass, freezer) -> None:
    options = {**_OPTIONS, OPEN_CONNECTIONS: {"abstell": ["flur"]}}
    d = await _make(hass, freezer, data=_data(fan=False), options=options, initial=_INIT)
    for _ in range(20):
        await d.step(30)
    abstell, kammer = d.room("abstell"), d.room("kammer")
    assert abstell["action"] == kammer["action"] == "Ventilate indirectly"
    assert abstell["reason"].endswith("open connection to Flur")
    assert "connected room" not in kammer["reason"] and "neighbouring room if possible" in kammer["reason"]
    assert "action_hint" not in abstell and "action_hint" not in kammer
