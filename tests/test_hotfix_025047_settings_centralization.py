from pathlib import Path
from datetime import datetime, timedelta
from custom_components.freshairiq.const import *
from custom_components.freshairiq.moisture_source import _source_signatures

ROOT=Path(__file__).parents[1]
CARD=(ROOT/'custom_components/freshairiq/frontend/freshairiq-card.js').read_text()
FLOW=(ROOT/'custom_components/freshairiq/config_flow.py').read_text()

def test_dashboard_support_tile_and_editor_visibility():
    assert 'show_support_button' in CARD
    assert 'id="support"' in CARD
    assert 'FRESHAIRIQ SUPPORT' in CARD
    for text in ['<b>Diagnosedaten</b><span>exportieren</span>','<b>Diagnosedaten</b><span>an Support senden</span>','support@freshairiq.com','Automatische Diagnoseübertragung','Verbesserungsvorschlag']:
        assert text in CARD

# test_dashboard_room_save_reads_ha_selector_value_not_selected_options: retired — dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services).

def test_room_reference_air_has_one_canonical_editor_surface():
    # Room-level duplicate controls are hidden; per-opening reference controls remain.
    assert 'entitySelect("room-ref-temp"' not in CARD
    assert 'entitySelect("room-ref-humidity"' not in CARD
    # removed: dashboard-side check (dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services)).
    assert 'CONF_ROOM_REFERENCE_TEMPERATURE' not in FLOW[FLOW.index('def _room_schema'):FLOW.index('def _flatten_sections')]

# test_all_requested_moisture_sources_are_offered: retired — dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services).

def test_washing_and_hung_laundry_have_distinct_physical_signatures():
    base={'samples':5.0,'ah_monotonic':1.0,'temp_monotonic':1.0,'peak_ah_rate':0.1}
    assert MOISTURE_SOURCE_WASHING_MACHINE in _source_signatures({MOISTURE_SOURCE_WASHING_MACHINE}, ah_rise=.2,temp_rise=.2,source_rate=2.5,generated_ml=20,pattern=base)
    assert MOISTURE_SOURCE_LAUNDRY_DRYING in _source_signatures({MOISTURE_SOURCE_LAUNDRY_DRYING}, ah_rise=.3,temp_rise=.05,source_rate=2.0,generated_ml=25,pattern=base)
    assert MOISTURE_SOURCE_LAUNDRY_DRYING not in _source_signatures({MOISTURE_SOURCE_LAUNDRY_DRYING}, ah_rise=.7,temp_rise=1.0,source_rate=7.0,generated_ml=60,pattern=base)
