"""Regression contract for v0.25.1.21 changelog/release hygiene."""
from collections import Counter
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

def test_current_changelog_version_is_unique_and_history_is_ordered():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    versions = re.findall(r"^##\s+(\d+\.\d+\.\d+\.\d+)(?:\s|$)", text, flags=re.MULTILINE)
    duplicates = sorted(v for v, count in Counter(versions).items() if count > 1)
    assert duplicates == [], f"Duplicate CHANGELOG version headings: {duplicates}"
    assert versions[:4] == ["0.25.1.21", "0.25.1.20", "0.25.1.19", "0.25.1.18"]

def test_025120_describes_support_share_not_retired_hub_upload():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    current = text.split("## 0.25.1.21", 1)[1].split("## 0.25.1.19", 1)[0]
    assert "native file share sheet" in current
    assert "support e-mail" in current
    assert "no support file is uploaded automatically" in current
    assert "60-minute cooldown" not in current
    assert "upload a complete retained diagnostics snapshot" not in current
