"""0.26.5.3 (user feedback FAIQ-FB-833697E303F8): ventilation log per day and as CSV."""
from __future__ import annotations

import csv
from datetime import date, datetime, timedelta, timezone
import io

from custom_components.freshairiq.ventilation_daily import build_daily_pdf, daily_summary, period_totals, ventilation_csv

TZ = timezone(timedelta(hours=2))


def _event(start: str, minutes: float, room: str = "Bad", removed: float | None = 100.0, valid: bool = True, **extra):
    started = datetime.fromisoformat(start)
    event = {"event_id": f"{room}:{start}", "room_key": room.lower(), "room_name": room, "started_at": started.isoformat(),
             "ended_at": (started + timedelta(minutes=minutes)).isoformat(), "duration_min": minutes, "removed_ml": removed,
             "measurement_valid": valid, "start_temperature_c": 21.04, "end_temperature_c": 19.5, "start_humidity_percent": 64.4,
             "end_humidity_percent": 55.2, "start_absolute_humidity_g_m3": 11.81, "end_absolute_humidity_g_m3": 9.4,
             "cross_ventilation": False, "recommendation_followed": True}
    event.update(extra)
    return event


EVENTS = [
    _event("2026-10-20T07:00:00+02:00", 10, "Bad", 150),
    _event("2026-10-20T07:05:00+02:00", 12, "Schlafzimmer", 90),
    _event("2026-10-20T21:00:00+02:00", 6, "Bad", None, valid=False),
    _event("2026-10-21T23:55:00+02:00", 15, "Küche", 40),  # over midnight: counts on the 21st
    _event("2026-10-22T22:30:00+00:00", 5, "Bad", 30),  # UTC 22:30 = 00:30 local on the 23rd
    {"started_at": "kaputt", "duration_min": 3},
    _event("2026-11-30T10:00:00+02:00", 5),  # outside the period
]


def test_one_row_per_day_for_the_whole_home():
    days = daily_summary(EVENTS, date(2026, 10, 20), date(2026, 10, 23), TZ, include_empty=False)
    assert [d["date"].isoformat() for d in days] == ["2026-10-20", "2026-10-21", "2026-10-23"]
    first = days[0]
    assert (first["count"], first["minutes"], first["avg_minutes"], first["removed_ml"], first["measured"], first["rooms"]) == (
        3, 28.0, 9.3, 240, 2, ["Bad", "Schlafzimmer"])
    assert days[1]["rooms"] == ["Küche"] and days[2]["count"] == 1
    with_empty = daily_summary(EVENTS, date(2026, 10, 20), date(2026, 10, 23), TZ, include_empty=True)
    assert [d["count"] for d in with_empty] == [3, 1, 0, 1]
    assert with_empty[2] == {"date": date(2026, 10, 22), "count": 0, "minutes": 0.0, "removed_ml": None, "measured": 0, "rooms": [], "avg_minutes": None}
    naive = daily_summary([_event("2026-10-20T07:00:00", 4)], date(2026, 10, 20), date(2026, 10, 20), TZ, include_empty=False)
    assert naive[0]["count"] == 1
    unmeasured = daily_summary([_event("2026-10-20T07:00:00+02:00", 4, valid=False)], date(2026, 10, 20), date(2026, 10, 20), TZ, include_empty=False)
    assert unmeasured[0]["removed_ml"] is None and unmeasured[0]["measured"] == 0


def test_period_totals():
    days = daily_summary(EVENTS, date(2026, 10, 20), date(2026, 10, 23), TZ, include_empty=True)
    assert period_totals(days) == {"days_with_airing": 3, "count": 5, "minutes": 48.0, "measured": 4, "removed_ml": 310,
                                   "avg_minutes_per_day": 16.0, "avg_minutes_per_airing": 9.6, "avg_removed_ml_per_day": 103}
    assert period_totals([]) == {"days_with_airing": 0, "count": 0, "minutes": 0, "measured": 0, "removed_ml": None,
                                 "avg_minutes_per_day": None, "avg_minutes_per_airing": None, "avg_removed_ml_per_day": None}


