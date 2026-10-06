"""Local ventilation history and human-readable PDF export for FreshAirIQ."""
from __future__ import annotations

from datetime import datetime, timedelta
from math import isfinite
from typing import Any

RETENTION_DAYS = 730
MAX_EVENTS = 10000


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) else None


def compact_ventilation_event(event: dict[str, Any]) -> dict[str, Any]:
    """Keep only user-facing local evidence required for the ventilation log."""
    return {
        "event_id": str(event.get("event_id") or ""),
        "room_key": str(event.get("key") or ""),
        "room_name": str(event.get("name") or event.get("key") or "Raum"),
        "started_at": event.get("started_at"),
        "ended_at": event.get("ended_at"),
        "duration_min": _num(event.get("duration_min")),
        "opening_mode": event.get("opening_learning_mode"),
        "cross_ventilation": bool(event.get("cross_ventilation")),
        "recommendation_followed": (None if event.get("recommendation_followed") is None else bool(event.get("recommendation_followed"))),
        "removed_ml": _num(event.get("removed_ml")),
        "measurement_valid": bool(event.get("moisture_measurement_valid")),
        "start_temperature_c": _num(event.get("start_temperature_c")),
        "end_temperature_c": _num(event.get("end_temperature_c")),
        "start_humidity_percent": _num(event.get("start_humidity_percent")),
        "end_humidity_percent": _num(event.get("end_humidity_percent")),
        "start_absolute_humidity_g_m3": _num(event.get("start_absolute_humidity_g_m3")),
        "end_absolute_humidity_g_m3": _num(event.get("end_absolute_humidity_g_m3")),
    }


