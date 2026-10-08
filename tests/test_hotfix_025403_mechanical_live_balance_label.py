from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_coordinator_exposes_mechanical_exhaust_state_to_room_payload():
    source = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    assert '"mechanical_exhaust_active": mechanical_exhaust_active' in source
    assert '"ventilation_type": mem.get("session_specialist_opening_mode") if mem.get("session_active") else None' in source


def test_live_moisture_balance_labels_running_exhaust_as_mechanical():
    js = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
    assert 'Boolean(r.configured_actuators?.mechanical_exhaust_active)' in js
    assert 'MECHANISCHE LÜFTUNG AKTIV' in js
    assert 'MECHANICAL VENTILATION ACTIVE' in js
    assert 'mechanicalActive ? "mdi:fan"' in js
