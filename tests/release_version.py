"""Single source of truth for assertions about the *current* release version.

Historical regression tests must validate behaviour, not pin a once-current version.
The authoritative runtime version remains manifest.json; tests read it dynamically.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT_RELEASE_VERSION = str(
    json.loads((ROOT / "custom_components/freshairiq/manifest.json").read_text(encoding="utf-8"))["version"]
)