def append_ventilation_log(history: Any, events: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    """Append completed sessions once and prune the fully local history."""
    rows = [dict(item) for item in history if isinstance(item, dict)] if isinstance(history, list) else []
    existing = {str(item.get("event_id")) for item in rows if item.get("event_id")}
    for event in events:
        item = compact_ventilation_event(event)
        if item["event_id"] and item["event_id"] in existing:
            continue
        rows.append(item)
        if item["event_id"]:
            existing.add(item["event_id"])
    cutoff = now - timedelta(days=RETENTION_DAYS)
    kept: list[dict[str, Any]] = []
    for item in rows:
        try:
            ended = datetime.fromisoformat(str(item.get("ended_at")))
        except (TypeError, ValueError):
            continue
        if ended.tzinfo is None and cutoff.tzinfo is not None:
            ended = ended.replace(tzinfo=cutoff.tzinfo)
        if ended >= cutoff:
            kept.append(item)
    return kept[-MAX_EVENTS:]


def filter_ventilation_log(history: Any, start: datetime, end: datetime) -> list[dict[str, Any]]:
    """Return events overlapping the selected inclusive report period."""
    rows = []
    for item in history if isinstance(history, list) else []:
        if not isinstance(item, dict):
            continue
        try:
            started = datetime.fromisoformat(str(item.get("started_at")))
            ended = datetime.fromisoformat(str(item.get("ended_at")))
        except (TypeError, ValueError):
            continue
        if start.tzinfo is not None:
            started = started.replace(tzinfo=start.tzinfo) if started.tzinfo is None else started.astimezone(start.tzinfo)
            ended = ended.replace(tzinfo=start.tzinfo) if ended.tzinfo is None else ended.astimezone(start.tzinfo)
        try:
            overlaps = ended >= start and started <= end
        except TypeError:
            continue
        if overlaps:
            rows.append(dict(item))
    return sorted(rows, key=lambda x: str(x.get("started_at") or ""))


def _pdf_escape(text: Any) -> str:
    raw = str(text or "").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return raw.encode("cp1252", "replace").decode("latin1")


def _fmt_dt(value: Any) -> str:
    try:
        return datetime.fromisoformat(str(value)).strftime("%d.%m.%Y %H:%M")
    except (TypeError, ValueError):
        return "–"


def _fmt(value: Any, digits: int = 1) -> str:
    number = _num(value)
    return "–" if number is None else f"{number:.{digits}f}".replace(".", ",")


def build_ventilation_pdf(events: list[dict[str, Any]], start: datetime, end: datetime) -> bytes:
    """Generate a compact room-grouped A4 table PDF (PDF 1.4 / WinAnsi)."""
    total_min = sum(max(_num(e.get("duration_min")) or 0.0, 0.0) for e in events)
    valid_removed = [_num(e.get("removed_ml")) for e in events if e.get("measurement_valid")]
    valid_removed = [v for v in valid_removed if v is not None]
    room_names = sorted({str(e.get("room_name") or "Raum") for e in events})

    objects: list[bytes] = []
    def add(data: str | bytes) -> int:
        objects.append(data.encode("latin1") if isinstance(data, str) else data)
        return len(objects)

    catalog = add("<< /Type /Catalog /Pages 2 0 R >>")
    add(b"")
    font = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    font_bold = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    page_streams: list[list[str]] = []
    current: list[str] = []
    y = 0.0

    def text(x: float, yy: float, value: Any, size: int = 8, bold: bool = False, rgb=(0.12, 0.16, 0.19)) -> None:
        r, g, b = rgb
        current.extend(["BT", f"{r:.3f} {g:.3f} {b:.3f} rg", f"/{'F2' if bold else 'F1'} {size} Tf", f"1 0 0 1 {x:.1f} {yy:.1f} Tm ({_pdf_escape(value)}) Tj", "ET"])

    def rect(x: float, yy: float, w: float, h: float, fill, stroke=None, width: float = 0.7) -> None:
        r, g, b = fill
        current.append(f"{r:.3f} {g:.3f} {b:.3f} rg")
        if stroke is None:
            current.append(f"{x:.1f} {yy:.1f} {w:.1f} {h:.1f} re f")
        else:
            sr, sg, sb = stroke
            current.extend([f"{sr:.3f} {sg:.3f} {sb:.3f} RG", f"{width:.2f} w", f"{x:.1f} {yy:.1f} {w:.1f} {h:.1f} re B"])

    def line(x1: float, y1: float, x2: float, y2: float, rgb=(0.78, 0.84, 0.87), width: float = 0.5) -> None:
        r, g, b = rgb
        current.extend([f"{r:.3f} {g:.3f} {b:.3f} RG", f"{width:.2f} w", f"{x1:.1f} {y1:.1f} m {x2:.1f} {y2:.1f} l S"])

    def header(first: bool = False) -> None:
        nonlocal y
        rect(0, 0, 595, 842, (0.985, 0.990, 0.992))
        rect(0, 770, 595, 72, (0.055, 0.090, 0.115))
        rect(42, 789, 28, 28, (0.20, 0.72, 0.86))
        text(50, 798, "FA", 10, True, (1, 1, 1))
        text(82, 805, "FreshAirIQ", 19, True, (1, 1, 1))
        text(82, 788, "Lueftungsprotokoll", 10, False, (0.72, 0.82, 0.87))
        text(444, 801, start.strftime("%d.%m.%Y"), 8, True, (0.75, 0.85, 0.89))
        text(444, 787, f"bis {end.strftime('%d.%m.%Y')}", 8, False, (0.75, 0.85, 0.89))
        y = 744
        if first:
            text(42, y, "Zusammenfassung", 12, True); y -= 42
            boxes = [
                ("LUEFTUNGEN", str(len(events))),
                ("GESAMTDAUER", f"{_fmt(total_min, 0)} min"),
                ("RAEUME", str(len(room_names))),
                ("FEUCHTEBILANZ", f"{_fmt(sum(valid_removed), 0)} ml" if valid_removed else "-"),
            ]
            x = 42
            for label, value in boxes:
                rect(x, y, 119, 36, (0.94, 0.965, 0.975), (0.79, 0.88, 0.91))
                text(x + 8, y + 23, label, 6, True, (0.34, 0.48, 0.55))
                text(x + 8, y + 8, value, 10, True, (0.07, 0.20, 0.25))
                x += 128
            y -= 18

    def finish_page() -> None:
        line(42, 34, 553, 34, (0.86, 0.89, 0.91), 0.5)
        text(42, 20, "FreshAirIQ - lokale Sensordokumentation", 6, False, (0.45, 0.52, 0.56))
        page_streams.append(list(current)); current.clear()

    # Compact table requested in GitHub issue #9.  One row represents one
    # completed ventilation session; rooms are grouped so repeated room names
    # no longer consume a full card per event.
    cols = [
        ("Datum", 42, 55), ("Zeit", 97, 72), ("Dauer", 169, 48),
        ("Temperatur", 217, 85), ("Luftfeuchte", 302, 78),
        ("Abs. Feuchte", 380, 86), ("Bilanz", 466, 45), ("Empf.", 511, 42),
    ]
    row_h = 22
    table_w = 511

    def table_header(room: str, continued: bool = False) -> None:
        nonlocal y
        label = f"{room}{' - Fortsetzung' if continued else ''}"
        rect(42, y - 24, table_w, 24, (0.93, 0.965, 0.975), (0.79, 0.88, 0.91))
        text(50, y - 16, label[:72], 10, True, (0.05, 0.22, 0.28)); y -= 24
        rect(42, y - 28, table_w, 28, (0.965, 0.975, 0.980), (0.79, 0.84, 0.87))
        for label, x, _w in cols:
            text(x + 3, y - 17, label, 6, True, (0.30, 0.40, 0.45))
        y -= 28

    def row_values(event: dict[str, Any]) -> list[str]:
        try:
            started = datetime.fromisoformat(str(event.get("started_at")))
            ended = datetime.fromisoformat(str(event.get("ended_at")))
            date = started.strftime("%d.%m.%y")
            period = f"{started.strftime('%H:%M')}-{ended.strftime('%H:%M')}"
        except (TypeError, ValueError):
            date, period = "-", "-"
        temp = f"{_fmt(event.get('start_temperature_c'))} -> {_fmt(event.get('end_temperature_c'))}"
        rh = f"{_fmt(event.get('start_humidity_percent'), 0)} -> {_fmt(event.get('end_humidity_percent'), 0)}"
        ah = f"{_fmt(event.get('start_absolute_humidity_g_m3'), 2)} -> {_fmt(event.get('end_absolute_humidity_g_m3'), 2)}"
        effect = f"{_fmt(event.get('removed_ml'), 0)} ml" if event.get("measurement_valid") else "n.v."
        followed = "Ja" if event.get("recommendation_followed") is True else ("Nein" if event.get("recommendation_followed") is False else "Nicht erfasst")
        return [date, period, f"{_fmt(event.get('duration_min'), 0)} min", temp, rh, ah, effect, followed]

    header(True)
    if not events:
        rect(42, y - 66, 511, 54, (0.965, 0.975, 0.980), (0.84, 0.88, 0.90))
        text(58, y - 34, "Keine erfassten Lueftungsvorgaenge im gewaehlten Zeitraum.", 10, True)
        text(58, y - 49, "Es werden ausschliesslich lokal gespeicherte, abgeschlossene Vorgaenge dokumentiert.", 8, False, (0.38, 0.46, 0.50))
    else:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for event in events:
            grouped.setdefault(str(event.get("room_name") or event.get("name") or "Raum"), []).append(event)
        for room in sorted(grouped):
            if y - 52 - row_h < 105:
                finish_page(); header(False)
            table_header(room)
            for event in grouped[room]:
                if y - row_h < 105:
                    finish_page(); header(False); table_header(room, True)
                rect(42, y - row_h, table_w, row_h, (1, 1, 1), (0.86, 0.89, 0.91), 0.4)
                values = row_values(event)
                for value, (_label, x, _w) in zip(values, cols):
                    text(x + 3, y - 14, value, 6, False)
                y -= row_h
            y -= 10

    text(42, 84, "Hinweis", 8, True, (0.30, 0.40, 0.45))
    text(42, 70, "Dieses Protokoll dokumentiert die von FreshAirIQ und Home Assistant erfassten Sensordaten.", 7, False, (0.42, 0.49, 0.53))
    text(42, 58, "Es ist keine rechtliche Bewertung oder Garantie fuer ein bestimmtes Lueftungsverhalten.", 7, False, (0.42, 0.49, 0.53))
    finish_page()

    page_ids = []
    for cmds in page_streams:
        stream = "\n".join(cmds).encode("latin1")
        content_id = add(f"<< /Length {len(stream)} >>\nstream\n".encode("latin1") + stream + b"\nendstream")
        page_id = add(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 {font} 0 R /F2 {font_bold} 0 R >> >> /Contents {content_id} 0 R >>")
        page_ids.append(page_id)
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(f'{i} 0 R' for i in page_ids)}] /Count {len(page_ids)} >>".encode("latin1")
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for idx, obj in enumerate(objects, 1):
        offsets.append(len(out)); out += f"{idx} 0 obj\n".encode(); out += obj; out += b"\nendobj\n"
    xref = len(out); out += f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode()
    for offset in offsets[1:]: out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects)+1} /Root {catalog} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)
