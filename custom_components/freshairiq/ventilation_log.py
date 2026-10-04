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
        "recommendation_followed": bool(event.get("recommendation_followed")),
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
        if started.tzinfo is None and start.tzinfo is not None:
            started = started.replace(tzinfo=start.tzinfo)
            ended = ended.replace(tzinfo=start.tzinfo)
        if ended >= start and started <= end:
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
    """Generate a dependency-free, local PDF report (PDF 1.4 / WinAnsi)."""
    total_min = sum(max(_num(e.get("duration_min")) or 0.0, 0.0) for e in events)
    valid_removed = [_num(e.get("removed_ml")) for e in events if e.get("measurement_valid")]
    valid_removed = [v for v in valid_removed if v is not None]
    room_names = sorted({str(e.get("room_name") or "Raum") for e in events})
    lines = [
        ("FreshAirIQ Lüftungsprotokoll", 16, True),
        (f"Zeitraum: {start.strftime('%d.%m.%Y')} bis {end.strftime('%d.%m.%Y')}", 10, False),
        ("Lokale Dokumentation der durch Sensoren erfassten Lüftungsvorgänge", 9, False),
        ("", 9, False),
        (f"Erfasste Lüftungen: {len(events)}   Gesamtdauer: {_fmt(total_min, 0)} min   Räume: {len(room_names)}", 10, True),
        (f"Gemessene Feuchtebilanz: {_fmt(sum(valid_removed), 0)} ml" if valid_removed else "Gemessene Feuchtebilanz: keine vollständigen Messwerte im Zeitraum", 10, False),
        ("", 9, False),
        ("Chronologisches Protokoll", 12, True),
    ]
    for event in events:
        effect = f"{_fmt(event.get('removed_ml'), 0)} ml" if event.get("measurement_valid") else "Messwert nicht vollständig"
        followed = "ja" if event.get("recommendation_followed") else "nein/nicht erfasst"
        lines.extend([
            (f"{_fmt_dt(event.get('started_at'))} – {_fmt_dt(event.get('ended_at'))} | {event.get('room_name') or event.get('name') or 'Raum'}", 10, True),
            (f"Dauer {_fmt(event.get('duration_min'), 1)} min | Feuchtebilanz {effect} | Empfehlung befolgt: {followed}", 9, False),
            (f"Klima: {_fmt(event.get('start_temperature_c'))} → {_fmt(event.get('end_temperature_c'))} °C | {_fmt(event.get('start_humidity_percent'),0)} → {_fmt(event.get('end_humidity_percent'),0)} % rF | {_fmt(event.get('start_absolute_humidity_g_m3'),2)} → {_fmt(event.get('end_absolute_humidity_g_m3'),2)} g/m³", 9, False),
            ("", 6, False),
        ])
    lines.extend([
        ("Hinweis", 10, True),
        ("Dieses Protokoll dokumentiert die von FreshAirIQ und Home Assistant erfassten Sensordaten. Es ist keine rechtliche Bewertung oder Garantie für ein bestimmtes Lüftungsverhalten.", 8, False),
    ])

    # Wrap into fixed-width text lines; generate as many A4 pages as necessary.
    wrapped: list[tuple[str, int, bool]] = []
    for text, size, bold in lines:
        width = 92 if size <= 9 else 82
        words = text.split()
        if not words:
            wrapped.append(("", size, bold)); continue
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if len(candidate) > width and current:
                wrapped.append((current, size, bold)); current = word
            else:
                current = candidate
        wrapped.append((current, size, bold))

    pages: list[list[tuple[str, int, bool]]] = []
    page: list[tuple[str, int, bool]] = []
    y = 790
    for row in wrapped:
        step = max(row[1] + 4, 11)
        if y - step < 48:
            pages.append(page); page = []; y = 790
        page.append(row); y -= step
    if page or not pages: pages.append(page)

    objects: list[bytes] = []
    def add(data: str | bytes) -> int:
        objects.append(data.encode("latin1") if isinstance(data, str) else data); return len(objects)
    catalog = add("<< /Type /Catalog /Pages 2 0 R >>")
    add(b"")  # pages placeholder
    font = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    font_bold = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    page_ids = []
    for rows in pages:
        cmds = ["BT", "1 0 0 1 48 790 Tm"]
        current_y = 790
        for text, size, bold in rows:
            step = max(size + 4, 11)
            cmds.append(f"/{'F2' if bold else 'F1'} {size} Tf")
            cmds.append(f"1 0 0 1 48 {current_y} Tm ({_pdf_escape(text)}) Tj")
            current_y -= step
        cmds.append("ET")
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
