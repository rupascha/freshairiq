"""0.26.4.7: regressions from the support exports of 9 October 2026.

* support-e926…: "Ca. 5 min nach dem Lüften sagt FreshAirIQ, jetzt ist der beste
  Zeitpunkt zum Lüften" – the post-close moisture rebound in the bathroom was
  read as a bath/shower and presented as "Jetzt ist das beste Lüftungsfenster".
* support-c9e4…: "Benachrichtigungen für Räume ohne Berechnung und Sensoren".
* all three exports: a suppressed notification was re-traced and the whole
  store re-written every 10 s cycle (persistence latency incidents).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import sys
import types

if "homeassistant" not in sys.modules:  # pragma: no cover - depends on test order
    ha = types.ModuleType("homeassistant")
    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = type("HomeAssistant", (), {})
    ha.core = core
    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.core"] = core

from custom_components.freshairiq.decision_brain import build_unified_decision
from custom_components.freshairiq.localize import Translator, _german_score
from custom_components.freshairiq.moisture_source import update_moisture_source
from custom_components.freshairiq.notifications import process_notifications

from pathlib import Path

ROOT_FILE = Path(__file__).resolve()
T0 = datetime(2026, 10, 9, 9, 0, tzinfo=timezone.utc)
BATH = ["shower", "bath"]


def _step(mem, minute, ah, *, open_=False, temp=21.0):
    return update_moisture_source(
        mem, now=T0 + timedelta(minutes=minute), absolute_humidity_g_m3=ah, reference_ah_g_m3=5.9,
        temperature_c=temp, volume_m3=31.2, window_open=open_, learning_rate_per_min=0.03,
        airflow_factor=1.0, cross_ventilation=False, configured_sources=BATH,
    )


def _aired_then_closed(mem):
    for minute in range(0, 46, 3):  # 45 min whole-house airing, humidity falls
        _step(mem, minute, 9.6 - minute * 0.02, open_=True)
    _step(mem, 47, 8.74)  # window closed at minute 47


# --------------------------------------------------------------------------- moisture source


def test_post_close_rebound_is_not_a_shower():
    """Shape of the support case: about +1 g/m³ within 5 min after closing, then flat."""
    mem: dict = {}
    _aired_then_closed(mem)
    states = [_step(mem, m, ah)["active"] for m, ah in ((50, 8.9), (52, 9.7), (55, 9.6), (58, 9.6), (62, 9.65))]
    assert states == [False] * 5
    assert mem.get("moisture_source_rebound_candidate") is None
    # Without the preceding airing the very same rise is a bath/shower signature.
    fresh: dict = {}
    _step(fresh, 47, 8.74)
    _step(fresh, 50, 8.9)
    assert _step(fresh, 52, 9.7)["active"] is True


def test_real_shower_right_after_closing_is_still_detected_once_it_keeps_rising():
    """Real curve from the same export on 8 Oct: shower 9 min after closing."""
    mem: dict = {}
    _aired_then_closed(mem)
    _step(mem, 50, 8.9)
    first = _step(mem, 52, 9.7)  # same start as the rebound …
    assert first["active"] is False
    assert mem["moisture_source_rebound_candidate"]["ah"] == 9.7
    assert _step(mem, 55, 10.0)["active"] is True  # … but it keeps climbing (confirmed after 3 min)
    assert mem["moisture_source_rebound_candidate"] is None


def test_strong_source_after_closing_needs_no_confirmation():
    mem: dict = {}
    _aired_then_closed(mem)
    assert _step(mem, 52, 10.3)["active"] is True  # +1.56 g/m³ in 5 min


def test_shower_without_recent_airing_is_detected_immediately_as_before():
    mem: dict = {}
    _step(mem, 0, 8.7)
    assert _step(mem, 5, 9.7)["active"] is True


def test_guard_ends_after_twenty_minutes():
    mem: dict = {}
    _aired_then_closed(mem)
    _step(mem, 68, 8.75)
    assert _step(mem, 73, 9.75)["active"] is True  # 26 min after closing: normal rules


# --------------------------------------------------------------------------- headline


def _decision(status):
    rooms = {"bad": {"key": "bad", "name": "Badezimmer", "delta_g_m3": 3.5, "potential_ml": 55}}
    rec = {"kind": "ventilate", "status": status, "title": "Feuchtequelle erkannt", "instruction": "Badezimmer jetzt lüften",
           "room_keys": ["bad"], "duration_min": 5}
    return build_unified_decision(rec, rooms, {})


def test_moisture_source_is_not_called_the_best_ventilation_window():
    out = _decision("moisture_source_active")
    brain = out.get("decision_brain", out)
    text = str(brain)
    assert "beste Lüftungsfenster" not in text
    assert brain["headline"] == "Feuchtequelle erkannt"
    assert brain["decision_label"] == "KURZ LÜFTEN"
    assert "nur für diesen Raum" in brain["summary"]
    assert brain["action_line"] == "Badezimmer · etwa 5 min"
    # The ordinary recommendation keeps its wording.
    normal = _decision("ventilate")
    assert normal.get("decision_brain", normal)["headline"] == "Jetzt ist das beste Lüftungsfenster"


def test_new_texts_have_english_translations():
    translator = Translator({"Badezimmer"})
    for text in ("KURZ LÜFTEN", "Dusche erkannt", "Feuchtequelle erkannt", "Betroffener Raum",
                 _decision("moisture_source_active").get("decision_brain", {}).get("summary", "")):
        assert not _german_score(translator.text(text)), text


# --------------------------------------------------------------------------- notifications


class _Services:
    def __init__(self):
        self.calls = []

    def has_service(self, domain, service):
        return domain == "notify" and service == "phone"

    async def async_call(self, domain, service, data, blocking=False):
        self.calls.append(data)


class _Hass:
    def __init__(self):
        self.services = _Services()


class _Store:
    def __init__(self):
        self.data: dict = {}
        self.rooms: dict = {}

    def room(self, key):
        return self.rooms.setdefault(key, {})


def _options(**extra):
    base = {
        "notifications_enabled": True, "notification_targets": ["notify.phone"], "notification_scope": "room",
        "notification_cooldown_min": 90, "notification_room_keys": [], "notify_sensor": True,
        "notify_ventilate": True, "notify_close": True, "notify_mould": True,
    }
    base.update(extra)
    return base


def _rooms():
    return {
        # Building-structure room: no sensors, no calculation.
        "flur": {"key": "flur", "name": "Flur", "action": "Monitor only", "calculation_enabled": False, "monitor_only": True,
                  "data_quality": "not_configured"},
        # Live-value room: sensors shown, calculation disabled.
        "kueche": {"key": "kueche", "name": "Küche", "action": "Monitor only", "calculation_enabled": False, "monitor_only": True,
                    "data_quality": "monitor_only"},
        # Calculated room with a real sensor problem still alerts.
        "buero": {"key": "buero", "name": "Büro", "action": "Check sensor", "calculation_enabled": True, "data_quality": "stale"},
    }


def test_rooms_without_calculation_never_send_sensor_alerts():
    hass, store = _Hass(), _Store()
    asyncio.run(process_notifications(hass, store, {"rooms": _rooms()}, _options(), T0, []))
    titles = [call.get("title", "") for call in hass.services.calls]
    assert any("Büro" in t for t in titles)
    assert not any("Flur" in t or "Küche" in t for t in titles)
    events = {(row["event"], row["status"]) for row in store.data["notification_diagnostics"]}
    assert events == {("sensor", "sent")}


def test_repeated_suppressions_fold_into_one_row_and_do_not_force_a_save():
    hass, store = _Hass(), _Store()
    data = {"rooms": _rooms()}
    assert asyncio.run(process_notifications(hass, store, data, _options(), T0, []))
    # Next cycles: the Büro alert is in cooldown. Before 0.26.4.7 every 10 s cycle
    # appended a row and returned changed=True (immediate full storage write).
    assert asyncio.run(process_notifications(hass, store, data, _options(), T0 + timedelta(seconds=10), [])) is True  # first cooldown row
    for i in range(2, 60):
        assert asyncio.run(process_notifications(hass, store, data, _options(), T0 + timedelta(seconds=10 * i), [])) is False
    trace = store.data["notification_diagnostics"]
    assert [(r["event"], r["status"], r.get("reason")) for r in trace] == [("sensor", "sent", None), ("sensor", "suppressed", "cooldown")]
    assert trace[-1]["repeat_count"] == 58
    assert trace[-1]["last_seen_at"] == (T0 + timedelta(seconds=590)).isoformat()
    # After the fold window a fresh row is written again (bounded, still visible).
    later = T0 + timedelta(minutes=45)
    assert asyncio.run(process_notifications(hass, store, data, _options(), later, [])) is True
    assert len(store.data["notification_diagnostics"]) == 3


def test_delivered_and_failed_notifications_are_never_folded():
    hass, store = _Hass(), _Store()
    rooms = {"bad": {"key": "bad", "name": "Bad", "action": "Ventilate", "data_quality": "ok", "mould_level": "Low"}}
    asyncio.run(process_notifications(hass, store, {"rooms": rooms}, _options(notification_cooldown_min=0), T0, []))
    rooms["bad"]["action"] = "Okay"
    asyncio.run(process_notifications(hass, store, {"rooms": rooms}, _options(notification_cooldown_min=0), T0 + timedelta(minutes=1), []))
    rooms["bad"]["action"] = "Ventilate"
    asyncio.run(process_notifications(hass, store, {"rooms": rooms}, _options(notification_cooldown_min=0), T0 + timedelta(minutes=2), []))
    sent = [r for r in store.data["notification_diagnostics"] if r["status"] == "sent"]
    assert len(sent) == 2 and all("repeat_count" not in r for r in sent)


# --------------------------------------------------------------------------- floor / house close


def _active(key, elapsed, action="Continue ventilating", **extra):
    return {"key": key, "action": action, "active": True, "close_decision_ready": True,
            "session_elapsed_min": elapsed, "goal_state": {}, **extra}


def test_floor_close_waits_for_the_minimum_airing_time_of_every_room():
    from custom_components.freshairiq.consolidation import aggregate_close_allowed

    # Support export: Schlafzimmer open for 1 min, Wohnzimmer opened right now.
    rooms = [_active("schlaf", 1.0), _active("wohnen", 0.0)]
    assert aggregate_close_allowed(rooms, low_return=True, thermal_bad=True, min_duration_min=3.0) is False
    rooms = [_active("schlaf", 4.0), _active("wohnen", 2.9)]
    assert aggregate_close_allowed(rooms, low_return=True, thermal_bad=False, min_duration_min=3.0) is False
    rooms = [_active("schlaf", 4.0), _active("wohnen", 3.0)]
    assert aggregate_close_allowed(rooms, low_return=True, thermal_bad=False, min_duration_min=3.0) is True
    # Without the new argument the previous behaviour is unchanged.
    assert aggregate_close_allowed([_active("a", 0.0)], low_return=True, thermal_bad=False) is True


def test_protection_and_unanimous_room_close_still_close_immediately():
    from custom_components.freshairiq.consolidation import aggregate_close_allowed

    hard = [_active("a", 0.5, goal_state={"hard_close": True}), _active("b", 0.2)]
    assert aggregate_close_allowed(hard, low_return=False, thermal_bad=False, min_duration_min=3.0) is True
    unanimous = [_active("a", 0.5, action="Close"), _active("b", 1.0, action="Close")]
    assert aggregate_close_allowed(unanimous, low_return=False, thermal_bad=False, min_duration_min=3.0) is True
    # Unknown session age never blocks (older payloads / partial test rooms).
    unknown = [_active("a", "nan?"), _active("b", None), _active("c", float("nan"))]
    assert aggregate_close_allowed(unknown, low_return=True, thermal_bad=False, min_duration_min=3.0) is True


def test_house_decision_passes_the_configured_minimum_duration():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "custom_components/freshairiq/house_decision.py").read_text(encoding="utf-8")
    assert source.count('min_duration_min=float(options.get("min_duration_min", 3.0))') == 2


# --------------------------------------------------------------------------- weather retries


def test_unusable_weather_entity_is_retried_with_backoff_not_every_minute():
    from tests.test_weather_future_024100 import _load_module as _load_weather

    wf = _load_weather()
    FORECAST_REFRESH_SECONDS, forecast_retry_delay_seconds = wf.FORECAST_REFRESH_SECONDS, wf.forecast_retry_delay_seconds

    delays = [forecast_retry_delay_seconds(n) for n in range(0, 9)]
    assert delays == [60, 60, 120, 300, 600, 1800, 3600, 3600, 3600]
    # 13 hours of a permanently broken provider: before 0.26.4.7 ≈ 780 attempts.
    elapsed, attempts = 0, 0
    while elapsed < 13 * 3600:
        attempts += 1
        elapsed += forecast_retry_delay_seconds(attempts)
    assert attempts <= 20
    assert FORECAST_REFRESH_SECONDS == 600


def test_weather_failures_record_a_privacy_safe_reason():
    from custom_components.freshairiq.robustness import RobustnessMonitor
    from tests.test_weather_future_024100 import _load_module as _load_weather

    async_hourly_forecast = _load_weather().async_hourly_forecast

    class _States:
        def __init__(self, forecast=None):
            self.forecast = forecast

        def get(self, entity_id):
            return types.SimpleNamespace(attributes={"forecast": self.forecast}) if self.forecast is not None else None

    class _Svc:
        def __init__(self, result=None, error=None):
            self.result, self.error = result, error

        async def async_call(self, *args, **kwargs):
            if self.error:
                raise self.error
            return self.result

    def run(result=None, error=None, forecast=None):
        hass = types.SimpleNamespace(services=_Svc(result, error), states=_States(forecast))
        status: dict = {}
        rows = asyncio.run(async_hourly_forecast(hass, "weather.home", status))
        return rows, status.get("reason")

    assert run(error=TimeoutError()) == ([], "timeout")
    assert run(error=RuntimeError("provider text")) == ([], "service_error")
    assert run(result={"weather.home": {"forecast": []}}) == ([], "no_hourly_rows")
    no_humidity = {"weather.home": {"forecast": [{"datetime": "2026-10-09T10:00:00+00:00", "temperature": 10}]}}
    assert run(result=no_humidity) == ([], "rows_without_temperature_or_humidity")
    ok = {"weather.home": {"forecast": [{"datetime": "2026-10-09T10:00:00+00:00", "temperature": 10, "humidity": 80}]}}
    rows, reason = run(result=ok)
    assert len(rows) == 1 and reason is None

    monitor = RobustnessMonitor()
    monitor.weather_failure("rows_without_temperature_or_humidity")
    monitor.weather_failure()
    snap = monitor.snapshot()
    assert snap["weather_fetch_failures"] == 2
    assert snap["weather_last_failure_reason"] == "rows_without_temperature_or_humidity"


# --------------------------------------------------------------------------- post-close observation


def test_post_close_window_stays_valid_when_the_sensor_only_holds_its_value_at_the_end():
    """Hub cluster FAIQ-POST-001: 98 % of observations were 'invalid' only because
    the frame was 'held'/'uncertain' at the exact 10-minute mark."""
    from custom_components.freshairiq.post_stabilization import start_post_close_observation, update_post_close_observation

    room: dict = {}
    start_post_close_observation(room, event_id="e1", room_key="bad", room_name="Bad", now=T0, close_ah=8.74,
                                 close_temp_c=21.0, removed_ml=120.0, volume_m3=31.2, frame_quality="excellent")
    for minute, ah in ((1, 8.8), (3, 8.9), (6, 9.0), (8, 9.1)):
        outcome, _ = update_post_close_observation(
            room, now=T0 + timedelta(minutes=minute), absolute_humidity_g_m3=ah, temperature_c=21.0,
            frame_quality="excellent", frame_valid=True, window_open=False, moisture_source_active=False)
        assert outcome is None
    outcome, _ = update_post_close_observation(
        room, now=T0 + timedelta(minutes=10.2), absolute_humidity_g_m3=None, temperature_c=None,
        frame_quality="held", frame_valid=False, window_open=False, moisture_source_active=False)
    assert outcome["status"] == "complete" and outcome["valid_for_analysis"] is True
    assert outcome["end_frame_quality"] == "excellent"
    assert outcome["post_close_delta_ml"] == round((9.1 - 8.74) * 31.2, 1)
    assert outcome["interpretation"] == "moisture_rebound"


def test_post_close_window_without_a_late_clean_sample_stays_invalid():
    from custom_components.freshairiq.post_stabilization import start_post_close_observation, update_post_close_observation

    room: dict = {}
    start_post_close_observation(room, event_id="e2", room_key="bad", room_name="Bad", now=T0, close_ah=8.74,
                                 close_temp_c=21.0, removed_ml=120.0, volume_m3=31.2, frame_quality="excellent")
    for minute in (1, 2):
        update_post_close_observation(room, now=T0 + timedelta(minutes=minute), absolute_humidity_g_m3=8.8, temperature_c=21.0,
                                      frame_quality="excellent", frame_valid=True, window_open=False, moisture_source_active=False)
    outcome, _ = update_post_close_observation(
        room, now=T0 + timedelta(minutes=10.5), absolute_humidity_g_m3=None, temperature_c=None,
        frame_quality="uncertain", frame_valid=False, window_open=False, moisture_source_active=False)
    assert outcome["status"] == "complete" and outcome["valid_for_analysis"] is False


def test_forecast_validation_summary_counts_why_comparisons_were_unusable():
    from custom_components.freshairiq.forecast_validation import _invalid_reason_counts

    records = [
        {"valid": False, "invalid_code": "moisture_source_during_session"},
        {"valid": False, "invalid_code": "no_frozen_start_forecast"},
        {"valid": False, "invalid_code": "no_frozen_start_forecast"},
        {"valid": False, "invalid_reason": "older record without code"},
        "broken",
    ]
    assert _invalid_reason_counts(records) == {
        "moisture_source_during_session": 1, "no_frozen_start_forecast": 2, "unrecorded": 2,
    }
    source = (ROOT_FILE.parents[1] / "custom_components/freshairiq/forecast_validation.py").read_text(encoding="utf-8")
    assert source.count("invalid_code = ") == 7  # default + one per reason


# --------------------------------------------------------------------------- GitHub #15


def _bath(**extra):
    from custom_components.freshairiq.model import RoomInput

    base = dict(key="bad", name="Bad", temperature=19.5, humidity=72.0, reference_temperature=10.0,
                reference_humidity=94.0, volume_m3=9.4, contact_open=False, contact_open_seconds=0.0)
    base.update(extra)
    return RoomInput(**base)


def _model_options():
    from custom_components.freshairiq.const import DEFAULT_OPTIONS

    opts = dict(DEFAULT_OPTIONS)
    opts.update({"start_rh": 62.0, "high_rh": 68.0, "min_delta": 2.5, "min_delta_high_rh": 1.5, "min_duration_min": 5.0,
                 "operating_profile": "comfort", "mould_warn_surface_rh": 85.0})
    return opts


def _delta(room):
    from custom_components.freshairiq.model import evaluate_room

    return evaluate_room(room, _model_options(), False)


def test_ventilation_start_has_hysteresis_instead_of_flapping_at_the_threshold():
    from custom_components.freshairiq.model import absolute_humidity

    # Find an outdoor humidity that leaves the drying gradient just below 1.5 g/m³.
    room_ah = absolute_humidity(19.5, 72.0)
    ref_rh = next(rh for rh in range(40, 101) if room_ah - absolute_humidity(13.0, rh) < 1.5)
    fresh = _delta(_bath(reference_temperature=13.0, reference_humidity=float(ref_rh)))
    assert 1.1 <= fresh.delta_g_m3 < 1.5
    assert fresh.ventilation_candidate is False  # a new recommendation needs the full gradient
    held = _delta(_bath(reference_temperature=13.0, reference_humidity=float(ref_rh), ventilation_latched=True))
    assert held.ventilation_candidate is True  # an existing one is not dropped by a 0.1 g/m³ wobble
    released = _delta(_bath(reference_humidity=100.0, humidity=64.0, ventilation_latched=True))
    assert released.ventilation_candidate is False  # far below the thresholds it ends


def test_close_threshold_scales_with_room_volume():
    from custom_components.freshairiq.model import min_return_volume_factor, scaled_min_return

    assert abs(scaled_min_return(25, 9.4) - 25 * 9.4 / 30) < 1e-9
    assert scaled_min_return(25, 30) == scaled_min_return(25, 80) == 25
    assert scaled_min_return(25, 3) == 25 * 0.25
    assert min_return_volume_factor(None) == min_return_volume_factor("x") == min_return_volume_factor(float("nan")) == 1.0


def test_small_bathroom_is_no_longer_closed_at_the_minimum_duration_by_an_unreachable_threshold():
    from custom_components.freshairiq.model import absolute_humidity

    session = dict(contact_open=True, contact_open_seconds=360.0, session_active=True, session_elapsed_min=6.0,
                   session_start_ah=absolute_humidity(19.5, 74.0), session_start_temp=19.5,
                   session_fresh_measurements=3, learning_rate=0.06, reference_humidity=70.0)
    small = _delta(_bath(**session))
    assert 7.9 <= small.moisture_effect_next_5_min_ml < 25  # physically possible in 9.4 m³, but far below 25 ml
    assert small.action == "Continue ventilating" and small.close_recommended is False
    # Once even the volume-scaled benefit is gone the session still closes normally.
    dry = _delta(_bath(**dict(session, humidity=60.0, reference_humidity=95.0)))
    assert dry.action == "Close"


def test_repeat_cooldown_now_also_applies_to_the_room_action():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    block = source[source.index("recently_ventilated = minutes_since_vent"):][:1600]
    assert 'cooldown_demoted = bool(recently_ventilated and result.action == "Ventilate" and not is_open and not mem["session_active"])' in block
    assert 'result.action = "Wait"' in block
    assert "ventilation_latched=bool(mem.get(\"ventilation_candidate_latched\", False))" in source


def test_cooldown_demoted_room_is_not_explained_as_too_small_gradient():
    from custom_components.freshairiq.const import DEFAULT_OPTIONS
    from custom_components.freshairiq.recommendation import build_recommendation

    room = {"key": "bad", "name": "Bad", "calculation_enabled": True, "data_quality": "ok", "active": False,
            "action": "Wait", "recently_ventilated": True, "repeat_cooldown_demoted": True, "humidity": 72,
            "surface_rh": 80, "mould_level": "High", "potential_ml": 30, "realistic_potential_ml": 30, "delta_g_m3": 3.0,
            "co2": None, "co2_available": False, "airflow_factor": 1, "forecast_temperature_change_c": -0.2,
            "temp_next_5_min_c": -0.2, "forecast_confidence": 80}
    out = build_recommendation({"bad": room}, dict(DEFAULT_OPTIONS), threshold_ml=500, total_potential_ml=30, recommended_duration_min=5)
    assert "zu klein" not in " ".join(out.get("reasons") or [])
    physics_wait = build_recommendation({"bad": dict(room, repeat_cooldown_demoted=False)}, dict(DEFAULT_OPTIONS),
                                        threshold_ml=500, total_potential_ml=30, recommended_duration_min=5)
    assert physics_wait["title"] == "Aktuell keine Lüftungsaktion"  # unchanged for genuinely blocked rooms


def test_review_fixes_are_wired():
    from pathlib import Path

    comp = Path(__file__).resolve().parents[1] / "custom_components/freshairiq"
    coordinator = (comp / "coordinator.py").read_text(encoding="utf-8")
    assert "result.ventilation_candidate and has_ventilation_contact and not mem[\"session_active\"]" in coordinator
    assert "Empfehlung bleibt trotz leichter Schwankung bestehen" in coordinator
    validation = (comp / "forecast_validation.py").read_text(encoding="utf-8")
    assert 'scaled_min_return(controls.get("min_return_next_5_min_ml", 25.0), args.get("volume_m3"))' in validation
    from custom_components.freshairiq.intervention import build_interventions  # noqa: F401  (import check)


def test_rebound_candidate_and_post_close_edge_inputs_are_tolerated():
    from custom_components.freshairiq.post_stabilization import _last_clean_sample

    mem: dict = {}
    _aired_then_closed(mem)
    _step(mem, 50, 8.9)
    mem["moisture_source_rebound_candidate"] = {"at": (T0 + timedelta(minutes=49)).isoformat(), "ah": "broken"}
    assert _step(mem, 52, 9.7)["active"] is False  # unreadable candidate -> no confirmation, no crash
    assert _last_clean_sample({"post_close_samples": [{"frame_quality": "excellent", "elapsed_min": 6}, "broken"]}, min_elapsed=5) == {
        "frame_quality": "excellent", "elapsed_min": 6}
