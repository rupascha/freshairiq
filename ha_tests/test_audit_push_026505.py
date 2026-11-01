"""0.26.5.5 audit: F03 push text names both the bedroom close and the shower room kept open; F02 minutes since the source ended."""
from __future__ import annotations

import pytest

from custom_components.freshairiq.notifications import _house_message
from tests.test_audit_fixes_026505 import shower_and_bedroom_chain


@pytest.mark.parametrize("hard", [True, False])
def test_house_push_says_close_the_bedroom_and_keep_the_shower_room_open(hard) -> None:
    out, rooms = shower_and_bedroom_chain(hard)
    title, text = _house_message(out, rooms)
    assert title == "FreshAirIQ · Jetzt schließen"
    assert text.startswith("Schlafzimmer schließen · Bad offen lassen")


def test_minutes_since_the_source_ended_from_the_stored_time_stamp() -> None:
    from datetime import datetime, timezone
    from custom_components.freshairiq.coordinator_room_model import _minutes_since
    from tests._source import module_source

    now = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
    assert _minutes_since("2026-10-30T11:57:00+00:00", now) == pytest.approx(3.0)
    assert _minutes_since(None, now) is None and _minutes_since("kaputt", now) is None
    assert _minutes_since("2026-10-30T11:57:00", now) is None  # naive vs aware: unknown, never a crash
    assert "moisture_source_ended_min=_minutes_since(moisture_source.get(\"last_ended_at\"), now)" in module_source("coordinator")
