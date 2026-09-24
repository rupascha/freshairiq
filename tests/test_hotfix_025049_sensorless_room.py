from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_sensorless_room_shell_is_supported_without_weakening_partial_setup_guard():
    flow = (ROOT / "custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")
    api = (ROOT / "custom_components/freshairiq/settings_api.py").read_text(encoding="utf-8")
    assert "if include and not has_temperature and not has_humidity and not contacts:" in flow
    assert "include = False" in flow
    assert "sensor_setup_started = bool(" in api
    assert "if include and sensor_setup_started and not raw.get(CONF_ROOM_TEMPERATURE):" in api
    assert "if include and sensor_setup_started and not raw.get(CONF_ROOM_HUMIDITY):" in api

def test_release_version_is_025049():
    import json
    manifest = json.loads((ROOT / "custom_components/freshairiq/manifest.json").read_text())
    package = json.loads((ROOT / "package.json").read_text())
    policy = json.loads((ROOT / "quality/quality_policy.json").read_text())
    assert manifest["version"] == package["version"] == policy["version"] == "0.25.0.64"
