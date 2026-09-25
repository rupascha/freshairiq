from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
COMP=ROOT/"custom_components"/"freshairiq"

def test_release_version_and_stable_hacs_description():
    assert json.loads((COMP/"manifest.json").read_text())["version"] == "0.25.0.76"
    readme=(ROOT/"README.md").read_text()
    assert "FreshAirIQ · Public Beta" in readme
    assert "0.25.0.76" not in readme and "0.25.0.76" not in readme
    assert json.loads((ROOT/"hacs.json").read_text())["render_readme"] is True

def test_laundry_moisture_sources_are_part_of_contract():
    from custom_components.freshairiq.const import MOISTURE_SOURCES
    assert {"washing_machine","dryer","ironing_station"} <= set(MOISTURE_SOURCES)
    de=json.loads((COMP/"translations"/"de.json").read_text())
    options=de["selector"]["moisture_source"]["options"]
    assert options["washing_machine"] == "Waschmaschine"
    assert options["dryer"] == "Trockner"
    assert options["ironing_station"] == "Bügelstation"

def test_android_scroll_contract_and_parent_position_stack():
    js=(COMP/"frontend"/"freshairiq-card.js").read_text()
    assert "min-height:0;flex:1 1 0;overflow-y:auto" in js
    assert "this._infoScrollStack" in js
    assert "_pushInfoViewport()" in js
    assert "const stackTop = this._infoScrollStack.length ? this._infoScrollStack.pop() : 0" in js
    assert "this._infoScrollByView" in js

def test_new_install_upload_has_30_minute_grace_after_enrollment():
    src=(COMP/"telemetry.py").read_text()
    assert "_INITIAL_UPLOAD_GRACE = timedelta(minutes=30)" in src
    assert 'self._runtime_state = "onboarding_grace"' in src
    assert "await self._async_ensure_enrolled(session, installation_id, timeout)" in src
