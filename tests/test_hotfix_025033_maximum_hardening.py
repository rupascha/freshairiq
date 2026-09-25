"""Regression contracts for v0.25.0.71 maximum hardening hotfix."""
from __future__ import annotations

import json
from pathlib import Path

from custom_components.freshairiq.measurement_frame import trusted_session_end_baseline

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"


def test_untrusted_session_clears_repeat_measurement_baselines() -> None:
    baseline = trusted_session_end_baseline(
        timestamp_gate_passed=False,
        end_humidity=57.5,
        end_absolute_humidity=9.25,
        reference_absolute_humidity=6.8,
    )
    assert baseline == {
        "end_humidity": None,
        "end_absolute_humidity": None,
        "reference_absolute_humidity": None,
    }


def test_trusted_session_preserves_repeat_measurement_baselines() -> None:
    baseline = trusted_session_end_baseline(
        timestamp_gate_passed=True,
        end_humidity="57.5",
        end_absolute_humidity=9.25,
        reference_absolute_humidity=6.8,
    )
    assert baseline == {
        "end_humidity": 57.5,
        "end_absolute_humidity": 9.25,
        "reference_absolute_humidity": 6.8,
    }


def test_nonfinite_repeat_baselines_are_rejected() -> None:
    baseline = trusted_session_end_baseline(
        timestamp_gate_passed=True,
        end_humidity=float("nan"),
        end_absolute_humidity=float("inf"),
        reference_absolute_humidity=None,
    )
    assert baseline == {
        "end_humidity": None,
        "end_absolute_humidity": None,
        "reference_absolute_humidity": None,
    }


def test_coordinator_uses_strict_baseline_helper() -> None:
    source = (COMP / "coordinator.py").read_text(encoding="utf-8")
    assert "repeat_baseline = trusted_session_end_baseline(" in source
    assert "timestamp_gate_passed=session_activity_eligible" in source
    assert 'mem["last_ventilation_end_humidity"] = (' in source
    assert 'mem["last_ventilation_reference_ah"] = (' in source


def test_waiting_ui_does_not_claim_learning() -> None:
    card = (COMP / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")
    assert "LÜFTUNG WIRD BEOBACHTET: FreshAirIQ sammelt aktuelle Temperatur- und Feuchtemeldungen" in card
    assert "LERNT JETZT: IQ lernt gerade den realen Luftaustausch · Lüftungsverlauf wird aufgezeichnet" not in card


def test_android_webview_is_a_real_compatibility_target() -> None:
    config = (ROOT / "playwright.config.mjs").read_text(encoding="utf-8")
    policy = json.loads((ROOT / "quality" / "quality_policy.json").read_text(encoding="utf-8"))
    assert "name: 'android-webview'" in config
    assert "isMobile: true" in config
    assert "hasTouch: true" in config
    assert "Android 15" in config
    assert "Home Assistant/2026.9.1" in config
    assert policy["compatibility"]["android_webview"]["is_mobile"] is True
    assert policy["compatibility"]["android_webview"]["has_touch"] is True
    assert len(policy["compatibility"]["android_webview"]["viewports"]) == 4


def test_staging_copy_is_version_neutral_and_release_versions_match() -> None:
    stale = "v0.25.0.25 ist ausschließlich mit dem lokalen Staging-Hub"
    assert stale not in (COMP / "strings.json").read_text(encoding="utf-8")
    assert stale not in (COMP / "translations" / "de.json").read_text(encoding="utf-8")
    assert "v0.25.0.25 connects only to the local staging Hub" not in (COMP / "translations" / "en.json").read_text(encoding="utf-8")
    assert "Hub-Status in v0.25.0." not in (COMP / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")

    manifest = json.loads((COMP / "manifest.json").read_text(encoding="utf-8"))
    policy = json.loads((ROOT / "quality" / "quality_policy.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "0.25.0.71"
    assert policy["version"] == "0.25.0.71"
    assert 'VERSION = "0.25.0.71"' in (COMP / "const.py").read_text(encoding="utf-8")
    for name in ("freshairiq-card.js", "freshairiq-panel.js", "freshairiq-loader.js"):
        assert 'const FAIQ_VERSION = "0.25.0.71";' in (COMP / "frontend" / name).read_text(encoding="utf-8")
