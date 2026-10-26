"""Per-room contact truth: three-state stabilisation, reference air and contact expiry."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    CONF_CONTACT_PASSAGE_DOORS,
    CONF_ROOM_CLIMATE,
    CONF_ROOM_EXHAUST_FAN,
    CONF_ROOM_EXHAUST_FAN_CONTROL,
    CONTACT_UNKNOWN_HOLD_SECONDS,
    SESSION_CLOSE_CONFIRM_SECONDS,
    THREE_STATE_TRANSITION_STABLE_SECONDS,
    THREE_STATE_UNKNOWN_HOLD_SECONDS,
)
from .coordinator_contacts import (
    _contact_ids,
    _contact_specific_reference,
    _contact_unknown_for,
    _open_seconds,
    _room_closed_for_seconds,
    _room_contacts_known,
    _room_ventilation_state,
)
from .coordinator_sources import _cover_learning_guard, _entity_active, _exhaust_stopped_for_seconds, _float_state
from .exhaust_reference import exhaust_reference_applies, exhaust_reference_pair
from .measurement_frame import build_measurement_frame
from .opening_state import (
    aggregate_opening_mode,
    normalize_opening_state,
    opening_contact_profile,
    specialist_opening_provenance,
    stabilise_explicit_mode,
)
from .robustness import finite_float


class RoomContactsMixin:
    """Per-room contact truth: three-state stabilisation, reference air and contact expiry."""

    hass: HomeAssistant  # provided by the coordinator

    def _stabilise_room_contacts(
        self,
        *,
        cfg: Any, changed: Any, mem: Any, now: Any,
    ) -> Any:
        """Three-state contact profile, debounced stable modes and passage doors."""
        contacts_known = _room_contacts_known(self.hass, cfg)
        configured_contact_ids = _contact_ids(cfg)
        configured_contacts = set(configured_contact_ids)
        remembered_all = set(str(x) for x in (mem.get("three_state_contacts") or []))
        # Capability memory belongs to the configured contact, never to the
        # room forever.  A replaced/removed three-state sensor must not make
        # a later binary-only configuration explicit-three-state.
        remembered_three_state = remembered_all & configured_contacts
        contact_modes, proven_three_state = opening_contact_profile(self.hass, configured_contact_ids, remembered_three_state)
        if proven_three_state != remembered_all:
            mem["three_state_contacts"] = sorted(proven_three_state)
            changed = True
        explicit_three_state = bool(proven_three_state)
        stable_contacts_raw = mem.get("stable_opening_modes") if isinstance(mem.get("stable_opening_modes"), dict) else {}
        stable_contacts = {str(k): v for k, v in stable_contacts_raw.items() if str(k) in configured_contacts}
        if stable_contacts != stable_contacts_raw:
            changed = True
        stable_since_raw = mem.get("stable_opening_since") if isinstance(mem.get("stable_opening_since"), dict) else {}
        stable_since_text = {str(k): str(v) for k, v in stable_since_raw.items() if str(k) in configured_contacts}
        if stable_since_text != stable_since_raw:
            changed = True
        stable_since: dict[str, datetime] = {}
        for _contact, _stamp in stable_since_text.items():
            try:
                stable_since[_contact] = datetime.fromisoformat(_stamp)
            except (TypeError, ValueError):
                changed = True
        passage_behavior_raw = mem.get("passage_behavior") if isinstance(mem.get("passage_behavior"), dict) else {}
        passage_behavior = {str(k): v for k, v in passage_behavior_raw.items() if str(k) in configured_contacts}
        if passage_behavior != passage_behavior_raw:
            mem["passage_behavior"] = passage_behavior
            changed = True
        session_passage_raw = mem.get("session_passage_contacts") if isinstance(mem.get("session_passage_contacts"), list) else []
        session_passage_contacts = [str(x) for x in session_passage_raw if str(x) in configured_contacts]
        if session_passage_contacts != session_passage_raw:
            mem["session_passage_contacts"] = session_passage_contacts
            # A contact disappearing during an active session makes the
            # specialised opening classification unauditable. Keep the
            # general session, but never teach an opening sub-model from it.
            if mem.get("session_active"):
                mem["session_opening_mode_mixed"] = True
                mem["session_learning_quarantined"] = True
                mem["session_learning_quarantine_code"] = "FAIQ-OPENING-3STATE-004"
            changed = True
        transition_suppressed = False
        three_state_unknown_contacts: list[str] = []
        three_state_stale_contacts: list[str] = []
        for entity_id in proven_three_state:
            current_mode = contact_modes.get(entity_id, "unknown")
            state_obj = self.hass.states.get(entity_id)
            changed_at = getattr(state_obj, "last_changed", None) if state_obj is not None else None
            # unknown/unavailable is absence of evidence. Hold the last
            # confirmed physical truth only for a short recovery window;
            # after that it is stale/uncertain, never silently "closed".
            if current_mode == "unknown" and stable_contacts.get(entity_id) in {"closed", "open", "tilted"}:
                unknown_age = None
                if isinstance(changed_at, datetime):
                    unknown_age = max((now - changed_at).total_seconds(), 0.0)
                # Battery-powered contacts are event-driven: an unavailable
                # interval is not evidence that the physical opening moved.
                # Keep the last confirmed physical state indefinitely, while
                # degrading *confidence* after the bounded recovery window.
                contact_modes[entity_id] = str(stable_contacts[entity_id])
                three_state_unknown_contacts.append(entity_id)
                if unknown_age is None or unknown_age > THREE_STATE_UNKNOWN_HOLD_SECONDS:
                    three_state_stale_contacts.append(entity_id)
                    if mem.get("session_active"):
                        mem["session_three_state_unknown_observed"] = True
                        mem["session_learning_quarantined"] = True
                        mem["session_learning_quarantine_code"] = "FAIQ-OPENING-3STATE-006"
                continue
            age = None
            if changed_at is not None:
                age = max((now - changed_at).total_seconds(), 0.0)
            stable_mode, suppressed = stabilise_explicit_mode(current_mode, stable_contacts.get(entity_id), age, threshold_seconds=THREE_STATE_TRANSITION_STABLE_SECONDS)
            if suppressed:
                contact_modes[entity_id] = stable_mode
                # Keep the timestamp paired with the previous stable mode.
                # On migration from a release that did not persist it, use
                # now conservatively rather than borrowing the candidate's
                # raw last_changed timestamp.
                if entity_id not in stable_since:
                    stable_since[entity_id] = now
                transition_suppressed = True
                mem["three_state_transients_suppressed"] = int(mem.get("three_state_transients_suppressed", 0) or 0) + 1
                changed = True
            elif current_mode in {"closed", "open", "tilted"}:
                previous_stable = stable_contacts.get(entity_id)
                stable_contacts[entity_id] = current_mode
                if previous_stable != current_mode or entity_id not in stable_since:
                    # Once confirmed, the physical transition began at the
                    # HA state change; confirmation itself happens later.
                    stable_since[entity_id] = changed_at if isinstance(changed_at, datetime) else now
        mem["stable_opening_modes"] = stable_contacts
        mem["stable_opening_since"] = {c: stamp.isoformat() for c, stamp in stable_since.items() if c in configured_contacts}
        previous_unknown_contacts = list(mem.get("three_state_unknown_contacts") or [])
        mem["three_state_unknown_contacts"] = sorted(three_state_unknown_contacts)
        mem["three_state_stale_contacts"] = sorted(three_state_stale_contacts)
        if previous_unknown_contacts != mem["three_state_unknown_contacts"]:
            changed = True
        if three_state_unknown_contacts and mem.get("session_active"):
            mem["session_three_state_unknown_observed"] = True
        opening_mode = aggregate_opening_mode(contact_modes)
        specialist_opening_mode, specialist_opening_signature = specialist_opening_provenance(contact_modes, proven_three_state)
        explicit_tilted = any(contact_modes.get(c) == "tilted" for c in proven_three_state)
        passage_contacts = cfg.get(CONF_CONTACT_PASSAGE_DOORS) if isinstance(cfg.get(CONF_CONTACT_PASSAGE_DOORS), dict) else {}
        active_passage_contacts = sorted(c for c in proven_three_state if bool(passage_contacts.get(c)) and contact_modes.get(c) == "open")
        passage_door_active = bool(active_passage_contacts)
        return (
            active_passage_contacts, changed, configured_contact_ids, contact_modes, contacts_known,
            explicit_three_state, explicit_tilted, opening_mode, passage_contacts, passage_door_active,
            proven_three_state, specialist_opening_mode, specialist_opening_signature, stable_since,
            three_state_stale_contacts, three_state_unknown_contacts, transition_suppressed,
        )

    def _room_session_contact_state(
        self,
        *,
        cfg: Any, changed: Any, configured_contact_ids: Any, contact_modes: Any, default_ref_rh: Any,
        default_ref_t: Any, default_reference_humidity_entity: Any, default_reference_temperature_entity: Any,
        humidity_state: Any, mem: Any, now: Any, outdoor_humidity_state: Any, outdoor_temp_state: Any,
        proven_three_state: Any, rh: Any, stable_since: Any, t: Any, temperature_state: Any,
    ) -> Any:
        """Physical contact truth, reference air, ventilation state, exhaust fan and contact expiry."""
        confirmed_close_seconds: float | None = None
        # Session lifecycle must consume the same stable truth as specialist
        # classification. Only proven three-state contacts are overridden;
        # classic binary contacts preserve their established behaviour.
        stable_session_modes = {c: contact_modes.get(c, "unknown") for c in proven_three_state}
        # All physical consumers must use the same debounced truth for proven
        # three-state contacts. Re-resolve the incoming-air source after the
        # stable modes are known so transient handle states cannot switch
        # reference air before confirmation. Binary contacts retain raw truth.
        physical_contact_modes = {
            c: (stable_session_modes[c] if c in stable_session_modes else ("open" if _open_seconds(self.hass, c, now) is not None else "closed"))
            for c in configured_contact_ids
        }
        cover_learning_guard = _cover_learning_guard(self.hass, cfg, physical_contact_modes, self.options)
        reference_temperature_entity, reference_humidity_entity, ref_t, ref_rh = _contact_specific_reference(
            self.hass, cfg,
            default_temp_entity=default_reference_temperature_entity,
            default_humidity_entity=default_reference_humidity_entity,
            default_temp=default_ref_t, default_humidity=default_ref_rh,
            contact_modes=physical_contact_modes,
        )
        reference_temperature_state = self.hass.states.get(reference_temperature_entity) if reference_temperature_entity else outdoor_temp_state
        reference_humidity_state = self.hass.states.get(reference_humidity_entity) if reference_humidity_entity else outdoor_humidity_state
        measurement_frame = build_measurement_frame(
            now, temperature_state=temperature_state, humidity_state=humidity_state,
            reference_temperature_state=reference_temperature_state, reference_humidity_state=reference_humidity_state,
        )
        is_open, raw_open_seconds = _room_ventilation_state(
            self.hass, cfg, now, honour_delays=False, contact_modes=stable_session_modes, contact_since=stable_since
        )
        raw_contact_open = bool(is_open)
        session_should, _ = _room_ventilation_state(
            self.hass, cfg, now, honour_delays=True, contact_modes=stable_session_modes, contact_since=stable_since
        )
        mechanical_exhaust_active = _entity_active(self.hass, cfg.get(CONF_ROOM_EXHAUST_FAN))
        reference_path = "default" if reference_temperature_entity == default_reference_temperature_entity else "opening"
        # 0.26.5.3: an exhaust fan draws its replacement air from the neighbouring
        # room. A configured pair is atomic: unavailable values never fall back
        # to outdoor air (same rule as opening-specific references).
        exhaust_pair = exhaust_reference_pair(cfg)
        if exhaust_pair is not None and exhaust_reference_applies(
            fan_configured=bool(cfg.get(CONF_ROOM_EXHAUST_FAN)), fan_active=mechanical_exhaust_active,
            window_open=raw_contact_open, has_contacts=bool(configured_contact_ids),
            auto_start=str(cfg.get(CONF_ROOM_EXHAUST_FAN_CONTROL) or "off") == "recommendation",
        ):
            reference_path = "neighbour_room"
            reference_temperature_entity, reference_humidity_entity = exhaust_pair
            ref_t = _float_state(self.hass, reference_temperature_entity)
            ref_rh = _float_state(self.hass, reference_humidity_entity)
            if ref_t is None or ref_rh is None or not (-30 < ref_t < 60 and 0 <= ref_rh <= 100):
                ref_t, ref_rh = None, None
            measurement_frame = build_measurement_frame(
                now, temperature_state=temperature_state, humidity_state=humidity_state,
                reference_temperature_state=self.hass.states.get(reference_temperature_entity),
                reference_humidity_state=self.hass.states.get(reference_humidity_entity),
            )
        self.__dict__.setdefault("_reference_paths", {})[str(cfg.get("key") or "")] = reference_path  # 0.26.5.4: wording, diagnostics
        # Mechanical exhaust is a first-class ventilation trigger. It shares
        # the session lifecycle but remains explicitly typed so its learning
        # evidence can never silently contaminate window-opening models.
        if mechanical_exhaust_active:
            is_open = True
            session_should = True
        climate_entity = cfg.get(CONF_ROOM_CLIMATE)
        climate_state = self.hass.states.get(climate_entity) if climate_entity else None
        thermostat_target = None
        if climate_state is not None and str(climate_state.state).lower() not in {"unknown", "unavailable"}:
            thermostat_target = finite_float(climate_state.attributes.get("temperature"))
        if not mem.get("session_active") and not raw_contact_open and not mechanical_exhaust_active and thermostat_target is not None and 12.0 <= thermostat_target <= 30.0:
            mem["last_plausible_comfort_target_c"] = round(float(thermostat_target), 1)
            mem["last_plausible_comfort_target_at"] = now.isoformat()

        # A proven three-state battery contact with a persisted stable state
        # remains physically evaluable while raw HA state is unavailable. Do
        # not route that case through the legacy startup-only keep-open guard.
        missing_since = self.__dict__.setdefault("_contacts_missing_since", {})
        expired_contacts: list[str] = []
        for contact_id in configured_contact_ids:
            state = self.hass.states.get(contact_id)
            if state is None:
                missing_since.setdefault(contact_id, now)
            else:
                missing_since.pop(contact_id, None)
            if (state is None or normalize_opening_state(state.state) == "unknown") and not (
                contact_id in proven_three_state and stable_session_modes.get(contact_id) in {"closed", "open", "tilted"}
            ) and _contact_unknown_for(state, missing_since.get(contact_id, now), now) > CONTACT_UNKNOWN_HOLD_SECONDS:
                expired_contacts.append(contact_id)
        lifecycle_contacts_known = all(
            ((state := self.hass.states.get(contact_id)) is not None
             and normalize_opening_state(state.state) != "unknown")
            or (contact_id in proven_three_state and stable_session_modes.get(contact_id) in {"closed", "open", "tilted"})
            or contact_id in expired_contacts
            for contact_id in configured_contact_ids
        ) if configured_contact_ids else True
        if expired_contacts and mem.get("session_active"):
            # The airing can end, but whether the dead opening was open is unknown:
            # never learn from it (0.26.5.0).
            mem["session_learning_quarantined"] = True
            mem["session_learning_quarantine_code"] = "FAIQ-CONTACT-UNKNOWN-001"
            mem["session_contact_unknown_expired"] = True
        # During HA startup a contact can temporarily be unavailable. Never
        # interpret an unresolved legacy/binary restore state as a real close.
        if mem.get("session_active") and not lifecycle_contacts_known:
            is_open = True
            session_should = True
        elif mem.get("session_active"):
            # Contact delays are a *start* gate only. Once a ventilation
            # session exists, reopening a contact must continue that same
            # session immediately instead of reapplying its opening delay.
            if is_open:
                session_should = True
            else:
                closed_for = _room_closed_for_seconds(self.hass, cfg, now, contact_modes=stable_session_modes)
                fan_stopped_for = _exhaust_stopped_for_seconds(self.hass, cfg.get(CONF_ROOM_EXHAUST_FAN), mem.get("session_started"), now)
                if closed_for is not None and fan_stopped_for is not None:
                    closed_for = min(closed_for, fan_stopped_for)
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
        return (
            changed, confirmed_close_seconds, cover_learning_guard, is_open, measurement_frame,
            mechanical_exhaust_active, physical_contact_modes, raw_contact_open, raw_open_seconds, ref_rh,
            ref_t, reference_humidity_entity, reference_temperature_entity, rh, session_should,
            stable_session_modes, t,
        )
