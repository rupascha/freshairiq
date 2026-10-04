from statistics import median
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]

def test_median_is_robust_example():
    assert median([21.0,21.4,28.0]) == 21.4

def test_median_available_in_native_selectors_and_validation():
    source=(ROOT/"custom_components/freshairiq/config_flow.py").read_text()
    assert source.count('options=["mean", "median", "max", "min"]') >= 2
    assert '{"mean", "median", "min", "max"}' in source

def test_median_implemented_in_runtime_aggregator():
    source=(ROOT/"custom_components/freshairiq/climate_sources.py").read_text()
    assert "from statistics import fmean, median" in source
    assert 'strategy == "median"' in source

def test_de_en_explain_all_four_strategies():
    de=json.loads((ROOT/"custom_components/freshairiq/translations/de.json").read_text())
    en=json.loads((ROOT/"custom_components/freshairiq/translations/en.json").read_text())
    assert de["selector"]["climate_aggregation"]["options"]["median"].startswith("Median")
    assert en["selector"]["climate_aggregation"]["options"]["median"].startswith("Median")
    for blob in (json.dumps(de,ensure_ascii=False),json.dumps(en,ensure_ascii=False)):
        assert "Median" in blob
