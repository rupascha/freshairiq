"""Support feedback (2026-10-17): the success message must not read like a request to send again."""
from __future__ import annotations

from pathlib import Path

CARD = (Path(__file__).resolve().parents[1] / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")


def _line() -> str:
    return next(line for line in CARD.splitlines() if '"support.success"' in line)


def test_success_message_says_nothing_else_is_needed() -> None:
    line = _line()
    assert "{caseLine}" in line
    assert "Du musst nichts weiter tun." in line
    assert "frühestens in 60 Minuten eine weitere Diagnose senden" in line
    assert "Nothing else to do." in line
    assert "send another report in 60 minutes at the earliest" in line


def test_old_resend_wording_is_gone() -> None:
    line = _line()
    assert "Ein erneuter Versand ist in 60 Minuten möglich" not in line
    assert "Another upload will be available" not in line
