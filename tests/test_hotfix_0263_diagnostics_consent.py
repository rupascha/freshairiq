"""0.26.3: automatic diagnostics sharing requires an explicit consent decision."""
from datetime import datetime
import json
from pathlib import Path

import pytest

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.diagnostic_transport import (
    effective_reporting_mode,
    normalise_consent,
    upload_due,
)
from custom_components.freshairiq.settings_contract import NATIVE_OPTION_KEYS

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components/freshairiq"


@pytest.mark.parametrize("consent", [None, "", "unset", "declined", "GRANTED?", 1])
@pytest.mark.parametrize("mode", ["daily", "weekly", "errors", "off"])
def test_no_scheduled_upload_without_explicit_consent(consent, mode):
    options = {"diagnostics_reporting_mode": mode}
    if consent is not None:
        options["diagnostics_consent"] = consent
    assert effective_reporting_mode(options) == "off"
    late_night = datetime(2026, 10, 8, 23, 59)
    assert upload_due(effective_reporting_mode(options), late_night, "install-1", problem_fingerprint="p") is False


@pytest.mark.parametrize("mode", ["daily", "weekly", "errors", "off"])
def test_granted_consent_keeps_the_chosen_cadence(mode):
    assert effective_reporting_mode({"diagnostics_consent": "granted", "diagnostics_reporting_mode": mode}) == mode


def test_granted_daily_upload_runs_in_its_slot():
    options = {"diagnostics_consent": "granted", "diagnostics_reporting_mode": "daily"}
    assert upload_due(effective_reporting_mode(options), datetime(2026, 10, 8, 23, 59), "install-1") is True


def test_existing_installations_without_a_decision_are_paused_not_assumed():
    # Pre-0.26.3 option dictionaries have no consent key at all.
    assert effective_reporting_mode({"diagnostics_reporting_mode": "daily"}) == "off"
    assert effective_reporting_mode(None) == "off"
    assert normalise_consent(" Granted ") == "granted"


def test_new_installations_start_undecided_and_the_key_is_on_both_settings_surfaces():
    assert DEFAULT_OPTIONS["diagnostics_consent"] == "unset"
    assert "diagnostics_consent" in NATIVE_OPTION_KEYS
    for name in ("translations/de.json", "translations/en.json", "strings.json"):
        step = json.loads((COMP / name).read_text(encoding="utf-8"))["options"]["step"]["diagnostics_sharing"]
        assert step["data"]["diagnostics_consent"] and step["data_description"]["diagnostics_consent"]


def test_dashboard_asks_admins_once_and_explains_the_real_destination():
    card = (COMP / "frontend/freshairiq-card.js").read_text(encoding="utf-8")
    assert 'consentState === "unset" && isAdmin && !this._consentDecided' in card
    # removed: dashboard-side check (dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services)).
    # removed: dashboard-side check (dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services)).
