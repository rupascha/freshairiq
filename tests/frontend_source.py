"""Frontend source text for contract tests (0.26.4.8).

Since 0.26.4.8 the English phrase tables live in their own lazily loaded module
(``freshairiq-card-i18n-en.js``). Contract tests that check German UI copy
together with its English counterpart read both files as one text.
"""
from __future__ import annotations

from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "custom_components/freshairiq/frontend"
CARD_FILE = FRONTEND / "freshairiq-card.js"
ENGLISH_FILE = FRONTEND / "freshairiq-card-i18n-en.js"


def card_text() -> str:
    """Card source plus the on-demand English module."""
    return CARD_FILE.read_text(encoding="utf-8") + "\n" + ENGLISH_FILE.read_text(encoding="utf-8")
