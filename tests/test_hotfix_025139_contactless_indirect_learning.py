from pathlib import Path
import json

from custom_components.freshairiq.passive_ventilation import learn_passive_exchange

ROOT = Path(__file__).resolve().parents[1]


def test_contactless_calculated_room_no_longer_requires_opening():
    flow = (ROOT / "custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")
    assert 'if include and not has_temperature:' in flow
    assert 'if include and not has_humidity:' in flow
    assert 'if include and not contacts:' not in flow
    assert 'Opening contacts are optional for calculated indoor rooms.' in flow


def test_dashboard_keeps_climate_pair_validation_without_contact_requirement():
    api = (ROOT / "custom_components/freshairiq/feedback_api.py").read_text(encoding="utf-8")
    # removed: dashboard-side check (dashboard settings and their write API removed in 0.26.4.3 (single settings surface: Devices & services)).
    # removed: dashboard-side check (dashboard settings and their write API removed in 0.26.4.3 (single settings surface: Devices & services)).
    flow = (ROOT / "custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")
    assert 'errors[CONF_ROOM_CONTACTS] = "ventilation_contact_required"' not in flow


def test_contactless_room_uses_separate_passive_model_and_is_not_directly_actionable():
    coordinator = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    assert 'effective_learning_rate = float(mem["learning_rate"] if has_ventilation_contact else mem.get("passive_learning_rate", 0.03))' in coordinator
    assert 'result.ventilation_candidate = False' in coordinator
    assert 'action = "Ventilate indirectly"' in coordinator
    assert '"ventilation_path": ("assigned_opening" if has_ventilation_contact else "indirect_unassigned")' in coordinator


def test_passive_learning_is_bounded_and_separate():
    learned = learn_passive_exchange(old_rate=0.03, old_samples=0, start_ah=12.0, current_ah=10.8, start_reference_ah=8.0, elapsed_min=10.0)
    assert learned["valid"] is True
    assert learned["samples"] == 1
    assert 0.002 <= learned["rate"] <= 0.25
    assert learned["observed_rate"] == 0.03
    invalid = learn_passive_exchange(old_rate=0.03, old_samples=4, start_ah=12.0, current_ah=11.9, start_reference_ah=11.9, elapsed_min=3.0)
    assert invalid == {"valid": False, "rate": 0.03, "samples": 4, "observed_rate": None}


def test_passive_learning_defaults_and_repair_are_persisted():
    storage = (ROOT / "custom_components/freshairiq/storage.py").read_text(encoding="utf-8")
    assert '"passive_learning_rate": 0.03' in storage
    assert '"passive_learning_samples": 0' in storage
    assert 'room["passive_learning_rate"] = 0.03 if passive_rate is None' in storage


def test_german_and_english_configuration_explain_optional_contacts():
    de = json.loads((ROOT / "custom_components/freshairiq/translations/de.json").read_text(encoding="utf-8"))
    en = json.loads((ROOT / "custom_components/freshairiq/translations/en.json").read_text(encoding="utf-8"))
    de_text = json.dumps(de, ensure_ascii=False)
    en_text = json.dumps(en, ensure_ascii=False)
    assert 'Öffnungskontakt ist optional' in de_text
    assert 'opening contact is optional' in en_text.lower()
    assert 'indirekte Lüftungswirkung lernen' in de_text
    assert 'learn indirect ventilation effects' in en_text


def test_release_025139_notes_are_preserved():
    assert (ROOT / "docs/releases/RELEASE_NOTES_0.25.1.39.md").is_file()
