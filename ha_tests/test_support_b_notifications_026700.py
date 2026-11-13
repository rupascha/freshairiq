"""0.26.7.0 support case B (real Home Assistant service registry): presence → decision → category → exceptions →
cooldown → delivery status, for the house scope of the reported setup.

Summarised evidence only: notification_scope=house, notify_only_when_home=true, notify_important_when_away=true,
notification_cooldown_min=90, repeat_recommendation_cooldown_min=120, two person trackers, one target; an
``iq_ventilate`` was "sent" while the closest presence sample (≈12 s away) said home=0, away=2, and ``iq_close`` /
``iq_ventilate`` followed each other within 5:38 min. The traces did not record presence at the send moment, so the
real cause cannot be proven from them. This test shows what the code does in each case and that every send attempt
now records the presence counts and the rule applied (no entity ids, no names).
"""
from __future__ import annotations

from datetime import timedelta

from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.freshairiq.notifications import process_notifications
from ha_tests.test_cov_notifications import NOW, Store, _options

TRACKERS = ["person.a", "person.b"]


def _house_options(**overrides):
    values = {
        "notification_scope": "house", "notification_targets": ["notify.phone"], "notification_cooldown_min": 90,
        "repeat_recommendation_cooldown_min": 120, "notify_only_when_home": True, "notify_important_when_away": True,
        "suppress_notifications_at_night": True, "adult_occupants": 2, "adult_presence_entities": TRACKERS,
    }
    values.update(overrides)
    return _options(**values)


def _data(kind: str, *, keys=("bad",), surface_rh: float = 60.0):
    rooms = {k: {"key": k, "name": k.title(), "action": "Wait", "data_quality": "ok", "mould_level": "Low",
                 "surface_rh": surface_rh} for k in keys}
    return {"rooms": rooms, "intelligent_recommendation": {"kind": kind, "room_keys": list(keys), "instruction": f"{kind} now"}}


def _house_rows(store, event):
    return [r for r in store.data.get("notification_diagnostics", []) if r.get("event") == event and r.get("scope") == "house"]


def _presence(hass, a: str, b: str) -> None:
    hass.states.async_set(TRACKERS[0], a)
    hass.states.async_set(TRACKERS[1], b)


async def test_house_chain_presence_category_exception_cooldown_status(hass) -> None:
    phone = async_mock_service(hass, "notify", "phone")
    store, options = Store(), _house_options()

    # everybody away: the house "ventilate" is held back, recorded as recipients_away with the evidence
    _presence(hass, "not_home", "Arbeit")
    await process_notifications(hass, store, _data("ventilate"), options, NOW, [])
    assert len(phone) == 0
    row = _house_rows(store, "iq_ventilate")[-1]
    assert (row["status"], row["reason"]) == ("not_sent", "recipients_away")
    assert row["presence"] == {"home": 0, "away": 2, "unknown": 0, "rule": "applied"}
    assert "person.a" not in str(row) and "Arbeit" not in str(row)            # counts only

    # an important warning still reaches the absent household (the configured exception)
    await process_notifications(hass, store, _data("sensor", keys=("garage",)), options, NOW, [])
    assert len(phone) == 1
    sensor_row = _house_rows(store, "iq_sensor")[-1]
    assert sensor_row["status"] == "sent" and sensor_row["presence"]["rule"] == "important_exception"

    # one tracker returns: the unchanged, not yet delivered recommendation goes out now – with evidence home=1
    _presence(hass, "home", "Arbeit")
    later = NOW + timedelta(minutes=1)
    await process_notifications(hass, store, _data("ventilate"), options, later, [])
    assert len(phone) == 2
    sent = _house_rows(store, "iq_ventilate")[-1]
    assert sent["status"] == "sent" and sent["presence"] == {"home": 1, "away": 1, "unknown": 0, "rule": "applied"}

    # a changed ventilate within the 90 min cooldown is suppressed (cooldown, not presence)
    await process_notifications(hass, store, _data("ventilate", keys=("bad", "kueche")), options, later + timedelta(minutes=5), [])
    assert len(phone) == 2
    assert _house_rows(store, "iq_ventilate")[-1]["reason"] == "cooldown"


async def test_close_then_ventilate_within_the_repeat_cooldown_is_held_unless_protection(hass) -> None:
    phone = async_mock_service(hass, "notify", "phone")
    store, options = Store(), _house_options()
    _presence(hass, "home", "home")
    await process_notifications(hass, store, _data("close"), options, NOW, [])
    assert len(phone) == 1
    # 5:38 min later: the reported opposite message – held by the repeat cooldown (120 min)
    await process_notifications(hass, store, _data("ventilate"), options, NOW + timedelta(minutes=5, seconds=38), [])
    assert len(phone) == 1
    # a critical mould risk in the named room is protection: it may reopen at once
    await process_notifications(hass, store, _data("ventilate", surface_rh=95.0), options, NOW + timedelta(minutes=6), [])
    assert len(phone) == 2


async def test_option_off_or_unknown_tracker_never_hides_a_message(hass) -> None:
    phone = async_mock_service(hass, "notify", "phone")
    store = Store()
    _presence(hass, "not_home", "unknown")              # unknown counts as home: nothing is suppressed on missing data
    await process_notifications(hass, store, _data("ventilate"), _house_options(), NOW, [])
    assert len(phone) == 1
    assert _house_rows(store, "iq_ventilate")[-1]["presence"] == {"home": 0, "away": 1, "unknown": 1, "rule": "applied"}
    store2 = Store()
    _presence(hass, "not_home", "not_home")
    await process_notifications(hass, store2, _data("ventilate"), _house_options(notify_only_when_home=False), NOW, [])
    assert len(phone) == 2
    assert _house_rows(store2, "iq_ventilate")[-1]["presence"]["rule"] == "off"
