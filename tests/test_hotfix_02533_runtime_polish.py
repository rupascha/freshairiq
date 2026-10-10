from pathlib import Path
import importlib.util
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def test_sensor_notifications_respect_runtime_recovery_grace_without_hiding_persistent_failures():
    s = (ROOT / "custom_components/freshairiq/notifications.py").read_text()
    assert 'sensor_recovery_active = bool(recovery.get("active"))' in s
    assert '    if not sensor_recovery_active:\n        for r in room_events["sensor"]:' in s  # 0.26.4.9: events + push
    assert 'kind == "sensor" and sensor_recovery_active' in s
    assert 'reason="sensor_recovery_grace"' in s
    assert 'not (kind == "sensor" and sensor_recovery_active)' in s


def test_obsolete_visible_support_status_card_is_removed_not_only_unrendered():
    s = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text()
    assert "_supportStatusCard(st)" not in s
    assert "Technischer Fehlercode für Support" not in s
    assert "Falls du keine Diagnosedatei senden kannst" not in s


def test_room_overview_has_explicit_dark_surface_and_high_contrast_title():
    s = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text()
    assert 'background:#172029' in s
    assert '.room-title{font-size:15px;font-weight:950;line-height:19px;color:#ffffff!important' in s


def test_pdf_is_structured_and_does_not_emit_unsupported_unicode_arrow():
    p = ROOT / "custom_components/freshairiq/ventilation_log.py"
    spec = importlib.util.spec_from_file_location("faiq_vlog_2533", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    event = {
        "room_name":"Wohnküche", "started_at":"2026-10-04T17:29:00+02:00", "ended_at":"2026-10-04T17:46:00+02:00",
        "duration_min":17.1, "removed_ml":19, "measurement_valid":True, "recommendation_followed":False,
        "start_temperature_c":21.0, "end_temperature_c":21.0, "start_humidity_percent":69, "end_humidity_percent":68,
        "start_absolute_humidity_g_m3":12.66, "end_absolute_humidity_g_m3":12.43,
    }
    pdf=m.build_ventilation_pdf([event], datetime(2026,9,4,tzinfo=timezone.utc), datetime(2026,10,4,tzinfo=timezone.utc))
    assert pdf.startswith(b"%PDF-1.4")
    assert b"Zusammenfassung" in pdf and b"Temperatur" in pdf and b"Abs. Feuchte" in pdf
    assert b" -> " in pdf
    assert b"? 21" not in pdf


def test_pdf_empty_and_multipage_paths_are_valid():
    p = ROOT / "custom_components/freshairiq/ventilation_log.py"
    spec = importlib.util.spec_from_file_location("faiq_vlog_2533_more", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    a=datetime(2026,9,4,tzinfo=timezone.utc); b=datetime(2026,10,4,tzinfo=timezone.utc)
    empty=m.build_ventilation_pdf([],a,b)
    assert b"Keine erfassten Lueftungsvorgaenge" in empty
    base={"room_name":"Raum", "started_at":"2026-10-04T17:29:00+02:00", "ended_at":"2026-10-04T17:46:00+02:00", "duration_min":17, "measurement_valid":False}
    many=m.build_ventilation_pdf([{**base,"room_name":f"Raum {i}"} for i in range(8)],a,b)
    assert b"Datum" in many and b"Zeit" in many
    assert many.count(b"/Type /Page ") > 1


def test_pdf_distinguishes_recommendation_false_from_not_recorded_and_preserves_tristate():
    p = ROOT / "custom_components/freshairiq/ventilation_log.py"
    spec = importlib.util.spec_from_file_location("faiq_vlog_2533_tri", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    a=datetime(2026,9,4,tzinfo=timezone.utc); b=datetime(2026,10,4,tzinfo=timezone.utc)
    base={"event_id":"e","key":"r","name":"Raum","room_name":"Raum","started_at":"2026-10-04T17:29:00+02:00","ended_at":"2026-10-04T17:46:00+02:00","duration_min":17,"measurement_valid":False}
    false_event={**base,"recommendation_followed":False}
    unknown_event={**base,"event_id":"e2","recommendation_followed":None}
    assert m.compact_ventilation_event(false_event)["recommendation_followed"] is False
    assert m.compact_ventilation_event(unknown_event)["recommendation_followed"] is None
    pdf_false=m.build_ventilation_pdf([false_event],a,b)
    pdf_unknown=m.build_ventilation_pdf([unknown_event],a,b)
    assert b"(Nein) Tj" in pdf_false
    assert b"Nicht erfasst" not in pdf_false
    assert b"(Nicht erfasst) Tj" in pdf_unknown


def test_pdf_cards_reserve_legal_note_area_on_final_page():
    p = ROOT / "custom_components/freshairiq/ventilation_log.py"
    spec = importlib.util.spec_from_file_location("faiq_vlog_2533_layout", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    a=datetime(2026,9,4,tzinfo=timezone.utc); b=datetime(2026,10,4,tzinfo=timezone.utc)
    base={"room_name":"Raum","started_at":"2026-10-04T17:29:00+02:00","ended_at":"2026-10-04T17:46:00+02:00","duration_min":17,"measurement_valid":False,"recommendation_followed":None}
    pdf=m.build_ventilation_pdf([{**base,"room_name":f"Raum {i}"} for i in range(12)],a,b)
    # Layout contract: compact table rows may not enter the note/footer reserve below y=105.
    source=p.read_text()
    assert "if y - row_h < 105:" in source
    assert b"Dieses Protokoll dokumentiert" in pdf
    assert pdf.count(b"/Type /Page ") > 1
