from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
DE = json.loads((ROOT / "custom_components/freshairiq/translations/de.json").read_text(encoding="utf-8"))

def _walk(v):
    if isinstance(v, dict):
        for x in v.values(): yield from _walk(x)
    elif isinstance(v, list):
        for x in v: yield from _walk(x)
    elif isinstance(v, str): yield v

def test_no_legacy_german_labels_remain():
    values=list(_walk(DE))
    assert not any("Abluftgerät" in x for x in values)
    assert not any("Klimaanlage/Heizung" in x for x in values)

def test_canonical_german_labels_exist_in_all_repeated_paths():
    values=list(_walk(DE))
    assert sum("Ablüfter / mechanische Lüftung" in x for x in values) >= 10
    assert sum("Thermostat / Klimagerät" in x for x in values) >= 10
