"""Coordinator for FreshAirIQ."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from math import cos, pi
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import *
from .energy import energy_price_per_kwh_equivalent, exchanged_air_fraction, heating_cost_context, ventilation_cost, ventilation_cost_for_duration, ventilation_cost_for_temperature_path
from .forecast import effective_night_rate_ml_h, estimated_daily_moisture_ml, horizon_forecast, in_night_window, night_interval_bounds, night_window_hours, overnight_forecast_ml, remaining_night_hours, update_night_learning
from .model import RoomInput, absolute_humidity, evaluate_room, update_learning
from .moisture_source import update_moisture_source
from .notifications import process_notifications
from .presence import resolve_occupancy
from .recommendation import build_recommendation
from .opening_strategy import enrich_opening_recommendation
from .personal_context import build_resident_context, personalise_recommendation
from .language_confidence import adapt_language_confidence
from .live_coach import refine_live_recommendation
from .anticipation import refine_with_anticipation
from .planner import build_multi_hour_plan, refine_with_plan
from .passive_ventilation import evaluate_passive_ventilation
from .intelligence import (
    build_intelligence_state, clear_session_behaviour, ensure_behaviour_defaults,
    learn_completed_session, learn_outcome_feedback, mark_recommendation_followed, sync_active_recommendation,
)
from .storage import LearningStore
from .decision import build_decision_simulation
from .weather_future import async_hourly_forecast, future_boundaries
from .routines import expected_source_rate, learn_source_pattern, project_generation_ml, response_pattern, routine_maturity
from .strategy import strategy_maturity
from .seasonality import learn_seasonal_source, seasonal_context
from .house_strategy import learn_house_outcome, house_strategy_fit, house_maturity
from .consolidation import aggregate_close_allowed, aggregate_close_gate_ready, stabilise_recommendation
from .decision_brain import build_unified_decision
from .decision_trace import build_decision_trace, build_recommendation_quality
from .diagnostics import FreshAirIQDiagnosticsRecorder
from .telemetry import FreshAirIQDiagnosticsClient
from .ventilation_result import append_completed_sessions, finalise_ventilation_group, include_ventilation_group_start, new_ventilation_group, update_session_cross_tracking
from .forecast_validation import (
    append_validation_record,
    build_validation_record,
    evaluate_start_forecast_at_duration,
    freeze_start_forecast_context,
    prediction_duration_comparable,
    validation_summary,
)
from .forecast_backtest import backtest_summary
from .measurement_frame import build_measurement_frame, last_valid_session_measurement, report_timestamp_after_boundary, session_measurement_quality, trusted_session_end_baseline
from .post_stabilization import start_post_close_observation, update_post_close_observation, prune_history as prune_stabilization_history, stabilization_summary
from .learning_components import build_learning_components_status
from .robustness import RobustnessMonitor, finite_float, prepare_runtime_rooms, safe_options
from .intervention import build_interventions
from .repairs import async_sync_missing_entity_issue

if TYPE_CHECKING:
    from .typing import FreshAirIQConfigEntry

_LOGGER = logging.getLogger(__name__)


def _float_state(hass: HomeAssistant, entity_id: str | None) -> float | None:
    if not entity_id: return None
    state = hass.states.get(entity_id)
    if state is None or state.state in {"unknown", "unavailable", "none", ""}: return None
    return finite_float(state.state)




def _state_report_timestamp(state: Any) -> str | None:
    """Return the newest sensor report timestamp with HA-version fallback.

    Home Assistant's ``last_reported`` advances for every state report, even
    when the value is unchanged. Older HA versions may not expose it, so
    ``last_updated`` remains the compatibility fallback.
    """
    if state is None:
        return None
    stamp = getattr(state, "last_reported", None) or getattr(state, "last_updated", None)
    return stamp.isoformat() if stamp is not None else None

def _weather_values(hass: HomeAssistant, entity_id: str | None) -> tuple[float | None, float | None]:
    if not entity_id: return None, None
    state = hass.states.get(entity_id)
    if state is None: return None, None
    temperature = finite_float(state.attributes.get("temperature"))
    humidity = finite_float(state.attributes.get("humidity"))
    return temperature, humidity


def _weather_wind(hass: HomeAssistant, entity_id: str | None) -> tuple[float | None, float | None]:
    if not entity_id: return None, None
    state = hass.states.get(entity_id)
    if state is None: return None, None
    bearing = state.attributes.get("wind_bearing")
    speed = state.attributes.get("wind_speed")
    bearing = finite_float(bearing)
    speed = finite_float(speed)
    return bearing, speed


def _contact_ids(room: dict[str, Any]) -> list[str]:
    contacts = room.get(CONF_ROOM_CONTACTS)
    if isinstance(contacts, str): return [contacts]
    if isinstance(contacts, list): return [str(x) for x in contacts if x]
    legacy = room.get(CONF_ROOM_CONTACT)
    return [legacy] if legacy else []



def _contact_specific_reference(
    hass: HomeAssistant, room: dict[str, Any], *,
    default_temp_entity: str | None, default_humidity_entity: str | None,
    default_temp: float | None, default_humidity: float | None,
) -> tuple[str | None, str | None, float | None, float | None]:
    """Return the conservative reference-air pair for the currently open contacts.

    A room may have openings into different air zones (for example outside and
    a winter garden). Each open contact contributes its own configured pair; an
    unconfigured contact inherits the room/global reference. If several openings
    are open at once, the moistest valid source is used. This is deliberately
    conservative: FreshAirIQ must not promise more dehumidification than the
    least favourable incoming air stream supports.
    """
    temp_map = room.get(CONF_CONTACT_REFERENCE_TEMPERATURES) or {}
    humidity_map = room.get(CONF_CONTACT_REFERENCE_HUMIDITIES) or {}
    open_ids = [cid for cid in _contact_ids(room) if _open_seconds(hass, cid, dt_util.utcnow()) is not None]
    if not open_ids:
        return default_temp_entity, default_humidity_entity, default_temp, default_humidity
    candidates = []
    for cid in open_ids:
        contact_te = str(temp_map.get(cid) or "").strip() or None
        contact_he = str(humidity_map.get(cid) or "").strip() or None
        local_configured = bool(contact_te or contact_he)
        # A local reference is atomic: never mix e.g. Wintergarten temperature
        # with outdoor humidity. More importantly, an explicitly configured
        # local source that is unavailable must NEVER silently turn into outside
        # air. With several simultaneously open paths, one unknown source makes
        # the combined incoming air unknown as well, so fail closed for the room.
        if contact_te and contact_he:
            te, he = contact_te, contact_he
            tv, hv = _float_state(hass, te), _float_state(hass, he)
        elif local_configured:
            return contact_te, contact_he, None, None
        else:
            te, he = default_temp_entity, default_humidity_entity
            tv, hv = default_temp, default_humidity
        if tv is None or hv is None or not (-30 < tv < 60 and 0 <= hv <= 100):
            return te, he, None, None
        candidates.append((absolute_humidity(tv, hv), te, he, tv, hv))
    if not candidates:
        return default_temp_entity, default_humidity_entity, default_temp, default_humidity
    _ah, te, he, tv, hv = max(candidates, key=lambda item: item[0])
    return te, he, tv, hv

def _opening_assessments(
    hass: HomeAssistant, room: dict[str, Any], *,
    room_temperature: float, room_humidity: float, volume_m3: float,
    default_temp_entity: str | None, default_humidity_entity: str | None,
    default_temp: float | None, default_humidity: float | None,
    learning_rate: float, learning_samples: int, co2: float | None, pollen: float,
    options: dict[str, Any], wind_bearing: float | None, wind_speed: float | None,
) -> list[dict[str, Any]]:
    """Evaluate every configured opening against its own incoming air.

    This is a side-channel decision aid only: it does not alter the canonical
    room result, forecast, learning state or session physics. Each opening is
    run through the same pure ``evaluate_room`` model with the same learned
    exchange rate, but with that opening's source-air pair and orientation.
    """
    temp_map = room.get(CONF_CONTACT_REFERENCE_TEMPERATURES) or {}
    humidity_map = room.get(CONF_CONTACT_REFERENCE_HUMIDITIES) or {}
    orientation_map = room.get(CONF_CONTACT_ORIENTATIONS) or {}
    fallback_orientation = str(room.get(CONF_ROOM_WINDOW_ORIENTATION, ORIENTATION_UNKNOWN))
    wind_enabled = bool(options.get("wind_orientation_enabled", True))
    out: list[dict[str, Any]] = []

    for contact in _contact_ids(room):
        local_te = str(temp_map.get(contact) or "").strip() or None
        local_he = str(humidity_map.get(contact) or "").strip() or None
        local_configured = bool(local_te or local_he)
        pair_complete = bool(local_te and local_he)
        if pair_complete:
            te, he = local_te, local_he
            source_t, source_rh = _float_state(hass, te), _float_state(hass, he)
            source_label = "lokale Referenz"
        elif local_configured:
            # Existing malformed legacy data must never be mixed with outdoor
            # values. Mark the opening unavailable until the pair is completed.
            te, he = local_te, local_he
            source_t, source_rh = None, None
            source_label = "unvollständige lokale Referenz"
        else:
            te, he = default_temp_entity, default_humidity_entity
            source_t, source_rh = default_temp, default_humidity
            source_label = "Außen-/Raumreferenz"

        state = hass.states.get(contact)
        friendly = str((state.attributes.get("friendly_name") if state else None) or contact)
        orientation = str(orientation_map.get(contact, fallback_orientation))
        airflow = _orientation_factor(orientation, wind_bearing, wind_speed, wind_enabled)
        available = (
            source_t is not None and source_rh is not None
            and -30 < float(source_t) < 60 and 0 <= float(source_rh) <= 100
        )
        row: dict[str, Any] = {
            "entity_id": contact,
            "name": friendly,
            "is_open": _open_seconds(hass, contact, dt_util.utcnow()) is not None,
            "orientation": orientation,
            "airflow_factor": airflow,
            "source_kind": "local_reference" if pair_complete else "default_reference",
            "source_label": source_label,
            "reference_temperature_entity": te,
            "reference_humidity_entity": he,
            "available": bool(available),
        }
        if not available:
            row["reason"] = "Referenzsensoren fehlen oder liefern keine gültigen Werte"
            out.append(row)
            continue

        simulated = evaluate_room(
            RoomInput(
                key=str(room.get("key") or "opening"),
                name=str(room.get(CONF_ROOM_NAME) or room.get("name") or "Raum"),
                temperature=float(room_temperature), humidity=float(room_humidity),
                reference_temperature=float(source_t), reference_humidity=float(source_rh),
                volume_m3=float(volume_m3), contact_open=False, contact_open_seconds=0.0,
                learning_rate=float(learning_rate), learning_samples=int(learning_samples),
                co2=co2, session_active=False, airflow_factor=airflow, pollen_index=float(pollen),
            ),
            options,
            False,
        )
        row.update({
            "reference_temperature_c": round(float(source_t), 2),
            "reference_humidity_percent": round(float(source_rh), 2),
            "reference_absolute_humidity_g_m3": round(absolute_humidity(float(source_t), float(source_rh)), 3),
            "delta_g_m3": round(float(simulated.delta_g_m3), 3),
            "potential_ml": int(simulated.potential_ml),
            "moisture_effect_next_5_min_ml": int(simulated.moisture_effect_next_5_min_ml),
            "temperature_effect_next_5_min_c": round(float(simulated.temp_next_5_min_c), 3),
            "ventilation_candidate": bool(simulated.ventilation_candidate),
            "cooling_candidate": bool(simulated.cooling_candidate),
            "model_action": str(simulated.action),
        })
        out.append(row)
    return out


def _open_seconds(hass: HomeAssistant, entity_id: str, now: datetime) -> float | None:
    state = hass.states.get(entity_id)
    if state is None or state.state not in {"on", "open", "opening"}: return None
    return max(0.0, (now - state.last_changed).total_seconds())


def _room_contacts_known(hass: HomeAssistant, room: dict[str, Any]) -> bool:
    """Return False while HA is still restoring a configured contact after startup."""
    ids = _contact_ids(room)
    if not ids:
        return True
    return all(
        (state := hass.states.get(entity_id)) is not None
        and state.state not in {"unknown", "unavailable", "none", ""}
        for entity_id in ids
    )


def _room_physical_opened_at(hass: HomeAssistant, room: dict[str, Any]) -> datetime | None:
    """Return the earliest current physical opening timestamp for a room."""
    opened: list[datetime] = []
    for entity_id in _contact_ids(room):
        state = hass.states.get(entity_id)
        if state is not None and state.state in {"on", "open", "opening"}:
            changed = getattr(state, "last_changed", None)
            if isinstance(changed, datetime):
                opened.append(changed)
    return min(opened) if opened else None


def _room_closed_for_seconds(hass: HomeAssistant, room: dict[str, Any], now: datetime) -> float | None:
    """Return how long the room has continuously been in its logical closed state.

    The contact mode matters: with ``any`` ventilation ends only when *all*
    contacts are closed, so the newest close transition defines the start of the
    closed state. With ``all`` ventilation ends when *any* required contact is
    closed, so the oldest currently closed contact defines that state. ``None``
    means the room is still logically open (or a contact state is unknown).
    """
    ids = _contact_ids(room)
    if not ids:
        return None
    open_states = {"on", "open", "opening"}
    unknown_states = {"unknown", "unavailable", "none", ""}
    closed_seconds: list[float] = []
    open_count = 0
    for entity_id in ids:
        state = hass.states.get(entity_id)
        if state is None or state.state in unknown_states:
            return None
        if state.state in open_states:
            open_count += 1
            continue
        closed_seconds.append(max(0.0, (now - state.last_changed).total_seconds()))

    mode = room.get(CONF_CONTACT_MODE, CONTACT_MODE_ANY)
    if mode == CONTACT_MODE_ALL:
        if open_count == len(ids):
            return None
        return max(closed_seconds) if closed_seconds else 0.0
    if open_count:
        return None
    return min(closed_seconds) if closed_seconds else 0.0


def _room_ventilation_state(hass: HomeAssistant, room: dict[str, Any], now: datetime, *, honour_delays: bool = False) -> tuple[bool, float]:
    ids = _contact_ids(room)
    if not ids: return False, 0.0
    delays = room.get(CONF_CONTACT_DELAYS) or {}
    fallback = int(room.get(CONF_CONTACT_DELAY, 0))
    opened: list[tuple[str, float]] = []
    for entity_id in ids:
        sec = _open_seconds(hass, entity_id, now)
        if sec is not None:
            opened.append((entity_id, sec))
    mode = room.get(CONF_CONTACT_MODE, CONTACT_MODE_ANY)

    def ready(item: tuple[str, float]) -> tuple[bool, float]:
        entity_id, sec = item
        delay = float(delays.get(entity_id, fallback)) if honour_delays else 0.0
        return sec >= delay, max(sec - delay, 0.0)

    if mode == CONTACT_MODE_ALL:
        if len(opened) != len(ids): return False, 0.0
        checked = [ready(x) for x in opened]
        if not all(x[0] for x in checked): return False, 0.0
        return True, min(x[1] for x in checked)
    checked = [ready(x) for x in opened]
    elapsed = [x[1] for x in checked if x[0]]
    return (True, max(elapsed)) if elapsed else (False, 0.0)


_ORIENTATION_DEG = {"n": 0, "ne": 45, "e": 90, "se": 135, "s": 180, "sw": 225, "w": 270, "nw": 315}


def _orientation_factor(orientation: str, wind_bearing: float | None, wind_speed: float | None, enabled: bool) -> float:
    """Conservative pressure-side airflow modifier from local wind direction."""
    if not enabled or orientation not in _ORIENTATION_DEG or wind_bearing is None: return 1.0
    speed_weight = min(max((wind_speed or 0.0) / 5.0, 0.0), 1.0)
    delta = abs((_ORIENTATION_DEG[orientation] - wind_bearing + 180) % 360 - 180)
    alignment = cos(delta * pi / 180.0)
    return round(min(max(1.0 + 0.30 * alignment * speed_weight, 0.70), 1.30), 3)


def _room_orientation_factor(hass: HomeAssistant, room: dict[str, Any], now: datetime, wind_bearing: float | None, wind_speed: float | None, enabled: bool) -> float:
    """Combine per-contact orientations; while ventilating, only open contacts count."""
    contacts = _contact_ids(room)
    mapping = room.get(CONF_CONTACT_ORIENTATIONS) or {}
    fallback = str(room.get(CONF_ROOM_WINDOW_ORIENTATION, ORIENTATION_UNKNOWN))
    open_contacts = [c for c in contacts if _open_seconds(hass, c, now) is not None]
    relevant = open_contacts or contacts
    if not relevant:
        return _orientation_factor(fallback, wind_bearing, wind_speed, enabled)
    factors = [_orientation_factor(str(mapping.get(c, fallback)), wind_bearing, wind_speed, enabled) for c in relevant]
    # Multiple openings on different façades should not create an unrealistic
    # wind bonus. Their mean is deliberately conservative; cross ventilation
    # is handled separately by the learned/cross-ventilation model.
    return round(sum(factors) / len(factors), 3)


def _recommendation(result: Any, options: dict[str, Any], *, pollen: float, co2: float | None, airflow: float, wind_bearing: float | None, wind_speed: float | None) -> tuple[str, str, list[str]]:
    """Build a room-specific recommendation with an explicit trigger and suitability reason.

    The house threshold is intentionally *not* used here. A room can therefore
    require ventilation because of its own RH / surface-RH / CO2 even when the
    summed house potential is still below the house-wide threshold.
    """
    reasons: list[str] = []
    if result.data_quality != "ok":
        return "Check sensor", "Messwerte fehlen oder sind unplausibel", ["Messwerte fehlen oder sind unplausibel; Sensoren prüfen"]

    start_rh = float(options.get("start_rh", 62.0))
    high_rh = float(options.get("high_rh", 68.0))
    mould_warn = float(options.get("mould_warn_surface_rh", 80.0))
    mould_critical = float(options.get("mould_critical_surface_rh", 90.0))
    co2_warn = float(options.get("co2_warn", 1000.0))
    co2_critical = float(options.get("co2_critical", 1400.0))
    min_delta = float(options.get("min_delta", 2.5))
    min_delta_high = float(options.get("min_delta_high_rh", 1.5))
    if str(options.get("operating_profile", "comfort")) == "dehumidify":
        min_delta = max(0.1, min_delta * 0.85)
        min_delta_high = max(0.1, min_delta_high * 0.85)

    humidity_high = float(result.humidity or 0) >= high_rh
    humidity_start = float(result.humidity or 0) >= start_rh
    mould_high = float(result.surface_rh or 0) >= mould_warn
    co2_high = co2 is not None and co2 >= co2_warn
    co2_urgent = co2 is not None and co2 >= co2_critical
    urgent = float(result.surface_rh or 0) >= mould_critical or co2_urgent
    pollen_blocked = bool(options.get("pollen_enabled", False)) and bool(options.get("pollen_strict_veto", True)) and pollen > float(options.get("pollen_max", 4)) and not urgent

    # State the room-specific trigger first. This text is shown verbatim in the
    # dashboard and notifications, so the user can immediately see *why* this
    # room needs attention.
    if humidity_high:
        reasons.append(f"Raumluftfeuchte {round(float(result.humidity or 0))} % ist zu hoch (Grenze {round(high_rh)} %)")
    elif humidity_start:
        reasons.append(f"Raumluftfeuchte {round(float(result.humidity or 0))} % liegt über dem Lüftungsstartwert {round(start_rh)} %")
    if mould_high:
        reasons.append(f"Oberflächenfeuchte {round(float(result.surface_rh or 0))} % erhöht das Schimmelrisiko")
    if co2_urgent:
        reasons.append(f"CO₂ {round(co2)} ppm ist kritisch (Grenze {round(co2_critical)} ppm)")
    elif co2_high:
        reasons.append(f"CO₂ {round(co2)} ppm liegt über der Warnschwelle {round(co2_warn)} ppm")

    source_active = bool(getattr(result, "moisture_source_active", False))
    source_label = str(getattr(result, "moisture_source_label", "Feuchtequelle") or "Feuchtequelle")
    source_conf = int(getattr(result, "moisture_source_confidence", 0) or 0)
    source_rate = float(getattr(result, "moisture_source_rate_ml_min", 0.0) or 0.0)
    if source_active:
        reasons.append(f"{source_label} wahrscheinlich aktiv ({source_conf} % Sicherheit); interne Feuchteproduktion etwa {source_rate * 60:.0f} ml/h")

    if result.active and source_active and float(result.delta_g_m3) > float(options.get("close_delta", 0.4)) and not pollen_blocked:
        action = "Continue ventilating"
        reasons.append("Die Referenzluft ist weiterhin trockener; die steigende Raumfeuchte stammt trotz wirksamer Lüftung aus der aktiven Feuchtequelle")
    elif result.active and result.close_recommended:
        action = "Close"
        if bool(getattr(result, "close_decision_model_fallback", False)):
            if bool(getattr(result, "future_moisture_risk_15", False)):
                reasons.append("Seit 15 Minuten fehlen zwei neue Klimamessungen; Wetterprognose zeigt, dass der Trocknungsvorteil in den nächsten 15 Minuten voraussichtlich verloren geht")
            else:
                reasons.append("Seit 15 Minuten fehlen zwei neue Klimamessungen; FreshAirIQ entscheidet ersatzweise anhand des physikalischen und gelernten Lüftungsmodells")
        else:
            reasons.append("Lüftungsziel erreicht oder zusätzlicher Nutzen ist zu gering")
    elif result.active:
        action = "Continue ventilating"
        if not bool(getattr(result, "close_decision_ready", True)):
            fresh = max(int(getattr(result, "fresh_measurements", 0) or 0), 0)
            reasons.append(f"Schließentscheidung wartet auf neue Klimamessungen ({fresh}/2)")
        elif bool(getattr(result, "close_decision_model_fallback", False)):
            reasons.append("Seit 15 Minuten fehlen zwei neue Klimamessungen; Modellbewertung sieht aktuell noch einen sinnvollen Lüftungsvorteil")
        else:
            reasons.append(f"Kurzfristiger Schließcheck (5 min): voraussichtlich {max(round(result.moisture_effect_next_5_min_ml), 0)} ml Feuchteabbau")
    elif pollen_blocked and (result.ventilation_candidate or result.cooling_candidate):
        action = "Do not ventilate"
        reasons.append(f"Pollenindex {pollen:.1f} liegt über dem Grenzwert {float(options.get('pollen_max',4)):.1f}")
    elif result.ventilation_candidate:
        action = "Ventilate"
        required_delta = min_delta_high if humidity_high else min_delta
        reasons.append(f"Außen-/Referenzluft ist {float(result.delta_g_m3):.1f} g/m³ trockener (mindestens {required_delta:.1f} g/m³ nötig)")
        reasons.append(f"Aktuell sind etwa {max(round(result.potential_ml),0)} ml Feuchtigkeit entfernbar")
    elif result.cooling_candidate:
        action = "Ventilate for cooling"
        reasons.append("Außenluft ist ausreichend kühler und der Feuchteeintrag bleibt vertretbar")
    elif humidity_high or mould_high or co2_high:
        # There is a genuine room problem, but the reference air is currently
        # unsuitable or not yet effective enough. Do not hide the trigger behind
        # a generic house-threshold message.
        if float(result.delta_g_m3) <= 0:
            action = "Do not ventilate"
            reasons.append("Lüften aktuell nicht sinnvoll: Außen-/Referenzluft ist gleich feucht oder feuchter")
        else:
            action = "Wait"
            required_delta = min_delta_high if humidity_high else min_delta
            reasons.append(f"Lüften noch nicht wirksam genug: Außen-/Referenzluft ist nur {float(result.delta_g_m3):.1f} g/m³ trockener; benötigt werden etwa {required_delta:.1f} g/m³")
    elif result.delta_g_m3 < -0.4:
        action = "Do not ventilate"
        reasons.append("Außen-/Referenzluft würde zusätzliche Feuchtigkeit eintragen")
    elif result.potential_ml > 0:
        action = "Wait"
        reasons.append("Etwas Entfeuchtungspotenzial vorhanden, aber noch kein raumspezifischer Lüftungsbedarf")
    else:
        action = "Okay"
        reasons.append("Kein relevanter Lüftungsbedarf")

    if bool(options.get("wind_orientation_enabled", True)) and wind_bearing is not None and action in {"Ventilate", "Continue ventilating", "Ventilate for cooling"}:
        if airflow >= 1.12:
            reasons.append("Windrichtung unterstützt den Luftwechsel")
        elif airflow <= .88:
            reasons.append("Windrichtung bremst den Luftwechsel")
        elif wind_speed is not None:
            reasons.append("Wind hat aktuell nur geringen Einfluss")
    return action, "; ".join(reasons), reasons


class FreshAirIQCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: "FreshAirIQConfigEntry", store: LearningStore) -> None:
        super().__init__(hass, logger=__import__("logging").getLogger(__name__), name=DOMAIN,
                         update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL), config_entry=entry)
        self.entry = entry; self.store = store; self._unsub_state = None; self._first_update = True
        self._contact_entities: set[str] = set()
        self._contact_confirm_unsubs: dict[str, Any] = {}
        self._final_measurement_unsubs: dict[str, Any] = {}
        self._refresh_coalesce_unsub = None
        self._hourly_forecast_cache: list[dict[str, Any]] = []
        self._hourly_forecast_fetched_at: datetime | None = None
        self.diagnostics = FreshAirIQDiagnosticsRecorder(hass, entry.entry_id, VERSION)
        self.robustness = RobustnessMonitor()
        self.telemetry = FreshAirIQDiagnosticsClient(
            hass,
            entry,
            self.diagnostics,
            health_provider=lambda: {
                "robustness": self.robustness.snapshot(),
                "diagnostics": self.diagnostics.status,
            },
        )
        self._unavailable_required_sources: set[str] = set()


    def _required_source_entities(self) -> set[str]:
        """Return entities whose loss prevents reliable core calculations."""
        required: set[str] = set()
        for entity_id in (
            self.entry.data.get(CONF_OUTDOOR_WEATHER),
            self.entry.data.get(CONF_OUTDOOR_TEMPERATURE),
            self.entry.data.get(CONF_OUTDOOR_HUMIDITY),
        ):
            if entity_id:
                required.add(str(entity_id))
        rooms = self.entry.data.get(CONF_ROOMS, [])
        if isinstance(rooms, list):
            for room in rooms:
                if not isinstance(room, dict) or not room.get(CONF_ROOM_INCLUDE_CALCULATIONS, True):
                    continue
                for key in (CONF_ROOM_TEMPERATURE, CONF_ROOM_HUMIDITY):
                    entity_id = room.get(key)
                    if entity_id:
                        required.add(str(entity_id))
                required.update(str(entity_id) for entity_id in _contact_ids(room) if entity_id)
        return required

    def _log_required_source_availability(self) -> None:
        """Log required-source loss and recovery once per state transition."""
        unavailable: set[str] = set()
        for entity_id in self._required_source_entities():
            state = self.hass.states.get(entity_id)
            if state is None or str(state.state).lower() in {"unknown", "unavailable", "none", ""}:
                unavailable.add(entity_id)

        newly_unavailable = unavailable - self._unavailable_required_sources
        recovered = self._unavailable_required_sources - unavailable
        for entity_id in sorted(newly_unavailable):
            _LOGGER.info("Required FreshAirIQ source %s is unavailable", entity_id)
        for entity_id in sorted(recovered):
            _LOGGER.info("Required FreshAirIQ source %s is available again", entity_id)
        self._unavailable_required_sources = unavailable

    @property
    def options(self) -> dict[str, Any]:
        options, repaired = safe_options(DEFAULT_OPTIONS, dict(self.entry.options))
        self.robustness.repaired_option_keys = repaired
        return options

    async def async_start_listeners(self) -> None:
        await self.telemetry.async_start()
        entities: set[str] = set()
        for entity_id in (self.entry.data.get(CONF_OUTDOOR_WEATHER), self.entry.data.get(CONF_OUTDOOR_TEMPERATURE), self.entry.data.get(CONF_OUTDOOR_HUMIDITY), self.entry.data.get(CONF_POLLEN_ENTITY)):
            if entity_id: entities.add(entity_id)
        self._contact_entities = set()
        options = self.options
        optional_sensor_keys = [
            (CONF_ROOM_VOC, bool(options.get("voc_sensor_enabled", True))),
            (CONF_ROOM_PM25, bool(options.get("pm25_sensor_enabled", True))),
            (CONF_ROOM_ILLUMINANCE, bool(options.get("illuminance_sensor_enabled", True))),
        ]
        for room in self.entry.data.get(CONF_ROOMS, []):
            for key in (CONF_ROOM_TEMPERATURE, CONF_ROOM_HUMIDITY, CONF_ROOM_REFERENCE_TEMPERATURE, CONF_ROOM_REFERENCE_HUMIDITY, CONF_ROOM_CO2):
                if room.get(key): entities.add(room[key])
            for key, enabled in optional_sensor_keys:
                if enabled and room.get(key):
                    entities.add(room[key])
            # Opening-specific climate references are first-class data sources.
            # They already exist in the room configuration, so no extra user
            # setup is required; listening to them also makes a requested refresh
            # immediately visible to the coordinator.
            for mapping_key in (CONF_CONTACT_REFERENCE_TEMPERATURES, CONF_CONTACT_REFERENCE_HUMIDITIES):
                mapping = room.get(mapping_key) or {}
                if isinstance(mapping, dict):
                    entities.update(str(entity_id) for entity_id in mapping.values() if entity_id)
            room_contacts = set(_contact_ids(room))
            self._contact_entities.update(room_contacts)
            entities.update(room_contacts)
        # Presence changes should recalculate live and night forecasts immediately.
        for entity_id in (*options.get("adult_presence_entities", []), *options.get("child_presence_entities", []), *options.get("presence_sensor_entities", []), *options.get("pet_safe_presence_entities", [])):
            if entity_id: entities.add(str(entity_id))
        self.robustness.listener_sources = len(entities)
        self._unsub_state = (
            async_track_state_change_event(self.hass, list(entities), self._async_source_changed)
            if entities else None
        )

    def _clear_runtime_listeners(self) -> None:
        """Remove state/contact listeners without touching persisted learning data."""
        if self._unsub_state:
            self._unsub_state()
            self._unsub_state = None
        for unsub in list(self._contact_confirm_unsubs.values()):
            unsub()
        self._contact_confirm_unsubs.clear()
        for unsub in list(self._final_measurement_unsubs.values()):
            unsub()
        self._final_measurement_unsubs.clear()
        if self._refresh_coalesce_unsub:
            self._refresh_coalesce_unsub()
            self._refresh_coalesce_unsub = None

    async def async_rebuild_listeners(self, *, invalidate_weather_cache: bool = False) -> None:
        """Rebuild source listeners after a live configuration change.

        This is intentionally lighter than unloading/reloading the complete config
        entry. Existing entities, learning state and platform registrations remain
        untouched; only the set of source entities that can trigger an immediate
        coordinator refresh is rebuilt from the updated ConfigEntry.

        When the configured weather entity changes, its hourly forecast cache must
        be cleared as well; otherwise a live source switch could temporarily keep
        using forecast rows fetched from the previous provider.
        """
        self._clear_runtime_listeners()
        if invalidate_weather_cache:
            self._hourly_forecast_cache = []
            self._hourly_forecast_fetched_at = None
        await self.async_start_listeners()

    async def async_stop_listeners(self) -> None:
        self._clear_runtime_listeners()
        await self.telemetry.async_stop()
        # Flush the latest live balance before reload/shutdown.
        await self.store.async_save()

    def _room_climate_refresh_entities(
        self, cfg: dict[str, Any], *,
        active_reference_temperature: str | None = None,
        active_reference_humidity: str | None = None,
    ) -> list[str]:
        """Return already-configured climate entities for a best-effort refresh.

        No integration- or vendor-specific entity is invented here. The helper
        only reuses entities the user already assigned to FreshAirIQ.
        """
        candidates: set[str] = set()
        for entity_id in (
            cfg.get(CONF_ROOM_TEMPERATURE), cfg.get(CONF_ROOM_HUMIDITY),
            cfg.get(CONF_ROOM_REFERENCE_TEMPERATURE), cfg.get(CONF_ROOM_REFERENCE_HUMIDITY),
            active_reference_temperature, active_reference_humidity,
            self.entry.data.get(CONF_OUTDOOR_TEMPERATURE),
            self.entry.data.get(CONF_OUTDOOR_HUMIDITY),
            self.entry.data.get(CONF_OUTDOOR_WEATHER),
        ):
            if entity_id:
                candidates.add(str(entity_id))
        for mapping_key in (CONF_CONTACT_REFERENCE_TEMPERATURES, CONF_CONTACT_REFERENCE_HUMIDITIES):
            mapping = cfg.get(mapping_key) or {}
            if isinstance(mapping, dict):
                candidates.update(str(entity_id) for entity_id in mapping.values() if entity_id)
        # Avoid calling update_entity for IDs that are not currently known to HA.
        return sorted(entity_id for entity_id in candidates if self.hass.states.get(entity_id) is not None)

    async def _async_request_room_sensor_refresh(
        self, cfg: dict[str, Any], *,
        active_reference_temperature: str | None = None,
        active_reference_humidity: str | None = None,
    ) -> None:
        """Ask Home Assistant to update known room/reference climate entities.

        This is deliberately best-effort. Polling integrations may update at
        once; sleeping/push battery devices may ignore the request. Either way,
        FreshAirIQ continues safely and evaluates the reports it actually sees.
        """
        entities = self._room_climate_refresh_entities(
            cfg,
            active_reference_temperature=active_reference_temperature,
            active_reference_humidity=active_reference_humidity,
        )
        if not entities:
            return
        try:
            await self.hass.services.async_call(
                "homeassistant", "update_entity", {"entity_id": entities}, blocking=False
            )
        except Exception:  # noqa: BLE001 - refresh support differs by integration/device
            _LOGGER.debug("Best-effort climate refresh failed for room %s", cfg.get("key"), exc_info=True)

    def _cancel_final_measurement_timer(self, room_key: str) -> None:
        unsub = self._final_measurement_unsubs.pop(str(room_key), None)
        if unsub:
            unsub()

    def _schedule_final_measurement_timeout(self, room_key: str, delay_s: float) -> None:
        room_key = str(room_key)
        if room_key in self._final_measurement_unsubs:
            return

        @callback
        def _timeout(_now: Any, *, _room_key: str = room_key) -> None:
            self._final_measurement_unsubs.pop(_room_key, None)
            self.hass.async_create_task(self.async_request_refresh())

        self._final_measurement_unsubs[room_key] = async_call_later(
            self.hass, max(float(delay_s), 0.05), _timeout
        )

    def _clear_final_measurement_wait(self, mem: dict[str, Any], room_key: str) -> None:
        self._cancel_final_measurement_timer(room_key)
        mem["session_close_pending"] = False
        mem["session_close_detected_at"] = None
        mem["session_close_wait_started_at"] = None
        mem["session_close_deadline_at"] = None
        mem["session_close_temperature_baseline"] = None
        mem["session_close_humidity_baseline"] = None
        mem["session_close_temperature_feedback"] = False
        mem["session_close_humidity_feedback"] = False
        mem["session_close_refresh_requested_at"] = None

    def _begin_final_measurement_wait(
        self, mem: dict[str, Any], cfg: dict[str, Any], *,
        now: datetime, physical_closed_at: datetime,
        temperature_state: Any, humidity_state: Any,
        active_reference_temperature: str | None,
        active_reference_humidity: str | None,
    ) -> None:
        if mem.get("session_close_pending"):
            return
        mem["session_close_pending"] = True
        mem["session_close_detected_at"] = mem.get("session_close_detected_at") or physical_closed_at.isoformat()
        mem["session_close_wait_started_at"] = now.isoformat()
        deadline = now + timedelta(seconds=SESSION_END_MEASUREMENT_WAIT_SECONDS)
        mem["session_close_deadline_at"] = deadline.isoformat()
        mem["session_close_temperature_baseline"] = _state_report_timestamp(temperature_state)
        mem["session_close_humidity_baseline"] = _state_report_timestamp(humidity_state)
        mem["session_close_temperature_feedback"] = False
        mem["session_close_humidity_feedback"] = False
        mem["session_close_refresh_requested_at"] = now.isoformat()
        self._schedule_final_measurement_timeout(cfg["key"], SESSION_END_MEASUREMENT_WAIT_SECONDS)
        self.hass.async_create_task(self._async_request_room_sensor_refresh(
            cfg,
            active_reference_temperature=active_reference_temperature,
            active_reference_humidity=active_reference_humidity,
        ))

    @staticmethod
    def _update_final_measurement_feedback(
        mem: dict[str, Any], temperature_state: Any, humidity_state: Any,
    ) -> int:
        current_temp = _state_report_timestamp(temperature_state)
        current_humidity = _state_report_timestamp(humidity_state)
        close_boundary = mem.get("session_close_detected_at")
        # A report that arrived during the 3 s close-confirmation window is still
        # a valid *post-close* response. Compare against the physical contact-close
        # boundary as well as the later refresh baseline so it cannot be lost.
        if current_temp and (
            report_timestamp_after_boundary(current_temp, close_boundary)
            if close_boundary else current_temp != mem.get("session_close_temperature_baseline")
        ):
            mem["session_close_temperature_feedback"] = True
        if current_humidity and (
            report_timestamp_after_boundary(current_humidity, close_boundary)
            if close_boundary else current_humidity != mem.get("session_close_humidity_baseline")
        ):
            mem["session_close_humidity_feedback"] = True
        return int(bool(mem.get("session_close_temperature_feedback"))) + int(bool(mem.get("session_close_humidity_feedback")))

    @callback
    def _async_source_changed(self, event: Any) -> None:
        self.robustness.source_event()
        # Sensor/contact changes trigger an immediate refresh; the 30 s timer is only fallback.
        # A contact that reports closed gets one additional refresh after the
        # fixed 3 s confirmation window. If that same contact reopens first, its
        # pending callback is cancelled. This prevents a brief accidental close
        # from ending/overwriting a still-running ventilation session.
        entity_id = str((event.data or {}).get("entity_id") or "")
        if entity_id in self._contact_entities:
            previous = self._contact_confirm_unsubs.pop(entity_id, None)
            if previous:
                previous()
            new_state = (event.data or {}).get("new_state")
            if (
                new_state is not None
                and new_state.state not in {"on", "open", "opening", "unknown", "unavailable", "none", ""}
            ):
                @callback
                def _confirm_close(_now: Any, *, _entity_id: str = entity_id) -> None:
                    self._contact_confirm_unsubs.pop(_entity_id, None)
                    self.hass.async_create_task(self.async_request_refresh())

                self._contact_confirm_unsubs[entity_id] = async_call_later(
                    self.hass, SESSION_CLOSE_CONFIRM_SECONDS, _confirm_close
                )
        # Coalesce bursts where a device reports temperature/humidity/contact
        # states a few milliseconds apart. The coordinator always reads the newest
        # HA state, so this reduces duplicate work without changing calculations.
        if self._refresh_coalesce_unsub is None:
            @callback
            def _coalesced_refresh(_now: Any) -> None:
                self._refresh_coalesce_unsub = None
                self.robustness.coalesced_refresh()
                self.hass.async_create_task(self.async_request_refresh())

            # Leading-edge debounce: one refresh is guaranteed after 120 ms even
            # when a chatty sensor keeps emitting state changes continuously.
            self._refresh_coalesce_unsub = async_call_later(self.hass, 0.12, _coalesced_refresh)

    async def _async_update_data(self) -> dict[str, Any]:
        """Run one update transaction and degrade cleanly on unexpected failures."""
        started = dt_util.now()
        try:
            data = await self._async_update_data_impl()
        except UpdateFailed as exc:
            self.robustness.failure(started, exc)
            raise
        except Exception as exc:  # noqa: BLE001 - coordinator must fail closed, not crash HA
            self.robustness.failure(started, exc)
            raise UpdateFailed(
                f"FreshAirIQ update failed safely ({type(exc).__name__}); previous coordinator data is retained"
            ) from exc
        self.robustness.success(started)
        # Repair issues represent configuration that requires user action, not
        # transient sensor unavailability. The helper checks both HA state and
        # entity registry before creating an issue.
        try:
            async_sync_missing_entity_issue(self.hass, self.entry)
        except Exception:  # noqa: BLE001 - Repairs must never break the control loop
            _LOGGER.debug("Could not synchronize FreshAirIQ repair issues", exc_info=True)
        data["runtime_robustness"] = self.robustness.snapshot()
        return data

    async def _async_update_data_impl(self) -> dict[str, Any]:
        self._log_required_source_availability()
        options = self.options
        occupancy = resolve_occupancy(options, self.hass.states.get)
        effective_adults = float(occupancy["expected_adults"])
        effective_children = float(occupancy["expected_children"])
        outdoor_weather_entity = self.entry.data.get(CONF_OUTDOOR_WEATHER)
        outdoor_weather_state = self.hass.states.get(outdoor_weather_entity) if outdoor_weather_entity else None
        outdoor_t, outdoor_rh = _weather_values(self.hass, outdoor_weather_entity)
        outdoor_temp_entity = self.entry.data.get(CONF_OUTDOOR_TEMPERATURE)
        outdoor_humidity_entity = self.entry.data.get(CONF_OUTDOOR_HUMIDITY)
        outdoor_temp_state = self.hass.states.get(outdoor_temp_entity) if outdoor_temp_entity else outdoor_weather_state
        outdoor_humidity_state = self.hass.states.get(outdoor_humidity_entity) if outdoor_humidity_entity else outdoor_weather_state
        sensor_t = _float_state(self.hass, outdoor_temp_entity); sensor_rh = _float_state(self.hass, outdoor_humidity_entity)
        if sensor_t is not None: outdoor_t = sensor_t
        if sensor_rh is not None: outdoor_rh = sensor_rh
        wind_bearing, wind_speed = _weather_wind(self.hass, self.entry.data.get(CONF_OUTDOOR_WEATHER))
        pollen = _float_state(self.hass, self.entry.data.get(CONF_POLLEN_ENTITY)) or 0.0
        now = dt_util.now(); results: dict[str, Any] = {}; changed = False; completed_sessions = []
        completed_house_sessions: list[dict[str, Any]] = []
        weather_entity = self.entry.data.get(CONF_OUTDOOR_WEATHER)
        if weather_entity and (
            self._hourly_forecast_fetched_at is None
            or (now - self._hourly_forecast_fetched_at).total_seconds() >= 600
        ):
            fetched_forecast = await async_hourly_forecast(self.hass, weather_entity)
            if fetched_forecast:
                # Replace only with a valid provider response. A transient weather
                # integration failure must not discard the last useful forecast.
                self._hourly_forecast_cache = fetched_forecast
                self._hourly_forecast_fetched_at = now
            elif self._hourly_forecast_cache:
                self.robustness.weather_failure()
                # Keep the previous forecast but retry soon instead of treating an
                # empty response like a successful ten-minute cache fill.
                self._hourly_forecast_fetched_at = now - timedelta(seconds=540)
            else:
                self.robustness.weather_failure()
                # No usable cache exists yet: retry after roughly one minute.
                self._hourly_forecast_fetched_at = now - timedelta(seconds=540)
        future_outdoor = future_boundaries(
            self._hourly_forecast_cache, now, outdoor_t, outdoor_rh
        ) if weather_entity else {}
        # Hotfix 0.20.2.1: the user-facing 15–120 minute forecast advances
        # through real 5-minute future weather boundaries. Keep this separate
        # from the compact public/diagnostic boundary set above.
        forecast_outdoor_steps = future_boundaries(
            self._hourly_forecast_cache, now, outdoor_t, outdoor_rh,
            delays=tuple(range(5, 121, 5)),
        ) if weather_entity else {}
        planning_delays = (60, 120, 180, 240, 360, 480)
        planning_outdoor = future_boundaries(
            self._hourly_forecast_cache, now, outdoor_t, outdoor_rh, delays=planning_delays
        ) if weather_entity else {}
        cross = self._cross_ventilation_active()

        rooms_cfg, runtime_room_issues = prepare_runtime_rooms(self.entry.data.get(CONF_ROOMS, []))
        self.robustness.runtime_config_issues = runtime_room_issues
        rooms_cfg = sorted(rooms_cfg, key=lambda r: (int(r.get(CONF_ROOM_SORT_ORDER, 9999)), r.get("name", "")))
        ventilation_group = self.store.data.get("ventilation_group")
        if not isinstance(ventilation_group, dict) or not ventilation_group.get("active"):
            persisted_starts = []
            for _cfg in rooms_cfg:
                _mem = self.store.room(_cfg["key"])
                if _mem.get("session_active") and _mem.get("session_started"):
                    physical_start = _room_physical_opened_at(self.hass, _cfg)
                    if physical_start is not None:
                        persisted_starts.append(physical_start)
                    try:
                        persisted_starts.append(datetime.fromisoformat(str(_mem["session_started"])))
                    except (TypeError, ValueError):
                        pass
            if persisted_starts:
                ventilation_group = new_ventilation_group(min(persisted_starts))
                self.store.data["ventilation_group"] = ventilation_group
                changed = True
            else:
                ventilation_group = None
        calc_volume_total = sum(
            max(float(r.get(CONF_ROOM_VOLUME, 0.0) or 0.0), 0.0)
            for r in rooms_cfg if r.get(CONF_ROOM_INCLUDE_CALCULATIONS, True)
        )
        daily_generation_prior = float(estimated_daily_moisture_ml(options, effective_adults, effective_children))
        forecast_horizon = int(round(min(max(float(options.get("forecast_horizon_min", 5)), 1.0), 120.0)))
        voc_sensor_enabled = bool(options.get("voc_sensor_enabled", True))
        pm25_sensor_enabled = bool(options.get("pm25_sensor_enabled", True))
        illuminance_sensor_enabled = bool(options.get("illuminance_sensor_enabled", True))
        for idx, cfg in enumerate(rooms_cfg):
            key = cfg["key"]; mem = self.store.room(key); ensure_behaviour_defaults(mem); include = bool(cfg.get(CONF_ROOM_INCLUDE_CALCULATIONS, True))
            # v0.21.0.2: structure-only rooms are valid building metadata and may
            # intentionally have no climate/contact entities. Never dereference
            # mandatory climate keys before the calculation flag has been checked.
            if not include:
                # v0.21.0.2: A monitor-only/structure room may still have real
                # climate sensors (for example a winter garden used as an outside
                # reference).  Keep those readings visible without allowing the
                # room to influence recommendations, learning, statistics or the
                # house balance.  This is intentionally display-only: no values
                # are estimated when a configured sensor is missing.
                temperature_entity = cfg.get(CONF_ROOM_TEMPERATURE)
                humidity_entity = cfg.get(CONF_ROOM_HUMIDITY)
                temperature_state = self.hass.states.get(temperature_entity) if temperature_entity else None
                humidity_state = self.hass.states.get(humidity_entity) if humidity_entity else None
                monitor_t = _float_state(self.hass, temperature_entity) if temperature_entity else None
                monitor_rh = _float_state(self.hass, humidity_entity) if humidity_entity else None
                monitor_valid = bool(
                    monitor_t is not None and monitor_rh is not None
                    and -10 < monitor_t < 50 and 5 <= monitor_rh <= 100
                )
                monitor_ah = absolute_humidity(monitor_t, monitor_rh) if monitor_valid else None
                monitor_voc = _float_state(self.hass, cfg.get(CONF_ROOM_VOC)) if voc_sensor_enabled and cfg.get(CONF_ROOM_VOC) else None
                monitor_pm25 = _float_state(self.hass, cfg.get(CONF_ROOM_PM25)) if pm25_sensor_enabled and cfg.get(CONF_ROOM_PM25) else None
                monitor_illuminance = _float_state(self.hass, cfg.get(CONF_ROOM_ILLUMINANCE)) if illuminance_sensor_enabled and cfg.get(CONF_ROOM_ILLUMINANCE) else None
                monitor_volume = max(float(cfg.get(CONF_ROOM_VOLUME, 0.0) or 0.0), 0.0)
                monitor_last = None
                for monitor_state in (temperature_state, humidity_state):
                    changed_at = getattr(monitor_state, "last_updated", None) if monitor_state is not None else None
                    if changed_at is not None and (monitor_last is None or changed_at > monitor_last):
                        monitor_last = changed_at
                sensor_configured = bool(temperature_entity and humidity_entity)
                results[key] = {
                    "key": key,
                    "name": cfg.get(CONF_ROOM_NAME, key),
                    "floor": cfg.get(CONF_ROOM_FLOOR, "Unzugeordnet"),
                    "volume_m3": round(monitor_volume, 1),
                    "calculation_enabled": False,
                    "monitor_only": True,
                    "sensor_data_configured": sensor_configured,
                    "sensor_data_available": monitor_valid,
                    "data_quality": "monitor_only" if monitor_valid else ("missing" if sensor_configured else "not_configured"),
                    "action": "Monitor only",
                    "reason": (
                        "Live sensor values are shown; climate calculations are disabled"
                        if monitor_valid else
                        "Configured climate sensors are currently unavailable"
                        if sensor_configured else
                        "Room is stored as building structure without climate calculations"
                    ),
                    "temperature": round(float(monitor_t), 2) if monitor_valid else None,
                    "humidity": round(float(monitor_rh), 2) if monitor_valid else None,
                    "absolute_humidity": round(float(monitor_ah), 2) if monitor_ah is not None else None,
                    "water_in_air_ml": int(round(float(monitor_ah) * monitor_volume)) if monitor_ah is not None else None,
                    "voc": monitor_voc, "voc_available": monitor_voc is not None, "voc_enabled": voc_sensor_enabled, "voc_configured": bool(cfg.get(CONF_ROOM_VOC)),
                    "pm25": monitor_pm25, "pm25_available": monitor_pm25 is not None, "pm25_enabled": pm25_sensor_enabled, "pm25_configured": bool(cfg.get(CONF_ROOM_PM25)),
                    "illuminance": monitor_illuminance, "illuminance_available": monitor_illuminance is not None, "illuminance_enabled": illuminance_sensor_enabled, "illuminance_configured": bool(cfg.get(CONF_ROOM_ILLUMINANCE)),
                    "last_measurement_at": monitor_last.isoformat() if monitor_last is not None else None,
                    "last_measurement_valid": monitor_valid if sensor_configured else None,
                    "active": False,
                    "open": False,
                    "close_recommended": False,
                    "contact_mode": cfg.get(CONF_CONTACT_MODE, CONTACT_MODE_ANY),
                    "contact_count": len(_contact_ids(cfg)),
                    "contact_entities": _contact_ids(cfg),
                    "contact_delays": dict(cfg.get(CONF_CONTACT_DELAYS, {})),
                    "contact_orientations": dict(cfg.get(CONF_CONTACT_ORIENTATIONS, {})),
                    "contact_reference_temperatures": dict(cfg.get(CONF_CONTACT_REFERENCE_TEMPERATURES, {})),
                    "contact_reference_humidities": dict(cfg.get(CONF_CONTACT_REFERENCE_HUMIDITIES, {})),
                    "moisture_sources": list(cfg.get(CONF_ROOM_MOISTURE_SOURCES, [])),
                    "window_orientation": cfg.get(CONF_ROOM_WINDOW_ORIENTATION, ORIENTATION_UNKNOWN),
                }
                continue
            temperature_entity = cfg.get(CONF_ROOM_TEMPERATURE)
            humidity_entity = cfg.get(CONF_ROOM_HUMIDITY)
            temperature_state = self.hass.states.get(temperature_entity) if temperature_entity else None
            humidity_state = self.hass.states.get(humidity_entity) if humidity_entity else None
            room_reference_temperature_entity = cfg.get(CONF_ROOM_REFERENCE_TEMPERATURE)
            room_reference_humidity_entity = cfg.get(CONF_ROOM_REFERENCE_HUMIDITY)
            default_reference_temperature_entity = room_reference_temperature_entity or outdoor_temp_entity
            default_reference_humidity_entity = room_reference_humidity_entity or outdoor_humidity_entity
            default_ref_t = _float_state(self.hass, room_reference_temperature_entity) if room_reference_temperature_entity else outdoor_t
            default_ref_rh = _float_state(self.hass, room_reference_humidity_entity) if room_reference_humidity_entity else outdoor_rh
            reference_temperature_entity, reference_humidity_entity, ref_t, ref_rh = _contact_specific_reference(
                self.hass, cfg,
                default_temp_entity=default_reference_temperature_entity,
                default_humidity_entity=default_reference_humidity_entity,
                default_temp=default_ref_t, default_humidity=default_ref_rh,
            )
            reference_temperature_state = self.hass.states.get(reference_temperature_entity) if reference_temperature_entity else outdoor_temp_state
            reference_humidity_state = self.hass.states.get(reference_humidity_entity) if reference_humidity_entity else outdoor_humidity_state
            t = _float_state(self.hass, temperature_entity) if temperature_entity else None; rh = _float_state(self.hass, humidity_entity) if humidity_entity else None
            measurement_frame = build_measurement_frame(
                now,
                temperature_state=temperature_state,
                humidity_state=humidity_state,
                reference_temperature_state=reference_temperature_state,
                reference_humidity_state=reference_humidity_state,
            )
            co2_entity = cfg.get(CONF_ROOM_CO2)
            co2 = _float_state(self.hass, co2_entity) if co2_entity else None
            co2_available = co2 is not None
            voc_configured_entity = cfg.get(CONF_ROOM_VOC)
            voc_entity = voc_configured_entity if voc_sensor_enabled else None
            voc = _float_state(self.hass, voc_entity) if voc_entity else None
            pm25_configured_entity = cfg.get(CONF_ROOM_PM25)
            pm25_entity = pm25_configured_entity if pm25_sensor_enabled else None
            pm25 = _float_state(self.hass, pm25_entity) if pm25_entity else None
            illuminance_configured_entity = cfg.get(CONF_ROOM_ILLUMINANCE)
            illuminance_entity = illuminance_configured_entity if illuminance_sensor_enabled else None
            illuminance = _float_state(self.hass, illuminance_entity) if illuminance_entity else None
            contacts_known = _room_contacts_known(self.hass, cfg)
            confirmed_close_seconds: float | None = None
            is_open, raw_open_seconds = _room_ventilation_state(self.hass, cfg, now, honour_delays=False)
            raw_contact_open = bool(is_open)
            session_should, _ = _room_ventilation_state(self.hass, cfg, now, honour_delays=True)
            # During HA startup a contact can temporarily be unavailable. Never
            # interpret that transient restore state as a real window-close event;
            # otherwise a persisted session is destroyed and restarts at 0 ml.
            if mem.get("session_active") and not contacts_known:
                is_open = True
                session_should = True
            elif mem.get("session_active"):
                # Contact delays are a *start* gate only. Once a ventilation
                # session exists, reopening a contact must continue that same
                # session immediately instead of reapplying its opening delay.
                if is_open:
                    session_should = True
                else:
                    closed_for = _room_closed_for_seconds(self.hass, cfg, now)
                    confirmed_close_seconds = closed_for
                    if closed_for is not None:
                        physical_close_candidate = now - timedelta(seconds=max(closed_for, 0.0))
                        # Freeze the physical close boundary immediately, before the
                        # 3 s debounce expires. Sensor reports after this instant are
                        # finalisation feedback and must never satisfy the in-session
                        # timestamp learning gate. A reopen clears this tentative close.
                        if not mem.get("session_close_detected_at"):
                            mem["session_close_detected_at"] = physical_close_candidate.isoformat()
                            changed = True
                    if closed_for is not None and closed_for < SESSION_CLOSE_CONFIRM_SECONDS:
                        # Keep the room logically open for exactly three seconds.
                        # A reopen inside this window therefore never finishes the
                        # session and can never create a spurious "last ventilation".
                        is_open = True
                        session_should = True
            if None in (t, rh, ref_t, ref_rh):
                t = t if t is not None else 999.0; rh = rh if rh is not None else -1.0
                ref_t = ref_t if ref_t is not None else 999.0; ref_rh = ref_rh if ref_rh is not None else -1.0

            # Monitor-only rooms never start sessions and never alter the IQ model/statistics.
            measurements_valid = (-10 < t < 50 and 5 <= rh <= 100 and -30 < ref_t < 60 and 0 <= ref_rh <= 100)
            session_should = session_should and include
            # Never create a session from startup placeholders (999/-1). Each
            # ventilation session starts with a fresh zero baseline; completed
            # session values are never carried into the next live balance.
            if session_should and not mem["session_active"] and measurements_valid:
                physical_started = _room_physical_opened_at(self.hass, cfg) or now
                if not isinstance(ventilation_group, dict) or not ventilation_group.get("active"):
                    ventilation_group = new_ventilation_group(physical_started)
                    self.store.data["ventilation_group"] = ventilation_group
                elif include_ventilation_group_start(ventilation_group, physical_started):
                    changed = True
                mem["session_active"] = True
                # Keep both clocks deliberately: session_started marks the first
                # trustworthy climate baseline used for moisture/temperature
                # forecast comparison and learning, while session_physical_started
                # marks the real contact opening used for physical runtime and
                # recommendation timing.
                mem["session_started"] = now.isoformat()
                mem["session_physical_started"] = physical_started.isoformat()
                mem["session_start_ah"] = absolute_humidity(t, rh)
                mem["session_start_source_ah"] = absolute_humidity(ref_t, ref_rh)
                mem["session_start_source_temp"] = ref_t
                mem["session_learning_start_ah"] = mem["session_start_ah"]
                mem["session_learning_source_ah"] = mem["session_start_source_ah"]
                mem["session_start_temp"] = t
                mem["session_result_base_ml"] = 0.0
                mem["session_result_ml"] = 0.0
                mem["close_notified"] = False
                temperature_state = self.hass.states.get(temperature_entity) if temperature_entity else None
                humidity_state = self.hass.states.get(humidity_entity) if humidity_entity else None
                temp_reported = _state_report_timestamp(temperature_state)
                humidity_reported = _state_report_timestamp(humidity_state)
                mem["session_last_temperature_update"] = temp_reported
                mem["session_last_humidity_update"] = humidity_reported
                # Persist the exact report clocks seen at physical/session start.
                # They are diagnostic evidence for the strict learning gate: a
                # value whose report timestamp never advances after opening must
                # never be treated as a fresh learning observation.
                mem["session_open_temperature_reported_at"] = temp_reported
                mem["session_open_humidity_reported_at"] = humidity_reported
                mem["session_last_valid_temperature"] = t
                mem["session_last_valid_humidity"] = rh
                mem["session_last_valid_reference_temperature"] = ref_t
                mem["session_last_valid_reference_humidity"] = ref_rh
                mem["session_last_valid_at"] = now.isoformat()
                # Reports that arrived after the physical opening but before a
                # configured contact-delay gate already belong to this airing.
                def _after_physical_open(stamp: str | None) -> bool:
                    if not stamp:
                        return False
                    try:
                        return datetime.fromisoformat(stamp) > physical_started
                    except (TypeError, ValueError):
                        return False
                mem["session_temperature_reports"] = int(_after_physical_open(temp_reported))
                mem["session_humidity_reports"] = int(_after_physical_open(humidity_reported))
                mem["session_fresh_measurements"] = min(
                    int(mem["session_temperature_reports"]) + int(mem["session_humidity_reports"]), 2
                )
                self._clear_final_measurement_wait(mem, key)
                mem["session_start_frame_quality"] = measurement_frame.get("quality")
                mem["session_start_frame_skew_s"] = measurement_frame.get("skew_s")
                mem["session_start_frame_max_age_s"] = measurement_frame.get("max_age_s")
                mem["session_start_frame_learning_eligible"] = bool(measurement_frame.get("learning_eligible"))
                # Explain start evidence separately from the strict in-session gate.
                # A held battery-sensor value can be plausible without being fresh;
                # it never bypasses the later timestamp activity requirement.
                try:
                    _start_age = float(measurement_frame.get("max_age_s") or 0.0)
                except (TypeError, ValueError, OverflowError):
                    _start_age = 999999.0
                if _start_age <= 300.0:
                    mem["start_measurement_state"] = "fresh"
                elif _start_age <= 1200.0 and measurement_frame.get("quality") not in {"invalid", "missing"}:
                    mem["start_measurement_state"] = "held_plausible"
                else:
                    mem["start_measurement_state"] = "uncertain"
                mem["start_measurement_in_session_gate_passed"] = False
                mem["session_learning_started"] = now.isoformat() if measurement_frame.get("learning_eligible") else None
                mem["session_last_eligible_ah"] = mem["session_start_ah"] if measurement_frame.get("learning_eligible") else None
                mem["session_last_eligible_at"] = now.isoformat() if measurement_frame.get("learning_eligible") else None
                mem["forecast_recent_removed_ml_min"] = None
                mem["forecast_recent_observed_at"] = None
                mem["session_moisture_source_detected"] = False
                mem["session_cross_active"] = bool(cross)
                mem["session_cross_seconds"] = 0.0
                mem["session_cross_last_update"] = now.isoformat()
                # Hotfix 0.20.2.6: a session prediction is frozen from the first
                # forecast calculated after the physical opening. Never carry a
                # previous recommendation/live forecast into a new session.
                mem["session_predicted_removed_ml"] = None
                mem["session_predicted_temperature_change_c"] = None
                mem["session_predicted_cost"] = None
                mem["session_prediction_confidence"] = None
                mem["session_prediction_snapshot_at"] = None
                mem["session_prediction_horizon_min"] = None
                mem["session_prediction_snapshot_elapsed_min"] = None
                mem["session_prediction_snapshot_valid"] = False
                mem["session_prediction_snapshot_pending"] = True
                mem["session_prediction_reference"] = None
                mem["session_prediction_start_context"] = None
                mem["session_validation_id"] = f"{key}:{now.isoformat()}"
                mem["session_prediction_time_aligned"] = False
                mem["session_prediction_snapshot_frame_quality"] = None
                mem["session_prediction_snapshot_frame_skew_s"] = None
                mem["session_prediction_snapshot_frame_max_age_s"] = None
                # Freeze the physical/logical start values immediately. Their
                # trustworthiness is decided later from actual sensor activity
                # during this session, not from an arbitrary age threshold alone.
                mem["session_validation_started"] = now.isoformat()
                mem["session_validation_start_ah"] = mem["session_start_ah"]
                mem["session_validation_start_source_ah"] = mem["session_start_source_ah"]
                mem["session_validation_start_temp"] = t
                mem["session_validation_start_source_temp"] = ref_t
                mem["session_last_validation_ah"] = mem["session_start_ah"]
                mem["session_last_validation_temp"] = t
                mem["session_last_validation_at"] = now.isoformat()
                mem["session_forecast_timeline"] = []
                mem["session_timeline_last_checkpoint_min"] = None
                if mark_recommendation_followed(self.store.data, mem, key, now):
                    changed = True
                # Baseline is captured first; only then ask HA/integration for a
                # fresh report. No extra entity configuration is required.
                self.hass.async_create_task(self._async_request_room_sensor_refresh(
                    cfg,
                    active_reference_temperature=reference_temperature_entity,
                    active_reference_humidity=reference_humidity_entity,
                ))
                changed = True

            # Restart continuity: keep the ORIGINAL session baseline across a
            # Home Assistant restart. This is the only way to continue the live
            # moisture balance physically from the moment the window was opened.
            # The separately persisted session_result_ml is only a display/fallback
            # value while climate sensors are temporarily unavailable during startup.
            # Once valid measurements return, evaluate_room() again compares the
            # current absolute humidity with the original session_start_ah and the
            # displayed balance therefore continues without a visible reset to 0 ml.
            if self._first_update and mem["session_active"]:
                mem.setdefault("session_learning_start_ah", mem.get("session_start_ah"))
                mem.setdefault("session_learning_source_ah", mem.get("session_start_source_ah"))

            # Repair persisted sessions from older versions. Never reset a valid
            # active session merely because it is old: a window may legitimately
            # remain open for hours. Only malformed/future timestamps or invalid
            # physical baselines are repaired.
            if mem["session_active"] and measurements_valid:
                persisted_start_temp = finite_float(mem.get("session_start_temp"))
                persisted_start_ah = finite_float(mem.get("session_start_ah"))
                bad_start_temp = persisted_start_temp is None or not (-10 < persisted_start_temp < 50)
                bad_start_ah = persisted_start_ah is None or not (0 < persisted_start_ah < 40)
                bad_started = False
                try:
                    started = datetime.fromisoformat(mem.get("session_started"))
                    age_min = (now - started).total_seconds() / 60.0
                    bad_started = age_min < -2.0
                except (TypeError, ValueError):
                    bad_started = True
                if bad_start_temp or bad_start_ah or bad_started:
                    mem["session_started"] = now.isoformat()
                    # A repaired legacy/corrupt session has no trustworthy
                    # historical baseline. Preserve a known physical opening
                    # timestamp when available; otherwise use the repair time.
                    physical_started = _room_physical_opened_at(self.hass, cfg) or now
                    mem["session_physical_started"] = physical_started.isoformat()
                    mem["session_start_temp"] = t
                    mem["session_start_ah"] = absolute_humidity(t, rh)
                    mem["session_start_source_ah"] = absolute_humidity(ref_t, ref_rh)
                    mem["session_start_source_temp"] = ref_t
                    mem["session_learning_start_ah"] = mem["session_start_ah"]
                    mem["session_learning_source_ah"] = mem["session_start_source_ah"]
                    mem["session_result_base_ml"] = 0.0
                    mem["session_result_ml"] = 0.0
                    mem["close_notified"] = False
                    temperature_state = self.hass.states.get(temperature_entity) if temperature_entity else None
                    humidity_state = self.hass.states.get(cfg[CONF_ROOM_HUMIDITY])
                    mem["session_last_temperature_update"] = _state_report_timestamp(temperature_state)
                    mem["session_last_humidity_update"] = _state_report_timestamp(humidity_state)
                    mem["session_open_temperature_reported_at"] = mem["session_last_temperature_update"]
                    mem["session_open_humidity_reported_at"] = mem["session_last_humidity_update"]
                    mem["session_last_valid_temperature"] = t
                    mem["session_last_valid_humidity"] = rh
                    mem["session_last_valid_reference_temperature"] = ref_t
                    mem["session_last_valid_reference_humidity"] = ref_rh
                    mem["session_last_valid_at"] = now.isoformat()
                    # A repaired/legacy session has no auditable report history.
                    # Start counting only reports whose timestamp advances after
                    # this repair instead of inferring activity from an old value.
                    mem["session_temperature_reports"] = 0
                    mem["session_humidity_reports"] = 0
                    mem["session_start_frame_quality"] = measurement_frame.get("quality")
                    mem["session_start_frame_skew_s"] = measurement_frame.get("skew_s")
                    mem["session_start_frame_max_age_s"] = measurement_frame.get("max_age_s")
                    mem["session_start_frame_learning_eligible"] = bool(measurement_frame.get("learning_eligible"))
                    mem["session_fresh_measurements"] = 0
                    mem["session_moisture_source_detected"] = False
                    mem["session_cross_active"] = bool(cross)
                    mem["session_cross_seconds"] = 0.0
                    mem["session_cross_last_update"] = now.isoformat()
                    changed = True

            if mem["session_active"] and measurements_valid:
                # Keep the latest numeric climate state seen while this session is
                # active. This is only an end-of-session availability fail-safe: it
                # does not increment report counters and cannot make a session learnable.
                snapshot = (t, rh, ref_t, ref_rh)
                previous_snapshot = (
                    mem.get("session_last_valid_temperature"),
                    mem.get("session_last_valid_humidity"),
                    mem.get("session_last_valid_reference_temperature"),
                    mem.get("session_last_valid_reference_humidity"),
                )
                if snapshot != previous_snapshot or not mem.get("session_last_valid_at"):
                    mem["session_last_valid_temperature"] = t
                    mem["session_last_valid_humidity"] = rh
                    mem["session_last_valid_reference_temperature"] = ref_t
                    mem["session_last_valid_reference_humidity"] = ref_rh
                    mem["session_last_valid_at"] = now.isoformat()
                    changed = True

            if mem["session_active"] and update_session_cross_tracking(mem, now, cross):
                changed = True

            # Count real room-climate reports after the physical opening.
            # Temperature and humidity both contribute; unchanged numeric values
            # still count when Home Assistant advances ``last_reported``. Reports
            # that arrive only after the physical close belong to the final grace
            # phase and do not retroactively prove in-session activity.
            if mem["session_active"]:
                try:
                    report_window_start = datetime.fromisoformat(str(mem.get("session_physical_started") or mem.get("session_started")))
                except (TypeError, ValueError):
                    report_window_start = now
                report_window_end = None
                if mem.get("session_close_detected_at"):
                    try:
                        report_window_end = datetime.fromisoformat(str(mem.get("session_close_detected_at")))
                    except (TypeError, ValueError):
                        report_window_end = None

                report_specs = (
                    (temperature_state, "session_last_temperature_update", "session_temperature_reports"),
                    (humidity_state, "session_last_humidity_update", "session_humidity_reports"),
                )
                for sensor_state, timestamp_key, counter_key in report_specs:
                    current_report = _state_report_timestamp(sensor_state)
                    previous_report = mem.get(timestamp_key)
                    if not current_report:
                        continue
                    if previous_report is None or self._first_update:
                        if previous_report != current_report:
                            mem[timestamp_key] = current_report
                            changed = True
                        continue
                    if current_report == previous_report:
                        continue
                    mem[timestamp_key] = current_report
                    try:
                        report_at = datetime.fromisoformat(current_report)
                        inside_session = report_at > report_window_start and (report_window_end is None or report_at <= report_window_end)
                    except (TypeError, ValueError):
                        inside_session = False
                    if inside_session:
                        mem[counter_key] = min(int(mem.get(counter_key, 0)) + 1, 99)
                    changed = True
                combined_reports = int(mem.get("session_temperature_reports", 0)) + int(mem.get("session_humidity_reports", 0))
                new_fresh = min(max(combined_reports, 0), 2)
                if int(mem.get("session_fresh_measurements", 0)) != new_fresh:
                    mem["session_fresh_measurements"] = new_fresh
                    changed = True

            # Learning retains the existing measurement-frame side channel, but
            # held/stale age alone no longer decides whether the completed session
            # is usable. The final decision is made from actual session activity.
            if mem["session_active"] and measurements_valid and measurement_frame.get("learning_eligible"):
                current_ah = absolute_humidity(t, rh)
                if not mem.get("session_learning_started"):
                    mem["session_learning_started"] = now.isoformat()
                    mem["session_learning_start_ah"] = current_ah
                    mem["session_learning_source_ah"] = absolute_humidity(ref_t, ref_rh)
                    mem["session_start_frame_quality"] = measurement_frame.get("quality")
                    mem["session_start_frame_skew_s"] = measurement_frame.get("skew_s")
                    mem["session_start_frame_max_age_s"] = measurement_frame.get("max_age_s")
                    mem["session_start_frame_learning_eligible"] = True
                    changed = True
                mem["session_last_eligible_ah"] = current_ah
                # Store the sensor report clock, not the coordinator-refresh clock.
                # This prevents repeatedly refreshed held values from looking new.
                report_stamps = [
                    getattr(temperature_state, "last_reported", None) or getattr(temperature_state, "last_updated", None),
                    getattr(humidity_state, "last_reported", None) or getattr(humidity_state, "last_updated", None),
                ]
                valid_stamps = [stamp for stamp in report_stamps if stamp is not None]
                mem["session_last_eligible_at"] = max(valid_stamps).isoformat() if valid_stamps else now.isoformat()

            # A/B frames still update the strict validation observation clock, but
            # the opening baseline itself was already frozen at session start.
            if mem["session_active"] and measurements_valid and measurement_frame.get("validation_eligible"):
                validation_ah = absolute_humidity(t, rh)
                mem["session_last_validation_ah"] = validation_ah
                mem["session_last_validation_temp"] = t
                report_stamps = [
                    getattr(temperature_state, "last_reported", None) or getattr(temperature_state, "last_updated", None),
                    getattr(humidity_state, "last_reported", None) or getattr(humidity_state, "last_updated", None),
                ]
                valid_stamps = [stamp for stamp in report_stamps if stamp is not None]
                mem["session_last_validation_at"] = max(valid_stamps).isoformat() if valid_stamps else now.isoformat()
                changed = True

            if mem["session_active"]:
                if session_should:
                    # A reopen during the 3 s close-confirmation window or the later
                    # end-measurement grace phase resumes the same ventilation. Clear
                    # the tentative physical-close boundary as well as pending timers.
                    if contacts_known and raw_contact_open and (mem.get("session_close_pending") or mem.get("session_close_detected_at")):
                        self._clear_final_measurement_wait(mem, key)
                        changed = True
                else:
                    # Preserve the actual contact-close time; the later sensor wait
                    # must never inflate ventilation duration.
                    physical_closed_at = now
                    if confirmed_close_seconds is not None:
                        physical_closed_at = now - timedelta(seconds=max(confirmed_close_seconds, 0.0))
                    if not mem.get("session_close_pending"):
                        self._begin_final_measurement_wait(
                            mem, cfg, now=now, physical_closed_at=physical_closed_at,
                            temperature_state=temperature_state, humidity_state=humidity_state,
                            active_reference_temperature=reference_temperature_entity,
                            active_reference_humidity=reference_humidity_entity,
                        )
                        changed = True

                    feedback_count = self._update_final_measurement_feedback(mem, temperature_state, humidity_state)
                    try:
                        deadline = datetime.fromisoformat(str(mem.get("session_close_deadline_at")))
                    except (TypeError, ValueError):
                        deadline = now
                    wait_expired = now >= deadline
                    if not wait_expired:
                        self._schedule_final_measurement_timeout(key, max((deadline - now).total_seconds(), 0.05))

                    # Two room-climate responses let us finish immediately. If a
                    # sleeping battery device does not answer, the grace phase is
                    # capped at 10 s and session activity decides measurement trust.
                    ready_to_finish = feedback_count >= 2 or wait_expired
                    if ready_to_finish:
                        try:
                            session_ended_at = datetime.fromisoformat(str(mem.get("session_close_detected_at")))
                        except (TypeError, ValueError):
                            session_ended_at = physical_closed_at

                        event = None
                        if measurements_valid:
                            # Missing post-close refresh feedback is not a rejection.
                            # The last currently held numeric state remains usable; the
                            # session quality stays "good" (0.75) instead of "high".
                            self._cancel_final_measurement_timer(key)
                            event = await self._finish_session(
                                mem, cfg, t, rh, ref_t, ref_rh, session_ended_at, cross, measurement_frame,
                                final_measurement_source="state_at_finalization",
                                final_measurement_timeout=wait_expired,
                            )
                        elif wait_expired:
                            # If HA marks a climate entity unavailable exactly at the
                            # deadline, finish from the most recent numeric climate
                            # snapshot already observed during this same session. This
                            # never creates timestamp evidence and therefore cannot
                            # bypass the strict in-session T+RH learning gate.
                            fallback = last_valid_session_measurement(mem)
                            self._cancel_final_measurement_timer(key)
                            if fallback is not None:
                                event = await self._finish_session(
                                    mem, cfg,
                                    fallback["temperature"], fallback["humidity"],
                                    fallback["reference_temperature"], fallback["reference_humidity"],
                                    session_ended_at, cross, measurement_frame,
                                    final_measurement_source="last_valid_session_state",
                                    final_measurement_timeout=True,
                                )
                            else:
                                # Legacy/corrupt restored sessions may have no stored
                                # numeric snapshot. They still must close deterministically
                                # after the grace window, but no physical outcome is learned.
                                event = self._finish_session_without_measurement(mem, cfg, session_ended_at)

                        if event:
                            completed_sessions.append(event)
                            changed = True

            elapsed = 0.0
            if mem["session_active"] and (mem.get("session_physical_started") or mem.get("session_started")):
                try:
                    elapsed_start = mem.get("session_physical_started") or mem.get("session_started")
                    elapsed_end = now
                    if mem.get("session_close_pending") and mem.get("session_close_detected_at"):
                        try:
                            elapsed_end = min(now, datetime.fromisoformat(str(mem.get("session_close_detected_at"))))
                        except (TypeError, ValueError):
                            elapsed_end = now
                    elapsed = max(0.0, (elapsed_end - datetime.fromisoformat(str(elapsed_start))).total_seconds() / 60.0)
                except (ValueError, TypeError):
                    elapsed = 0.0

            airflow = _room_orientation_factor(self.hass, cfg, now, wind_bearing, wind_speed, bool(options.get("wind_orientation_enabled", True)))
            moisture_source = {"active": False, "recovery": False, "label": "Feuchtequelle", "configured_sources": [], "confidence": 0, "source_rate_ml_min": 0.0, "generated_ml_window": 0.0, "observed_change_ml_window": 0.0, "ventilation_change_ml_window": 0.0, "absolute_humidity_rise_g_m3": 0.0, "temperature_rise_c": 0.0, "window_min": 0.0, "started_at": None, "last_ended_at": None, "changed": False}
            if measurements_valid:
                moisture_source = update_moisture_source(
                    mem, now=now,
                    absolute_humidity_g_m3=absolute_humidity(t, rh),
                    reference_ah_g_m3=absolute_humidity(ref_t, ref_rh),
                    temperature_c=t, volume_m3=float(cfg[CONF_ROOM_VOLUME]),
                    window_open=bool(is_open),
                    learning_rate_per_min=float(mem.get("learning_rate", .03)),
                    airflow_factor=airflow, cross_ventilation=cross,
                    configured_sources=list(cfg.get(CONF_ROOM_MOISTURE_SOURCES, []) or []),
                )
                changed = changed or bool(moisture_source.get("changed"))
                if moisture_source.get("active") and mem.get("session_active"):
                    if not mem.get("session_moisture_source_detected"):
                        mem["session_moisture_source_detected"] = True
                        changed = True

            # v0.20.3.4: observe the first ten minutes after closing to quantify
            # hygroscopic moisture rebound. This remains diagnostic-only: the
            # production forecast and adaptive coefficients are intentionally
            # untouched until enough real observations exist.
            stabilization_outcome, stabilization_changed = update_post_close_observation(
                mem, now=now,
                absolute_humidity_g_m3=(absolute_humidity(t, rh) if measurements_valid else None),
                temperature_c=(t if measurements_valid else None),
                frame_quality=measurement_frame.get("quality"),
                frame_valid=bool(measurement_frame.get("validation_eligible")) and measurements_valid,
                window_open=bool(is_open or mem.get("session_active")),
                moisture_source_active=bool(moisture_source.get("active") or moisture_source.get("recovery")),
            )
            if stabilization_changed:
                changed = True
            if stabilization_outcome is not None:
                history = list(self.store.data.get("post_close_stabilization_history") or [])
                history.append(stabilization_outcome)
                self.store.data["post_close_stabilization_history"] = prune_stabilization_history(history, now, days=30)
                changed = True
            _contact_ref_t = cfg.get(CONF_CONTACT_REFERENCE_TEMPERATURES) or {}
            _contact_ref_h = cfg.get(CONF_CONTACT_REFERENCE_HUMIDITIES) or {}
            active_contact_reference = any(
                _open_seconds(self.hass, _cid, now) is not None
                and str(_contact_ref_t.get(_cid) or "").strip()
                and str(_contact_ref_h.get(_cid) or "").strip()
                and str(_contact_ref_t.get(_cid)) == str(reference_temperature_entity)
                and str(_contact_ref_h.get(_cid)) == str(reference_humidity_entity)
                for _cid in _contact_ids(cfg)
            )
            room_input = RoomInput(
                key=key, name=cfg[CONF_ROOM_NAME], temperature=t, humidity=rh, reference_temperature=ref_t, reference_humidity=ref_rh,
                volume_m3=float(cfg[CONF_ROOM_VOLUME]), contact_open=is_open, contact_open_seconds=raw_open_seconds,
                learning_rate=float(mem["learning_rate"]), learning_samples=int(mem["learning_samples"]), co2=co2,
                session_active=bool(mem["session_active"]), session_elapsed_min=elapsed, session_start_ah=mem.get("session_start_ah"),
                session_start_temp=mem.get("session_start_temp"), session_result_base_ml=float(mem.get("session_result_base_ml", 0.0)),
                session_result_ml=float(mem.get("session_result_ml", 0.0)), close_notified=bool(mem.get("close_notified", False)),
                airflow_factor=airflow, pollen_index=pollen,
                session_fresh_measurements=int(mem.get("session_fresh_measurements", 0)),
                future_reference_temperature_15=(
                    float(future_outdoor[15]["temperature_c"])
                    if 15 in future_outdoor
                    and not cfg.get(CONF_ROOM_REFERENCE_TEMPERATURE)
                    and not cfg.get(CONF_ROOM_REFERENCE_HUMIDITY)
                    and not active_contact_reference
                    else None
                ),
                future_reference_humidity_15=(
                    float(future_outdoor[15]["humidity"])
                    if 15 in future_outdoor
                    and not cfg.get(CONF_ROOM_REFERENCE_TEMPERATURE)
                    and not cfg.get(CONF_ROOM_REFERENCE_HUMIDITY)
                    and not active_contact_reference
                    else None
                ),
                moisture_source_active=bool(moisture_source.get("active")),
                moisture_source_recovery=bool(moisture_source.get("recovery")),
                moisture_source_label=str(moisture_source.get("label") or "Feuchtequelle"),
                moisture_source_confidence=int(moisture_source.get("confidence") or 0),
                moisture_source_rate_ml_min=float(moisture_source.get("source_rate_ml_min") or 0.0),
            )
            result = evaluate_room(room_input, options, cross)

            # Recommendation Engine v2 and the live forecast both use
            # persistence and trend. Forecast learning is based on absolute
            # humidity (g/m³), not RH alone, so temperature-driven RH changes
            # are not mistaken for water entering/leaving the room.
            humidity_trend = float(mem.get("humidity_trend_pct_h", 0.0) or 0.0)
            high_since = mem.get("humidity_high_since")
            if result.data_quality == "ok":
                start_rh = float(options.get("start_rh", 62.0))
                if float(result.humidity or 0.0) >= start_rh:
                    if not high_since:
                        mem["humidity_high_since"] = now.isoformat(); high_since = mem["humidity_high_since"]; changed = True
                elif high_since:
                    mem["humidity_high_since"] = None; high_since = None; changed = True

                prev_at = mem.get("forecast_observation_at")
                prev_ah = mem.get("forecast_observation_ah")
                prev_temp = mem.get("forecast_observation_temp")
                prev_ref_ah = mem.get("forecast_observation_ref_ah")
                prev_open = bool(mem.get("forecast_observation_open"))
                update_observation = prev_at is None or prev_ah is None
                if prev_at is not None and prev_ah is not None:
                    try:
                        age_min = (now - datetime.fromisoformat(prev_at)).total_seconds() / 60.0
                        if 5.0 <= age_min <= 30.0:
                            curr_ah = float(result.absolute_humidity or 0.0)
                            legacy_prev_rh = mem.get("humidity_observation_rh")
                            if legacy_prev_rh is not None:
                                raw_trend = (float(result.humidity) - float(legacy_prev_rh)) / max(age_min / 60.0, 1/60)
                                humidity_trend = max(min(raw_trend, 20.0), -20.0)
                                mem["humidity_trend_pct_h"] = round(humidity_trend, 2)

                            volume = max(float(cfg[CONF_ROOM_VOLUME]), 0.0)
                            observed_ml_min = (curr_ah - float(prev_ah)) * volume / max(age_min, 1.0)
                            observed_temp_min = 0.0 if prev_temp is None else (t - float(prev_temp)) / max(age_min, 1.0)
                            residual_ml_min = observed_ml_min
                            residual_temp_min = observed_temp_min
                            if prev_open and mem.get("session_active"):
                                # Recent *measured* net removal rate. Positive = moisture
                                # actually left the room.  The running forecast blends this
                                # cautiously with the physical model so a stalled 60-minute
                                # session cannot keep promising the same theoretical removal.
                                mem["forecast_recent_removed_ml_min"] = round(-observed_ml_min, 4)
                                mem["forecast_recent_observed_at"] = now.isoformat()
                                curr_ref_ah = float(result.reference_humidity or 0.0)
                                avg_ref_ah = (float(prev_ref_ah) + curr_ref_ah) / 2.0 if prev_ref_ah is not None else curr_ref_ah
                                avg_room_ah = (float(prev_ah) + curr_ah) / 2.0
                                interval_fraction = exchanged_air_fraction(
                                    float(mem.get("learning_rate", .03)), age_min,
                                    (1.25 if cross else 1.0) * airflow,
                                )
                                physical_removed = (avg_room_ah - avg_ref_ah) * volume * interval_fraction
                                residual_ml_min = observed_ml_min + physical_removed / max(age_min, 1.0)
                                if prev_temp is not None:
                                    avg_room_temp = (float(prev_temp) + t) / 2.0
                                    physical_dt = (ref_t - avg_room_temp) * interval_fraction
                                    residual_temp_min = observed_temp_min - physical_dt / max(age_min, 1.0)

                            residual_bound = max(8.0, volume * 0.25)
                            residual_ml_min = min(max(residual_ml_min, -residual_bound), residual_bound)
                            old_source = mem.get("forecast_source_ml_min")
                            alpha = 0.35 if mem.get("session_active") else 0.22
                            mem["forecast_source_ml_min"] = round(
                                residual_ml_min if old_source is None else float(old_source) * (1-alpha) + residual_ml_min * alpha, 4
                            )
                            residual_temp_min = min(max(residual_temp_min, -0.20), 0.20)
                            old_thermal = mem.get("forecast_thermal_residual_c_min")
                            mem["forecast_thermal_residual_c_min"] = round(
                                residual_temp_min if old_thermal is None else float(old_thermal) * (1-alpha) + residual_temp_min * alpha, 5
                            )
                            mem["forecast_observation_samples"] = min(int(mem.get("forecast_observation_samples", 0)) + 1, 1000)
                            update_observation = True
                        elif age_min > 30.0:
                            update_observation = True
                    except (TypeError, ValueError):
                        update_observation = True
                if update_observation:
                    mem["forecast_observation_at"] = now.isoformat()
                    mem["forecast_observation_ah"] = float(result.absolute_humidity or 0.0)
                    mem["forecast_observation_temp"] = float(t)
                    mem["forecast_observation_ref_ah"] = float(result.reference_humidity or 0.0)
                    mem["forecast_observation_open"] = bool(is_open)
                    mem["humidity_observation_at"] = now.isoformat()
                    mem["humidity_observation_rh"] = float(result.humidity)
                    changed = True

            high_duration = 0.0
            if high_since:
                try:
                    high_duration = max(0.0, (now - datetime.fromisoformat(high_since)).total_seconds() / 60.0)
                except (TypeError, ValueError):
                    high_duration = 0.0

            mem["last_measurement_at"] = now.isoformat()
            mem["last_measurement_valid"] = result.data_quality == "ok"
            action, reason, reason_list = _recommendation(result, options, pollen=pollen, co2=co2, airflow=airflow, wind_bearing=wind_bearing, wind_speed=wind_speed)
            result.action = action; result.reason = reason
            if mem["session_active"] and result.data_quality == "ok":
                if abs(float(mem.get("session_result_ml", 0.0)) - float(result.result_ml)) >= 0.01:
                    mem["session_result_ml"] = float(result.result_ml); changed = True
            if not include and result.data_quality == "ok":
                result.action = "Monitor only"; result.reason = "Room is visible but excluded from FreshAirIQ calculations"; result.close_recommended = False
            fraction = exchanged_air_fraction(float(mem["learning_rate"]), 5, (1.25 if cross else 1.0) * airflow)
            delivered, purchased, cost = ventilation_cost(float(cfg[CONF_ROOM_VOLUME]), t, ref_t, fraction, options) if -30 < ref_t < 60 and -10 < t < 50 else (0, 0, 0)
            # Reheating cost is only meaningful when the next ventilation step
            # is expected to cool the room. Warming by outdoor air is not billed
            # as a reheating loss.
            if result.temp_next_5_min_c >= 0 or result.action == "Ventilate for cooling":
                purchased = 0.0; cost = 0.0
            start_temp = mem.get("session_start_temp")
            temp_change = round(t - float(start_temp), 1) if mem["session_active"] and start_temp is not None else 0.0
            fuel = heating_cost_context(delivered, options)

            room_prior_ml_min = 0.0
            if calc_volume_total > 0:
                room_prior_ml_min = (daily_generation_prior / 1440.0) * (float(cfg[CONF_ROOM_VOLUME]) / calc_volume_total)
            learned_source_for_forecast = mem.get("forecast_source_ml_min")
            if moisture_source.get("active"):
                detected_rate = max(float(moisture_source.get("source_rate_ml_min") or 0.0), 0.0)
                learned_source_for_forecast = max(float(learned_source_for_forecast or 0.0), detected_rate)
            recent_removed_rate = mem.get("forecast_recent_removed_ml_min")
            recent_removed_at = mem.get("forecast_recent_observed_at")
            if recent_removed_rate is not None and recent_removed_at:
                try:
                    if (now - datetime.fromisoformat(str(recent_removed_at))).total_seconds() > 30 * 60:
                        recent_removed_rate = None
                except (TypeError, ValueError):
                    recent_removed_rate = None
            forecast_model_maturity = min(
                95.0,
                55.0
                + min(int(mem.get("learning_samples", 0)), 10) * 2.0
                + min(int(mem.get("outcome_feedback_samples", 0)), 10) * 2.0
                + min(int(mem.get("forecast_observation_samples", 0)), 6) * 1.0,
            )
            forecast_args = dict(
                current_ah=float(result.absolute_humidity or 0.0),
                source_ah=float(result.reference_humidity or 0.0),
                current_temp_c=t, source_temp_c=ref_t,
                volume_m3=float(cfg[CONF_ROOM_VOLUME]),
                rate_per_min=float(mem.get("learning_rate", .03)),
                airflow_bonus=(1.25 if cross else 1.0) * airflow,
                prior_source_ml_min=room_prior_ml_min,
                learned_source_ml_min=learned_source_for_forecast,
                learned_thermal_residual_c_min=mem.get("forecast_thermal_residual_c_min"),
                observation_samples=int(mem.get("forecast_observation_samples", 0)),
                model_maturity_pct=forecast_model_maturity,
                measurement_frame_quality=str(measurement_frame.get("quality") or "stale"),
                running=bool(mem.get("session_active") and is_open),
                session_elapsed_min=elapsed,
                session_fresh_measurements=int(mem.get("session_fresh_measurements", 0)),
                recent_observed_removed_ml_min=recent_removed_rate,
                future_source_boundaries=(
                    forecast_outdoor_steps
                    if not cfg.get(CONF_ROOM_REFERENCE_TEMPERATURE)
                    and not cfg.get(CONF_ROOM_REFERENCE_HUMIDITY)
                    and not active_contact_reference
                    else None
                ),
            )
            if result.data_quality == "ok":
                # Hotfix 0.17.0.2: the freely selectable long-horizon card is a
                # decision forecast, not a promise to keep drying indefinitely.
                # Cap only horizons >5 min at the configured room humidity target.
                # The internal 5-minute control forecast remains uncapped by the
                # comfort target, but during a mature running session it may be
                # corrected by the recent measured removal rate.  That prevents
                # the live coach from extending a session after real drying stalls.
                target_ah = absolute_humidity(t, float(options.get("target_rh", 58.0)))
                dynamic = horizon_forecast(
                    horizon_min=forecast_horizon,
                    target_ah=target_ah,
                    cap_positive_to_target=forecast_horizon > 5,
                    min_return_next_5_min_ml=float(options.get("min_return_next_5_min_ml", 25.0)),
                    max_temp_loss_next_5_min_c=float(options.get("max_temp_loss_next_5_min_c", 0.6)),
                    min_efficiency_ml_per_01c=float(options.get("min_efficiency_ml_per_01c", 8.0)),
                    min_duration_min=float(options.get("min_duration_min", 3.0)),
                    max_duration_min=float(options.get("max_duration_min", 20.0)),
                    operating_profile=str(options.get("operating_profile", "comfort")),
                    **forecast_args,
                )
                dynamic5 = horizon_forecast(horizon_min=5, **forecast_args)
            else:
                dynamic = {
                    "horizon_min": forecast_horizon, "moisture_effect_ml": 0,
                    "physical_moisture_effect_ml": 0, "internal_moisture_effect_ml": 0,
                    "net_moisture_change_ml": 0, "temperature_change_c": 0.0,
                    "exchange_fraction": 0.0, "confidence": 0,
                    "source_rate_ml_min": 0.0, "method": "unavailable",
                }
                dynamic5 = dict(dynamic, horizon_min=5)
            if result.data_quality == "ok":
                temperature_path = dynamic.get("temperature_path") or []
                if temperature_path:
                    fdel, fpurchased, fcost = ventilation_cost_for_temperature_path(
                        float(cfg[CONF_ROOM_VOLUME]), float(mem.get("learning_rate", .03)),
                        (1.25 if cross else 1.0) * airflow, temperature_path, options,
                    )
                else:
                    fdel, fpurchased, fcost = ventilation_cost_for_duration(
                        float(cfg[CONF_ROOM_VOLUME]), t, ref_t, float(mem.get("learning_rate", .03)),
                        forecast_horizon, (1.25 if cross else 1.0) * airflow, options,
                    )
            else:
                fdel, fpurchased, fcost = (0.0, 0.0, 0.0)
            if float(dynamic.get("temperature_change_c", 0.0)) >= 0 or result.action == "Ventilate for cooling":
                fdel = 0.0; fpurchased = 0.0; fcost = 0.0
            ffuel = heating_cost_context(fdel, options)

            if (
                mem.get("session_active")
                and mem.get("session_prediction_snapshot_pending")
                and mem.get("session_validation_started")
                and result.data_quality == "ok"
            ):
                # Hotfix 0.24.14.1: freeze the complete START model immediately
                # from the numeric opening baseline. Whether that baseline is
                # allowed into objective scoring is decided only after the session
                # from real post-open sensor activity, so sleeping battery sensors
                # no longer lose their start forecast merely because last_reported
                # was old at the exact opening instant.
                try:
                    measurement_started = datetime.fromisoformat(str(mem.get("session_validation_started")))
                    measurement_elapsed_now = max(0.0, (now - measurement_started).total_seconds() / 60.0)
                except (TypeError, ValueError):
                    measurement_elapsed_now = 0.0

                if measurement_elapsed_now <= 2.5:
                    recommended_total_horizon = mem.get("session_recommended_duration_min")
                    if recommended_total_horizon is not None:
                        # Recommendation duration is counted from physical opening.
                        # The frozen model starts at the confirmed measurement
                        # baseline, so predict only the still remaining part.
                        initial_horizon = max(float(recommended_total_horizon) - elapsed, 1.0)
                    elif dynamic.get("optimal_close_in_min") is not None:
                        initial_horizon = max(float(dynamic.get("optimal_close_in_min")), 1.0)
                    else:
                        initial_horizon = max(float(forecast_horizon), 1.0)
                    initial_horizon = min(initial_horizon, 120.0)

                    start_ah = float(mem.get("session_validation_start_ah") or absolute_humidity(t, rh))
                    start_source_ah = float(mem.get("session_validation_start_source_ah") or absolute_humidity(ref_t, ref_rh))
                    start_temp = float(mem.get("session_validation_start_temp") if mem.get("session_validation_start_temp") is not None else t)
                    start_source_temp = float(mem.get("session_validation_start_source_temp") if mem.get("session_validation_start_source_temp") is not None else ref_t)
                    start_target_ah = absolute_humidity(start_temp, float(options.get("target_rh", 58.0)))
                    start_context = freeze_start_forecast_context(
                        forecast_args,
                        target_ah=start_target_ah,
                        options=options,
                        start_ah=start_ah,
                        start_source_ah=start_source_ah,
                        start_temp_c=start_temp,
                        start_source_temp_c=start_source_temp,
                    )
                    start_prediction = evaluate_start_forecast_at_duration(start_context, initial_horizon)
                    if start_prediction is not None:
                        mem["session_prediction_start_context"] = start_context
                        mem["session_predicted_removed_ml"] = start_prediction["predicted_removed_ml"]
                        mem["session_predicted_temperature_change_c"] = start_prediction["predicted_temperature_change_c"]
                        mem["session_predicted_cost"] = start_prediction["predicted_cost"]
                        mem["session_prediction_confidence"] = start_prediction["confidence"]
                        mem["session_prediction_snapshot_at"] = now.isoformat()
                        mem["session_prediction_horizon_min"] = initial_horizon
                        mem["session_prediction_snapshot_elapsed_min"] = round(measurement_elapsed_now, 3)
                        mem["session_prediction_snapshot_valid"] = True
                        mem["session_prediction_time_aligned"] = False
                        mem["session_prediction_reference"] = "session_start_curve_v2"
                        mem["session_prediction_snapshot_frame_quality"] = measurement_frame.get("quality")
                        mem["session_prediction_snapshot_frame_skew_s"] = measurement_frame.get("skew_s")
                        mem["session_prediction_snapshot_frame_max_age_s"] = measurement_frame.get("max_age_s")
                    else:
                        mem["session_prediction_snapshot_valid"] = False
                        mem["session_prediction_reference"] = "start_snapshot_invalid"
                else:
                    # This mainly covers restored/reloaded sessions for which the
                    # integration was not running at the real logical start.
                    mem["session_prediction_snapshot_valid"] = False
                    mem["session_prediction_reference"] = "start_snapshot_missed"
                mem["session_prediction_snapshot_pending"] = False
                changed = True

            # Validation Engine v2: keep a time-resolved forecast trajectory for
            # the active session. Every point predicts the FINAL state at the
            # original frozen start horizon, using only information available at
            # that checkpoint. This is intentionally diagnostic-only.
            if (
                mem.get("session_active")
                and result.data_quality == "ok"
                and mem.get("session_prediction_snapshot_valid")
                and mem.get("session_prediction_horizon_min") is not None
            ):
                timeline = list(mem.get("session_forecast_timeline") or [])
                start_ah = float(mem.get("session_start_ah") or 0.0)
                current_ah = absolute_humidity(t, rh)
                actual_so_far = float(mem.get("session_result_base_ml", 0.0)) + (start_ah - current_ah) * float(cfg[CONF_ROOM_VOLUME])
                temp_start = float(mem.get("session_start_temp") if mem.get("session_start_temp") is not None else t)
                actual_temp_delta = t - temp_start
                target_horizon = max(float(mem.get("session_prediction_horizon_min") or 0.0), 1.0)

                # Ensure the immutable start point exists exactly once.
                if not any(str(point.get("kind")) == "start" for point in timeline if isinstance(point, dict)):
                    timeline.append({
                        "kind": "start",
                        "checkpoint_min": 0.0,
                        "captured_at": mem.get("session_prediction_snapshot_at") or now.isoformat(),
                        "elapsed_min": round(elapsed, 3),
                        "timing_error_min": round(elapsed, 3),
                        "actual_removed_ml": round(actual_so_far, 1),
                        "actual_temperature_change_c": round(actual_temp_delta, 2),
                        "predicted_final_removed_ml": round(float(mem.get("session_predicted_removed_ml") or 0.0), 1),
                        "predicted_final_temperature_change_c": round(float(mem.get("session_predicted_temperature_change_c") or 0.0), 2),
                        "remaining_horizon_min": round(max(target_horizon - elapsed, 0.0), 2),
                        "next_5_min_net_moisture_change_ml": round(float(dynamic5.get("net_moisture_change_ml", dynamic5.get("moisture_effect_ml", 0.0)) or 0.0), 1),
                        "next_5_min_temperature_change_c": round(float(dynamic5.get("temperature_change_c", 0.0) or 0.0), 2),
                        "confidence": int(mem.get("session_prediction_confidence") or 0),
                        "method": str(dynamic.get("method") or "unknown"),
                        "measurement_frame_quality": mem.get("session_prediction_snapshot_frame_quality"),
                        "measurement_frame_skew_s": mem.get("session_prediction_snapshot_frame_skew_s"),
                        "measurement_frame_max_age_s": mem.get("session_prediction_snapshot_frame_max_age_s"),
                    })
                    mem["session_timeline_last_checkpoint_min"] = 0.0
                    changed = True

                checkpoint = int(elapsed // 5.0) * 5
                last_checkpoint = float(mem.get("session_timeline_last_checkpoint_min") or 0.0)
                if checkpoint >= 5 and checkpoint > last_checkpoint and elapsed <= target_horizon + 3.0:
                    remaining = max(target_horizon - elapsed, 0.0)
                    if remaining > 0.25:
                        live_to_end = horizon_forecast(
                            horizon_min=remaining,
                            target_ah=target_ah,
                            cap_positive_to_target=remaining > 5,
                            min_return_next_5_min_ml=float(options.get("min_return_next_5_min_ml", 25.0)),
                            max_temp_loss_next_5_min_c=float(options.get("max_temp_loss_next_5_min_c", 0.6)),
                            min_efficiency_ml_per_01c=float(options.get("min_efficiency_ml_per_01c", 8.0)),
                            min_duration_min=float(options.get("min_duration_min", 3.0)),
                            max_duration_min=float(options.get("max_duration_min", 20.0)),
                            operating_profile=str(options.get("operating_profile", "comfort")),
                            **forecast_args,
                        )
                        predicted_final_removed = actual_so_far + float(live_to_end.get("net_moisture_change_ml", 0.0) or 0.0)
                        predicted_final_temp = actual_temp_delta + float(live_to_end.get("temperature_change_c", 0.0) or 0.0)
                    else:
                        predicted_final_removed = actual_so_far
                        predicted_final_temp = actual_temp_delta
                        live_to_end = {"confidence": dynamic.get("confidence", 0), "method": "horizon_reached"}
                    timeline.append({
                        "kind": "live",
                        "checkpoint_min": float(checkpoint),
                        "captured_at": now.isoformat(),
                        "elapsed_min": round(elapsed, 3),
                        "timing_error_min": round(elapsed - float(checkpoint), 3),
                        "actual_removed_ml": round(actual_so_far, 1),
                        "actual_temperature_change_c": round(actual_temp_delta, 2),
                        "predicted_final_removed_ml": round(predicted_final_removed, 1),
                        "predicted_final_temperature_change_c": round(predicted_final_temp, 2),
                        "remaining_horizon_min": round(remaining, 2),
                        "next_5_min_net_moisture_change_ml": round(float(dynamic5.get("net_moisture_change_ml", dynamic5.get("moisture_effect_ml", 0.0)) or 0.0), 1),
                        "next_5_min_temperature_change_c": round(float(dynamic5.get("temperature_change_c", 0.0) or 0.0), 2),
                        "confidence": int(live_to_end.get("confidence", 0) or 0),
                        "method": str(live_to_end.get("method") or "unknown"),
                        "measurement_frame_quality": measurement_frame.get("quality"),
                        "measurement_frame_skew_s": measurement_frame.get("skew_s"),
                        "measurement_frame_max_age_s": measurement_frame.get("max_age_s"),
                    })
                    mem["session_forecast_timeline"] = timeline[-32:]
                    mem["session_timeline_last_checkpoint_min"] = float(checkpoint)
                    changed = True
                elif timeline != list(mem.get("session_forecast_timeline") or []):
                    mem["session_forecast_timeline"] = timeline[-32:]

            if result.data_quality == "ok" and self.store.record_room_temperature_point(key, now.replace(tzinfo=None), t, days=30): changed = True
            minutes_since_vent = None
            if mem.get("last_ventilation_ended_at"):
                try: minutes_since_vent = max(0.0, (now-datetime.fromisoformat(mem["last_ventilation_ended_at"])).total_seconds()/60.0)
                except (TypeError, ValueError): minutes_since_vent = None
            stabilization_min = float(options.get("post_ventilation_stabilization_min", 4.0))
            repeat_cooldown = float(options.get("repeat_recommendation_cooldown_min", 120.0))
            stabilization = minutes_since_vent is not None and minutes_since_vent < stabilization_min
            last_ref_ah = mem.get("last_ventilation_reference_ah")
            current_ref_ah = float(result.reference_humidity or 0.0)
            weather_improved = False
            if last_ref_ah is not None:
                # A tiny weather fluctuation must not immediately re-arm a room.
                # Require a materially drier reference than at the previous close.
                weather_improved = current_ref_ah <= float(last_ref_ah) - max(float(options.get("repeat_weather_improvement_g_m3", 1.0)), 1.5)
            urgent_override = (float(result.surface_rh or 0.0) >= float(options.get("mould_warn_surface_rh", 80.0)) or (co2 is not None and co2 >= float(options.get("co2_critical", 1400.0))))
            repeat_min_benefit = float(options.get("repeat_min_benefit_ml", 80.0))
            last_end_rh = finite_float(mem.get("last_ventilation_end_humidity"))
            humidity_rebound = None if last_end_rh is None else float(rh) - float(last_end_rh)
            strong_new_source = bool(
                (moisture_source.get("active") or moisture_source.get("recovery"))
                and float(moisture_source.get("confidence", 0.0) or 0.0) >= 90.0
                and float(result.potential_ml or 0.0) >= max(repeat_min_benefit * 1.5, 150.0)
                and (humidity_rebound is None or humidity_rebound >= 3.0)
            )
            # Prevent a credibility-breaking recommendation reversal directly
            # after closing. A changed reference path (e.g. Wintergarten ->
            # outside) may look like better weather, but may only bypass the
            # normal repeat cooldown after this anti-flap floor. Real urgency or
            # a strong new moisture source can still override immediately.
            anti_flap_min = max(stabilization_min, min(15.0, repeat_cooldown))
            weather_override_allowed = bool(
                weather_improved and minutes_since_vent is not None and minutes_since_vent >= anti_flap_min
            )
            cooldown_override = bool(strong_new_source or weather_override_allowed or urgent_override)
            stabilizing = stabilization
            recently_ventilated = minutes_since_vent is not None and minutes_since_vent < repeat_cooldown and not cooldown_override
            if (
                include and result.data_quality == "ok" and not is_open and not mem.get("session_active")
                and not moisture_source.get("active") and not moisture_source.get("recovery")
                and not stabilizing and mem.get("forecast_source_ml_min") is not None
            ):
                source_value = float(mem.get("forecast_source_ml_min") or 0.0)
                if learn_source_pattern(mem, now, source_value):
                    learn_seasonal_source(mem, now, source_value)
                    changed = True
            routine_rate, routine_samples = expected_source_rate(mem, now)
            routine_response = response_pattern(mem, now)
            season_ctx = seasonal_context(mem, now)
            seasonal_routine_rate = (
                float(routine_rate) * float(season_ctx.get("factor", 1.0))
                if routine_rate is not None else None
            )
            opening_assessments = _opening_assessments(
                self.hass, cfg,
                room_temperature=float(t), room_humidity=float(rh), volume_m3=float(cfg[CONF_ROOM_VOLUME]),
                default_temp_entity=default_reference_temperature_entity,
                default_humidity_entity=default_reference_humidity_entity,
                default_temp=default_ref_t, default_humidity=default_ref_rh,
                learning_rate=float(mem.get("learning_rate", .03)),
                learning_samples=int(mem.get("learning_samples", 0)), co2=co2, pollen=pollen,
                options=options, wind_bearing=wind_bearing, wind_speed=wind_speed,
            )
            room_threshold_mode = str(cfg.get(CONF_ROOM_THRESHOLD_MODE, ROOM_THRESHOLD_AUTOMATIC) or ROOM_THRESHOLD_AUTOMATIC)
            if room_threshold_mode == ROOM_THRESHOLD_PERCENT:
                room_threshold_effective_ml = max(float(result.water_in_air_ml or 0.0) * float(cfg.get(CONF_ROOM_THRESHOLD_PERCENT, 5.0) or 5.0) / 100.0, 0.0)
            elif room_threshold_mode == ROOM_THRESHOLD_FIXED:
                room_threshold_effective_ml = max(float(cfg.get(CONF_ROOM_THRESHOLD_ML, 100.0) or 100.0), 0.0)
            else:
                room_threshold_mode = ROOM_THRESHOLD_AUTOMATIC
                room_threshold_effective_ml = max(float(options.get("min_potential_room_ml", 100.0) or 100.0), 0.0)

            results[key] = result.as_dict() | {
                "learning_diagnosis": mem.get("diagnosis", ""), "learning_sample_credit": round(float(mem.get("learning_sample_credit", 0.0) or 0.0), 3), "co2": co2, "co2_available": co2_available, "co2_data_quality": ("ok" if co2_available else "missing" if co2_entity else "not_configured"),
                "voc": voc, "voc_available": voc is not None, "voc_enabled": voc_sensor_enabled, "voc_configured": bool(voc_configured_entity),
                "pm25": pm25, "pm25_available": pm25 is not None, "pm25_enabled": pm25_sensor_enabled, "pm25_configured": bool(pm25_configured_entity),
                "illuminance": illuminance, "illuminance_available": illuminance is not None, "illuminance_enabled": illuminance_sensor_enabled, "illuminance_configured": bool(illuminance_configured_entity),
                "learned_exchange_rate_per_min": round(float(mem.get("learning_rate", .03)), 3),
                "behaviour_recommendation_opportunities": int(mem.get("recommendation_opportunities", 0)), "behaviour_recommendation_followed": int(mem.get("recommendation_followed", 0)), "behaviour_recommendation_follow_rate": mem.get("recommendation_follow_rate"),
                "behaviour_preferred_duration_min": mem.get("preferred_duration_min"), "behaviour_duration_samples": int(mem.get("duration_samples", 0)), "behaviour_avg_follow_delay_min": mem.get("avg_follow_delay_min"), "behaviour_follow_delay_samples": int(mem.get("follow_delay_samples", 0)), "behaviour_avg_duration_deviation_min": mem.get("avg_duration_deviation_min"),
                "forecast_observation_samples": int(mem.get("forecast_observation_samples", 0)), "forecast_source_ml_min": mem.get("forecast_source_ml_min"), "forecast_thermal_residual_c_min": mem.get("forecast_thermal_residual_c_min"),
                "routine_maturity": routine_maturity(mem), "routine_source_samples": int(mem.get("routine_source_samples", 0)), "routine_response_samples": int(mem.get("routine_response_samples", 0)),
                "routine_expected_source_ml_min": round(seasonal_routine_rate, 3) if seasonal_routine_rate is not None else None, "routine_current_bucket_samples": int(routine_samples), "routine_response": routine_response,
                "season": season_ctx.get("season"), "seasonal_factor": season_ctx.get("factor"), "seasonal_maturity": season_ctx.get("maturity"),
                "seasonal_source_rate_ml_min": season_ctx.get("season_rate_ml_min"), "long_term_source_rate_ml_min": season_ctx.get("long_term_rate_ml_min"),
                "seasonal_samples": int(mem.get("seasonal_samples", 0)), "long_term_source_samples": int(mem.get("long_term_source_samples", 0)),
                "routine_source_buckets": mem.get("routine_source_buckets", {}),
                "strategy_maturity": strategy_maturity(mem), "strategy_samples": int(mem.get("strategy_samples", 0)),
                "strategy_follow_samples": int(mem.get("strategy_follow_samples", 0)), "strategy_outcome_samples": int(mem.get("strategy_outcome_samples", 0)),
                "outcome_feedback_samples": int(mem.get("outcome_feedback_samples", 0)), "outcome_removed_factor": float(mem.get("outcome_removed_factor", 1.0) or 1.0), "outcome_temperature_factor": float(mem.get("outcome_temperature_factor", 1.0) or 1.0),
                "shadow_learning_samples": int(mem.get("shadow_learning_samples", 0)), "shadow_learning_total_samples": int(mem.get("shadow_learning_total_samples", 0)), "shadow_learning_status": mem.get("shadow_learning_status"), "shadow_learning_last_action": mem.get("shadow_learning_last_action"), "shadow_learning_last_improvement_pct": mem.get("shadow_learning_last_improvement_pct"), "shadow_learning_promotions": int(mem.get("shadow_learning_promotions", 0)), "shadow_learning_rollbacks": int(mem.get("shadow_learning_rollbacks", 0)), "shadow_rollback_active": bool(mem.get("shadow_rollback_active")),
                "outcome_avg_removed_error_ml": mem.get("outcome_avg_removed_error_ml"), "outcome_avg_temperature_error_c": mem.get("outcome_avg_temperature_error_c"), "outcome_success_rate": mem.get("outcome_success_rate"),
                "session_recommended_duration_min": mem.get("session_recommended_duration_min"), "session_predicted_removed_ml": mem.get("session_predicted_removed_ml"), "session_predicted_temperature_change_c": mem.get("session_predicted_temperature_change_c"), "session_prediction_confidence": mem.get("session_prediction_confidence"), "session_prediction_snapshot_at": mem.get("session_prediction_snapshot_at"), "session_prediction_horizon_min": mem.get("session_prediction_horizon_min"), "session_prediction_snapshot_elapsed_min": mem.get("session_prediction_snapshot_elapsed_min"), "session_prediction_snapshot_valid": bool(mem.get("session_prediction_snapshot_valid")), "session_prediction_reference": mem.get("session_prediction_reference"),
                "session_elapsed_min": round(elapsed, 1), "temperature_change_c": temp_change, "volume_m3": round(float(cfg[CONF_ROOM_VOLUME]), 1),
                "contact_mode": cfg.get(CONF_CONTACT_MODE, CONTACT_MODE_ANY), "contact_count": len(_contact_ids(cfg)), "contact_entities": _contact_ids(cfg), "contact_delays": dict(cfg.get(CONF_CONTACT_DELAYS, {})), "contact_orientations": dict(cfg.get(CONF_CONTACT_ORIENTATIONS, {})), "contact_reference_temperatures": dict(cfg.get(CONF_CONTACT_REFERENCE_TEMPERATURES, {})), "contact_reference_humidities": dict(cfg.get(CONF_CONTACT_REFERENCE_HUMIDITIES, {})), "active_reference_temperature_entity": reference_temperature_entity, "active_reference_humidity_entity": reference_humidity_entity, "opening_assessments": opening_assessments,
                "next_5_min_heat_kwh": delivered, "next_5_min_purchased_kwh": purchased, "next_5_min_cost": cost, "next_5_min_energy_amount": fuel["amount"], "next_5_min_energy_unit": fuel["unit"],
                "forecast_horizon_min": forecast_horizon, "forecast_moisture_effect_ml": int(dynamic["moisture_effect_ml"]),
                "forecast_physical_moisture_effect_ml": int(dynamic["physical_moisture_effect_ml"]), "forecast_uncapped_moisture_effect_ml": int(dynamic.get("uncapped_physical_moisture_effect_ml", dynamic["physical_moisture_effect_ml"])), "forecast_target_limited": bool(dynamic.get("target_limited", False)), "forecast_target_cap_ml": dynamic.get("target_cap_ml"), "forecast_live_adapted": bool(dynamic.get("live_adapted", False)), "forecast_live_observation_weight": float(dynamic.get("live_observation_weight", 0.0) or 0.0), "forecast_observed_projection_ml": dynamic.get("observed_projection_ml"), "forecast_internal_moisture_effect_ml": int(dynamic["internal_moisture_effect_ml"]),
                "forecast_net_moisture_change_ml": int(dynamic.get("net_moisture_change_ml", dynamic["moisture_effect_ml"])),
                "forecast_5_min_moisture_effect_ml": int(dynamic5["moisture_effect_ml"]),
                "forecast_5_min_net_moisture_change_ml": int(dynamic5.get("net_moisture_change_ml", dynamic5["moisture_effect_ml"])),
                "forecast_5_min_temperature_change_c": round(float(dynamic5["temperature_change_c"]), 2),
                "forecast_5_min_confidence": int(dynamic5["confidence"]),
                "forecast_temperature_change_c": round(float(dynamic["temperature_change_c"]), 2), "forecast_confidence": int(dynamic["confidence"]),
                "forecast_source_rate_ml_min": float(dynamic["source_rate_ml_min"]), "forecast_method": dynamic["method"],
                "forecast_simulation_steps": int(dynamic.get("simulation_steps", 1)), "forecast_simulated_final_ah": dynamic.get("simulated_final_ah"),
                "forecast_future_weather_used": bool(dynamic.get("future_weather_used", False)), "forecast_future_weather_confidence": dynamic.get("future_weather_confidence"),
                "forecast_optimal_close_in_min": dynamic.get("optimal_close_in_min"), "forecast_optimal_close_reason": dynamic.get("optimal_close_reason"),
                "forecast_max_cumulative_temp_loss_c": dynamic.get("max_cumulative_temp_loss_c"), "forecast_min_end_temp_c": dynamic.get("min_forecast_end_temp_c"),
                "forecast_heat_kwh": fdel, "forecast_purchased_kwh": fpurchased, "forecast_cost": fcost,
                "forecast_energy_amount": ffuel["amount"], "forecast_energy_unit": ffuel["unit"],
                "free_cooling_kwh": delivered if result.action == "Ventilate for cooling" else 0.0,
                "calculation_enabled": include, "floor": cfg.get(CONF_ROOM_FLOOR, FLOOR_GROUND), "sort_order": int(cfg.get(CONF_ROOM_SORT_ORDER, idx)),
                "ventilation_threshold_mode": room_threshold_mode, "ventilation_threshold_percent": float(cfg.get(CONF_ROOM_THRESHOLD_PERCENT, 5.0) or 5.0), "ventilation_threshold_configured_ml": float(cfg.get(CONF_ROOM_THRESHOLD_ML, 100.0) or 100.0), "ventilation_threshold_effective_ml": round(room_threshold_effective_ml, 1),
                "window_orientation": cfg.get(CONF_ROOM_WINDOW_ORIENTATION, ORIENTATION_UNKNOWN), "airflow_factor": airflow,
                "configured_moisture_sources": list(cfg.get(CONF_ROOM_MOISTURE_SOURCES, []) or []),
                "moisture_source_active": bool(moisture_source.get("active")), "moisture_source_recovery": bool(moisture_source.get("recovery")),
                "moisture_source_label": moisture_source.get("label"), "moisture_source_identified_source": moisture_source.get("identified_source"), "moisture_source_message": moisture_source.get("message"), "moisture_source_ambiguous": bool(moisture_source.get("ambiguous")), "moisture_source_confidence": int(moisture_source.get("confidence", 0)),
                "moisture_source_rate_ml_min": float(moisture_source.get("source_rate_ml_min", 0.0)), "moisture_source_generated_ml_window": float(moisture_source.get("generated_ml_window", 0.0)),
                "moisture_source_observed_change_ml_window": float(moisture_source.get("observed_change_ml_window", 0.0)), "moisture_source_ventilation_change_ml_window": float(moisture_source.get("ventilation_change_ml_window", 0.0)),
                "moisture_source_ah_rise_g_m3": float(moisture_source.get("absolute_humidity_rise_g_m3", 0.0)), "moisture_source_window_min": float(moisture_source.get("window_min", 0.0)),
                "moisture_source_started_at": moisture_source.get("started_at"), "moisture_source_last_ended_at": moisture_source.get("last_ended_at"),
                "recommendation_reasons": reason_list, "humidity_trend_pct_h": round(humidity_trend, 2), "humidity_high_duration_min": round(high_duration, 1),
                "last_measurement_at": mem.get("last_measurement_at"), "last_measurement_valid": mem.get("last_measurement_valid"),
                "measurement_frame_quality": measurement_frame.get("quality"), "measurement_frame_learning_eligible": bool(measurement_frame.get("learning_eligible")),
                "measurement_frame_skew_s": measurement_frame.get("skew_s"), "measurement_frame_full_skew_s": measurement_frame.get("full_skew_s"), "measurement_frame_reference_skew_s": measurement_frame.get("reference_skew_s"), "measurement_frame_max_age_s": measurement_frame.get("max_age_s"),
                "frame_age_temp_s": measurement_frame.get("age_temperature_s"), "frame_age_humidity_s": measurement_frame.get("age_humidity_s"),
                "frame_age_reference_temp_s": measurement_frame.get("age_reference_temperature_s"), "frame_age_reference_humidity_s": measurement_frame.get("age_reference_humidity_s"),
                "measurement_frame_reason": measurement_frame.get("reason"),
                # Intelligence 2.0 time-evidence must travel with the room snapshot.
                # build_learning_components_status() consumes `results`, not the
                # raw persistence dict; omitting these fields flattened all
                # independent-day counters to zero despite valid stored evidence.
                "learning_observation_dates": list(mem.get("learning_observation_dates") or []),
                "routine_observation_dates": list(mem.get("routine_observation_dates") or []),
                "strategy_observation_dates": list(mem.get("strategy_observation_dates") or []),
                "personal_context_observation_dates": list(mem.get("personal_context_observation_dates") or []),
                "seasonal_observation_days": dict(mem.get("seasonal_observation_days") or {}),
                "post_close_stabilization_active": bool(mem.get("post_close_active")),
                "post_close_stabilization": mem.get("post_close_last_outcome"),
                "start_measurement_state": mem.get("start_measurement_state"),
                "start_measurement_in_session_gate_passed": bool(mem.get("start_measurement_in_session_gate_passed")),
                "session_fresh_measurements": int(mem.get("session_fresh_measurements", 0)),
                "session_temperature_reports": int(mem.get("session_temperature_reports", 0)),
                "session_humidity_reports": int(mem.get("session_humidity_reports", 0)),
                "session_finalization_pending": bool(mem.get("session_close_pending")),
                "session_finalization_deadline_at": mem.get("session_close_deadline_at"),
                "session_final_temperature_feedback": bool(mem.get("session_close_temperature_feedback")),
                "session_final_humidity_feedback": bool(mem.get("session_close_humidity_feedback")),
                "session_measurement_quality": session_measurement_quality(
                    int(mem.get("session_fresh_measurements", 0)),
                    temperature_reports=int(mem.get("session_temperature_reports", 0)),
                    humidity_reports=int(mem.get("session_humidity_reports", 0)),
                    final_temperature_feedback=bool(mem.get("session_close_temperature_feedback")),
                    final_humidity_feedback=bool(mem.get("session_close_humidity_feedback")),
                ),
                "close_decision_ready": bool(result.close_decision_ready),
                "last_learning_at": mem.get("last_learning_at"), "last_learning_valid": mem.get("last_learning_valid"),
                "stabilizing": stabilizing, "recently_ventilated": recently_ventilated, "repeat_cooldown_override": cooldown_override,
                "minutes_since_last_ventilation": round(minutes_since_vent,1) if minutes_since_vent is not None else None,
                "repeat_humidity_rebound_percent": round(humidity_rebound, 1) if humidity_rebound is not None else None,
                "history_14d": self.store.room_history_days(key, int(options.get("statistics_days", 14))), "temperature_history_14d": self.store.room_temperature_points(key, int(options.get("statistics_days", 14))),
            }
            results[key]["pollen_blocked"] = bool(
                options.get("pollen_enabled", False)
                and options.get("pollen_strict_veto", True)
                and pollen > float(options.get("pollen_max", 4.0))
            )
            interventions = build_interventions(
                room=results[key],
                config=cfg,
                options=options,
                entity_state=lambda entity_id: (self.hass.states.get(entity_id).state if self.hass.states.get(entity_id) else None),
            )
            results[key]["interventions"] = interventions
            results[key]["primary_intervention"] = interventions[0] if interventions else None
            results[key]["configured_actuators"] = {
                "contact_covers": {str(k): list(v or []) for k, v in (cfg.get(CONF_CONTACT_COVERS, {}) or {}).items()},
                "covers": list(cfg.get(CONF_ROOM_COVERS, []) or []),  # legacy fallback only
                "climate": cfg.get(CONF_ROOM_CLIMATE),
                "exhaust_fan": cfg.get(CONF_ROOM_EXHAUST_FAN),
                "supply_fan": cfg.get(CONF_ROOM_SUPPLY_FAN),
                "ventilation_device": cfg.get(CONF_ROOM_VENTILATION_DEVICE),
                "dehumidifier": cfg.get(CONF_ROOM_DEHUMIDIFIER),
                "humidifier": cfg.get(CONF_ROOM_HUMIDIFIER),
                "air_purifier": cfg.get(CONF_ROOM_AIR_PURIFIER),
            }

        valid_all = [r for r in results.values() if r["data_quality"] == "ok"]
        valid = [r for r in valid_all if r.get("calculation_enabled", True)]
        bad = [r for r in results.values() if r["data_quality"] != "ok" and r.get("calculation_enabled", True)]
        active = [r for r in valid if r["active"]]; close = [r for r in valid if r["action"] == "Close"]

        # Hotfix 0.20.2.4: detect closed rooms that are measurably participating
        # in the current house ventilation.  This is deliberately conservative:
        # a same-floor/explicit connection makes a room only a *candidate*; the
        # room's own absolute-humidity sensor must then move toward its current
        # ventilation reference.  The estimate is display-only and is NOT added
        # to live_balance_ml, because that could double-count moisture transported
        # through an actively ventilated neighbouring room.
        active_keys = {str(r.get("key")) for r in active}
        active_floors = {str(r.get("floor", "")) for r in active}
        cross_zone_pairs: set[frozenset[str]] = set()
        for _pair in str(options.get("cross_zone_connections", "") or "").split(","):
            _keys = [x.strip() for x in _pair.split("+") if x.strip()]
            if len(_keys) == 2:
                cross_zone_pairs.add(frozenset(_keys))
        passive_group_id = (
            str(ventilation_group.get("started_at"))
            if isinstance(ventilation_group, dict) and ventilation_group.get("active")
            else None
        )
        for _key, _room in results.items():
            _mem = self.store.room(_key)
            _room["passive_ventilation_active"] = False
            _room["passive_ventilation_estimated_ml"] = 0.0
            _room["passive_ventilation_confidence"] = 0
            _room["passive_ventilation_reason"] = None
            _room["passive_ventilation_estimated"] = True

            _is_active = bool(_room.get("active"))
            _valid = (
                _room.get("data_quality") == "ok"
                and _room.get("calculation_enabled", True)
                and not _room.get("moisture_source_active")
                and not _room.get("moisture_source_recovery")
            )
            _same_floor = str(_room.get("floor", "")) in active_floors if active_floors else False
            _explicit_link = any(frozenset((_key, akey)) in cross_zone_pairs for akey in active_keys)
            _active_same_floor_count = sum(1 for a in active if str(a.get("floor", "")) == str(_room.get("floor", "")))
            # Same-floor proximity alone is weak evidence. Require at least two
            # active openings on that floor, while an explicit configured link
            # remains strong evidence on its own.
            _connection_strength = 1.0 if _explicit_link else (0.65 if _same_floor and _active_same_floor_count >= 2 else 0.0)
            _connected = bool(active and _connection_strength >= 0.45)

            if _is_active or not _valid or not _connected or passive_group_id is None:
                for _field in (
                    "passive_group_id", "passive_observation_started_at",
                    "passive_start_ah", "passive_start_reference_ah", "passive_samples",
                ):
                    if _mem.get(_field) is not None:
                        _mem[_field] = None
                        changed = True
                continue

            _current_ah = float(_room.get("absolute_humidity") or 0.0)
            _reference_ah = float(_room.get("reference_humidity") or 0.0)
            _volume = float(_room.get("volume_m3") or 0.0)
            if _mem.get("passive_group_id") != passive_group_id or _mem.get("passive_start_ah") is None:
                _mem["passive_group_id"] = passive_group_id
                _mem["passive_observation_started_at"] = now.isoformat()
                _mem["passive_start_ah"] = _current_ah
                _mem["passive_start_reference_ah"] = _reference_ah
                _mem["passive_samples"] = [{"elapsed_min": 0.0, "ah": _current_ah, "reference_ah": _reference_ah}]
                changed = True
                continue

            try:
                _passive_started = datetime.fromisoformat(str(_mem.get("passive_observation_started_at")))
                _elapsed_passive = max(0.0, (now - _passive_started).total_seconds() / 60.0)
            except (TypeError, ValueError):
                _mem["passive_observation_started_at"] = now.isoformat()
                _mem["passive_start_ah"] = _current_ah
                _mem["passive_start_reference_ah"] = _reference_ah
                _mem["passive_samples"] = [{"elapsed_min": 0.0, "ah": _current_ah, "reference_ah": _reference_ah}]
                changed = True
                continue

            _samples = list(_mem.get("passive_samples") or [])
            if not _samples or abs(float(_samples[-1].get("ah", _current_ah)) - _current_ah) >= 0.015 or _elapsed_passive - float(_samples[-1].get("elapsed_min", 0.0)) >= 1.5:
                _samples.append({"elapsed_min": round(_elapsed_passive, 3), "ah": _current_ah, "reference_ah": _reference_ah})
                _samples = _samples[-8:]
                _mem["passive_samples"] = _samples
                changed = True

            _passive = evaluate_passive_ventilation(
                start_ah=float(_mem.get("passive_start_ah") or _current_ah),
                current_ah=_current_ah,
                reference_ah=_reference_ah,
                volume_m3=_volume,
                elapsed_min=_elapsed_passive,
                connected=True,
                start_reference_ah=float(_mem.get("passive_start_reference_ah") or _reference_ah),
                samples=_samples,
                connection_strength=_connection_strength,
            )
            _room["passive_ventilation_active"] = bool(_passive.get("active"))
            _room["passive_ventilation_estimated_ml"] = float(_passive.get("estimated_ml", 0.0) or 0.0)
            _room["passive_ventilation_confidence"] = int(_passive.get("confidence", 0) or 0)
            _room["passive_ventilation_reason"] = _passive.get("reason")
            _room["passive_ventilation_elapsed_min"] = round(_elapsed_passive, 1)
        if completed_sessions:
            if not isinstance(ventilation_group, dict) or not ventilation_group.get("active"):
                starts = []
                for event in completed_sessions:
                    raw = event.get("started_at")
                    if raw:
                        try:
                            starts.append(datetime.fromisoformat(str(raw)))
                        except (TypeError, ValueError):
                            pass
                ventilation_group = new_ventilation_group(min(starts) if starts else now)
                self.store.data["ventilation_group"] = ventilation_group
            if append_completed_sessions(ventilation_group, completed_sessions):
                changed = True

        any_house_session_active = any(
            bool(self.store.room(cfg["key"]).get("session_active"))
            for cfg in rooms_cfg if cfg.get(CONF_ROOM_INCLUDE_CALCULATIONS, True)
        )
        if isinstance(ventilation_group, dict) and ventilation_group.get("active") and not any_house_session_active:
            group_ended_at = now
            event_ends: list[datetime] = []
            for event in ventilation_group.get("sessions", []):
                try:
                    event_ends.append(datetime.fromisoformat(str(event.get("ended_at"))))
                except (TypeError, ValueError):
                    pass
            if event_ends:
                group_ended_at = max(event_ends)
            completed_house_sessions = [
                dict(event) for event in ventilation_group.get("sessions", [])
                if isinstance(event, dict)
            ]
            result = finalise_ventilation_group(
                ventilation_group, group_ended_at, display_minutes=POST_VENTILATION_RESULT_MINUTES
            )
            if result is not None:
                self.store.data["last_ventilation"] = result
                validation_record = build_validation_record(
                    result, completed_house_sessions, model_version=VERSION
                )
                self.store.data["forecast_validation_history"] = append_validation_record(
                    self.store.data.get("forecast_validation_history") or [],
                    validation_record,
                    group_ended_at,
                )
                changed = True
            self.store.data["ventilation_group"] = None
            ventilation_group = None
            changed = True

        candidates = [r for r in valid if r.get("ventilation_candidate", False)]; cooling = [r for r in valid if r["action"] == "Ventilate for cooling"]
        # Keep the displayed "removable" value semantically identical to the
        # room breakdown: theoretical current potential across every valid room.
        # Decision logic remains based only on actionable ventilation candidates.
        potential = sum(max(float(r.get("potential_ml", 0)), 0.0) for r in valid)
        actionable_potential = sum(max(float(r.get("potential_ml", 0)), 0.0) for r in candidates)
        # House live balance is strictly the currently running sessions.
        # Completed room results may remain available for diagnostics but must
        # never be summed into a new/restarted live session.
        live = sum(r["result_ml"] for r in active)
        # Signed physical effect: + means removable/removed internally, - means moisture would be/was added.
        next5_effect = sum(r.get("forecast_5_min_moisture_effect_ml", r.get("moisture_effect_next_5_min_ml", 0)) for r in active)
        # When no ventilation is running, expose the aggregate 5-minute moisture
        # gain of rooms for which outside/reference air is currently wetter.
        # This is deliberately separate from removable potential so a negative
        # physical effect can never invalidate the dashboard state.
        moisture_gain_next5 = sum(
            max(0, -int(r.get("forecast_5_min_moisture_effect_ml", r.get("moisture_effect_next_5_min_ml", 0))))
            for r in valid if r.get("action") == "Do not ventilate"
        )
        forecast_effect = sum(float(r.get("forecast_moisture_effect_ml", 0)) for r in active)
        forecast_uncapped_effect = sum(float(r.get("forecast_uncapped_moisture_effect_ml", r.get("forecast_moisture_effect_ml", 0))) for r in active)
        forecast_target_limited = bool(active) and any(bool(r.get("forecast_target_limited")) for r in active)
        forecast_live_adapted = bool(active) and any(bool(r.get("forecast_live_adapted")) for r in active)
        forecast_live_observation_weight = max((float(r.get("forecast_live_observation_weight", 0.0) or 0.0) for r in active), default=0.0)
        forecast_cost = sum(float(r.get("forecast_cost", 0)) for r in active)
        forecast_heat = sum(float(r.get("forecast_heat_kwh", 0)) for r in active)
        active_forecast_volume = sum(float(r.get("volume_m3", 0)) for r in active)
        forecast_temp = (
            sum(float(r.get("forecast_temperature_change_c", 0)) * float(r.get("volume_m3", 0)) for r in active) / active_forecast_volume
            if active_forecast_volume > 0 else 0.0
        )
        forecast_confidence = round(
            sum(float(r.get("forecast_confidence", 0)) * float(r.get("volume_m3", 0)) for r in active) / active_forecast_volume
            if active_forecast_volume > 0 else 0.0
        )
        active_close_times = [
            float(r.get("forecast_optimal_close_in_min")) for r in active
            if r.get("forecast_optimal_close_in_min") is not None
        ]
        # A house-wide close time exists only when every active room reaches an
        # efficient end point inside the chosen horizon. Otherwise at least one
        # room is still predicted to benefit beyond the horizon.
        forecast_optimal_close_in_min = (
            round(max(active_close_times), 1)
            if active and len(active_close_times) == len(active) else None
        )
        max_surface = max((r["surface_rh"] for r in valid), default=0)
        total_water = sum(r["water_in_air_ml"] for r in valid)
        if valid and self.store.record_house_water(now.replace(tzinfo=None), total_water): changed = True
        threshold_mode = str(options.get("threshold_mode", "adaptive_home_size"))
        expected_daily_generation = estimated_daily_moisture_ml(options)
        current_daily_generation = estimated_daily_moisture_ml(options, effective_adults, effective_children)
        threshold_reason = ""
        if threshold_mode == "fixed_ml":
            ventilation_threshold = float(options.get("min_potential_total_ml", 500))
            threshold_reason = "fixed_ml"
        elif threshold_mode == "percent_total_water":
            ventilation_threshold = total_water * float(options.get("min_potential_percent_total_water", 10.0)) / 100.0
            threshold_reason = "percent_total_water"
        else:
            # Aim for roughly four meaningful ventilation opportunities per day
            # (inside the requested 3–5 range). The water-content bounds make
            # the result scale with monitored dwelling size instead of using a
            # one-size-fits-all mL trigger.
            daily_target = expected_daily_generation / 4.0
            lower = total_water * 0.06
            upper = total_water * 0.12
            ventilation_threshold = min(max(daily_target, lower), upper) if total_water > 0 else daily_target
            # On warm-season mornings/evenings, exploit cooler outside air by
            # lowering the trigger. This encourages early/late airing without
            # forcing ventilation during the hottest part of the day.
            avg_indoor_t = sum(float(r["temperature"]) * float(r["volume_m3"]) for r in valid) / max(sum(float(r["volume_m3"]) for r in valid), 1) if valid else 0.0
            opportunity = now.month in (5, 6, 7, 8, 9) and (now.hour < 9 or now.hour >= 19) and outdoor_t is not None and avg_indoor_t - outdoor_t >= 2.0
            if opportunity:
                ventilation_threshold *= 0.75
                threshold_reason = "adaptive_home_size_cool_window"
            else:
                threshold_reason = "adaptive_home_size"

        urgent_any = any(
            float(r.get("surface_rh", 0)) >= float(options.get("mould_critical_surface_rh", 90.0))
            or (r.get("co2_available", False) and float(r.get("co2", 0) or 0) >= float(options.get("co2_critical", 1400.0)))
            for r in valid
        )
        urgent_actionable = any(
            r.get("ventilation_candidate", False)
            and (
                float(r.get("surface_rh", 0)) >= float(options.get("mould_critical_surface_rh", 90.0))
                or (r.get("co2_available", False) and float(r.get("co2", 0) or 0) >= float(options.get("co2_critical", 1400.0)))
            )
            for r in valid
        )
        pollen_blocked = (
            bool(options.get("pollen_enabled", False))
            and bool(options.get("pollen_strict_veto", True))
            and pollen > float(options.get("pollen_max", 4.0))
            and not urgent_any
        )
        if bad: status = "sensor_error"; status_text = f"Check {len(bad)} room sensor set(s)"
        elif close: status = "close_windows"; status_text = f"Close {len(close)} room(s)"
        elif active:
            status = "ventilation_running"
            status_text = f"Ventilation running · {round(live)} ml removed" if live >= 0 else f"Ventilation running · {abs(round(live))} ml added"
        elif urgent_actionable:
            status = "ventilate"; status_text = "Ventilate now · critical indoor air condition"
        elif cooling: status = "cooling_recommended"; status_text = f"Summer cooling useful in {len(cooling)} room(s)"
        elif pollen_blocked and actionable_potential >= ventilation_threshold: status = "pollen_warning"; status_text = f"Pollen load {pollen:.1f} · ventilation postponed"
        elif actionable_potential >= ventilation_threshold:
            # The house-level "ventilate now" state is governed by the displayed
            # house threshold. High room RH remains visible in room/mould details,
            # but must not silently bypass the threshold shown to the user.
            status = "ventilate"; status_text = f"Ventilate now · about {round(actionable_potential)} ml actionable"
        else: status = "okay"; status_text = "Keep windows closed"

        confidence = round(sum(min(r["learning_samples"], 10) for r in valid) / max(len(valid) * 10, 1) * 100)
        reference_temp = outdoor_t if outdoor_t is not None else 10.0; max_delta = max((r["delta_g_m3"] for r in valid), default=0.0)
        base = 4 if reference_temp <= 0 else 5 if reference_temp <= 5 else 7 if reference_temp <= 10 else 10 if reference_temp <= 15 else 12 if reference_temp <= 20 else 15
        adj = -2 if max_delta >= 5 else -1 if max_delta >= 3 else 3 if max_delta < 2 else 0
        recommended = int(min(max(base + adj, float(options["min_duration_min"])), float(options["max_duration_min"])))

        # Hotfix 0.9.4.7: the user-facing moisture potential is the amount that
        # FreshAirIQ expects to exchange during the recommended airing time, not
        # the theoretical 100% replacement of all room air.  The physical basis
        # remains the absolute-humidity gradient (inside - reference/outside);
        # the learned per-room exchange rate then determines how much of that
        # gradient is realistically reached.  Keep the sign: positive means
        # removable moisture, negative means outside/reference air would add it.
        realistic_house_effect = 0.0
        realistic_actionable_potential = 0.0
        for r in valid:
            fraction = exchanged_air_fraction(
                float(r.get("learned_exchange_rate_per_min", .03)),
                recommended,
                (1.25 if cross else 1.0) * float(r.get("airflow_factor", 1.0)),
            )
            realistic = (
                float(r.get("delta_g_m3", 0.0))
                * float(r.get("volume_m3", 0.0))
                * fraction
            )
            r["realistic_potential_ml"] = round(realistic)
            r["theoretical_potential_ml"] = int(r.get("potential_ml", 0) or 0)
            r["potential_horizon_min"] = recommended
            realistic_house_effect += realistic
            if r.get("ventilation_candidate", False):
                realistic_actionable_potential += max(realistic, 0.0)

        max_elapsed = max((float(r.get("session_elapsed_min", 0)) for r in active), default=0.0); remaining = round(recommended - max_elapsed, 1) if active else float(recommended)
        active_volume = sum(float(r.get("volume_m3", 0)) for r in active)
        temp_live = round(sum(float(r.get("temperature_change_c", 0)) * float(r.get("volume_m3", 0)) for r in active) / active_volume, 1) if active_volume > 0 else 0.0
        avg_temp = round(sum(float(r["temperature"]) * float(r["volume_m3"]) for r in valid) / sum(float(r["volume_m3"]) for r in valid), 2) if valid and sum(float(r["volume_m3"]) for r in valid) > 0 else 0.0
        stats_days = int(options.get("statistics_days", 14))
        if valid and self.store.record_temperature_point(now.replace(tzinfo=None), avg_temp, days=30): changed = True

        if options.get("night_forecast_enabled") and valid and not active and in_night_window(now, options.get("night_start_hour"), options.get("night_end_hour")):
            last_raw = self.store.data.get("night_last_snapshot"); last_water = self.store.data.get("night_last_water_ml")
            if not last_raw or last_water is None:
                self.store.data["night_last_snapshot"] = now.isoformat(); self.store.data["night_last_water_ml"] = round(total_water); changed = True
            else:
                try:
                    last_dt = datetime.fromisoformat(last_raw); hours = (now - last_dt).total_seconds() / 3600.0
                    if hours >= .25:
                        if hours <= 1.5:
                            observed_rate = (total_water - float(last_water)) / hours
                            # Store a household-normalised rate so a night with
                            # one resident home does not permanently teach the
                            # model that a four-person household only emits one
                            # person's moisture. The live forecast scales it back
                            # to the currently detected occupancy.
                            current_prior = max(effective_night_rate_ml_h(options, None, 0, effective_adults, effective_children), 1.0)
                            configured_prior = max(effective_night_rate_ml_h(options, None, 0), 1.0)
                            normalised_rate = observed_rate * (configured_prior / current_prior)
                            rate, samples = update_night_learning(self.store.data.get("night_model_ml_h"), int(self.store.data.get("night_model_samples", 0)), normalised_rate)
                            if samples != self.store.data.get("night_model_samples"):
                                self.store.data["night_model_ml_h"] = rate; self.store.data["night_model_samples"] = samples
                                nights = self.store.data.get("night_observed_dates")
                                if not isinstance(nights, list):
                                    nights = []
                                # Attribute after-midnight samples to the night
                                # that started on the previous calendar day.
                                night_day = (now.date() if now.hour >= 12 else (now - timedelta(days=1)).date()).isoformat()
                                if night_day not in nights:
                                    nights.append(night_day)
                                    nights = nights[-500:]
                                self.store.data["night_observed_dates"] = nights
                        self.store.data["night_last_snapshot"] = now.isoformat(); self.store.data["night_last_water_ml"] = round(total_water); changed = True
                except (ValueError, TypeError): self.store.data["night_last_snapshot"] = now.isoformat(); self.store.data["night_last_water_ml"] = round(total_water); changed = True
        elif not in_night_window(now, options.get("night_start_hour"), options.get("night_end_hour")) and self.store.data.get("night_last_snapshot") is not None:
            self.store.data["night_last_snapshot"] = None; self.store.data["night_last_water_ml"] = None; changed = True

        # v0.18.0.3: establish one exact night window before any night-facing
        # calculation. Forecast value, strategy text and notifications therefore
        # describe the same hours and the same hourly weather rows.
        def _time_value(value: Any, default_hour: int) -> tuple[int, int]:
            try:
                raw = str(value)
                if ":" in raw:
                    hour_raw, minute_raw = raw.split(":", 1)
                    return int(hour_raw) % 24, min(max(int(minute_raw[:2]), 0), 59)
                return int(raw) % 24, 0
            except (TypeError, ValueError):
                return default_hour, 0

        night_start_h, night_start_m = _time_value(options.get("night_start_hour", "22:00"), 22)
        current_minutes = now.hour * 60 + now.minute + now.second / 60.0
        start_minutes = night_start_h * 60 + night_start_m
        configured_night_hours = night_window_hours(options.get("night_start_hour"), options.get("night_end_hour"))
        hours_to_start = ((start_minutes - current_minutes) % 1440.0) / 60.0 if configured_night_hours > 0 else 24.0
        night_strategy_relevant = bool(options.get("night_forecast_enabled")) and configured_night_hours > 0 and (
            in_night_window(now, options.get("night_start_hour"), options.get("night_end_hour"))
            or hours_to_start <= 3.0
        )
        night_start_dt, night_end_dt = night_interval_bounds(
            now, options.get("night_start_hour", "22:00"), options.get("night_end_hour", "07:00")
        )

        night_rows = [
            x for x in self._hourly_forecast_cache
            if night_start_dt <= x.get("datetime", night_start_dt - timedelta(days=1)) <= night_end_dt
        ]
        night_hours = max((night_end_dt - night_start_dt).total_seconds() / 3600.0, 0.0)
        night_forecast_base = overnight_forecast_ml(
            options, self.store.data.get("night_model_ml_h"), int(self.store.data.get("night_model_samples", 0)),
            adults=effective_adults, children=effective_children, hours=night_hours,
        ) if options.get("night_forecast_enabled") else 0

        # Intelligent night model: occupancy + learned baseline + current room
        # residuals + real outdoor conditions through windows that are actually
        # open. Weather and trend terms use the same learned room air-exchange
        # model as the configurable short-term forecast.
        weather_effect = 0.0
        trend_effect = 0.0
        if options.get("night_forecast_enabled"):
            minutes_remaining = max(night_hours * 60.0, 0.0)
            trend_minutes = min(minutes_remaining, 60.0)
            # Use the same hourly night weather that the strategy will explain.
            # Current outdoor air is only a fallback when the provider has no
            # usable night forecast. This prevents text and ml values describing
            # different physical nights.
            forecast_night_ah = (
                sum(float(x.get("absolute_humidity", 0)) for x in night_rows) / len(night_rows)
                if night_rows else None
            )
            out_ah = forecast_night_ah
            if out_ah is None and outdoor_t is not None and outdoor_rh is not None:
                out_ah = absolute_humidity(outdoor_t, outdoor_rh)
            for r in valid:
                room_volume = float(r.get("volume_m3", 0) or 0)
                room_share = room_volume / calc_volume_total if calc_volume_total > 0 else 0.0
                room_prior = (daily_generation_prior / 1440.0) * room_share
                observed_source = float(r.get("forecast_source_rate_ml_min", room_prior) or room_prior)
                obs_samples = int(r.get("forecast_confidence", 0) or 0)
                trend_weight = min(max(obs_samples / 80.0, 0.0), 1.0)
                # Current shower/cooking/desorption behaviour only influences the
                # early part of a long night; it is deliberately not projected
                # linearly until morning.
                trend_effect += (observed_source - room_prior) * trend_minutes * trend_weight
                if out_ah is not None and r.get("open"):
                    fraction = exchanged_air_fraction(
                        float(r.get("learned_exchange_rate_per_min", .03)),
                        minutes_remaining,
                        float(r.get("airflow_factor", 1.0)) * (1.25 if cross else 1.0),
                    )
                    weather_effect += (out_ah - float(r.get("absolute_humidity", out_ah))) * room_volume * fraction

        routine_night_projection = 0.0
        routine_night_maturity = 0.0
        routine_night_adjustment = 0.0
        if options.get("night_forecast_enabled") and valid and night_hours > 0:
            routine_night_projection, routine_night_maturity = project_generation_ml(valid, now, night_hours * 60.0)
            if routine_night_maturity >= 15.0:
                # Blend cautiously with the established occupancy/night model.
                # The routine layer may refine timing, but cannot replace the
                # biological prior after only a few observations.
                weight = min(routine_night_maturity / 100.0, 0.55)
                routine_night_adjustment = (routine_night_projection - night_forecast_base) * weight
        # Plausibility guard: immature trend/routine layers may refine but must not
        # swamp the biology/occupancy prior. This also keeps guest influence visible.
        trend_cap = max(float(night_forecast_base) * 0.35, 150.0)
        routine_cap = max(float(night_forecast_base) * 0.45, 200.0)
        trend_effect = min(max(trend_effect, -trend_cap), trend_cap)
        routine_night_adjustment = min(max(routine_night_adjustment, -routine_cap), routine_cap)
        night_forecast = max(0, round(night_forecast_base + weather_effect + trend_effect + routine_night_adjustment))
        night_samples = int(self.store.data.get("night_model_samples", 0))
        raw_night_confidence = (
            28.0 + min(night_samples, 20) * 2.0
            + float(occupancy.get("presence_confidence", 50)) * 0.22
            + min(float(routine_night_maturity), 100.0) * 0.18
            - max(night_hours - 8.0, 0.0) * 1.5
        )
        maturity_cap = 50.0 + min(night_samples, 20) * 1.5 + min(float(routine_night_maturity), 100.0) * 0.20
        night_confidence = int(round(min(max(raw_night_confidence, 20.0), min(maturity_cap, 95.0))))
        night_buffer = min(round(actionable_potential * .40), round(night_forecast * .40)) if night_forecast > 0 else 0

        # v0.18.0.3: explainable night strategy consumes the exact same night
        # window and hourly forecast rows as the ml projection above. Urgent
        # safety/live states retain priority in the unified decision layer.
        avg_indoor_ah = (
            sum(float(r.get("absolute_humidity", 0)) * float(r.get("volume_m3", 0)) for r in valid)
            / max(sum(float(r.get("volume_m3", 0)) for r in valid), 1.0)
        ) if valid else 0.0
        night_weather_available = len(night_rows) >= 2
        night_avg_ah = sum(float(x.get("absolute_humidity", 0)) for x in night_rows) / len(night_rows) if night_rows else None
        night_min_temp = min((float(x.get("temperature_c", 0)) for x in night_rows), default=None)
        night_max_rh = max((float(x.get("humidity", 0)) for x in night_rows), default=None)
        night_rain_prob = max((float(x.get("precipitation_probability", 0)) for x in night_rows), default=0.0)
        night_rain_mm = sum(float(x.get("precipitation_mm", 0)) for x in night_rows)
        rainy_conditions = {"rainy", "pouring", "lightning-rainy", "hail", "snowy-rainy"}

        def _rain_row(row: dict[str, Any]) -> bool:
            return (
                float(row.get("precipitation_probability", 0) or 0) >= 55.0
                or float(row.get("precipitation_mm", 0) or 0) >= 0.2
                or str(row.get("condition", "")) in rainy_conditions
            )

        night_rain_expected = night_rain_prob >= 55.0 or night_rain_mm >= 0.5 or any(_rain_row(x) for x in night_rows)
        first_rain_row = next((x for x in night_rows if _rain_row(x)), None)
        first_rain_dt = first_rain_row.get("datetime") if first_rain_row else None
        minutes_until_rain = (
            max((first_rain_dt - now).total_seconds() / 60.0, 0.0)
            if isinstance(first_rain_dt, datetime) else None
        )
        rain_start_label = first_rain_dt.strftime("%H:%M") if isinstance(first_rain_dt, datetime) else None
        pre_rain_rows = [
            x for x in night_rows
            if isinstance(first_rain_dt, datetime) and x.get("datetime") < first_rain_dt
        ]
        pre_rain_avg_ah = (
            sum(float(x.get("absolute_humidity", 0)) for x in pre_rain_rows) / len(pre_rain_rows)
            if pre_rain_rows else None
        )
        current_outdoor_ah = (
            absolute_humidity(outdoor_t, outdoor_rh)
            if outdoor_t is not None and outdoor_rh is not None else None
        )
        night_ah_delta = (night_avg_ah - avg_indoor_ah) if night_avg_ah is not None else None
        open_rooms = [r.get("name") for r in valid if r.get("open")]

        # v0.18.0.4: select concrete rooms for controlled night ventilation
        # before calculating thermal/moisture impact. The displayed room choice
        # and the simulated choice are therefore identical. Only rooms with a
        # configured ventilation contact can be selected.
        night_avg_temp = (
            sum(float(x.get("temperature_c", 0)) for x in night_rows) / len(night_rows)
            if night_rows else None
        )
        controlled_open_factor = 0.30
        thermal_retention_factor = 0.35
        night_room_candidates: list[dict[str, Any]] = []
        if night_avg_ah is not None and night_avg_temp is not None and night_hours > 0:
            for r in valid:
                if int(r.get("contact_count", 0) or 0) <= 0:
                    continue
                volume = max(float(r.get("volume_m3", 0) or 0), 0.0)
                room_ah = float(r.get("absolute_humidity", night_avg_ah) or night_avg_ah)
                if volume <= 0 or room_ah - night_avg_ah < 0.6:
                    continue
                rate = max(float(r.get("learned_exchange_rate_per_min", .03) or .03), 0.0)
                airflow = max(float(r.get("airflow_factor", 1.0) or 1.0), 0.0) * controlled_open_factor
                fraction = exchanged_air_fraction(rate, night_hours * 60.0, airflow)
                samples = int(r.get("outcome_feedback_samples", 0) or 0)
                outcome_weight = min(samples / 8.0, 1.0)
                temp_factor = 1.0 + (
                    min(max(float(r.get("outcome_temperature_factor", 1.0) or 1.0), 0.60), 1.50) - 1.0
                ) * outcome_weight
                room_temp = float(r.get("temperature", night_avg_temp) or night_avg_temp)
                raw_drop = min((night_avg_temp - room_temp) * fraction, 0.0)
                projected_drop = raw_drop * thermal_retention_factor * temp_factor
                moisture_effect = (night_avg_ah - room_ah) * volume * fraction
                delivered, _purchased, cost = ventilation_cost(
                    volume, room_temp, night_avg_temp,
                    min(fraction * thermal_retention_factor, 1.0), options,
                )
                if night_avg_temp >= room_temp:
                    # Warmer outside air does not create a reheating loss.
                    delivered = 0.0
                    cost = 0.0
                # Rank by useful moisture removal, with a mild thermal penalty.
                score = max(-moisture_effect, 0.0) - abs(projected_drop) * volume * 0.10
                night_room_candidates.append({
                    "room": r, "name": str(r.get("name") or r.get("key") or "Raum"),
                    "volume": volume, "fraction": fraction,
                    "moisture_effect_ml": moisture_effect,
                    "temperature_change_c": projected_drop,
                    "energy_kwh": delivered, "cost": cost, "score": score,
                })

        night_room_candidates.sort(key=lambda x: (float(x.get("score", 0)), -float(x.get("temperature_change_c", 0))), reverse=True)
        selected_night = night_room_candidates[:1]
        if len(night_room_candidates) > 1 and (
            -float(night_room_candidates[1].get("moisture_effect_ml", 0)) >= 50.0
            or -float(night_room_candidates[1].get("moisture_effect_ml", 0)) >= 0.45 * max(-float(night_room_candidates[0].get("moisture_effect_ml", 0)), 1.0)
        ):
            selected_night.append(night_room_candidates[1])

        selected_night_names = [str(x["name"]) for x in selected_night]
        thermal_volume = sum(float(x.get("volume", 0)) for x in selected_night)
        thermal_weighted_drop = sum(float(x.get("temperature_change_c", 0)) * float(x.get("volume", 0)) for x in selected_night)
        night_energy_kwh = sum(float(x.get("energy_kwh", 0)) for x in selected_night)
        night_energy_cost = sum(float(x.get("cost", 0)) for x in selected_night)
        selected_weather_effect = sum(float(x.get("moisture_effect_ml", 0)) for x in selected_night)
        night_temperature_change_c = thermal_weighted_drop / thermal_volume if thermal_volume > 0 else None
        max_night_temp_loss_c = max(float(options.get("max_temp_loss_next_5_min_c", 0.6) or 0.6) * 2.5, 1.0)
        thermal_ok = (
            bool(selected_night)
            and night_temperature_change_c is not None
            and night_temperature_change_c >= -max_night_temp_loss_c
        )

        # Separate the passive closed-window night from the current state and
        # from the selected strategy. This prevents one number being presented
        # as if it represented all three scenarios.
        night_forecast_closed = round(
            night_forecast_base + trend_effect + routine_night_adjustment
        )
        night_forecast_with_selected = round(night_forecast_closed + selected_weather_effect) if selected_night else None

        prebed_minutes = min(max(round(recommended), 10), 30)
        pre_vent_source_ah = pre_rain_avg_ah
        if current_outdoor_ah is not None and not in_night_window(now, options.get("night_start_hour"), options.get("night_end_hour")):
            pre_vent_source_ah = current_outdoor_ah
        pre_vent_effect = 0.0
        if selected_night and pre_vent_source_ah is not None:
            for item in selected_night:
                r = item["room"]
                room_ah = float(r.get("absolute_humidity", pre_vent_source_ah) or pre_vent_source_ah)
                if room_ah <= pre_vent_source_ah:
                    continue
                rate = max(float(r.get("learned_exchange_rate_per_min", .03) or .03), 0.0)
                airflow = max(float(r.get("airflow_factor", 1.0) or 1.0), 0.0)
                fraction = exchanged_air_fraction(rate, prebed_minutes, airflow)
                pre_vent_effect += (pre_vent_source_ah - room_ah) * float(item.get("volume", 0)) * fraction
        night_forecast_after_prevent = round(night_forecast_closed + pre_vent_effect) if pre_vent_effect < -1.0 else None

        night_strategy = {
            "active": night_strategy_relevant,
            "weather_available": night_weather_available,
            "action": "monitor",
            "label": "NACHTSTRATEGIE",
            "headline": "FreshAirIQ beobachtet die Nachtentwicklung",
            "instruction": "Fensterzustand vor der Nacht erneut bewerten",
            "summary": "Die Wetter- und Feuchteprognose reicht noch nicht für eine belastbare Fensterstrategie.",
            "reasons": [],
            "confidence": min(night_confidence, 65 if not night_weather_available else 95),
            "rain_expected": night_rain_expected,
            "rain_probability": round(night_rain_prob),
            "rain_mm": round(night_rain_mm, 1),
            "rain_start": first_rain_dt.isoformat() if isinstance(first_rain_dt, datetime) else None,
            "rain_start_label": rain_start_label,
            "minutes_until_rain": round(minutes_until_rain) if minutes_until_rain is not None else None,
            "outside_ah_g_m3": round(night_avg_ah, 2) if night_avg_ah is not None else None,
            "inside_ah_g_m3": round(avg_indoor_ah, 2),
            "outside_minus_inside_ah_g_m3": round(night_ah_delta, 2) if night_ah_delta is not None else None,
            "min_temperature_c": round(night_min_temp, 1) if night_min_temp is not None else None,
            "average_temperature_c": round(night_avg_temp, 1) if night_avg_temp is not None else None,
            "projected_room_temperature_change_c": round(night_temperature_change_c, 1) if night_temperature_change_c is not None else None,
            "max_acceptable_room_temperature_loss_c": round(max_night_temp_loss_c, 1),
            "projected_reheat_energy_kwh": round(night_energy_kwh, 2),
            "projected_reheat_cost": round(night_energy_cost, 2),
            "max_humidity": round(night_max_rh) if night_max_rh is not None else None,
            "open_rooms": [str(x) for x in open_rooms if x],
            "selected_rooms": selected_night_names,
            "forecast_ml": night_forecast,
            "forecast_current_state_ml": night_forecast,
            "forecast_closed_windows_ml": night_forecast_closed,
            "forecast_without_action_ml": night_forecast_closed,
            "forecast_with_strategy_ml": None,
            "strategy_moisture_effect_ml": None,
            "hours": round(night_hours, 1),
        }
        if night_strategy_relevant and night_weather_available and night_ah_delta is not None:
            if night_rain_expected and night_ah_delta > -0.6:
                night_strategy.update({
                    "action": "close",
                    "label": "NACHT · FENSTER SCHLIESSEN",
                    "headline": "Heute Nacht Fenster geschlossen halten",
                    "instruction": "Alle geöffneten Fenster vor der Nacht schließen" if open_rooms else "Fenster über Nacht geschlossen lassen",
                    "summary": "Die Nachtprognose erwartet Niederschlag und keine ausreichend trockenere Außenluft. Offene Fenster würden den Feuchteschutz daher nicht sinnvoll unterstützen.",
                    "forecast_without_action_ml": night_forecast if open_rooms else night_forecast_closed,
                    "forecast_with_strategy_ml": night_forecast_closed,
                    "strategy_moisture_effect_ml": night_forecast_closed - (night_forecast if open_rooms else night_forecast_closed),
                    "reasons": [
                        (f"Regenphase beginnt voraussichtlich gegen {rain_start_label} Uhr" if rain_start_label else (f"Niederschlagsrisiko bis {round(night_rain_prob)} %" if night_rain_prob else "Niederschlag wird in der Nacht erwartet")),
                        f"Nachtluft liegt im Mittel bei {night_avg_ah:.1f} g/m³ absoluter Feuchte",
                        f"Mit geschlossenen Fenstern werden bis zum Nachtende etwa {night_forecast_closed:+.0f} ml erwartet",
                    ],
                })
            elif night_ah_delta <= -0.6 and night_rain_expected:
                # A rain forecast only justifies pre-ventilation when there is
                # a real dry window left before precipitation starts. Otherwise
                # closing is the only actionable, safe statement.
                dry_before_rain = pre_vent_source_ah is not None and pre_vent_source_ah <= avg_indoor_ah - 0.6
                enough_time = minutes_until_rain is not None and minutes_until_rain >= prebed_minutes + 5
                if selected_night and dry_before_rain and enough_time:
                    room_text = " + ".join(selected_night_names)
                    deadline = f" bis spätestens {rain_start_label} Uhr" if rain_start_label else " vor der Regenphase"
                    night_strategy.update({
                        "action": "pre_ventilate",
                        "label": "NACHT · VORHER LÜFTEN",
                        "headline": "Trockene Luft vor dem Regen gezielt nutzen",
                        "instruction": f"{room_text}{deadline} etwa {prebed_minutes} Minuten stoßlüften und danach schließen",
                        "summary": "Vor Beginn des Niederschlags bleibt ein ausreichend trockenes Lüftungsfenster. Danach empfiehlt FreshAirIQ wegen des Regens keine unbeaufsichtigte Daueröffnung.",
                        "forecast_without_action_ml": night_forecast_closed,
                        "forecast_with_strategy_ml": night_forecast_after_prevent,
                        "strategy_moisture_effect_ml": round(pre_vent_effect),
                        "reasons": [
                            f"Vor der Regenphase ist die Außenluft etwa {abs((pre_vent_source_ah or avg_indoor_ah) - avg_indoor_ah):.1f} g/m³ trockener als die Raumluft",
                            f"Regenphase beginnt voraussichtlich gegen {rain_start_label} Uhr" if rain_start_label else f"Niederschlagsrisiko bis {round(night_rain_prob)} %",
                            f"Für das Stoßlüften sind noch etwa {round(minutes_until_rain)} Minuten Zeit" if minutes_until_rain is not None else "Zeitfenster vor dem Regen ist ausreichend",
                        ],
                    })
                else:
                    night_strategy.update({
                        "action": "close",
                        "label": "NACHT · FENSTER SCHLIESSEN",
                        "headline": "Regenfenster ist für Vorlüften zu knapp",
                        "instruction": "Fenster über Nacht geschlossen lassen",
                        "summary": "Die Nachtluft wäre zeitweise trocken genug, vor dem prognostizierten Regen bleibt aber kein ausreichend belastbares Lüftungsfenster für eine sichere Vorlüftung.",
                        "forecast_without_action_ml": night_forecast if open_rooms else night_forecast_closed,
                        "forecast_with_strategy_ml": night_forecast_closed,
                        "strategy_moisture_effect_ml": night_forecast_closed - (night_forecast if open_rooms else night_forecast_closed),
                        "reasons": [
                            f"Regenphase beginnt voraussichtlich gegen {rain_start_label} Uhr" if rain_start_label else f"Niederschlagsrisiko bis {round(night_rain_prob)} %",
                            f"Benötigtes Stoßlüftungsfenster etwa {prebed_minutes} Minuten plus Sicherheitsreserve",
                            "FreshAirIQ empfiehlt keine Nachtöffnung ohne ausreichendes trockenes Zeitfenster",
                        ],
                    })
            elif night_ah_delta <= -0.6 and thermal_ok and selected_night:
                room_text = " + ".join(selected_night_names)
                night_strategy.update({
                    "action": "open_selected",
                    "label": "NACHT · KONTROLLIERT LÜFTEN",
                    "headline": "Die Nacht eignet sich für kontrollierte Nachtlüftung",
                    "instruction": f"{room_text} über Nacht nur teilweise geöffnet lassen",
                    "summary": "Die prognostizierte Nachtluft bleibt deutlich trockener und das thermische Modell erwartet für genau diese ausgewählten Räume nur eine begrenzte Abkühlung.",
                    "forecast_without_action_ml": night_forecast_closed,
                    "forecast_with_strategy_ml": night_forecast_with_selected,
                    "strategy_moisture_effect_ml": round(selected_weather_effect),
                    "reasons": [
                        f"Nachtluft ist im Mittel etwa {abs(night_ah_delta):.1f} g/m³ trockener als die Raumluft",
                        f"Ausgewählt: {room_text}; erwartete mittlere Abkühlung etwa {abs(night_temperature_change_c or 0):.1f} °C (Grenze {max_night_temp_loss_c:.1f} °C)",
                        f"Geschätzter Wiederaufheizbedarf etwa {night_energy_kwh:.2f} kWh / {night_energy_cost:.2f} €",
                        f"Fenster zu: {night_forecast_closed:+.0f} ml · mit Strategie: {float(night_forecast_with_selected or 0):+.0f} ml",
                    ],
                })
            elif night_ah_delta <= -0.6 and selected_night and not thermal_ok:
                room_text = " + ".join(selected_night_names)
                night_strategy.update({
                    "action": "pre_ventilate",
                    "label": "NACHT · VORHER LÜFTEN",
                    "headline": "Trockene Nachtluft nutzen, aber nicht dauerhaft",
                    "instruction": f"Vor dem Schlafengehen {room_text} etwa {prebed_minutes} Minuten stoßlüften und danach schließen",
                    "summary": "Die Nachtluft wäre für den Feuchteabbau geeignet, eine dauerhafte Öffnung würde die ausgewählten Räume laut thermischem Modell jedoch zu stark abkühlen.",
                    "forecast_without_action_ml": night_forecast_closed,
                    "forecast_with_strategy_ml": night_forecast_after_prevent,
                    "strategy_moisture_effect_ml": round(pre_vent_effect) if pre_vent_effect < -1 else None,
                    "reasons": [
                        f"Nachtluft ist im Mittel etwa {abs(night_ah_delta):.1f} g/m³ trockener als die Raumluft",
                        f"Dauerlüftung in {room_text} würde dort im Mittel etwa {abs(night_temperature_change_c or 0):.1f} °C Abkühlung verursachen",
                        f"FreshAirIQ akzeptiert höchstens etwa {max_night_temp_loss_c:.1f} °C prognostizierten Verlust",
                        f"Tiefste Außentemperatur etwa {night_min_temp:.1f} °C" if night_min_temp is not None else "Die Temperaturprognose wird weiter bewertet",
                    ],
                })
            elif night_ah_delta <= -0.6 and not selected_night:
                night_strategy.update({
                    "action": "closed_monitor",
                    "label": "NACHT · BEOBACHTEN",
                    "headline": "Trockene Nachtluft erkannt, aber kein Fenster sicher auswählbar",
                    "instruction": "Fenster zunächst geschlossen lassen",
                    "summary": "Die Außenluft wäre günstig, FreshAirIQ hat jedoch keinen berechenbaren Raum mit konfiguriertem Lüftungskontakt gefunden. Deshalb wird keine pauschale Nachtöffnung empfohlen.",
                    "reasons": [
                        f"Nachtluft ist im Mittel etwa {abs(night_ah_delta):.1f} g/m³ trockener als die Raumluft",
                        "Für kontrollierte Nachtlüftung muss mindestens ein geeigneter Raum mit Fenster-/Türkontakt eindeutig auswählbar sein",
                    ],
                })
            elif night_ah_delta >= 0.4:
                night_strategy.update({
                    "action": "close",
                    "label": "NACHT · FENSTER SCHLIESSEN",
                    "headline": "Feuchte Nachtluft besser draußen lassen",
                    "instruction": "Fenster über Nacht geschlossen lassen",
                    "summary": "Die prognostizierte Außenluft ist feuchter als die aktuelle Raumluft. Dauerhaft offene Fenster würden voraussichtlich zusätzliche Feuchtigkeit eintragen.",
                    "forecast_without_action_ml": night_forecast if open_rooms else night_forecast_closed,
                    "forecast_with_strategy_ml": night_forecast_closed,
                    "strategy_moisture_effect_ml": night_forecast_closed - (night_forecast if open_rooms else night_forecast_closed),
                    "reasons": [
                        f"Nachtluft ist im Mittel etwa {night_ah_delta:.1f} g/m³ feuchter als die Raumluft",
                        f"Maximale prognostizierte relative Außenfeuchte etwa {round(night_max_rh or 0)} %",
                        f"Mit geschlossenen Fenstern werden bis zum Nachtende etwa {night_forecast_closed:+.0f} ml erwartet",
                    ],
                })
            else:
                night_strategy.update({
                    "action": "closed_monitor",
                    "label": "NACHT · BEOBACHTEN",
                    "headline": "Für die Nacht ist kein Dauerlüften nötig",
                    "instruction": "Fenster zunächst geschlossen lassen",
                    "summary": "Außenfeuchte und Temperatur ergeben aktuell keinen klaren Vorteil für dauerhaft geöffnete Fenster. FreshAirIQ bewertet die Nacht weiter neu.",
                    "forecast_without_action_ml": night_forecast_closed,
                    "forecast_with_strategy_ml": night_forecast_closed,
                    "strategy_moisture_effect_ml": 0,
                    "reasons": [
                        f"Differenz Außen-/Innenfeuchte nachts nur {night_ah_delta:+.1f} g/m³",
                        f"Tiefste prognostizierte Außentemperatur etwa {night_min_temp:.1f} °C" if night_min_temp is not None else "Temperaturprognose wird weiter beobachtet",
                    ],
                })

        if night_strategy.get("action") == "close":
            night_recommendation = str(night_strategy.get("instruction"))
        elif night_strategy.get("action") in {"open_selected", "pre_ventilate"}:
            night_recommendation = str(night_strategy.get("instruction"))
        elif night_buffer >= 100:
            night_recommendation = f"Vorlüften kann etwa {night_buffer} ml Puffer schaffen."
        elif night_forecast >= 150:
            night_recommendation = "Nachtfeuchte wird erhöht erwartet; FreshAirIQ beobachtet die Entwicklung weiter."
        else:
            night_recommendation = "Vorlüften ist aktuell nicht zwingend nötig."

        room_meta_for_house = {
            str(k): {"floor": r.get("floor"), "name": r.get("name", k)}
            for k, r in results.items()
        }
        # Learn the house strategy exactly once per completed house ventilation,
        # using every room session in that batch. Learning each room-close cycle
        # separately would fragment staggered multi-room ventilation into several
        # false "house" outcomes.
        if completed_house_sessions:
            completed_cross = any(bool(event.get("cross_ventilation")) for event in completed_house_sessions)
            if learn_house_outcome(
                self.store.data, completed_house_sessions, room_meta_for_house,
                cross=completed_cross, expected_occupants=float(occupancy.get("expected_total", 0.0)), observed_at=now,
            ):
                changed = True

        # Recommendation Engine v2: collapse all room diagnostics into one
        # prioritised house action. Room diagnostics remain available in the
        # room view, but the main dashboard no longer presents competing calls
        # to action.
        intelligent_recommendation = build_recommendation(
            results,
            options,
            threshold_ml=ventilation_threshold,
            total_potential_ml=realistic_actionable_potential,
            recommended_duration_min=recommended,
            pollen_index=pollen,
            pollen_blocked=pollen_blocked,
            night_forecast_ml=night_forecast,
        )
        intelligent_recommendation = refine_with_anticipation(
            intelligent_recommendation, results, options, now
        )
        intelligent_recommendation = build_decision_simulation(
            results, options, intelligent_recommendation,
            night_forecast_ml=night_forecast, night_confidence=night_confidence,
            future_outdoor=future_outdoor, now=now,
        )
        intelligent_recommendation = refine_live_recommendation(
            results, options, intelligent_recommendation
        )
        day_night_plan = build_multi_hour_plan(
            results, options, now,
            future_outdoor=planning_outdoor,
            night_forecast_ml=night_forecast,
            night_confidence=night_confidence,
            horizon_hours=8.0,
        )
        intelligent_recommendation = refine_with_plan(
            intelligent_recommendation, day_night_plan
        )
        house_fit = house_strategy_fit(
            self.store.data,
            [str(x) for x in (intelligent_recommendation.get("room_keys") or [])],
            room_meta_for_house,
            cross=cross,
            expected_occupants=float(occupancy.get("expected_total", 0.0)),
        )
        intelligent_recommendation["house_strategy"] = house_fit
        if float(house_fit.get("maturity", 0.0) or 0.0) >= 20.0:
            reasons = list(intelligent_recommendation.get("reasons") or [])
            if float(house_fit.get("efficiency_factor", 1.0) or 1.0) >= 1.10:
                reasons.append("Hauslernen: diese Raum-/Etagenstrategie war bisher überdurchschnittlich effizient")
            elif float(house_fit.get("efficiency_factor", 1.0) or 1.0) <= 0.90:
                reasons.append("Hauslernen: diese Raum-/Etagenstrategie war bisher eher unterdurchschnittlich effizient")
            intelligent_recommendation["reasons"] = reasons[:6]

        # Hotfix 0.17.0.8: first make the technical recommendation final, then
        # render the user-facing Decision Brain from that canonical result.
        # No later layer may change kind/rooms/duration after Decision Brain.
        intelligent_recommendation = stabilise_recommendation(
            intelligent_recommendation, results, options
        )
        intelligent_recommendation = build_unified_decision(
            intelligent_recommendation, results, options, cross_active=cross,
            night_strategy=night_strategy,
        )
        # Adaptive presentation mode: when most of the monitored house is being
        # aired, communicate one house action instead of noisy per-room closing.
        monitored_count = max(len(valid), 1)
        active_ratio = len(active) / monitored_count
        previous_house_mode = bool(self.store.data.get("house_ventilation_mode", False))
        enter_ratio = float(options.get("house_ventilation_enter_ratio", 0.75))
        exit_ratio = float(options.get("house_ventilation_exit_ratio", 0.50))
        house_ventilation_mode = active_ratio >= (exit_ratio if previous_house_mode else enter_ratio)
        if house_ventilation_mode != previous_house_mode:
            self.store.data["house_ventilation_mode"] = house_ventilation_mode
            changed = True
        active_by_floor: dict[str, list[dict[str, Any]]] = {}
        valid_by_floor: dict[str, list[dict[str, Any]]] = {}
        for _r in valid:
            valid_by_floor.setdefault(str(_r.get("floor") or "Unzugeordnet"), []).append(_r)
        for _r in active:
            active_by_floor.setdefault(str(_r.get("floor") or "Unzugeordnet"), []).append(_r)
        floor_name, floor_active = max(active_by_floor.items(), key=lambda item: len(item[1]), default=("", []))
        floor_display_name = {"ground_floor": "Erdgeschoss", "upper_floor": "Obergeschoss", "basement": "Kellergeschoss", "base_floor": "Kellergeschoss", "attic": "Dachgeschoss", "other": "Sonstiger Bereich"}.get(str(floor_name), str(floor_name or "Stockwerk"))
        floor_total = len(valid_by_floor.get(floor_name, [])) if floor_name else 0
        floor_active_ratio = (len(floor_active) / floor_total) if floor_total else 0.0
        # A changed real-world ventilation pattern must win over the previous
        # single-room recommendation. Two openings already count as floor mode
        # when they cover at least half of that floor; three active rooms always
        # establish a deliberate floor ventilation even on larger floors.
        floor_ventilation_mode = bool(
            not house_ventilation_mode and floor_total > 0
            and len(floor_active) >= 2
            and (len(floor_active) >= 3 or floor_active_ratio >= 0.5)
        )

        if house_ventilation_mode and active:
            intelligent_recommendation["presentation_scope"] = "house"
            intelligent_recommendation["presentation_active_rooms"] = len(active)
            intelligent_recommendation["presentation_total_rooms"] = len(valid)

            # Hotfix 0.20.2.5: house ventilation is a real aggregate decision,
            # not a presentation wrapper around room-by-room close commands.
            # The next 5-minute benefit and thermal cost are aggregated across
            # every actively ventilated room. Individual close requests are
            # suppressed until the common house endpoint is reached.
            # Signed NET five-minute effect. Positive means the house loses
            # moisture, negative means it gains moisture. Previously negative
            # rooms were discarded here, while the card displayed their signed
            # contribution; that produced contradictions such as −9 ml in the
            # tile but "14 ml Entfeuchtung" in the explanation.
            house_next5_removed = sum(float(r.get("forecast_5_min_net_moisture_change_ml", r.get("forecast_5_min_moisture_effect_ml", 0.0)) or 0.0) for r in active)
            house_next5_temp_loss = sum(
                max(-float(r.get("forecast_5_min_temperature_change_c", 0.0)), 0.0) * float(r.get("volume_m3", 0.0))
                for r in active
            ) / max(sum(float(r.get("volume_m3", 0.0)) for r in active), 1.0)
            house_min_return = float(options.get("min_return_next_5_min_ml", 25.0)) * max(len(active) ** 0.5, 1.0)
            house_efficiency = 999.0 if house_next5_temp_loss <= 0.05 else house_next5_removed / (house_next5_temp_loss * 10.0)
            house_thermal_bad = (
                str(options.get("operating_profile", "comfort")) != "summer_cooling"
                and house_next5_temp_loss >= float(options.get("max_temp_loss_next_5_min_c", 0.6))
                and house_efficiency < float(options.get("min_efficiency_ml_per_01c", 8.0))
            )
            house_low_return = house_next5_removed < house_min_return
            house_close_gate_ready = aggregate_close_gate_ready(active)
            house_should_close = aggregate_close_allowed(
                active, low_return=house_low_return, thermal_bad=house_thermal_bad
            )
            active_room_keys = [str(r.get("key")) for r in active]

            intelligent_recommendation["house_next_5_min_moisture_effect_ml"] = round(house_next5_removed)
            intelligent_recommendation["house_next_5_min_temperature_loss_c"] = round(house_next5_temp_loss, 2)
            intelligent_recommendation["house_decision_threshold_ml"] = round(house_min_return)
            intelligent_recommendation["room_keys"] = active_room_keys
            if house_should_close:
                intelligent_recommendation["kind"] = "close"
                intelligent_recommendation["status"] = "close_windows"
                intelligent_recommendation["title"] = "Der sinnvolle Lüftungspunkt ist erreicht"
                intelligent_recommendation["instruction"] = "Hauslüftung beenden"
                intelligent_recommendation["summary"] = "Der zusätzliche Gesamtnutzen der Hauslüftung ist gegenüber Feuchteziel und Temperaturverlust nicht mehr ausreichend."
                intelligent_recommendation["reasons"] = [
                    f"Hausweiter Nettoeffekt der nächsten 5 Minuten: {round(house_next5_removed)} ml Feuchteabbau" if house_next5_removed >= 0 else f"Hausweiter Nettoeffekt der nächsten 5 Minuten: {abs(round(house_next5_removed))} ml Feuchtezunahme",
                    f"Gemeinsamer Schwellwert für diese Hauslüftung: etwa {round(house_min_return)} ml in 5 Minuten",
                    f"Mittlere prognostizierte Abkühlung der aktiven Räume: {house_next5_temp_loss:.1f} °C",
                ]
            else:
                intelligent_recommendation["kind"] = "continue"
                intelligent_recommendation["status"] = "ventilation_running"
                intelligent_recommendation["title"] = "Hauslüftung läuft"
                intelligent_recommendation["instruction"] = "Hausweit weiterlüften"
                if house_close_gate_ready:
                    intelligent_recommendation["summary"] = "Die Hauslüftung bringt insgesamt noch ausreichend Nutzen. FreshAirIQ bewertet die aktiven Räume gemeinsam und gibt währenddessen keine einzelnen Schließhinweise aus."
                    gate_reason = None
                else:
                    intelligent_recommendation["summary"] = "Die Schließentscheidung bleibt gesperrt, bis alle aktiven Räume zwei neue Feuchtemeldungen geliefert haben oder die 15-Minuten-Modellfreigabe greift."
                    ready_count = sum(bool(r.get("close_decision_ready", False)) for r in active)
                    gate_reason = f"Schließfreigabe noch nicht vollständig: {ready_count}/{len(active)} aktive Räume freigegeben"
                    if intelligent_recommendation.get("duration_min") in (0, 0.0):
                        intelligent_recommendation["duration_min"] = None
                intelligent_recommendation["reasons"] = [
                    *([gate_reason] if gate_reason else []),
                    f"Hausweiter Nettoeffekt der nächsten 5 Minuten: {round(house_next5_removed)} ml Feuchteabbau" if house_next5_removed >= 0 else f"Hausweiter Nettoeffekt der nächsten 5 Minuten: {abs(round(house_next5_removed))} ml Feuchtezunahme",
                    f"Gemeinsamer Schwellwert für diese Hauslüftung: etwa {round(house_min_return)} ml in 5 Minuten",
                    f"Mittlere prognostizierte Abkühlung der aktiven Räume: {house_next5_temp_loss:.1f} °C",
                ]

            # The frontend deliberately prefers decision_brain over the raw
            # recommendation fields. Replace the previously room-specific brain
            # with the aggregate house decision, otherwise stale room chips and
            # room wording would remain visible despite the correct house logic.
            intelligent_recommendation["decision_brain"] = {
                "version": "v1-house",
                "decision_label": "HAUSLÜFTUNG",
                "headline": intelligent_recommendation["title"],
                "action_line": intelligent_recommendation["instruction"],
                "summary": intelligent_recommendation["summary"],
                "why": list(intelligent_recommendation.get("reasons") or []),
                "impact": {
                    "moisture_ml": round(house_next5_removed),
                    "temperature_c": round(-house_next5_temp_loss, 2),
                    "cost": round(float(forecast_cost), 2),
                    "duration_min": intelligent_recommendation.get("duration_min"),
                    "confidence": round(float(forecast_confidence)),
                },
                "comparison": {},
                "alternative": None,
                "selected_rooms": [],
                "short_term_options": 0,
                "long_term_options": 0,
                "cross_ventilation": bool(cross),
                "night_strategy": night_strategy if isinstance(night_strategy, dict) else {},
                "night_strategy_primary": False,
            }
        elif floor_ventilation_mode:
            floor_next5_removed = sum(float(r.get("forecast_5_min_net_moisture_change_ml", r.get("forecast_5_min_moisture_effect_ml", 0.0)) or 0.0) for r in floor_active)
            floor_temp_loss = sum(max(-float(r.get("forecast_5_min_temperature_change_c", 0.0)), 0.0) * float(r.get("volume_m3", 0.0)) for r in floor_active) / max(sum(float(r.get("volume_m3", 0.0)) for r in floor_active), 1.0)
            floor_threshold = float(options.get("min_return_next_5_min_ml", 25.0)) * max(len(floor_active) ** 0.5, 1.0)
            floor_efficiency = 999.0 if floor_temp_loss <= 0.05 else floor_next5_removed / (floor_temp_loss * 10.0)
            floor_thermal_bad = (str(options.get("operating_profile", "comfort")) != "summer_cooling" and floor_temp_loss >= float(options.get("max_temp_loss_next_5_min_c", 0.6)) and floor_efficiency < float(options.get("min_efficiency_ml_per_01c", 8.0)))
            floor_low_return = floor_next5_removed < floor_threshold
            floor_close_gate_ready = aggregate_close_gate_ready(floor_active)
            floor_should_close = aggregate_close_allowed(
                floor_active, low_return=floor_low_return, thermal_bad=floor_thermal_bad
            )
            intelligent_recommendation["presentation_scope"] = "floor"
            intelligent_recommendation["presentation_floor"] = floor_display_name
            intelligent_recommendation["room_keys"] = [str(r.get("key")) for r in floor_active]
            intelligent_recommendation["floor_next_5_min_moisture_effect_ml"] = round(floor_next5_removed)
            if floor_should_close:
                intelligent_recommendation.update({
                    "kind": "close", "status": "close_windows",
                    "title": "Etagenlüftung hat ihr sinnvolles Ziel erreicht",
                    "instruction": f"{floor_display_name} schließen",
                    "summary": "FreshAirIQ hat die Situation nach den zusätzlich geöffneten Fenstern neu bewertet. Die Räume werden jetzt als gemeinsame Etagenlüftung beurteilt; der zusätzliche Gesamtnutzen ist nicht mehr ausreichend.",
                    "reasons": [f"{len(floor_active)} aktive Lüftungsräume auf dieser Etage werden gemeinsam bewertet", f"Nettoeffekt der nächsten 5 Minuten: {round(floor_next5_removed)} ml", f"Gemeinsamer Schwellwert: etwa {round(floor_threshold)} ml in 5 Minuten"],
                })
            else:
                floor_ready_count = sum(bool(r.get("close_decision_ready", False)) for r in floor_active)
                floor_gate_reason = None if floor_close_gate_ready else f"Schließfreigabe noch nicht vollständig: {floor_ready_count}/{len(floor_active)} aktive Räume freigegeben"
                intelligent_recommendation.update({
                    "kind": "continue", "status": "ventilation_running",
                    "title": "Situation neu eingeschätzt: Etagenlüftung läuft",
                    "instruction": f"{floor_display_name} gemeinsam weiterlüften",
                    "summary": "Durch die zusätzlich geöffneten Fenster hat sich die Lüftungssituation geändert. FreshAirIQ bewertet jetzt die Wirkung der gesamten Etage statt an der früheren Einzelraum-Empfehlung festzuhalten." if floor_close_gate_ready else "Die Schließentscheidung bleibt gesperrt, bis alle aktiven Räume dieser Etage zwei neue Feuchtemeldungen geliefert haben oder die 15-Minuten-Modellfreigabe greift.",
                    "reasons": [*([floor_gate_reason] if floor_gate_reason else []), f"{len(floor_active)} aktive Lüftungsräume auf derselben Etage erkannt", f"Gemeinsamer Nettoeffekt der nächsten 5 Minuten: {round(floor_next5_removed)} ml", f"Gemeinsamer Schwellwert: etwa {round(floor_threshold)} ml in 5 Minuten"],
                })
                if not floor_close_gate_ready and intelligent_recommendation.get("duration_min") in (0, 0.0):
                    intelligent_recommendation["duration_min"] = None
            intelligent_recommendation["decision_brain"] = {
                "version": "v1-floor", "decision_label": "ETAGENLÜFTUNG",
                "headline": intelligent_recommendation["title"], "action_line": intelligent_recommendation["instruction"],
                "summary": intelligent_recommendation["summary"], "why": list(intelligent_recommendation.get("reasons") or []),
                "impact": {"moisture_ml": round(floor_next5_removed), "temperature_c": round(-floor_temp_loss, 2), "cost": round(float(forecast_cost), 2), "duration_min": intelligent_recommendation.get("duration_min"), "confidence": round(float(forecast_confidence))},
                "comparison": {}, "alternative": None, "selected_rooms": [], "short_term_options": 0, "long_term_options": 0, "cross_ventilation": bool(cross), "night_strategy": night_strategy if isinstance(night_strategy, dict) else {}, "night_strategy_primary": False,
            }
        else:
            intelligent_recommendation["presentation_scope"] = "rooms"

        # Personal Context Engine v1 is the final presentation layer. Running it
        # here also covers the aggregate house-ventilation presentation above.
        # It is presentation-only and cannot alter the canonical physical action.
        resident_context = build_resident_context(
            options, self.hass.states,
            expected_occupants=float(occupancy.get("expected_total", 0.0)),
        )
        intelligent_recommendation = personalise_recommendation(
            intelligent_recommendation, results, options, now=now,
            expected_occupants=float(occupancy.get("expected_total", 0.0)),
            resident_context=resident_context,
        )
        # Language Confidence Layer v1 changes only how the final decision is
        # expressed. Model maturity and current-situation confidence are kept
        # separate so a mature room can still be described cautiously when the
        # present measurement/weather situation is uncertain.
        intelligent_recommendation = adapt_language_confidence(
            intelligent_recommendation, results, self.store.data
        )
        # Opening Strategy v1: the existing engines decide WHETHER and WHERE to
        # ventilate. Only after that decision is final do we choose WHICH
        # configured opening(s) best match the current source air. This keeps
        # every canonical physics/forecast/learning value unchanged.
        intelligent_recommendation = enrich_opening_recommendation(
            intelligent_recommendation, results, options
        )

        # Decision Intelligence & Validation v1: attach an observational trace
        # only after every layer has finished. It cannot alter the canonical
        # action and therefore cannot destabilise the proven ventilation logic.
        _decision_validation = validation_summary(
            self.store.data.get("forecast_validation_history") or [], days=30
        )
        intelligent_recommendation["decision_trace"] = build_decision_trace(
            intelligent_recommendation, results, validation=_decision_validation
        )
        intelligent_recommendation["recommendation_quality"] = build_recommendation_quality(
            _decision_validation
        )

        if sync_active_recommendation(self.store.data, intelligent_recommendation, now):
            changed = True
        iq_state = build_intelligence_state(
            results, intelligent_recommendation,
            forecast_confidence=forecast_confidence, overnight_confidence=night_confidence,
            presence_confidence=float(occupancy.get("presence_confidence", 50)), night_samples=night_samples, now=now,
        )
        status = str(intelligent_recommendation.get("status") or status)
        status_text = f"{intelligent_recommendation.get('title', '')} · {intelligent_recommendation.get('instruction', '')}".strip(" ·")
        displayed_recommended = recommended
        if str(intelligent_recommendation.get("kind") or "") == "ventilate" and intelligent_recommendation.get("duration_min") is not None:
            displayed_recommended = float(intelligent_recommendation["duration_min"])
        elif active and intelligent_recommendation.get("live_coach_target_min") is not None:
            displayed_recommended = float(intelligent_recommendation["live_coach_target_min"])
            remaining = float(intelligent_recommendation.get("live_coach_remaining_min", remaining))
        if str(intelligent_recommendation.get("kind") or "") == "close":
            # A close action is immediate, but the dashboard's IQ-ZEIT tile should
            # still show how far the real session has already passed its target.
            # Negative remaining time is rendered as "+X min über Ziel".
            remaining = min(0.0, round(float(displayed_recommended) - max_elapsed, 1))

        # Routine bucket tables are an internal model. Keep only compact
        # Hotfix 0.20.2.6: when house mode is active, the short-term tile and
        # the explanation consume the exact same signed aggregate value.
        if house_ventilation_mode and active:
            _house_short = intelligent_recommendation.get("house_next_5_min_moisture_effect_ml")
            if _house_short is not None:
                next5_effect = float(_house_short)
                if forecast_horizon == 5:
                    forecast_effect = float(_house_short)

        # summaries in coordinator data so the dashboard payload stays small.
        for _room in results.values():
            _room.pop("routine_source_buckets", None)

        history = self.store.history_days(stats_days)
        history_summary = {"removed_ml": round(sum(float(x.get("removed_ml", 0)) for x in history)), "sessions": sum(int(x.get("sessions", 0)) for x in history), "moisture_measured_sessions": sum(int(x.get("moisture_measured_sessions", 0)) for x in history), "moisture_unmeasured_sessions": sum(int(x.get("moisture_unmeasured_sessions", 0)) for x in history), "ventilation_minutes": round(sum(float(x.get("ventilation_minutes", 0)) for x in history), 1), "energy_kwh": round(sum(float(x.get("energy_kwh", 0)) for x in history), 3), "cost": round(sum(float(x.get("cost", 0)) for x in history), 2)}
        today_row = history[-1] if history else {}; elapsed_day_fraction = (now.hour * 60 + now.minute) / 1440.0
        expected_generated_so_far = round(current_daily_generation * elapsed_day_fraction); moisture_balance_today = round(expected_generated_so_far - float(today_row.get("removed_ml", 0)))
        adults = int(options.get("adult_occupants", 0)); children = int(options.get("child_occupants", 0))

        stale_rooms = [r for r in results.values() if r.get("calculation_enabled", True) and r.get("data_quality") != "ok"]
        co2_rooms = sum(1 for r in valid if r.get("co2_available"))
        frame_quality_counts = {
            quality: sum(1 for r in results.values() if r.get("calculation_enabled", True) and r.get("measurement_frame_quality") == quality)
            for quality in ("excellent", "acceptable", "uncertain", "stale")
        }
        system_check = {
            "configured_rooms": len([r for r in results.values() if r.get("calculation_enabled", True)]),
            "valid_rooms": len(valid),
            "stale_or_invalid_rooms": len(stale_rooms),
            "weather_available": bool(outdoor_t is not None and outdoor_rh is not None),
            "future_weather_available": bool(future_outdoor),
            "co2_rooms": co2_rooms,
            "co2_optional": True,
            "measurement_frame_quality_counts": frame_quality_counts,
            "measurement_frame_learning_eligible_rooms": sum(1 for r in results.values() if r.get("calculation_enabled", True) and r.get("measurement_frame_learning_eligible")),
            "night_model_samples": night_samples,
            "night_model_maturity_percent": min(100, round(night_samples / 20 * 100)),
            "routine_maturity_percent": round(routine_night_maturity),
            "runtime_config_issues": list(self.robustness.runtime_config_issues),
            "repaired_option_keys": list(self.robustness.repaired_option_keys),
            "overall": "Gut – Lernen läuft" if valid and not stale_rooms and not self.robustness.runtime_config_issues else ("Eingeschränkt – Konfiguration/Sensordaten prüfen" if valid else "Nicht bereit"),
        }
        forecast_validation_status = _decision_validation
        forecast_backtest_status = backtest_summary(self.store.data.get("forecast_validation_history") or [], days=30)
        post_close_status = stabilization_summary(self.store.data.get("post_close_stabilization_history") or [])
        learning_components_status = build_learning_components_status(
            results,
            self.store.data,
            forecast_backtest=forecast_backtest_status,
            post_close_stabilization=post_close_status,
        )

        pending_final_rooms = [r for r in results.values() if r.get("session_finalization_pending")]
        pending_deadlines = []
        for room in pending_final_rooms:
            try:
                pending_deadlines.append(datetime.fromisoformat(str(room.get("session_finalization_deadline_at"))))
            except (TypeError, ValueError):
                pass
        final_wait_remaining_s = max(
            [max((deadline - now).total_seconds(), 0.0) for deadline in pending_deadlines] or [0.0]
        )
        finalizing_measurements = {
            "active": bool(pending_final_rooms),
            "room_count": len(pending_final_rooms),
            "room_names": [str(room.get("name") or room.get("key")) for room in pending_final_rooms],
            "wait_remaining_s": round(final_wait_remaining_s, 1),
            "max_wait_s": SESSION_END_MEASUREMENT_WAIT_SECONDS,
            "temperature_feedback_count": sum(bool(room.get("session_final_temperature_feedback")) for room in pending_final_rooms),
            "humidity_feedback_count": sum(bool(room.get("session_final_humidity_feedback")) for room in pending_final_rooms),
            "message": "Fenster geschlossen · FreshAirIQ wartet kurz auf aktuelle Rückmeldungen der Klimasensoren und wertet danach die Lüftung aus.",
        }

        data = {
            "status": status, "status_text": status_text, "rooms": results, "levels": list(self.entry.data.get(CONF_LEVELS, [])), "potential_total_ml": round(realistic_house_effect), "actionable_potential_ml": round(realistic_actionable_potential), "theoretical_potential_total_ml": round(potential), "theoretical_actionable_potential_ml": round(actionable_potential), "live_balance_ml": round(live), "next_5_min_ml": round(max(next5_effect, 0)), "next_5_min_effect_ml": round(next5_effect), "moisture_gain_next_5_min_ml": round(moisture_gain_next5),
            "forecast_horizon_min": forecast_horizon, "forecast_moisture_effect_ml": round(forecast_effect), "forecast_uncapped_moisture_effect_ml": round(forecast_uncapped_effect), "forecast_target_limited": forecast_target_limited, "forecast_live_adapted": forecast_live_adapted, "forecast_live_observation_weight": round(forecast_live_observation_weight, 3),
            "forecast_temperature_change_c": round(forecast_temp, 2), "forecast_cost": round(forecast_cost, 4),
            "forecast_heat_kwh": round(forecast_heat, 4), "forecast_confidence": forecast_confidence,
            "forecast_optimal_close_in_min": forecast_optimal_close_in_min,
            "max_surface_rh": max_surface, "total_water_ml": round(total_water), "ventilation_threshold_ml": round(ventilation_threshold), "ventilation_threshold_percent": float(options.get("min_potential_percent_total_water", 10)), "ventilation_threshold_mode": threshold_mode, "ventilation_threshold_reason": threshold_reason,
            "prognosis_confidence": confidence, "cross_ventilation": cross, "recommended_duration_min": displayed_recommended, "remaining_duration_min": remaining, "temperature_change_live_c": temp_live,
            "last_learning_diagnosis": self.store.data.get("last_diagnosis", ""), "operating_profile": options.get("operating_profile", "comfort"), "cooling_rooms": len(cooling),
            "overnight_forecast_ml": night_forecast, "overnight_forecast_base_ml": night_forecast_base,
            "overnight_weather_effect_ml": round(weather_effect), "overnight_trend_effect_ml": round(trend_effect),
            "overnight_routine_projection_ml": round(routine_night_projection), "overnight_routine_adjustment_ml": round(routine_night_adjustment), "routine_night_maturity": round(routine_night_maturity),
            "overnight_hours_remaining": round(night_hours, 2), "overnight_confidence": night_confidence,
            "night_model_ml_h": round(effective_night_rate_ml_h(options, self.store.data.get("night_model_ml_h"), int(self.store.data.get("night_model_samples", 0)), effective_adults, effective_children), 1),
            "night_model_samples": night_samples, "night_recommendation": night_recommendation,
            "night_strategy": night_strategy,
            "history_14d": history, "water_history_14d": self.store.water_history_days(stats_days), "history_summary": history_summary, "statistics_days": stats_days,
            "occupants": adults + children, "adult_occupants": adults, "child_occupants": children,
            "effective_occupants": occupancy["expected_total"], "effective_adults": occupancy["expected_adults"], "effective_children": occupancy["expected_children"],
            "tracked_occupants": occupancy["tracked_total"], "home_tracked_occupants": occupancy["home_adults"] + occupancy["home_children"],
            "away_tracked_occupants": occupancy["away_adults"] + occupancy["away_children"], "unknown_tracked_occupants": occupancy["unknown_adults"] + occupancy["unknown_children"],
            "untracked_adults": occupancy["untracked_adults"], "untracked_children": occupancy["untracked_children"],
            "guest_adults": occupancy["guest_adults"], "guest_children": occupancy["guest_children"], "presence_confidence": occupancy["presence_confidence"],
            "presence_explanation": occupancy.get("presence_explanation"), "pets_in_household": occupancy.get("pets_in_household", False),
            "soft_presence_score": occupancy.get("soft_presence_score", 0.0), "active_presence_sensors": occupancy.get("active_presence_sensors", []),
            "property_type": options.get("property_type", PROPERTY_HOUSE), "heating_system": options.get("heating_system"),
            "energy_price_per_kwh": energy_price_per_kwh_equivalent(options), "notifications_enabled": bool(options.get("notifications_enabled")), "estimated_moisture_generation_day_ml": current_daily_generation, "configured_moisture_generation_day_ml": expected_daily_generation, "estimated_generated_so_far_ml": expected_generated_so_far, "moisture_balance_today_ml": moisture_balance_today,
            "pollen_enabled": bool(options.get("pollen_enabled")), "pollen_index": pollen, "pollen_limit": float(options.get("pollen_max", 4)), "pollen_blocked": pollen_blocked,
            "wind_bearing": wind_bearing, "wind_speed": wind_speed, "last_ventilation": self.store.data.get("last_ventilation"),
            "finalizing_measurements": finalizing_measurements,
            "forecast_validation": forecast_validation_status,
            "recommendation_quality": intelligent_recommendation.get("recommendation_quality", {}),
            "decision_trace": intelligent_recommendation.get("decision_trace", {}),
            "forecast_backtest": forecast_backtest_status,
            "post_close_stabilization": post_close_status,
            "learning_components": learning_components_status,
            "post_close_stabilization_history": list(self.store.data.get("post_close_stabilization_history") or [])[-100:],
            "intelligent_recommendation": intelligent_recommendation, "recommendation_engine": "v3", "house_ventilation_mode": house_ventilation_mode, "house_ventilation_active_ratio": round(active_ratio, 3), "floor_ventilation_mode": floor_ventilation_mode, "floor_ventilation_floor": floor_display_name if floor_ventilation_mode else None, "room_sort_order": [str(r.get("key")) for r in rooms_cfg], "system_check": system_check,
            "iq_state": iq_state, "intelligence_engine": "v13", "decision_engine": "v6", "live_coach_engine": "v1", "anticipation_engine": "v1", "planner_engine": "v1", "seasonal_engine": "v1", "house_strategy_engine": "v1", "consolidation_engine": "v1", "decision_brain_engine": "v1", "decision_trace_engine": "v1",
            "future_weather_available": bool(future_outdoor), "future_weather_boundaries": future_outdoor, "day_night_plan": day_night_plan,
            "house_strategy_maturity": house_maturity(self.store.data), "house_strategy_samples": int(self.store.data.get("house_strategy_samples", 0)),
            "sign_convention": "display: moisture_removed=-, moisture_added=+",
            "outdoor_temperature": round(outdoor_t, 2) if outdoor_t is not None else None,
            "outdoor_humidity": round(outdoor_rh, 2) if outdoor_rh is not None else None,
            "outdoor_absolute_humidity": round(absolute_humidity(outdoor_t, outdoor_rh), 3) if outdoor_t is not None and outdoor_rh is not None and -30 < outdoor_t < 60 and 0 <= outdoor_rh <= 100 else None,
            "outdoor_data_quality": "ok" if outdoor_t is not None and outdoor_rh is not None and -30 < outdoor_t < 60 and 0 <= outdoor_rh <= 100 else "missing_or_invalid",
        }
        changed = changed or await process_notifications(self.hass, self.store, data, options, now, completed_sessions)
        if changed: await self.store.async_save()
        self.diagnostics.update_configuration_snapshot(self.entry.data, options, data, now)
        await self.diagnostics.async_record(data, self.store.data, now, completed_sessions)
        data["diagnostics"] = self.diagnostics.status
        data["diagnostics_upload"] = self.telemetry.status
        self._first_update = False
        return data

    def _reset_completed_session_runtime(self, mem: dict[str, Any], room_key: str) -> None:
        """Clear only per-session runtime state after a definitive room close."""
        clear_session_behaviour(mem)
        self._cancel_final_measurement_timer(room_key)
        mem.update({
            "session_active": False,
            "session_started": None,
            "session_physical_started": None,
            "session_start_ah": None,
            "session_start_source_ah": None,
            "session_learning_start_ah": None,
            "session_learning_source_ah": None,
            "session_learning_started": None,
            "session_last_eligible_ah": None,
            "session_last_eligible_at": None,
            "session_start_temp": None,
            "session_result_base_ml": 0.0,
            "close_notified": False,
            "session_fresh_measurements": 0,
            "session_temperature_reports": 0,
            "session_humidity_reports": 0,
            "session_last_temperature_update": None,
            "session_last_humidity_update": None,
            "session_open_temperature_reported_at": None,
            "session_open_humidity_reported_at": None,
            "session_last_valid_temperature": None,
            "session_last_valid_humidity": None,
            "session_last_valid_reference_temperature": None,
            "session_last_valid_reference_humidity": None,
            "session_last_valid_at": None,
            "session_close_pending": False,
            "session_close_detected_at": None,
            "session_close_wait_started_at": None,
            "session_close_deadline_at": None,
            "session_close_temperature_baseline": None,
            "session_close_humidity_baseline": None,
            "session_close_temperature_feedback": False,
            "session_close_humidity_feedback": False,
            "session_close_refresh_requested_at": None,
            "forecast_recent_removed_ml_min": None,
            "forecast_recent_observed_at": None,
            "session_moisture_source_detected": False,
            "session_cross_active": False,
            "session_cross_seconds": 0.0,
            "session_cross_last_update": None,
            "session_forecast_timeline": [],
            "session_timeline_last_checkpoint_min": None,
            "session_start_frame_quality": None,
            "session_start_frame_skew_s": None,
            "session_start_frame_max_age_s": None,
            "session_start_frame_learning_eligible": False,
            "session_prediction_snapshot_frame_quality": None,
            "session_prediction_snapshot_frame_skew_s": None,
            "session_prediction_snapshot_frame_max_age_s": None,
            "session_validation_id": None,
            "session_prediction_start_context": None,
            "session_prediction_time_aligned": False,
            "session_validation_started": None,
            "session_validation_start_ah": None,
            "session_validation_start_source_ah": None,
            "session_validation_start_temp": None,
            "session_validation_start_source_temp": None,
            "session_last_validation_ah": None,
            "session_last_validation_temp": None,
            "session_last_validation_at": None,
        })

    def _finish_session_without_measurement(
        self, mem: dict[str, Any], cfg: dict[str, Any], now: datetime
    ) -> dict[str, Any]:
        """Close a room session when no numeric end climate value is recoverable.

        This is a hard availability fail-safe, not a new learning path. The real
        ventilation duration is retained, but moisture/temperature outcome,
        physical learning, forecast calibration and repeat baselines are all
        explicitly unavailable.
        """
        started_raw = mem.get("session_physical_started") or mem.get("session_started")
        try:
            started = datetime.fromisoformat(str(started_raw)) if started_raw else now
        except (TypeError, ValueError):
            started = now
        if now < started:
            now = started
        elapsed = max(0.0, (now - started).total_seconds() / 60.0)
        elapsed_seconds = elapsed * 60.0
        cross_seconds = min(
            max(finite_float(mem.get("session_cross_seconds"), 0.0) or 0.0, 0.0),
            elapsed_seconds,
        )
        session_quality = session_measurement_quality(
            int(mem.get("session_fresh_measurements", 0)),
            temperature_reports=int(mem.get("session_temperature_reports", 0)),
            humidity_reports=int(mem.get("session_humidity_reports", 0)),
            final_temperature_feedback=bool(mem.get("session_close_temperature_feedback")),
            final_humidity_feedback=bool(mem.get("session_close_humidity_feedback")),
        )
        diagnosis = (
            "Lernmessung übersprungen: Nach dem Schließen war innerhalb der "
            "Abschlusswartezeit kein verwendbarer Temperatur-/Feuchte-Endwert verfügbar."
        )
        mem["diagnosis"] = diagnosis
        mem["last_learning_at"] = dt_util.now().isoformat()
        mem["last_learning_valid"] = False
        self.store.data["last_diagnosis"] = f"{cfg['name']}: {diagnosis}"
        self.store.record_session(
            now.replace(tzinfo=None), 0.0, elapsed, 0.0, 0.0, 0.0, cfg["key"], moisture_valid=False
        )
        learn_completed_session(mem, elapsed)
        pc_dates = mem.get("personal_context_observation_dates")
        if not isinstance(pc_dates, list):
            pc_dates = []
        pc_day = now.date().isoformat()
        if pc_day not in pc_dates:
            pc_dates.append(pc_day)
        mem["personal_context_observation_dates"] = pc_dates[-730:]

        event_id = f"{cfg['key']}:{started.isoformat()}:{now.isoformat()}"
        event = {
            "event_id": event_id,
            "validation_session_id": mem.get("session_validation_id") or event_id,
            "key": cfg["key"],
            "name": cfg["name"],
            "floor": cfg.get(CONF_ROOM_FLOOR, FLOOR_GROUND),
            "sort_order": int(cfg.get(CONF_ROOM_SORT_ORDER, 9999)),
            "volume_m3": float(cfg[CONF_ROOM_VOLUME]),
            "started_at": started.isoformat(),
            "ended_at": now.isoformat(),
            "measurement_started_at": mem.get("session_started"),
            "measurement_duration_min": round(elapsed, 3),
            "removed_ml": None,
            "raw_removed_ml": None,
            "moisture_measurement_valid": False,
            "duration_min": elapsed,
            "validation_removed_ml": None,
            "validation_duration_min": None,
            "validation_temp_delta_c": None,
            "temp_delta_c": None,
            "energy_kwh": None,
            "cost": None,
            "cross_ventilation": cross_seconds > 0.0,
            "cross_ventilation_minutes": round(cross_seconds / 60.0, 2),
            "cross_ventilation_percent": round((cross_seconds / elapsed_seconds * 100.0) if elapsed_seconds > 0 else 0.0, 1),
            "learning_valid": False,
            "measurement_frame_learning_eligible": False,
            "session_measurement_quality": session_quality.get("quality"),
            "session_measurement_quality_reason": f"{session_quality.get('reason') or ''} Abschlussmessung nicht verfügbar.",
            "session_timestamp_activity_gate_passed": bool(session_quality.get("timestamp_gate_passed")),
            "session_fresh_measurements": int(mem.get("session_fresh_measurements", 0)),
            "session_temperature_reports": int(mem.get("session_temperature_reports", 0)),
            "session_humidity_reports": int(mem.get("session_humidity_reports", 0)),
            "session_open_temperature_reported_at": mem.get("session_open_temperature_reported_at"),
            "session_open_humidity_reported_at": mem.get("session_open_humidity_reported_at"),
            "session_last_temperature_reported_at": mem.get("session_last_temperature_update"),
            "session_last_humidity_reported_at": mem.get("session_last_humidity_update"),
            "final_temperature_feedback": bool(mem.get("session_close_temperature_feedback")),
            "final_humidity_feedback": bool(mem.get("session_close_humidity_feedback")),
            "final_measurement_refresh_requested_at": mem.get("session_close_refresh_requested_at"),
            "final_measurement_wait_started_at": mem.get("session_close_wait_started_at"),
            "measurement_finalized_at": dt_util.now().isoformat(),
            "final_measurement_source": "unavailable_after_grace",
            "final_measurement_timeout": True,
            "final_measurement_available": False,
            "moisture_source_contaminated": bool(mem.get("session_moisture_source_detected")),
            "recommendation_followed": bool(mem.get("session_recommendation_followed")),
            "recommended_duration_min": mem.get("session_recommended_duration_min"),
            "outcome_feedback_learned": False,
            "outcome_feedback_action": "skipped",
            "outcome_feedback_reason": "Keine belastbare Abschlussmessung verfügbar; Prognose und Lernmodell bleiben unverändert.",
            "outcome_feedback_accuracy": None,
            "predicted_removed_ml": mem.get("session_predicted_removed_ml"),
            "predicted_temperature_change_c": mem.get("session_predicted_temperature_change_c"),
            "predicted_cost": mem.get("session_predicted_cost"),
            "prediction_confidence": mem.get("session_prediction_confidence"),
            "prediction_snapshot_at": mem.get("session_prediction_snapshot_at"),
            "prediction_horizon_min": mem.get("session_prediction_horizon_min"),
            "prediction_snapshot_elapsed_min": mem.get("session_prediction_snapshot_elapsed_min"),
            "prediction_reference": mem.get("session_prediction_reference"),
            "prediction_time_aligned": False,
            "prediction_measurement_duration_min": None,
            "prediction_comparable": False,
            "forecast_timeline": list(mem.get("session_forecast_timeline") or []) + [{
                "kind": "end",
                "checkpoint_min": round(elapsed, 3),
                "captured_at": now.isoformat(),
                "elapsed_min": round(elapsed, 3),
                "timing_error_min": 0.0,
                "actual_removed_ml": None,
                "raw_actual_removed_ml": None,
                "actual_temperature_change_c": None,
                "predicted_final_removed_ml": None,
                "predicted_final_temperature_change_c": None,
                "remaining_horizon_min": 0.0,
                "confidence": None,
                "method": "end_measurement_unavailable",
                "measurement_frame_quality": "unavailable",
                "measurement_frame_skew_s": None,
                "measurement_frame_max_age_s": None,
            }],
        }
        mem["session_result_ml"] = 0.0
        mem["last_ventilation_ended_at"] = now.isoformat()
        mem["last_ventilation_removed_ml"] = None
        mem["last_ventilation_end_humidity"] = None
        mem["last_ventilation_end_absolute_humidity"] = None
        mem["last_ventilation_reference_ah"] = None
        mem["post_close_active"] = False
        mem["post_close_last_outcome"] = {
            "event_id": event_id,
            "quality": "insufficient",
            "eligible": False,
            "reason": "Post-close learning skipped: no usable end climate measurement was available.",
        }
        self._reset_completed_session_runtime(mem, cfg["key"])
        return event


    async def _finish_session(
        self,
        mem: dict[str, Any],
        cfg: dict[str, Any],
        t: float,
        rh: float,
        ref_t: float,
        ref_rh: float,
        now: datetime,
        cross: bool,
        measurement_frame: dict[str, Any] | None = None,
        *,
        final_measurement_source: str = "state_at_finalization",
        final_measurement_timeout: bool = False,
    ) -> dict[str, Any]:
        # Compatibility for direct/internal callers that predate Measurement
        # Frames. Production coordinator paths always provide the current frame.
        if not isinstance(measurement_frame, dict):
            measurement_frame = {"quality": "legacy", "learning_eligible": True, "validation_eligible": True, "skew_s": None, "max_age_s": None}
        measurement_started_raw = mem.get("session_learning_started") or mem.get("session_started")
        physical_started_raw = mem.get("session_physical_started") or measurement_started_raw
        try: measurement_started = datetime.fromisoformat(measurement_started_raw) if measurement_started_raw else now
        except (ValueError, TypeError): measurement_started = now
        try: started = datetime.fromisoformat(physical_started_raw) if physical_started_raw else measurement_started
        except (ValueError, TypeError): started = measurement_started
        if now < started:
            now = started
        if measurement_started < started:
            measurement_started = started
        if now < measurement_started:
            measurement_started = now
        elapsed = max(0.0, (now - started).total_seconds() / 60.0)
        measurement_elapsed = max(0.0, (now - measurement_started).total_seconds() / 60.0)
        end_ah = absolute_humidity(t, rh) if -10 < t < 50 and 5 <= rh <= 100 else 0.0
        session_quality = session_measurement_quality(
            int(mem.get("session_fresh_measurements", 0)),
            temperature_reports=int(mem.get("session_temperature_reports", 0)),
            humidity_reports=int(mem.get("session_humidity_reports", 0)),
            final_temperature_feedback=bool(mem.get("session_close_temperature_feedback")),
            final_humidity_feedback=bool(mem.get("session_close_humidity_feedback")),
        )
        # In-session timestamp activity remains a hard gate. Historical
        # measurement-frame age classes may describe confidence, but they can no
        # longer make a session learnable when either room-climate channel never
        # produced a newer report after the physical opening.
        session_activity_eligible = bool(session_quality.get("timestamp_gate_passed"))
        mem["start_measurement_in_session_gate_passed"] = session_activity_eligible
        # Objective validation now uses the same strict in-session timestamp
        # activity gate. Frame age/skew remains visible for diagnostics, but it
        # can neither bypass nor independently invalidate proven sensor activity.
        validation_end_ah = end_ah if session_activity_eligible else None
        validation_end_temp = t if session_activity_eligible else None
        validation_end_quality = measurement_frame.get("quality")
        validation_end_skew_s = measurement_frame.get("skew_s")
        validation_end_max_age_s = measurement_frame.get("max_age_s")
        # Deliberately no fallback to an older pre-close validation frame here.
        # Without the strict in-session timestamp gate, such a fallback could make
        # a held value look like fresh evidence and contaminate learning/validation.

        source_ah = finite_float(mem.get("session_learning_source_ah"))
        if source_ah is None:
            source_ah = finite_float(mem.get("session_start_source_ah"), 0.0) or 0.0
        if source_ah <= 0 and -30 < ref_t < 60 and 0 <= ref_rh <= 100: source_ah = absolute_humidity(ref_t, ref_rh)
        learning_start_ah = finite_float(mem.get("session_learning_start_ah"))
        if learning_start_ah is None:
            learning_start_ah = finite_float(mem.get("session_start_ah"), 0.0) or 0.0
        live_start_ah = finite_float(mem.get("session_start_ah"), 0.0) or 0.0
        result_base_ml = finite_float(mem.get("session_result_base_ml"), 0.0) or 0.0
        session_removed = result_base_ml + (live_start_ah - end_ah) * float(cfg[CONF_ROOM_VOLUME])
        mem["session_result_ml"] = session_removed
        source_contaminated = bool(mem.get("session_moisture_source_detected"))
        frame_learning_eligible = session_activity_eligible
        if source_contaminated:
            rate = float(mem["learning_rate"]); samples = int(mem["learning_samples"])
            diagnosis = "Lernmessung übersprungen: aktive interne Feuchtequelle während der Lüftung erkannt"
            valid = False
        elif not frame_learning_eligible:
            rate = float(mem["learning_rate"]); samples = int(mem["learning_samples"])
            diagnosis = f"Lernmessung übersprungen: {session_quality.get('reason') or 'Temperatur und Luftfeuchtigkeit haben während der Lüftung keine ausreichend neuen Zeitstempel geliefert.'}"
            valid = False
        else:
            old_rate = float(mem["learning_rate"])
            rate, samples, diagnosis, valid = update_learning(old_rate=old_rate, old_samples=int(mem["learning_samples"]), elapsed_min=measurement_elapsed, start_ah=learning_start_ah, end_ah=end_ah, source_ah=source_ah, learning_enabled=bool(self.options["learning_enabled"]), max_duration_min=float(self.options.get("learning_max_duration_min", 120)))
            if valid:
                # The session timestamp gate is now the authority for adaptive
                # influence. Legacy frame classes remain diagnostic context only
                # and may never upgrade a 0.75 "good" session to full weight.
                activity_weight = float(session_quality.get("learning_weight", 0.0) or 0.0)
                frame_weight = activity_weight
                rate = old_rate + (float(rate) - old_rate) * frame_weight

                # Maturity uses the same evidence weight as the coefficient update.
                # Keep ``learning_samples`` integer-compatible for the established UI
                # and models, but accumulate fractional evidence until one full sample
                # has genuinely been earned. Four 0.75 sessions therefore count as
                # three maturity samples instead of four.
                old_samples = int(mem.get("learning_samples", 0))
                try:
                    prior_credit = min(max(float(mem.get("learning_sample_credit", 0.0) or 0.0), 0.0), 0.999999)
                except (TypeError, ValueError, OverflowError):
                    prior_credit = 0.0
                evidence_total = prior_credit + max(min(frame_weight, 1.0), 0.0)
                sample_increment = int(evidence_total)
                samples = min(old_samples + sample_increment, 1000)
                mem["learning_sample_credit"] = 0.0 if samples >= 1000 else round(evidence_total - sample_increment, 6)
                # ``update_learning`` reports the unweighted candidate sample
                # number. Rewrite that label so diagnostics cannot claim a full
                # maturity sample when only fractional evidence was credited.
                diagnosis = diagnosis.replace(
                    f"Learned: sample {old_samples + 1}",
                    f"Learned: evidence {samples}+{mem['learning_sample_credit']:.2f}",
                    1,
                )
                if frame_weight < 1.0:
                    diagnosis = f"{diagnosis} · qualitätsgewichtet ({frame_weight:.2f})"
                diagnosis = f"{diagnosis} · Lernreife-Evidenz +{frame_weight:.2f} (Proben {samples}, Rest {mem['learning_sample_credit']:.2f})"
                dates = mem.get("learning_observation_dates")
                if not isinstance(dates, list):
                    dates = []
                day = now.date().isoformat()
                if day not in dates:
                    dates.append(day)
                mem["learning_observation_dates"] = dates[-730:]
        mem["learning_rate"] = rate; mem["learning_samples"] = samples; mem["diagnosis"] = diagnosis; mem["last_learning_at"] = now.isoformat(); mem["last_learning_valid"] = bool(valid); self.store.data["last_diagnosis"] = f"{cfg['name']}: {diagnosis}"
        temp_start = finite_float(mem.get("session_start_temp"), t)
        if temp_start is None:
            temp_start = t
        temp_delta = t - temp_start
        elapsed_seconds = max(elapsed * 60.0, 0.0)
        cross_seconds = min(max(finite_float(mem.get("session_cross_seconds"), 0.0) or 0.0, 0.0), elapsed_seconds)
        # A session may be cross-ventilated only for part of its runtime.  Use
        # the time-weighted airflow bonus instead of sampling the contact state
        # after it has already been closed.
        cross_ratio = cross_seconds / elapsed_seconds if elapsed_seconds > 0 else 0.0
        cross_multiplier = 1.0 + 0.25 * cross_ratio
        fraction = exchanged_air_fraction(float(rate), elapsed, cross_multiplier); _delivered, purchased, cost = ventilation_cost(float(cfg[CONF_ROOM_VOLUME]), temp_start, ref_t, fraction, self.options)
        if temp_delta >= 0 or (self.options.get("operating_profile") == PROFILE_SUMMER_COOLING and ref_t < temp_start):
            purchased = 0.0; cost = 0.0
        self.store.record_session(now.replace(tzinfo=None), session_removed, elapsed, temp_delta, purchased, cost, cfg["key"], moisture_valid=session_activity_eligible)
        learn_completed_session(mem, elapsed)
        pc_dates = mem.get("personal_context_observation_dates")
        if not isinstance(pc_dates, list):
            pc_dates = []
        pc_day = now.date().isoformat()
        if pc_day not in pc_dates:
            pc_dates.append(pc_day)
        mem["personal_context_observation_dates"] = pc_dates[-730:]
        # Hotfix 0.24.14.1: compare the immutable START model with the duration
        # that was actually measured.  The end measurement only selects the
        # point on the frozen start-time forecast curve; it is never fed back as
        # a prediction input.  This removes the previous systematic mismatch in
        # which (for example) a 15-minute start forecast was rejected when the
        # user happened to close the window after 9 or 25 minutes.
        validation_started = None
        try:
            validation_started = datetime.fromisoformat(str(mem.get("session_validation_started"))) if mem.get("session_validation_started") else None
        except (TypeError, ValueError):
            validation_started = None
        validation_elapsed = max(0.0, (now - validation_started).total_seconds() / 60.0) if validation_started else 0.0
        validation_start_ah = finite_float(mem.get("session_validation_start_ah"))
        validation_start_temp = finite_float(mem.get("session_validation_start_temp"))
        validation_removed = (
            (validation_start_ah - validation_end_ah) * float(cfg[CONF_ROOM_VOLUME])
            if validation_start_ah is not None and validation_end_ah is not None
            else None
        )
        validation_temp_delta = (
            validation_end_temp - validation_start_temp
            if validation_start_temp is not None and validation_end_temp is not None
            else None
        )

        start_context = mem.get("session_prediction_start_context")
        aligned_prediction = evaluate_start_forecast_at_duration(start_context, validation_elapsed)
        prediction_time_aligned = aligned_prediction is not None
        if aligned_prediction is not None:
            mem["session_predicted_removed_ml"] = aligned_prediction["predicted_removed_ml"]
            mem["session_predicted_temperature_change_c"] = aligned_prediction["predicted_temperature_change_c"]
            mem["session_predicted_cost"] = aligned_prediction["predicted_cost"]
            mem["session_prediction_confidence"] = aligned_prediction["confidence"]
            mem["session_prediction_horizon_min"] = aligned_prediction["duration_min"]
            mem["session_prediction_reference"] = "session_start_curve_v2"
            mem["session_prediction_time_aligned"] = True
            # A valid frozen start context is enough for an informational
            # same-duration comparison. Objective validation/learning remains
            # deliberately stricter and is gated below by measurement quality.
            original_snapshot_valid = True
            prediction_comparable = True
        else:
            # Backward compatibility for a session restored from a pre-hotfix
            # store: keep the previous fixed-horizon test when no v2 start
            # context exists.
            snapshot_horizon = mem.get("session_prediction_horizon_min")
            original_snapshot_valid = bool(mem.get("session_prediction_snapshot_valid"))
            snapshot_valid = original_snapshot_valid and snapshot_horizon is not None
            if snapshot_valid:
                snapshot_horizon_f = max(float(snapshot_horizon), 1.0)
                prediction_comparable = prediction_duration_comparable(elapsed, snapshot_horizon_f)
            else:
                prediction_comparable = False
            mem["session_prediction_time_aligned"] = False

        snapshot_frame_valid = bool(session_activity_eligible)
        end_frame_valid = bool(
            session_activity_eligible
            and validation_end_ah is not None
            and validation_end_temp is not None
        )
        if source_contaminated or not snapshot_frame_valid or not end_frame_valid:
            prediction_comparable = False

        # Objective validation and adaptive forecast learning share the same
        # mandatory timestamp-activity gate. Legacy frame classes remain
        # diagnostic metadata only; neither ``held`` nor ``excellent`` may
        # bypass a missing in-session report from temperature or humidity.
        start_learning_valid = session_activity_eligible
        end_learning_valid = session_activity_eligible
        prediction_learning_eligible = bool(
            session_activity_eligible
            and original_snapshot_valid
            and prediction_time_aligned
            and start_learning_valid
            and end_learning_valid
        )
        mem["session_prediction_snapshot_valid"] = bool(prediction_learning_eligible)
        activity_weight = float(session_quality.get("learning_weight", 0.0) or 0.0)
        mem["session_prediction_learning_weight"] = activity_weight if session_activity_eligible else 0.0
        feedback_processed = False if source_contaminated else learn_outcome_feedback(mem, session_removed, temp_delta)
        feedback_learned = bool(feedback_processed and mem.get("last_outcome_feedback_applied", False))
        mem["session_prediction_snapshot_valid"] = bool(original_snapshot_valid)
        if source_contaminated:
            feedback_action = "skipped"
            feedback_reason = "Lernanpassung übersprungen, weil während der Lüftung eine interne Feuchtequelle erkannt wurde."
            feedback_accuracy = None
        elif feedback_processed:
            feedback_action = mem.get("last_outcome_feedback_action")
            feedback_reason = mem.get("last_outcome_feedback_reason")
            feedback_accuracy = mem.get("last_outcome_feedback_accuracy")
        else:
            feedback_action = "skipped"
            if prediction_time_aligned and (not snapshot_frame_valid or not end_frame_valid):
                feedback_reason = "Die Startprognose wurde auf exakt dieselbe Messdauer abgeglichen, aber Temperatur und Luftfeuchtigkeit haben während dieser Lüftung nicht beide mindestens einen neueren Sensor-Zeitstempel geliefert. Deshalb werden weder Prognosegenauigkeit noch Lernmodell aus diesem Vergleich angepasst. Die Lern-Auswertung kann deshalb verzögert erscheinen."
            elif prediction_time_aligned:
                feedback_reason = "Startprognose wurde mit exakt derselben Messdauer verglichen. Für diese Lüftung wurde daraus keine Modellanpassung abgeleitet."
            elif original_snapshot_valid and mem.get("session_prediction_horizon_min") is not None and not prediction_comparable:
                feedback_reason = "Ältere Startprognose ohne eingefrorene Startkurve konnte nicht zuverlässig auf die tatsächliche Messdauer abgeglichen werden. Sie verändert das Prognosemodell nicht."
            else:
                feedback_reason = "Beim bestätigten Lüftungsstart konnte keine Startprognose eingefroren werden; diese Lüftung wird deshalb nicht zur Prognoseanpassung verwendet."
            feedback_accuracy = None
        event_id = f"{cfg['key']}:{started.isoformat()}:{now.isoformat()}"
        event = {
            "event_id": event_id,
            "validation_session_id": mem.get("session_validation_id") or event_id,
            "key": cfg["key"], "name": cfg["name"],
            "floor": cfg.get(CONF_ROOM_FLOOR, FLOOR_GROUND),
            "sort_order": int(cfg.get(CONF_ROOM_SORT_ORDER, 9999)),
            "volume_m3": float(cfg[CONF_ROOM_VOLUME]),
            "started_at": started.isoformat(), "ended_at": now.isoformat(),
            "measurement_started_at": measurement_started.isoformat(),
            "measurement_duration_min": round(measurement_elapsed, 3),
            "removed_ml": session_removed if session_activity_eligible else None,
            "raw_removed_ml": round(session_removed, 1),
            "moisture_measurement_valid": bool(session_activity_eligible),
            "duration_min": elapsed,
            "validation_removed_ml": round(validation_removed, 1) if validation_removed is not None else None,
            "validation_duration_min": round(validation_elapsed, 3) if validation_started is not None else None,
            "validation_temp_delta_c": round(validation_temp_delta, 2) if validation_temp_delta is not None else None,
            "temp_delta_c": temp_delta, "energy_kwh": purchased, "cost": cost,
            "cross_ventilation": cross_seconds > 0.0,
            "cross_ventilation_minutes": round(cross_seconds / 60.0, 2),
            "cross_ventilation_percent": round(cross_ratio * 100.0, 1),
            "learning_valid": valid,
            "measurement_frame_learning_eligible": bool(frame_learning_eligible),
            "session_measurement_quality": session_quality.get("quality"),
            "session_measurement_quality_reason": session_quality.get("reason"),
            "session_timestamp_activity_gate_passed": bool(session_quality.get("timestamp_gate_passed")),
            "session_fresh_measurements": int(mem.get("session_fresh_measurements", 0)),
            "session_temperature_reports": int(mem.get("session_temperature_reports", 0)),
            "session_humidity_reports": int(mem.get("session_humidity_reports", 0)),
            "session_open_temperature_reported_at": mem.get("session_open_temperature_reported_at"),
            "session_open_humidity_reported_at": mem.get("session_open_humidity_reported_at"),
            "session_last_temperature_reported_at": mem.get("session_last_temperature_update"),
            "session_last_humidity_reported_at": mem.get("session_last_humidity_update"),
            "final_temperature_feedback": bool(mem.get("session_close_temperature_feedback")),
            "final_humidity_feedback": bool(mem.get("session_close_humidity_feedback")),
            "final_measurement_refresh_requested_at": mem.get("session_close_refresh_requested_at"),
            "final_measurement_wait_started_at": mem.get("session_close_wait_started_at"),
            "measurement_finalized_at": dt_util.now().isoformat(),
            "final_measurement_source": final_measurement_source,
            "final_measurement_timeout": bool(final_measurement_timeout),
            "final_measurement_available": True,
            "last_valid_session_measurement_at": mem.get("session_last_valid_at"),
            "start_measurement_frame_quality": mem.get("session_start_frame_quality"),
            "start_measurement_frame_skew_s": mem.get("session_start_frame_skew_s"),
            "start_measurement_frame_max_age_s": mem.get("session_start_frame_max_age_s"),
            "prediction_measurement_frame_quality": mem.get("session_prediction_snapshot_frame_quality"),
            "prediction_measurement_frame_skew_s": mem.get("session_prediction_snapshot_frame_skew_s"),
            "prediction_measurement_frame_max_age_s": mem.get("session_prediction_snapshot_frame_max_age_s"),
            "end_measurement_frame_quality": validation_end_quality,
            "end_measurement_frame_skew_s": validation_end_skew_s,
            "end_measurement_frame_max_age_s": validation_end_max_age_s,
            "moisture_source_contaminated": source_contaminated,
            "recommendation_followed": bool(mem.get("session_recommendation_followed")),
            "recommended_duration_min": mem.get("session_recommended_duration_min"),
            "outcome_feedback_learned": feedback_learned,
            "outcome_feedback_action": feedback_action,
            "outcome_feedback_reason": feedback_reason,
            "outcome_feedback_accuracy": feedback_accuracy,
            "predicted_removed_ml": mem.get("session_predicted_removed_ml"),
            "predicted_temperature_change_c": mem.get("session_predicted_temperature_change_c"),
            "predicted_cost": mem.get("session_predicted_cost"),
            "prediction_confidence": mem.get("session_prediction_confidence"),
            "prediction_snapshot_at": mem.get("session_prediction_snapshot_at"),
            "prediction_horizon_min": mem.get("session_prediction_horizon_min"),
            "prediction_snapshot_elapsed_min": mem.get("session_prediction_snapshot_elapsed_min"),
            "prediction_reference": mem.get("session_prediction_reference"),
            "prediction_time_aligned": bool(prediction_time_aligned),
            "prediction_measurement_duration_min": round(validation_elapsed, 3),
            "prediction_comparable": bool(prediction_comparable),
            "forecast_timeline": list(mem.get("session_forecast_timeline") or []) + [{
                "kind": "end",
                "checkpoint_min": round(measurement_elapsed, 3),
                "captured_at": now.isoformat(),
                "elapsed_min": round(measurement_elapsed, 3),
                "timing_error_min": 0.0,
                "actual_removed_ml": round(session_removed, 1) if session_activity_eligible else None,
                "raw_actual_removed_ml": round(session_removed, 1),
                "actual_temperature_change_c": round(temp_delta, 2),
                "predicted_final_removed_ml": None,
                "predicted_final_temperature_change_c": None,
                "remaining_horizon_min": 0.0,
                "confidence": None,
                "method": "observed_end",
                "measurement_frame_quality": measurement_frame.get("quality"),
                "measurement_frame_skew_s": measurement_frame.get("skew_s"),
                "measurement_frame_max_age_s": measurement_frame.get("max_age_s"),
            }],
        }
        mem["last_ventilation_ended_at"] = now.isoformat()
        mem["last_ventilation_removed_ml"] = round(session_removed, 1) if session_activity_eligible else None
        repeat_reference_ah = (
            absolute_humidity(ref_t, ref_rh)
            if -30 < ref_t < 60 and 0 <= ref_rh <= 100
            else None
        )
        repeat_baseline = trusted_session_end_baseline(
            timestamp_gate_passed=session_activity_eligible,
            end_humidity=rh,
            end_absolute_humidity=end_ah,
            reference_absolute_humidity=repeat_reference_ah,
        )
        mem["last_ventilation_end_humidity"] = (
            round(repeat_baseline["end_humidity"], 1)
            if repeat_baseline["end_humidity"] is not None else None
        )
        mem["last_ventilation_end_absolute_humidity"] = (
            round(repeat_baseline["end_absolute_humidity"], 3)
            if repeat_baseline["end_absolute_humidity"] is not None else None
        )
        mem["last_ventilation_reference_ah"] = (
            round(repeat_baseline["reference_absolute_humidity"], 3)
            if repeat_baseline["reference_absolute_humidity"] is not None else None
        )
        if session_activity_eligible:
            start_post_close_observation(
                mem, event_id=event_id, room_key=cfg["key"], room_name=cfg["name"], now=now, close_ah=end_ah, close_temp_c=t,
                removed_ml=session_removed, volume_m3=float(cfg[CONF_ROOM_VOLUME]),
                frame_quality=measurement_frame.get("quality"),
            )
        else:
            # Without proven in-session T+RH activity the end baseline is not
            # strong enough to seed post-close rebound learning either.
            mem["post_close_active"] = False
            mem["post_close_last_outcome"] = {
                "event_id": event_id,
                "quality": "insufficient",
                "eligible": False,
                "reason": "Post-close learning skipped: no complete in-session temperature/humidity timestamp evidence.",
            }
        self._reset_completed_session_runtime(mem, cfg["key"])
        return event

    def _cross_ventilation_active(self) -> bool:
        pairs_raw = str(self.options.get("cross_ventilation_pairs", "")).strip()
        if not pairs_raw: return False
        room_by_key = {r["key"]: r for r in self.entry.data.get(CONF_ROOMS, []) if r.get(CONF_ROOM_INCLUDE_CALCULATIONS, True)}
        now = dt_util.now()
        for pair in pairs_raw.split(","):
            keys = [x.strip() for x in pair.split("+") if x.strip()]
            if len(keys) == 2 and all(k in room_by_key for k in keys):
                a,b=(room_by_key[k] for k in keys)
                same_zone = str(a.get(CONF_ROOM_FLOOR,"")) == str(b.get(CONF_ROOM_FLOOR,""))
                links = str(self.options.get("cross_zone_connections", ""))
                explicit = f"{keys[0]}+{keys[1]}" in links or f"{keys[1]}+{keys[0]}" in links
                if same_zone or explicit:
                    # Contact delays gate only the *start* of a room session. If a
                    # running session is reopened after a brief close, cross-flow
                    # must resume immediately as well instead of waiting through
                    # the opening delay a second time.
                    pair_open = True
                    for key in keys:
                        active_session = bool((self.store.data.get("rooms", {}).get(key) or {}).get("session_active"))
                        room_open = _room_ventilation_state(
                            self.hass, room_by_key[key], now,
                            honour_delays=not active_session,
                        )[0]
                        if not room_open:
                            pair_open = False
                            break
                    if pair_open:
                        return True
        return False
