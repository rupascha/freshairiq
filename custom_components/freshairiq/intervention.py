"""Optional room-climate intervention planning for FreshAirIQ.

The intervention layer deliberately sits *beside* the canonical ventilation
physics.  It never mutates forecasts, learning coefficients or session state.
It translates an already evaluated room state plus optional equipment into a
ranked list of possible actions.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable


@dataclass(slots=True, frozen=True)
class Intervention:
    """One optional action FreshAirIQ can recommend."""

    key: str
    title: str
    reason: str
    priority: int
    entity_id: str | None = None
    service: str | None = None
    service_data: dict[str, Any] | None = None
    category: str = "assist"
    automatic_safe: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _f(value: Any, default: float = 0.0) -> float:
    """Return a finite float; optional sensor/persistence data is untrusted."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if number != number or number in (float("inf"), float("-inf")):
        return default
    return number


def _entity_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item]
    return []


def _service_for_turn_on(entity_id: str | None) -> str | None:
    if not entity_id or "." not in entity_id:
        return None
    domain = entity_id.split(".", 1)[0]
    if domain in {"fan", "switch", "humidifier"}:
        return f"{domain}.turn_on"
    return None


def build_interventions(
    *,
    room: dict[str, Any],
    config: dict[str, Any],
    options: dict[str, Any],
    entity_state: Callable[[str], str | None] | None = None,
) -> list[dict[str, Any]]:
    """Return ranked optional interventions without changing canonical logic.

    The output is deterministic and conservative.  Actuation is opt-in and only
    actions with an explicit Home Assistant service are executable.
    """
    del entity_state  # reserved for state-aware suppression in later releases

    humidity = _f(room.get("humidity"))
    temperature = _f(room.get("temperature"))
    co2 = None if room.get("co2") is None else _f(room.get("co2"))
    voc = None if room.get("voc") is None else _f(room.get("voc"))
    pm25 = None if room.get("pm25") is None else _f(room.get("pm25"))
    illuminance = None if room.get("illuminance") is None else _f(room.get("illuminance"))
    action = str(room.get("action") or "")
    source_active = bool(room.get("moisture_source_active"))
    pollen_blocked = bool(room.get("pollen_blocked"))

    interventions: list[Intervention] = []

    def add(
        key: str,
        title: str,
        reason: str,
        priority: int,
        entity_id: str,
        *,
        service: str | None = None,
        service_data: dict[str, Any] | None = None,
        category: str = "assist",
        automatic_safe: bool = False,
    ) -> None:
        # Every caller resolves and validates an entity id before entering this
        # helper. Keeping that invariant here avoids an unreachable nested branch.
        interventions.append(
            Intervention(
                key=key,
                title=title,
                reason=reason,
                priority=priority,
                entity_id=entity_id,
                service=service,
                service_data=service_data,
                category=category,
                automatic_safe=automatic_safe,
            )
        )

    # Mechanical ventilation / supply air can substitute for a window when the
    # canonical room decision wants fresh air or when CO2 is critical.
    wants_fresh_air = action in {"Ventilate", "Continue ventilating", "Ventilate for cooling"}
    co2_high = co2 is not None and co2 >= _f(options.get("co2_warn"), 1000.0)
    air_quality_high = (
        (voc is not None and voc >= _f(options.get("voc_warn"), 600.0))
        or (pm25 is not None and pm25 >= _f(options.get("pm25_warn"), 15.0))
    )

    ventilation_entity = str(config.get("ventilation_device") or "") or None
    supply_entity = str(config.get("supply_fan") or "") or None
    if wants_fresh_air or co2_high:
        target = ventilation_entity or supply_entity
        if target:
            add(
                "mechanical_ventilation",
                "Mechanische Lüftung nutzen",
                "Frischluftbedarf erkannt; vorhandene Lüftung kann die Fensterlüftung unterstützen oder ersetzen.",
                96 if co2_high else 86,
                target,
                service=_service_for_turn_on(target),
                service_data={"entity_id": target},
                category="ventilation",
                automatic_safe=True,
            )

    # Extraction is most useful during a known moisture event.
    exhaust = str(config.get("exhaust_fan") or "") or None
    if exhaust and (source_active or humidity >= _f(options.get("high_rh"), 68.0)):
        add(
            "extract_moisture",
            "Abluft einschalten",
            "Aktive Feuchtequelle oder hohe Raumfeuchte erkannt.",
            98 if source_active else 90,
            exhaust,
            service=_service_for_turn_on(exhaust),
            service_data={"entity_id": exhaust},
            category="dehumidification",
            automatic_safe=True,
        )

    # A dehumidifier is especially valuable when opening windows is currently
    # unfavourable (pollen veto / no drying gradient).
    dehumidifier = str(config.get("dehumidifier") or "") or None
    if dehumidifier and humidity >= _f(options.get("start_rh"), 62.0):
        priority = 94 if pollen_blocked or action in {"Do not ventilate", "Wait"} else 78
        add(
            "dehumidify",
            "Entfeuchter nutzen",
            "Die Raumfeuchte ist erhöht; technische Entfeuchtung ist verfügbar.",
            priority,
            dehumidifier,
            service=_service_for_turn_on(dehumidifier),
            service_data={"entity_id": dehumidifier},
            category="dehumidification",
            automatic_safe=True,
        )

    # Air purifier for particles/VOC or pollen-limited window ventilation.
    purifier = str(config.get("air_purifier") or "") or None
    if purifier and (air_quality_high or pollen_blocked):
        reason = "Außenluft ist pollenbedingt ungünstig." if pollen_blocked and not air_quality_high else "Erhöhte Partikel-/VOC-Belastung erkannt."
        add(
            "purify_air",
            "Luftreiniger nutzen",
            reason,
            92 if air_quality_high else 82,
            purifier,
            service=_service_for_turn_on(purifier),
            service_data={"entity_id": purifier},
            category="air_quality",
            automatic_safe=True,
        )

    # Humidification is intentionally separated from ventilation and only
    # offered at clearly dry indoor humidity.
    humidifier = str(config.get("humidifier") or "") or None
    if humidifier and 0 < humidity < _f(options.get("humidify_below_rh"), 35.0):
        add(
            "humidify",
            "Luft befeuchten",
            "Die Raumluft ist deutlich trocken.",
            72,
            humidifier,
            service=_service_for_turn_on(humidifier),
            service_data={"entity_id": humidifier},
            category="humidification",
            automatic_safe=True,
        )

    # Shading is a passive first-line cooling measure.  It never replaces a
    # ventilation recommendation; it complements it without consuming energy.
    contact_cover_map = config.get("contact_covers") or {}
    cover_pairs: list[tuple[str | None, str]] = []
    if isinstance(contact_cover_map, dict):
        for contact_id, raw_covers in contact_cover_map.items():
            for cover in _entity_list(raw_covers):
                cover_pairs.append((str(contact_id), cover))
    if not cover_pairs:
        # Compatibility only: old multi-opening rooms could have a room-wide
        # list that cannot be migrated to one opening without guessing.
        cover_pairs = [(None, cover) for cover in _entity_list(config.get("covers"))]
    hot = temperature >= _f(options.get("shade_above_temp_c"), 24.0)
    bright = illuminance is None or illuminance >= _f(options.get("shade_min_illuminance_lx"), 10000.0)
    if cover_pairs and hot and bright:
        for contact_id, cover in cover_pairs:
            add(
                "shade",
                "Sonnenschutz schließen",
                ("Der Raum ist warm und der dieser Öffnung zugeordnete Sonnenschutz steht zur Verfügung." if contact_id else "Der Raum ist warm und Sonnenschutz steht zur Verfügung."),
                76,
                cover,
                service="cover.close_cover",
                service_data={"entity_id": cover},
                category="cooling",
                automatic_safe=True,
            )

    # Climate systems are recommended only when the room is hot and natural
    # cooling is not already the canonical preferred action.  FreshAirIQ does
    # not choose an HVAC mode/target automatically because comfort settings are
    # device- and household-specific.
    climate = str(config.get("climate") or "") or None
    if climate and hot and action != "Ventilate for cooling":
        add(
            "climate_cooling",
            "Klimaanlage prüfen",
            "Der Raum ist warm und natürliche Kühlung ist aktuell nicht die bevorzugte Maßnahme.",
            68,
            climate,
            category="cooling",
            automatic_safe=False,
        )

    interventions.sort(key=lambda item: (-item.priority, item.key, item.entity_id or ""))
    return [item.as_dict() for item in interventions]


def executable_intervention(interventions: list[dict[str, Any]], key: str | None = None) -> dict[str, Any] | None:
    """Return the requested or highest-ranked executable intervention."""
    candidates = [item for item in interventions if item.get("service") and item.get("entity_id")]
    if key:
        candidates = [item for item in candidates if item.get("key") == key]
    return candidates[0] if candidates else None
