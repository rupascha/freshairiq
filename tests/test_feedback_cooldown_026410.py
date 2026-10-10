"""0.26.4.10 (to-do "Feedback alle 15min"): one feedback per 15 minutes, visible to the user."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from custom_components.freshairiq.cooldown import (
    FEEDBACK_COOLDOWN_SECONDS, cooldown_result, hub_retry_after, remaining_seconds, started_cooldown,
)
from tests.frontend_source import CARD_FILE

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


def test_remaining_time_and_results():
    assert FEEDBACK_COOLDOWN_SECONDS == 900
    until = started_cooldown(NOW)
    assert remaining_seconds(until, NOW) == 900
    assert remaining_seconds(until, NOW + timedelta(seconds=899.5)) == 1
    assert remaining_seconds(until, NOW + timedelta(seconds=901)) == 0
    assert remaining_seconds(None, NOW) == 0 and remaining_seconds("kaputt", NOW) == 0
    assert remaining_seconds(NOW + timedelta(minutes=5), NOW) == 300  # datetime objects work too
    naive = (NOW + timedelta(minutes=2)).replace(tzinfo=None)
    assert remaining_seconds(naive.isoformat(), NOW) == 120  # naive store value, aware clock
    assert remaining_seconds((NOW + timedelta(minutes=2)).isoformat(), NOW.replace(tzinfo=None)) == 120
    result = cooldown_result(0, NOW)
    assert result["accepted"] is False and result["reason"] == "cooldown" and result["retry_after_seconds"] == 1
    assert hub_retry_after({"detail": {"error": "feedback_cooldown", "retry_after_seconds": 321}}) == 321
    assert hub_retry_after({"retry_after_seconds": "60"}) == 60
    assert hub_retry_after({"detail": "x"}) is None and hub_retry_after(None) is None
    assert hub_retry_after({"retry_after_seconds": 0}) is None and hub_retry_after({"retry_after_seconds": "x"}) is None


def test_integration_and_card_wiring():
    telemetry = (ROOT / "custom_components/freshairiq/telemetry.py").read_text(encoding="utf-8")
    assert 'left = remaining_seconds(self._state.get("feedback_cooldown_until"), now)' in telemetry
    assert "if response.status == 429:" in telemetry
    assert '"feedback_cooldown_until": self._state.get("feedback_cooldown_until"),' in telemetry
    api = (ROOT / "custom_components/freshairiq/feedback_api.py").read_text(encoding="utf-8")
    assert 'if isinstance(result, dict) and result.get("reason") == "cooldown":' in api and "status_code=429" in api
    card = CARD_FILE.read_text(encoding="utf-8")
    assert '"feedback.cooldown_hint": { de: "Feedback ist alle 15 Minuten möglich."' in card
    assert 'id="feedback-send"${feedbackMins ? " disabled" : ""}' in card
    assert "this._feedbackCooldownUntil = parsed.cooldown_until;" in card
