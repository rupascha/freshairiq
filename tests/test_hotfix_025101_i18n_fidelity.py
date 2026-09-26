from pathlib import Path
import json, re

ROOT = Path(__file__).resolve().parents[1]
CARD = (ROOT / 'custom_components/freshairiq/frontend/freshairiq-card.js').read_text(encoding='utf-8')

def _native_pairs():
    match = re.search(r'const FAIQ_NATIVE_EN = (\[.*?\]);\nconst ', CARD, re.S)
    assert match
    return json.loads(match.group(1))

def test_025101_release_version_and_ai_i18n_contract():
    assert 'const FAIQ_VERSION = "0.25.1.6";' in CARD
    for token in [
        '["FreshAirIQ übernimmt", "FreshAirIQ is handling it"]',
        'more rooms without urgent action needed',
        'room(s) are being tracked automatically.',
        'min remaining',
    ]:
        assert token in CARD

def test_025101_long_native_english_copy_keeps_information_density():
    pairs = _native_pairs()
    suspicious = [(de, en) for de, en in pairs if len(de) > 180 and len(en) / len(de) < 0.55]
    assert suspicious == []
