"""Ventilation log per day and as CSV (pure, 0.26.5.3).

User feedback (FAIQ-FB-833697E303F8): over a longer period the PDF should show
on which days the home was aired – minutes in total and on average, and the
moisture removed – compactly, and the data should also be available as CSV.

* ``daily_summary`` – one row per day for the whole home (all rooms), an airing
  counts on the day it started; moisture is summed over measured airings only
  and the number of measured airings is stated;
* ``period_totals`` – sums and averages of the period;
* ``ventilation_csv`` – single airings or one row per day (days without airing
  included, so charts have no gaps); German: semicolon and decimal comma,
  English: comma and decimal point; UTF-8 with BOM so spreadsheets detect it;
* ``build_daily_pdf`` – the daily table as PDF (days without airing left out).
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timedelta, tzinfo
import io
from typing import Any

from .ventilation_log import _PDF_EN, _num, _pdf_escape, _serialise_pdf


def _local(value: Any, tz: tzinfo) -> datetime | None:
    try:
        stamp = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return stamp.replace(tzinfo=tz) if stamp.tzinfo is None else stamp.astimezone(tz)


def _minutes(event: dict[str, Any]) -> float:
    return max(_num(event.get("duration_min")) or 0.0, 0.0)


def daily_summary(events: list[dict[str, Any]], start: date, end: date, tz: tzinfo, *, include_empty: bool) -> list[dict[str, Any]]:
    """One row per day of the period (whole home); airings count on their start day."""
    days: dict[date, dict[str, Any]] = {}
    for event in events:
        started = _local(event.get("started_at"), tz)
        if started is None or not start <= started.date() <= end:
            continue
        day = days.setdefault(started.date(), {"date": started.date(), "count": 0, "minutes": 0.0, "removed_ml": 0.0, "measured": 0, "rooms": set()})
        day["count"] += 1
        day["minutes"] += _minutes(event)
        day["rooms"].add(str(event.get("room_name") or event.get("room_key") or "?"))
        removed = _num(event.get("removed_ml"))
        if event.get("measurement_valid") and removed is not None:
            day["removed_ml"] += removed
            day["measured"] += 1
    rows = []
    current = start
    while current <= end:
        day = days.get(current)
        if day is None and include_empty:
            day = {"date": current, "count": 0, "minutes": 0.0, "removed_ml": 0.0, "measured": 0, "rooms": set()}
        if day is not None:
            rows.append({**day, "rooms": sorted(day["rooms"]), "avg_minutes": round(day["minutes"] / day["count"], 1) if day["count"] else None,
                         "minutes": round(day["minutes"], 1), "removed_ml": round(day["removed_ml"]) if day["measured"] else None})
        current += timedelta(days=1)
    return rows


def period_totals(days: list[dict[str, Any]]) -> dict[str, Any]:
    aired = [day for day in days if day["count"]]
    count = sum(day["count"] for day in aired)
    minutes = sum(day["minutes"] for day in aired)
    measured = sum(day["measured"] for day in aired)
    removed = sum(day["removed_ml"] or 0.0 for day in aired)
    return {
        "days_with_airing": len(aired), "count": count, "minutes": round(minutes, 1), "measured": measured,
        "removed_ml": round(removed) if measured else None,
        "avg_minutes_per_day": round(minutes / len(aired), 1) if aired else None,
        "avg_minutes_per_airing": round(minutes / count, 1) if count else None,
        "avg_removed_ml_per_day": round(removed / len(aired)) if aired and measured else None,
    }


_CSV_TEXT = {
    "de": {
        "session": ["Datum", "Beginn", "Ende", "Raum", "Dauer (min)", "Entfernte Feuchte (ml)", "Gemessen", "Temperatur vorher (°C)",
                    "Temperatur nachher (°C)", "Luftfeuchte vorher (%)", "Luftfeuchte nachher (%)", "Abs. Feuchte vorher (g/m³)",
                    "Abs. Feuchte nachher (g/m³)", "Querlüftung", "Empfehlung befolgt"],
        "day": ["Datum", "Lüftungen", "Minuten gesamt", "Ø Minuten je Lüftung", "Entfernte Feuchte (ml)", "Gemessene Lüftungen", "Räume"],
        "yes": "ja", "no": "nein",
    },
    "en": {
        "session": ["Date", "Start", "End", "Room", "Duration (min)", "Moisture removed (mL)", "Measured", "Temperature before (°C)",
                    "Temperature after (°C)", "Humidity before (%)", "Humidity after (%)", "Abs. humidity before (g/m³)",
                    "Abs. humidity after (g/m³)", "Cross ventilation", "Recommendation followed"],
        "day": ["Date", "Ventilations", "Total minutes", "Avg minutes per ventilation", "Moisture removed (mL)", "Measured ventilations", "Rooms"],
        "yes": "yes", "no": "no",
    },
}


def _cell(value: Any, german: bool, digits: int = 1) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        text = f"{value:.{digits}f}" if isinstance(value, float) else str(value)
        return text.replace(".", ",") if german else text
    text = str(value)
    # never let a spreadsheet run a room name as a formula
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


def ventilation_csv(events: list[dict[str, Any]], start: date, end: date, tz: tzinfo, *, language: str, daily: bool) -> str:
    german = str(language or "de").lower().startswith("de")
    words = _CSV_TEXT["de" if german else "en"]
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";" if german else ",", lineterminator="\r\n")
    if daily:
        writer.writerow(words["day"])
        for day in daily_summary(events, start, end, tz, include_empty=True):
            writer.writerow([day["date"].isoformat(), day["count"], _cell(day["minutes"], german), _cell(day["avg_minutes"], german),
                             _cell(day["removed_ml"], german), day["measured"], _cell(", ".join(day["rooms"]), german)])
    else:
        writer.writerow(words["session"])
        flag = lambda value: "" if value is None else (words["yes"] if value else words["no"])  # noqa: E731
        for event in events:
            started, ended = _local(event.get("started_at"), tz), _local(event.get("ended_at"), tz)
            removed = _num(event.get("removed_ml")) if event.get("measurement_valid") else None
            writer.writerow([
                started.date().isoformat() if started else "", started.strftime("%H:%M") if started else "", ended.strftime("%H:%M") if ended else "",
                _cell(event.get("room_name") or event.get("room_key"), german), _cell(_minutes(event), german), _cell(removed, german, 0),
                flag(bool(event.get("measurement_valid"))),
                *(_cell(_num(event.get(key)), german, digits) for key, digits in (
                    ("start_temperature_c", 1), ("end_temperature_c", 1), ("start_humidity_percent", 0), ("end_humidity_percent", 0),
                    ("start_absolute_humidity_g_m3", 2), ("end_absolute_humidity_g_m3", 2))),
                flag(event.get("cross_ventilation")), flag(event.get("recommendation_followed")),
            ])
    return "﻿" + out.getvalue()


_DAILY_EN = {
    "Lueftungsprotokoll - pro Tag": "Ventilation log - per day", "LUEFTUNGSTAGE": "DAYS WITH AIRING", "LUEFTUNGEN": "VENTILATIONS",
    "MINUTEN GESAMT": "TOTAL MINUTES", "ENTFERNTE FEUCHTE": "MOISTURE REMOVED", "O MIN PRO LUEFTUNGSTAG": "AVG MIN PER DAY",
    "O MIN JE LUEFTUNG": "AVG MIN PER AIRING", "O FEUCHTE PRO LUEFTUNGSTAG": "AVG MOISTURE PER DAY", "GEMESSEN": "MEASURED",
    "Lueftungen": "Airings", "Minuten": "Minutes", "O je Lueftung": "Avg/airing", "Entfernte Feuchte": "Moisture removed",
    "Gemessen": "Measured", "Raeume": "Rooms", "von": "of", "Eine Lueftung zaehlt am Tag ihres Beginns. Feuchte nur aus gemessenen Lueftungen.":
    "An airing counts on the day it started. Moisture only from measured airings.",
}


def build_daily_pdf(days: list[dict[str, Any]], totals: dict[str, Any], start: datetime, end: datetime, language: str = "de") -> bytes:
    """Compact A4 PDF: summary boxes and one row per day with airing."""
    english = not str(language or "de").lower().startswith("de")
    tr = lambda value: (_DAILY_EN.get(value) or _PDF_EN.get(value, value)) if english else ("Ø " + value[2:] if value.startswith("O ") else value)  # noqa: E731
    num = lambda value, digits=0: "-" if value is None else (f"{value:.{digits}f}" if english else f"{value:.{digits}f}".replace(".", ","))  # noqa: E731
    date_fmt = "%Y-%m-%d" if english else "%d.%m.%Y"
    objects: list[bytes] = []

    def add(data: str | bytes) -> int:
        objects.append(data.encode("latin1") if isinstance(data, str) else data)
        return len(objects)

    catalog = add("<< /Type /Catalog /Pages 2 0 R >>")
    add(b"")
    font = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    font_bold = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    pages: list[list[str]] = []
    cmds: list[str] = []

    def text(x: float, y: float, value: Any, size: int = 8, bold: bool = False, rgb=(0.12, 0.16, 0.19)) -> None:
        cmds.extend(["BT", "{:.3f} {:.3f} {:.3f} rg".format(*rgb), f"/{'F2' if bold else 'F1'} {size} Tf", f"1 0 0 1 {x:.1f} {y:.1f} Tm ({_pdf_escape(value)}) Tj", "ET"])

    def rect(x: float, y: float, w: float, h: float, fill, stroke=(0.84, 0.88, 0.90)) -> None:
        cmds.extend(["{:.3f} {:.3f} {:.3f} rg".format(*fill), "{:.3f} {:.3f} {:.3f} RG".format(*stroke), "0.5 w", f"{x:.1f} {y:.1f} {w:.1f} {h:.1f} re B"])

    def page_head() -> float:
        rect(0, 0, 595, 842, (0.985, 0.990, 0.992), (0.985, 0.990, 0.992))
        rect(0, 770, 595, 72, (0.055, 0.090, 0.115), (0.055, 0.090, 0.115))
        text(42, 805, "FreshAirIQ", 19, True, (1, 1, 1))
        text(42, 788, tr("Lueftungsprotokoll - pro Tag"), 10, False, (0.72, 0.82, 0.87))
        text(444, 801, start.strftime(date_fmt), 8, True, (0.75, 0.85, 0.89))
        text(444, 787, f"{tr('bis')} {end.strftime(date_fmt)}", 8, False, (0.75, 0.85, 0.89))
        return 744

    cols = [("Datum", 42, 70), ("Lueftungen", 112, 52), ("Minuten", 164, 52), ("O je Lueftung", 216, 62),
            ("Entfernte Feuchte", 278, 80), ("Gemessen", 358, 52), ("Raeume", 410, 143)]

    def table_head(y: float) -> float:
        rect(42, y - 22, 511, 22, (0.93, 0.965, 0.975), (0.79, 0.88, 0.91))
        for label, x, _w in cols:
            text(x + 3, y - 14, tr(label), 6, True, (0.30, 0.40, 0.45))
        return y - 22

    y = page_head()
    boxes = [
        ("LUEFTUNGSTAGE", str(totals["days_with_airing"])), ("LUEFTUNGEN", str(totals["count"])),
        ("MINUTEN GESAMT", f"{num(totals['minutes'])} min"), ("ENTFERNTE FEUCHTE", f"{num(totals['removed_ml'])} ml" if totals["removed_ml"] is not None else "-"),
        ("O MIN PRO LUEFTUNGSTAG", f"{num(totals['avg_minutes_per_day'], 1)} min"), ("O MIN JE LUEFTUNG", f"{num(totals['avg_minutes_per_airing'], 1)} min"),
        ("O FEUCHTE PRO LUEFTUNGSTAG", f"{num(totals['avg_removed_ml_per_day'])} ml" if totals["avg_removed_ml_per_day"] is not None else "-"),
        ("GEMESSEN", f"{totals['measured']} {tr('von')} {totals['count']}"),
    ]
    for index, (label, value) in enumerate(boxes):
        x, top = 42 + (index % 4) * 128, y - 36 - (index // 4) * 44
        rect(x, top, 119, 36, (0.94, 0.965, 0.975), (0.79, 0.88, 0.91))
        text(x + 8, top + 23, tr(label), 6, True, (0.34, 0.48, 0.55))
        text(x + 8, top + 8, value, 10, True, (0.07, 0.20, 0.25))
    y = table_head(y - 36 - 44 - 18)
    for day in days:
        if y - 18 < 70:
            text(42, 40, "FreshAirIQ", 6, False, (0.45, 0.52, 0.56))
            pages.append(cmds[:]); cmds.clear()
            y = table_head(page_head())
        rect(42, y - 18, 511, 18, (1, 1, 1), (0.86, 0.89, 0.91))
        removed = f"{num(day['removed_ml'])} ml" if day["removed_ml"] is not None else "-"
        values = [day["date"].strftime(date_fmt), str(day["count"]), num(day["minutes"]), num(day["avg_minutes"], 1),
                  removed, f"{day['measured']}/{day['count']}", ", ".join(day["rooms"])[:42]]
        for value, (_label, x, _w) in zip(values, cols):
            text(x + 3, y - 12, value, 6)
        y -= 18
    text(42, 52, tr("Eine Lueftung zaehlt am Tag ihres Beginns. Feuchte nur aus gemessenen Lueftungen."), 7, False, (0.42, 0.49, 0.53))
    text(42, 40, "FreshAirIQ", 6, False, (0.45, 0.52, 0.56))
    pages.append(cmds[:])
    return _serialise_pdf(add=add, catalog=catalog, font=font, font_bold=font_bold, objects=objects, page_streams=pages)
