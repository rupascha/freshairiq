from datetime import datetime, timezone
from custom_components.freshairiq.ventilation_log import build_ventilation_pdf


def _event(event_id, room, start, end):
    return {
        "event_id": event_id, "room_name": room, "started_at": start, "ended_at": end,
        "duration_min": 10, "removed_ml": 42, "measurement_valid": True,
        "recommendation_followed": True, "start_temperature_c": 21.5, "end_temperature_c": 21.2,
        "start_humidity_percent": 55, "end_humidity_percent": 50,
        "start_absolute_humidity_g_m3": 11.2, "end_absolute_humidity_g_m3": 9.85,
    }


def test_issue_9_pdf_is_compact_room_grouped_table():
    events = [
        _event("a", "Wohnzimmer", "2026-01-01T13:18:00+01:00", "2026-01-01T13:28:00+01:00"),
        _event("b", "Wohnzimmer", "2026-01-01T14:50:00+01:00", "2026-01-01T15:00:00+01:00"),
    ]
    pdf = build_ventilation_pdf(events, datetime(2026,1,1,tzinfo=timezone.utc), datetime(2026,1,2,tzinfo=timezone.utc))
    assert pdf.startswith(b"%PDF-1.4")
    for label in [b"Datum", b"Zeit", b"Dauer", b"Temperatur", b"Luftfeuchte", b"Abs. Feuchte", b"Bilanz", b"Empf."]:
        assert label in pdf
    assert pdf.count(b"Wohnzimmer") == 1
    assert b"13:18-13:28" in pdf and b"14:50-15:00" in pdf
    assert b"21,5 -> 21,2" in pdf and b"55 -> 50" in pdf and b"11,20 -> 9,85" in pdf


def test_issue_9_table_repeats_room_header_after_page_break():
    events = [_event(str(i), "Wohnzimmer", "2026-01-01T13:18:00+01:00", "2026-01-01T13:28:00+01:00") for i in range(40)]
    pdf = build_ventilation_pdf(events, datetime(2026,1,1,tzinfo=timezone.utc), datetime(2026,1,2,tzinfo=timezone.utc))
    assert pdf.count(b"/Type /Page ") > 1
    assert b"Wohnzimmer - Fortsetzung" in pdf
    assert pdf.count(b"(Datum) Tj") > 1


def test_issue_9_table_handles_invalid_event_dates_without_breaking_export():
    event = _event("bad", "Raum", "not-a-date", "also-bad")
    pdf = build_ventilation_pdf([event], datetime(2026,1,1,tzinfo=timezone.utc), datetime(2026,1,2,tzinfo=timezone.utc))
    assert pdf.startswith(b"%PDF-1.4")
    assert b"(-) Tj" in pdf
