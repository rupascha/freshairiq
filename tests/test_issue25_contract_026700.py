"""GitHub #25 (0.26.7.0 check): every reader of the raw cross-ventilation options resolves them through
``cross_pairs`` – recommendation, sessions, floor/house context. Settings, defaults, diagnostics and the parser
itself only store or describe the text. The dashboard, floor and house layers receive the resolved result only."""
from __future__ import annotations

import re
from pathlib import Path

COMP = Path(__file__).resolve().parents[1] / "custom_components" / "freshairiq"
STORAGE_ONLY = {"cross_pairs.py", "const.py", "settings_contract.py", "config_flow_schemas.py", "config_flow_options.py",
                "config_flow_options_settings.py", "diagnostic_transport.py", "diagnostics_privacy.py", "config_flow.py"}
RAW = re.compile(r"""options\.get\(\s*["'](cross_ventilation_pairs|cross_zone_connections)["']""")


def test_every_runtime_reader_resolves_pairs_through_cross_pairs():
    readers = {}
    for path in sorted(COMP.glob("*.py")):
        if path.name in STORAGE_ONLY:
            continue
        text = path.read_text(encoding="utf-8")
        if RAW.search(text):
            readers[path.name] = "cross_pairs" in text
    assert readers == {"coordinator_house.py": True, "coordinator_sessions.py": True, "recommendation.py": True}


def test_the_frontend_never_parses_the_raw_text():
    for path in (COMP / "frontend").glob("*.js"):
        assert "cross_ventilation_pairs" not in path.read_text(encoding="utf-8"), path.name
