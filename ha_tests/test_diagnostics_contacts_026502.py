"""0.26.5.2 (community: two contacts at one window, maybe a self-built three-state
sensor): the anonymous diagnostics tell the kind and origin of every contact and
how many contacts of a room share one display name – still without names or IDs."""
from __future__ import annotations

import json

from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from ha_tests.test_cov_diagnostics_storage import _recorder, cfg  # noqa: F401 - fixture


async def test_contact_kind_origin_and_shared_names(hass, cfg) -> None:  # noqa: F811
    registry = er.async_get(hass)
    template = registry.async_get_or_create("sensor", "template", "schlafzimmer_fenster_3", suggested_object_id="schlafzimmer_fenster")
    hass.states.async_set("binary_sensor.fenster_links", "off", {"friendly_name": "Fenster Schlafzimmer"})
    hass.states.async_set("binary_sensor.fenster_rechts", "off", {"friendly_name": "Fenster Schlafzimmer"})
    hass.states.async_set(template.entity_id, "tilted", {"friendly_name": "Fenster Schlafzimmer (3)"})
    contacts = ["binary_sensor.fenster_links", "binary_sensor.fenster_rechts", template.entity_id]
    recorder = _recorder(hass)
    recorder.update_configuration_snapshot(
        {"rooms": [{"key": "schlaf", "name": "Schlafzimmer", "contacts": contacts}]}, {},
        {"rooms": {"schlaf": {"three_state_contacts": [template.entity_id]}}}, dt_util.now(),
    )
    room = recorder._config_snapshot["rooms"][0]
    assert room["contact_count"] == 3 and room["contacts_sharing_a_name"] == 2
    assert [(o["entity_domain"], o["platform"], o["three_state"]) for o in room["openings"]] == [
        ("binary_sensor", None, False), ("binary_sensor", None, False), ("sensor", "template", True),
    ]
    text = json.dumps(recorder._config_snapshot)
    assert "fenster_links" not in text and "Fenster Schlafzimmer" not in text and template.entity_id not in text
