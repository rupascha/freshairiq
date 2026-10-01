from pathlib import Path
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from custom_components.freshairiq.opening_state import opening_contact_profile, aggregate_opening_mode, stabilise_explicit_mode, update_passage_pattern

ROOT=Path(__file__).parents[1]
class States:
    def __init__(self, rows): self.rows=rows
    def get(self,k): return self.rows.get(k)
class Hass:
    def __init__(self, rows): self.states=States(rows)
def st(value, options=None):
    return SimpleNamespace(state=value, attributes={"options": options or []}, last_changed=datetime.now(timezone.utc)-timedelta(seconds=10))

def test_real_and_helper_three_state_are_selectable_on_both_surfaces():
    cf=(ROOT/'custom_components/freshairiq/config_flow.py').read_text()
    ui=(ROOT/'custom_components/freshairiq/frontend/freshairiq-card.js').read_text()
    for domain in ('binary_sensor','sensor','input_select','select'):
        assert domain in cf and domain in ui

def test_mixed_binary_and_three_state_capability_stays_per_contact():
    h=Hass({'binary_sensor.window':st('on'), 'input_select.door':st('tilted',['closed','open','tilted'])})
    modes, proven=opening_contact_profile(h,['binary_sensor.window','input_select.door'])
    assert proven=={'input_select.door'}
    assert modes=={'binary_sensor.window':'open','input_select.door':'tilted'}
    assert aggregate_opening_mode(modes)=='mixed'

def test_two_explicit_contacts_preserve_mixed_open_tilted():
    h=Hass({'sensor.a':st('open',['closed','open','tilted']), 'sensor.b':st('tilted',['closed','open','tilted'])})
    modes, proven=opening_contact_profile(h,['sensor.a','sensor.b'])
    assert proven=={'sensor.a','sensor.b'} and aggregate_opening_mode(modes)=='mixed'

def test_handle_transient_is_stabilised_per_contact():
    assert stabilise_explicit_mode('tilted','open',0.4,threshold_seconds=3.0)==('open',True)
    assert stabilise_explicit_mode('tilted','open',3.1,threshold_seconds=3.0)==('tilted',False)

def test_passage_pattern_needs_three_observations_and_counterevidence_can_unlearn():
    x={}
    for _ in range(3): x=update_passage_pattern(x,pulled_shut_evidence=True)
    assert x['learned'] and x['confidence']==1.0
    x=update_passage_pattern(x,pulled_shut_evidence=False)
    assert x['learned'] and x['confidence']==0.75
    x=update_passage_pattern(x,pulled_shut_evidence=False)
    assert not x['learned'] and x['confidence']==0.6

def test_binary_sensor_never_becomes_explicit_three_state_from_duration():
    h=Hass({'binary_sensor.window':st('on')})
    modes, proven=opening_contact_profile(h,['binary_sensor.window'])
    assert modes['binary_sensor.window']=='open' and not proven
