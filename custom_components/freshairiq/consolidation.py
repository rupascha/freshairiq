"""FreshAirIQ final recommendation consolidation and invariant checks.

This module intentionally adds no new intelligence. It is the final guard between
the layered intelligence pipeline and Home Assistant/UI output.
"""
from __future__ import annotations

from math import isfinite
from typing import Any


_KINDS = {"okay", "sensor", "ventilate", "wait", "prepare", "pollen_wait", "continue", "close"}
_STATUS_BY_KIND = {
    "okay": "okay",
    "sensor": "sensor_error",
    "ventilate": "ventilate",
    "wait": "wait",
    "prepare": "wait",
    "pollen_wait": "pollen_warning",
    "continue": "ventilation_running",
    "close": "close_windows",
}

_SEVERITY_BY_KIND = {
    "okay": "neutral",
    "sensor": "danger",
    "ventilate": "good",
    "wait": "neutral",
    "prepare": "attention",
    "pollen_wait": "warning",
    "continue": "good",
    "close": "warning",
}


def _f(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        return out if isfinite(out) else default
    except (TypeError, ValueError):
        return default


def _unique_text(values: Any, limit: int = 6) -> list[str]:
    out: list[str] = []
    if not isinstance(values, (list, tuple)):
        return out
    for value in values:
        text = str(value or "").strip()
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def aggregate_close_gate_ready(rooms: list[dict[str, Any]]) -> bool:
    """Return whether every targeted active room has released the close gate."""
    return bool(rooms) and all(bool(room.get("close_decision_ready", False)) for room in rooms)


def aggregate_close_allowed(
    rooms: list[dict[str, Any]],
    *,
    low_return: bool,
    thermal_bad: bool,
) -> bool:
    """Allow an aggregate close only after every affected room released its gate."""
    if not aggregate_close_gate_ready(rooms):
        return False
    return bool(
        all(str(room.get("action")) == "Close" for room in rooms)
        or low_return
        or thermal_bad
    )


def stabilise_recommendation(
    recommendation: dict[str, Any],
    rooms: dict[str, dict[str, Any]],
    options: dict[str, Any],
) -> dict[str, Any]:
    """Apply final consistency and real-time safety invariants."""
    out = dict(recommendation or {})
    checks: list[str] = []

    valid_keys = {
        str(k) for k, room in rooms.items()
        if room.get("calculation_enabled", True) and room.get("data_quality") == "ok"
    }
    configured_keys = {str(k) for k in rooms}
    requested = [str(x) for x in (out.get("room_keys") or [])]
    filtered = [k for k in requested if k in configured_keys]
    if filtered != requested:
        checks.append("stale_room_keys_removed")
    out["room_keys"] = filtered

    calculated = [r for r in rooms.values() if r.get("calculation_enabled", True)]
    valid = [r for r in calculated if r.get("data_quality") == "ok"]
    active = [r for r in valid if r.get("active")]
    closing = [r for r in active if (r.get("close_recommended") or str(r.get("action")) == "Close") and not r.get("moisture_source_active")]
    max_duration = _f(options.get("max_duration_min"), 20.0)
    tolerated_long_open = [
        r for r in active
        if not r.get("moisture_source_active")
        and _f(r.get("session_elapsed_min")) >= max_duration + 10.0
        and _f(r.get("temperature_change_c")) > -1.5
        and _f(r.get("delta_g_m3")) >= -0.2
        and _f(r.get("forecast_5_min_temperature_change_c", r.get("temp_next_5_min_c"))) > -0.6
    ]
    tolerated_keys = {str(r.get("key")) for r in tolerated_long_open}
    closing = [r for r in closing if str(r.get("key")) not in tolerated_keys]
    effective_active = [r for r in active if str(r.get("key")) not in tolerated_keys]

    original_kind = str(out.get("kind") or "okay")
    kind = original_kind
    if kind not in _KINDS:
        kind = "okay"
        checks.append("unknown_kind_normalised")

    # Final real-time invariant: an already open ventilation session must never
    # be turned into a future wait/prepare/okay action by a later prediction layer.
    source_running = [r for r in active if r.get("moisture_source_active") and _f(r.get("delta_g_m3")) > _f(options.get("close_delta"), 0.4)]
    if source_running:
        kind = "continue"
        out["room_keys"] = [str(r.get("key")) for r in source_running if r.get("key") is not None]
        labels = ", ".join(dict.fromkeys(str(r.get("moisture_source_label") or "Feuchtequelle") for r in source_running))
        out["title"] = f"{labels} erkannt"
        out["instruction"] = "Wirksame Lüftung weiterführen"
        out["summary"] = "Während die interne Feuchte- und Wärmequelle aktiv ist, hat die trocknere Außen-/Referenzluft Vorrang vor einer normalen Schließempfehlung."
        out["duration_min"] = None
        checks.append("active_moisture_source_overrides_close")
    elif closing:
        # v0.20.5.0: active moisture sources outrank closing, while a very
        # long, thermally stable opening is treated as a probable tilt/dauer-open
        # state instead of pinning the dashboard on "close" indefinitely.
        # Hotfix 0.19.1.1: room-level marginal thresholds must not cause a
        # premature whole-house close when the selected open rooms still have a
        # meaningful combined 5-minute drying return.  This is a final
        # consistency guard only; hard max-duration and poor thermal-efficiency
        # closes remain authoritative.
        profile = str(options.get("operating_profile", "comfort"))
        min_return = _f(options.get("min_return_next_5_min_ml"), 25.0)
        max_temp_loss = _f(options.get("max_temp_loss_next_5_min_c"), 0.6)
        min_efficiency = _f(options.get("min_efficiency_ml_per_01c"), 8.0)
        if profile == "dehumidify":
            min_return *= 0.60
            max_temp_loss *= 1.50
            min_efficiency *= 0.60
        elif profile == "summer_cooling":
            min_return *= 0.50

        combined_next5 = sum(
            max(_f(r.get("forecast_5_min_moisture_effect_ml", r.get("moisture_effect_next_5_min_ml"))), 0.0)
            for r in closing
        )
        hard_closing = [
            r for r in closing
            if _f(r.get("session_elapsed_min")) >= _f(options.get("max_duration_min"), 20.0)
            or (
                profile != "summer_cooling"
                and _f(r.get("forecast_5_min_temperature_change_c", r.get("temp_next_5_min_c"))) <= -max_temp_loss
                and _f(r.get("efficiency_ml_per_01c"), 999.0) < min_efficiency
            )
        ]

        if combined_next5 >= min_return and not hard_closing:
            kind = "continue"
            out["room_keys"] = [str(r.get("key")) for r in active if r.get("key") is not None]
            out["title"] = "Lüftung läuft"
            out["instruction"] = "Lüftung weiterführen"
            out["summary"] = "Der gemeinsame kurzfristige Feuchteertrag ist noch relevant; FreshAirIQ wartet mit der Schließempfehlung."
            out["duration_min"] = max(_f(out.get("duration_min"), 1.0), 1.0)
            checks.append("premature_aggregate_close_blocked")
        else:
            selected_closing = hard_closing if combined_next5 >= min_return and hard_closing else closing
            kind = "close"
            out["room_keys"] = [str(r.get("key")) for r in selected_closing if r.get("key") is not None]
            out["title"] = "Jetzt schließen"
            out["instruction"] = "Fenster der genannten Räume schließen"
            out["summary"] = "Die laufende Lüftung hat ihren sinnvollen Endpunkt erreicht."
            checks.append("hard_close_subset_selected" if selected_closing is hard_closing else "close_state_authoritative")
    elif tolerated_long_open and not effective_active:
        kind = "okay"
        out["status"] = "passive_open_monitor"
        out["room_keys"] = [str(r.get("key")) for r in tolerated_long_open if r.get("key") is not None]
        out["title"] = "Daueröffnung wird beobachtet"
        out["instruction"] = "Fenster kann vorerst gekippt/offen bleiben"
        out["summary"] = "FreshAirIQ vermutet eine bewusste Dauer- oder Kippöffnung. Solange Temperatur und Feuchtebilanz stabil bleiben, verdrängt die Schließaufforderung keine wichtigeren Empfehlungen."
        out["duration_min"] = None
        checks.append("long_open_monitor_mode")
    elif effective_active and kind == "close":
        # Hotfix 0.17.0.5 central invariant: downstream intelligence layers may
        # refine *when* to close, but only for rooms whose two-report / 15-min
        # gate has been released by the room model. A close targeting multiple
        # active rooms is allowed only when every targeted room is ready.
        target_keys = {str(k) for k in out.get("room_keys", [])}
        targeted_active = [
            r for r in effective_active
            if not target_keys or str(r.get("key")) in target_keys
        ]
        close_gate_ready = bool(targeted_active) and all(
            bool(r.get("close_decision_ready", False)) for r in targeted_active
        )
        if not close_gate_ready:
            kind = "continue"
            out["room_keys"] = [str(r.get("key")) for r in active if r.get("key") is not None]
            out["title"] = "Lüftung läuft"
            out["instruction"] = "Lüftung weiter beobachten"
            out["summary"] = "Die Schließentscheidung wartet noch auf die erforderliche Mess- oder Modellfreigabe."
            # Pipeline consistency: when a downstream close is rejected, remove
            # close-only live-coach presentation data as well. Otherwise a final
            # `continue` could still carry `live_coach_state=close` or 0 min.
            if str(out.get("live_coach_state") or "") == "close":
                out["live_coach_state"] = "awaiting_measurements"
                out["live_coach_reason"] = out["summary"]
                out["live_coach_remaining_min"] = None
                checks.append("stale_live_coach_close_cleared")
            if out.get("duration_min") in (0, 0.0):
                out["duration_min"] = None
                checks.append("blocked_close_duration_cleared")
            checks.append("unreleased_close_blocked")
        else:
            checks.append("released_downstream_close_allowed")
    elif effective_active and kind not in {"continue", "sensor"}:
        kind = "continue"
        out["room_keys"] = [str(r.get("key")) for r in effective_active if r.get("key") is not None]
        out["title"] = "Lüftung läuft"
        out["instruction"] = "Lüftung weiter beobachten"
        out["summary"] = "Eine reale Lüftung läuft; Zukunftsplanung ist bis zum Abschluss nachgeordnet."
        checks.append("active_session_authoritative")

    if calculated and not valid:
        kind = "sensor"
        out["room_keys"] = []
        out["title"] = "Sensordaten prüfen"
        out["instruction"] = "Mindestens einen gültigen Raumdatensatz wiederherstellen"
        out["summary"] = "FreshAirIQ kann ohne gültige Raumdaten keine belastbare Empfehlung berechnen."
        checks.append("no_valid_room_guard")

    out["kind"] = kind
    # Preserve established status subtypes (e.g. moisture_gain) unless this
    # final gate actually changed the action kind.
    if "long_open_monitor_mode" in checks:
        out["status"] = "passive_open_monitor"
    elif kind != original_kind or not out.get("status"):
        out["status"] = _STATUS_BY_KIND.get(kind, "okay")
    if kind != original_kind:
        # Keep UI emphasis aligned with the final action after a guard changed
        # the kind (e.g. rejected close -> continue).
        out["severity"] = _SEVERITY_BY_KIND.get(kind, "neutral")
        checks.append("severity_aligned_with_final_kind")

    # Numeric output normalisation prevents NaN/inf from leaking into HA state
    # attributes or JavaScript rendering.
    numeric_defaults = {
        "duration_min": None,
        "estimated_removed_ml": 0.0,
        "expected_temperature_change_c": 0.0,
        "estimated_reheat_cost": 0.0,
        "forecast_confidence": 0.0,
    }
    for key, default in numeric_defaults.items():
        value = out.get(key)
        if value is None and default is None:
            continue
        clean = _f(value, default or 0.0)
        if value is not None:
            try:
                raw = float(value)
                if not isfinite(raw):
                    checks.append(f"{key}_nonfinite_normalised")
            except (TypeError, ValueError):
                checks.append(f"{key}_invalid_normalised")
        out[key] = clean

    if kind == "close":
        # Hotfix 0.17.0.6: a final close decision is an immediate action.
        # The ventilation minimum duration applies only while ventilation is
        # still recommended and must never turn 0 min / "close now" back
        # into additional ventilation time.
        if out.get("duration_min") not in (None, 0, 0.0):
            checks.append("close_duration_forced_zero")
        out["duration_min"] = 0.0
    elif out.get("duration_min") is not None:
        configured_low = max(_f(options.get("min_duration_min"), 3.0), 1.0)
        high = max(_f(options.get("max_duration_min"), 30.0), configured_low)
        # Hotfix 0.17.0.7: the configured minimum is a start guard for a new
        # ventilation recommendation. During an already active session,
        # duration_min is a *remaining* time and must be allowed to count down
        # below that minimum (for example 0.5 min instead of being inflated
        # back to 3 min). A true close decision is still handled above as 0.0.
        low = 0.0 if (kind == "continue" and active) else configured_low
        original = _f(out.get("duration_min"), low)
        bounded = min(max(original, low), high)
        if abs(bounded-original) > 1e-9:
            checks.append("duration_bounded")
        if kind == "continue" and active and original < configured_low:
            checks.append("active_remaining_duration_preserved")
        out["duration_min"] = round(bounded, 1)

    out["estimated_removed_ml"] = max(round(_f(out.get("estimated_removed_ml"))), 0)
    out["estimated_reheat_cost"] = round(max(_f(out.get("estimated_reheat_cost")), 0.0), 4)
    out["forecast_confidence"] = round(min(max(_f(out.get("forecast_confidence")), 0.0), 100.0))
    out["expected_temperature_change_c"] = round(_f(out.get("expected_temperature_change_c")), 2)
    out["reasons"] = _unique_text(out.get("reasons"), 6)

    # Clean selected option if its referenced room set became invalid.
    if kind in {"ventilate", "continue", "close", "prepare"} and not out["room_keys"] and valid_keys:
        checks.append("action_without_room_reference")

    selected_rooms = [rooms[k] for k in out.get("room_keys", []) if k in rooms]
    selected_floors = {str(r.get("floor") or "") for r in selected_rooms}
    if len(selected_rooms) == 1:
        out["recommendation_scope"] = "room"
    elif len(selected_rooms) > 1 and len(selected_floors) == 1:
        floor = next(iter(selected_floors))
        floor_label = {"ground_floor":"Erdgeschoss","ground floor":"Erdgeschoss","Ground Floor":"Erdgeschoss","upper_floor":"Obergeschoss","upper floor":"Obergeschoss","Upper Floor":"Obergeschoss","basement":"Kellergeschoss","base_floor":"Kellergeschoss","base floor":"Kellergeschoss","Basement":"Kellergeschoss","attic":"Dachgeschoss","Attic":"Dachgeschoss"}.get(floor, floor or "Stockwerk")
        out["recommendation_scope"] = "floor"
        out["recommendation_floor"] = floor
        out["recommendation_floor_label"] = floor_label
        if kind == "ventilate":
            out["title"] = f"{floor_label} lüften"
        elif kind == "continue":
            out["title"] = f"{floor_label}-Lüftung läuft"
    elif len(selected_rooms) > 1:
        out["recommendation_scope"] = "house"

    out["consolidation_engine"] = "v1"
    out["consolidation_checks"] = checks
    out["consolidated"] = True
    return out