def _rows(text: str, delimiter: str):
    assert text.startswith("﻿")
    return list(csv.reader(io.StringIO(text[1:]), delimiter=delimiter))


def test_csv_per_day_includes_days_without_airing():
    rows = _rows(ventilation_csv(EVENTS, date(2026, 10, 20), date(2026, 10, 23), TZ, language="de", daily=True), ";")
    assert rows[0] == ["Datum", "Lüftungen", "Minuten gesamt", "Ø Minuten je Lüftung", "Entfernte Feuchte (ml)", "Gemessene Lüftungen", "Räume"]
    assert rows[1] == ["2026-10-20", "3", "28,0", "9,3", "240", "2", "Bad, Schlafzimmer"]
    assert rows[3] == ["2026-10-22", "0", "0,0", "", "", "0", ""]
    en = _rows(ventilation_csv(EVENTS, date(2026, 10, 20), date(2026, 10, 23), TZ, language="en", daily=True), ",")
    assert en[0][1] == "Ventilations" and en[1] == ["2026-10-20", "3", "28.0", "9.3", "240", "2", "Bad, Schlafzimmer"]


def test_csv_single_airings():
    events = [EVENTS[0], EVENTS[2], _event("2026-10-21T08:00:00+02:00", 5, "=SUMME(A1)", 20, cross_ventilation=True, recommendation_followed=None)]
    rows = _rows(ventilation_csv(events, date(2026, 10, 20), date(2026, 10, 21), TZ, language="de", daily=False), ";")
    assert rows[0][:6] == ["Datum", "Beginn", "Ende", "Raum", "Dauer (min)", "Entfernte Feuchte (ml)"]
    assert rows[1] == ["2026-10-20", "07:00", "07:10", "Bad", "10,0", "150", "ja", "21,0", "19,5", "64", "55", "11,81", "9,40", "nein", "ja"]
    assert rows[2][5:7] == ["", "nein"]  # not measured: no moisture value
    assert rows[3][3] == "'=SUMME(A1)" and rows[3][13:] == ["ja", ""]
    en = _rows(ventilation_csv([EVENTS[0], {"started_at": None}], date(2026, 10, 20), date(2026, 10, 20), TZ, language="en", daily=False), ",")
    assert en[1][4:7] == ["10.0", "150", "yes"] and en[2][:3] == ["", "", ""]


def _pdf_text(pdf: bytes) -> str:
    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF")
    return pdf.decode("latin1")


def test_daily_pdf_german_and_english_with_several_pages():
    days = daily_summary(EVENTS, date(2026, 10, 20), date(2026, 10, 23), TZ, include_empty=False)
    start, end = datetime(2026, 10, 20, tzinfo=TZ), datetime(2026, 10, 23, 23, 59, tzinfo=TZ)
    german = _pdf_text(build_daily_pdf(days, period_totals(days), start, end, "de"))
    assert "Lueftungsprotokoll - pro Tag" in german and "\xd8 MIN JE LUEFTUNG" in german and "\xd8 MIN PRO LUEFTUNGSTAG" in german and "20.10.2026" in german
    assert "240 ml" in german and "2/3" in german and "Bad, Schlafzimmer" in german and "9,3" in german
    english = _pdf_text(build_daily_pdf(days, period_totals(days), start, end, "en"))
    assert "Ventilation log - per day" in english and "AVG MIN PER AIRING" in english and "2026-10-20" in english and "9.3" in english
    many = [{"date": date(2026, 1, 1) + timedelta(days=i), "count": 1, "minutes": 5.0, "avg_minutes": 5.0, "removed_ml": None,
             "measured": 0, "rooms": ["Bad"]} for i in range(120)]
    pdf = _pdf_text(build_daily_pdf(many, period_totals(many), start, end, "de"))
    assert pdf.count("/Type /Page ") >= 3 and "/Count " in pdf
    empty = _pdf_text(build_daily_pdf([], period_totals([]), start, end, "de"))
    assert "/Count 1" in empty and "- ml" not in empty
