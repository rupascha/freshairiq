"""Regression contract for v0.25.1.17 changelog heading hygiene hotfix."""
from collections import Counter
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_changelog_has_no_duplicate_version_headings_and_025113_entries_are_preserved():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    headings = re.findall(r"^##\\s+(\\d+\\.\\d+\\.\\d+\\.\\d+)(?:\\s|$)", text, flags=re.MULTILINE)
    duplicates = sorted(version for version, count in Counter(headings).items() if count > 1)
    assert duplicates == [], f"Duplicate CHANGELOG version headings: {duplicates}"

    required = (
        "Freshy verwendet jetzt denselben konfigurierten Nachtzeitraum",
        "Sensor-Recovery als echte, isoliert testbare State-Machine abgesichert",
        "Sensor-Recovery auf die für Feuchteberechnungen erforderlichen Klimaquellen begrenzt",
        "Pure-Logic-Coverage wieder auf 100 % abgesichert",
        "Echter Browser-Regressionstest für exakte Dashboard-Scrollposition",
        "Added import of Home Assistant Areas and Floor assignments",
        "Pure-Logic-Coverage-Gate auf 90 % angehoben",
    )
    for entry in required:
        assert entry in text
