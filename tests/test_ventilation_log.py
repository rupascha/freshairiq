from datetime import datetime, timezone
from custom_components.freshairiq.ventilation_log import append_ventilation_log, filter_ventilation_log, build_ventilation_pdf


def _event(event_id="e1", ended="2026-10-04T10:10:00+00:00"):
    return {"event_id":event_id,"key":"living","name":"Wohnzimmer","started_at":"2026-10-04T10:00:00+00:00","ended_at":ended,"duration_min":10,"removed_ml":180,"moisture_measurement_valid":True,"start_temperature_c":21.2,"end_temperature_c":20.7,"start_humidity_percent":65,"end_humidity_percent":59,"start_absolute_humidity_g_m3":11.9,"end_absolute_humidity_g_m3":10.2,"recommendation_followed":True}


def test_log_append_deduplicates_and_preserves_room_name():
    now=datetime(2026,10,4,11,tzinfo=timezone.utc)
    rows=append_ventilation_log([],[_event(),_event()],now)
    assert len(rows)==1
    assert rows[0]["room_name"]=="Wohnzimmer"
    assert rows[0]["removed_ml"]==180


def test_log_prunes_old_and_filters_period():
    now=datetime(2026,10,4,11,tzinfo=timezone.utc)
    old=_event("old","2024-01-01T10:10:00+00:00"); old["started_at"]="2024-01-01T10:00:00+00:00"
    rows=append_ventilation_log([old],[_event()],now)
    assert [r["event_id"] for r in rows]==["e1"]
    selected=filter_ventilation_log(rows,datetime(2026,10,4,0,tzinfo=timezone.utc),datetime(2026,10,4,23,59,tzinfo=timezone.utc))
    assert len(selected)==1


def test_pdf_is_valid_and_contains_local_report_text():
    pdf=build_ventilation_pdf([_event()],datetime(2026,10,1,tzinfo=timezone.utc),datetime(2026,10,4,tzinfo=timezone.utc))
    assert pdf.startswith(b"%PDF-1.4")
    assert b"Wohnzimmer" in pdf
    assert b"%%EOF" in pdf


def test_log_handles_invalid_values_naive_dates_and_non_lists():
    now=datetime(2026,10,4,11,tzinfo=timezone.utc)
    bad=_event("bad"); bad["duration_min"]="x"; bad["removed_ml"]=float("nan"); bad["ended_at"]="not-a-date"
    assert append_ventilation_log(None,[],now)==[]
    assert append_ventilation_log([bad],[],now)==[]
    naive=_event("naive","2026-10-04T10:10:00"); naive["started_at"]="2026-10-04T10:00:00"
    rows=append_ventilation_log([], [naive], now)
    assert len(rows)==1 and rows[0]["duration_min"]==10
    assert filter_ventilation_log(["bad", {"started_at":"bad","ended_at":"bad"}],datetime(2026,10,4,tzinfo=timezone.utc),datetime(2026,10,5,tzinfo=timezone.utc))==[]
    assert len(filter_ventilation_log(rows,datetime(2026,10,4,tzinfo=timezone.utc),datetime(2026,10,5,tzinfo=timezone.utc)))==1


def test_pdf_helpers_invalid_and_multi_page():
    from custom_components.freshairiq.ventilation_log import _fmt_dt, _fmt, _pdf_escape
    assert _fmt_dt("bad") == "–"
    assert _fmt("bad") == "–"
    assert "\\(" in _pdf_escape("(x)")
    events=[]
    for i in range(80):
        e=_event(f"e{i}")
        e["room_name"]="Sehr langes Wohnzimmer mit Zusatzbezeichnung " + ("X"*100)
        e["measurement_valid"]=False
        e["recommendation_followed"]=False
        events.append(e)
    pdf=build_ventilation_pdf(events,datetime(2026,10,1,tzinfo=timezone.utc),datetime(2026,10,4,tzinfo=timezone.utc))
    assert pdf.count(b"/Type /Page ") > 1


def test_filter_skips_timezone_incompatible_event_when_report_bounds_are_naive():
    event=_event()
    selected=filter_ventilation_log(
        [event],
        datetime(2026,10,4,0),
        datetime(2026,10,4,23,59),
    )
    assert selected == []
