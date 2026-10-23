"""E09 regressions: nightly diagnostics uploads spread over 00:30-06:00.

Time base: the local Home Assistant time zone (``dt_util.now()``), as before.
Acceptance limits were fixed before the first run (work order E09):
* every slot lies in [00:30:00, 06:00:00) local time;
* with 10 000 synthetic installations each 5-minute bucket of the 330-minute
  window is used and holds at most 125 % of the uniform expectation;
* no single minute holds more than twice the expected 30.3 installations and no
  single second more than 5 (natural collisions remain possible);
* per installation: same slot after a restart, one upload per night, no
  catch-up outside the window, DST nights neither skip nor duplicate.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from custom_components.freshairiq.diagnostic_transport import (
    NIGHT_WINDOW_END_SECONDS,
    NIGHT_WINDOW_SECONDS,
    NIGHT_WINDOW_START_SECONDS,
    deterministic_upload_offset_seconds,
    deterministic_upload_slot,
    effective_reporting_mode,
    in_upload_window,
    next_nightly_upload_time,
    nightly_upload_time,
    retry_delay_seconds,
    upload_due,
)
from tests._source import module_source

BERLIN = ZoneInfo("Europe/Berlin")
INSTALLS = [f"faiq-synthetic-{i:05d}" for i in range(10_000)]
ROOT = Path(__file__).resolve().parents[1]


def test_window_constants_are_0030_to_0600():
    assert NIGHT_WINDOW_START_SECONDS == 30 * 60
    assert NIGHT_WINDOW_END_SECONDS == 6 * 3600
    assert NIGHT_WINDOW_SECONDS == 330 * 60


def test_slots_cover_the_whole_window_evenly():
    offsets = [deterministic_upload_offset_seconds(i) for i in INSTALLS]
    assert min(offsets) >= NIGHT_WINDOW_START_SECONDS
    assert max(offsets) < NIGHT_WINDOW_END_SECONDS
    buckets = Counter((o - NIGHT_WINDOW_START_SECONDS) // 300 for o in offsets)
    expected = len(INSTALLS) / 66
    assert set(buckets) == set(range(66))  # including both window edges
    assert max(buckets.values()) <= expected * 1.25
    minutes = Counter(o // 60 for o in offsets)
    assert max(minutes.values()) <= 2 * len(INSTALLS) / 330
    seconds = Counter(offsets)
    assert max(seconds.values()) <= 5
    # No shared 03:00 wave: 03:00-03:01 holds about 1/330 of all installations.
    assert sum(1 for o in offsets if 3 * 3600 <= o < 3 * 3600 + 60) <= 2 * len(INSTALLS) / 330


def test_slot_is_stable_per_installation_and_minute_view_is_compatible():
    for install in INSTALLS[:50]:
        offset = deterministic_upload_offset_seconds(install)
        assert deterministic_upload_offset_seconds(install) == offset  # e.g. after a restart
        assert deterministic_upload_slot(install) == (offset // 3600, (offset % 3600) // 60)
    # Different installations get different slots; rare natural collisions are allowed.
    assert len({deterministic_upload_offset_seconds(i) for i in INSTALLS[:50]}) >= 48


def _simulate(install: str, start: datetime, hours: int, *, mode: str = "daily", step_s: int = 900,
              online=lambda t: True, last: datetime | None = None):
    """Drive upload_due like telemetry.py: a 15-minute check grid plus the
    exact slot timer (next_nightly_upload_time); every due check succeeds."""
    uploads: list[datetime] = []
    utc = start.astimezone(timezone.utc)
    end = utc + timedelta(hours=hours)
    checks = {utc + timedelta(seconds=n * step_s) for n in range(hours * 3600 // step_s)}
    cursor = start
    while cursor.astimezone(timezone.utc) < end:
        slot = next_nightly_upload_time(cursor, install)
        checks.add(slot.astimezone(timezone.utc))
        cursor = slot + timedelta(seconds=1)
    for point in sorted(c for c in checks if c < end):
        now = point.astimezone(start.tzinfo)
        if not online(now):
            continue
        if upload_due(mode, now, install, last_success_at=last.isoformat() if last else None):
            uploads.append(now)
            last = now
    return uploads


def test_one_upload_per_night_inside_the_window():
    for install in INSTALLS[:40]:
        uploads = _simulate(install, datetime(2026, 10, 12, 12, 0, tzinfo=BERLIN), 72)
        assert len(uploads) == 3
        assert len({u.date() for u in uploads}) == 3
        for upload in uploads:
            assert in_upload_window(upload, install)
            assert upload == nightly_upload_time(upload, install)  # exactly at the slot


def test_dst_nights_neither_skip_nor_duplicate():
    for night in (datetime(2026, 3, 28, 22, 0, tzinfo=BERLIN), datetime(2026, 10, 24, 22, 0, tzinfo=BERLIN)):
        for install in INSTALLS[:300]:
            uploads = _simulate(install, night, 12)
            assert len(uploads) == 1, (night, install, uploads)
            local = uploads[0]
            assert (0, 30) <= (local.hour, local.minute) < (6, 0)


def test_missed_slot_waits_for_next_night_instead_of_a_daytime_wave():
    # Home Assistant offline the whole night, back at 07:00 (e.g. after an update).
    restart = datetime(2026, 10, 14, 7, 0, tzinfo=BERLIN)
    yesterday = datetime(2026, 10, 13, 3, 0, tzinfo=BERLIN).isoformat()
    assert not any(upload_due("daily", restart, i, last_success_at=yesterday) for i in INSTALLS)
    install = INSTALLS[7]
    uploads = _simulate(install, datetime(2026, 10, 14, 0, 0, tzinfo=BERLIN), 48,
                        online=lambda t: t >= restart)
    assert len(uploads) == 1 and uploads[0].date() == datetime(2026, 10, 15).date()


def test_many_clients_restarting_together_inside_the_window_stay_spread():
    restart = datetime(2026, 10, 14, 2, 0, tzinfo=BERLIN)
    yesterday = datetime(2026, 10, 13, 2, 0, tzinfo=BERLIN).isoformat()
    due_now = sum(upload_due("daily", restart, i, last_success_at=yesterday) for i in INSTALLS)
    # Only installations whose slot already passed tonight (00:30-02:00) are due:
    expected = len(INSTALLS) * 90 / 330
    assert 0.8 * expected <= due_now <= 1.2 * expected
    nxt = Counter(next_nightly_upload_time(restart, i).replace(second=0) for i in INSTALLS
                  if not upload_due("daily", restart, i, last_success_at=yesterday))
    assert max(nxt.values()) <= 2 * len(INSTALLS) / 330


def test_retry_backoff_is_individual_bounded_and_honours_retry_after():
    assert retry_delay_seconds(1) == 300  # unchanged without installation id
    delays = {retry_delay_seconds(1, i) for i in INSTALLS[:200]}
    assert min(delays) >= 300 and max(delays) <= 375
    assert len(delays) > 50
    assert retry_delay_seconds(3, "x") == retry_delay_seconds(3, "x")
    assert retry_delay_seconds(99, "x") <= 6 * 3600 * 1.25
    assert retry_delay_seconds(1, "x", retry_after="1800") == 1800
    assert retry_delay_seconds(1, None, retry_after=60) == 300  # never shorter than backoff
    assert retry_delay_seconds(1, None, retry_after="bad") == 300
    assert retry_delay_seconds(1, None, retry_after=10 ** 9) == 300  # absurd values ignored


def test_retry_after_0600_waits_for_next_night():
    install = INSTALLS[3]
    late = datetime(2026, 10, 14, 6, 0, 1, tzinfo=BERLIN)
    assert upload_due("daily", late, install, last_success_at=None) is False
    assert upload_due("daily", nightly_upload_time(late + timedelta(days=1), install), install) is True


def test_weekly_missed_slot_is_taken_up_in_a_following_night():
    install = INSTALLS[11]
    history = datetime(2026, 10, 4, 12, 0, tzinfo=BERLIN)  # last weekly upload before the run
    uploads = _simulate(install, datetime(2026, 10, 5, 0, 0, tzinfo=BERLIN), 24 * 21, mode="weekly", last=history)
    assert len(uploads) == 3 and all(in_upload_window(u, install) for u in uploads)
    weekday = uploads[0].weekday()
    offline_night = [u for u in uploads if u.date() == uploads[1].date()][0]
    uploads = _simulate(install, datetime(2026, 10, 5, 0, 0, tzinfo=BERLIN), 24 * 21, mode="weekly", last=history,
                        online=lambda t: t.date() != offline_night.date())
    assert len(uploads) == 3
    assert uploads[1].date() == offline_night.date() + timedelta(days=1)
    assert all(in_upload_window(u, install) for u in uploads)
    assert uploads[2].weekday() == weekday


def test_error_mode_opt_out_and_manual_paths_are_unchanged():
    noon = datetime(2026, 10, 14, 12, 0, tzinfo=BERLIN)
    assert upload_due("errors", noon, INSTALLS[0], problem_fingerprint="a", last_problem_fingerprint="b") is True
    assert effective_reporting_mode({"diagnostics_reporting_mode": "daily"}) == "off"
    assert upload_due("off", nightly_upload_time(noon, INSTALLS[0]), INSTALLS[0]) is False
    telemetry = module_source("telemetry")
    # Manual/support sends bypass the cadence (force/manual) exactly as before.
    assert "if not force and not first_sync_due and not upload_due(" in telemetry
    assert "async_track_point_in_time(self.hass, self._slot_reached, target)" in telemetry
    assert "retry_delay_seconds(failures, installation_id, self._retry_after_seconds)" in telemetry
