from types import SimpleNamespace
from custom_components.freshairiq.opening_state import advertises_three_states, normalize_opening_state, room_opening_mode

class States:
    def __init__(self, rows): self.rows=rows
    def get(self, key): return self.rows.get(key)
class Hass:
    def __init__(self, rows): self.states=States(rows)
def st(value, **attrs): return SimpleNamespace(state=value, attributes=attrs)

def test_binary_contact_stays_binary_even_when_open():
    state=st('on', device_class='window')
    assert not advertises_three_states('binary_sensor.window', state)
    mode, proven=room_opening_mode(Hass({'binary_sensor.window':state}), ['binary_sensor.window'])
    assert mode == 'open' and proven == set()

def test_native_enum_three_state_is_automatic_before_first_tilt():
    state=st('closed', options=['closed','open','tilted'])
    assert advertises_three_states('sensor.window_position', state)
    mode, proven=room_opening_mode(Hass({'sensor.window_position':state}), ['sensor.window_position'])
    assert mode == 'closed' and proven == {'sensor.window_position'}

def test_helper_three_way_contact_is_compatible():
    state=st('gekippt', options=['zu','auf','gekippt'])
    mode, proven=room_opening_mode(Hass({'input_select.window_state':state}), ['input_select.window_state'])
    assert mode == 'tilted' and proven == {'input_select.window_state'}

def test_observed_tilt_proves_sensor_without_options_and_persists():
    hass=Hass({'sensor.window':st('tilted')})
    mode, proven=room_opening_mode(hass,['sensor.window'])
    assert mode == 'tilted' and proven == {'sensor.window'}
    hass.states.rows['sensor.window']=st('open')
    mode, proven2=room_opening_mode(hass,['sensor.window'],proven)
    assert mode == 'open' and proven2 == proven

def test_unknown_fails_safe_instead_of_guessing():
    mode, proven=room_opening_mode(Hass({'sensor.window':st('half_open')}),['sensor.window'])
    assert mode == 'unknown' and not proven

def test_german_and_english_normalization():
    for raw in ('tilted','kipp','gekippt'): assert normalize_opening_state(raw)=='tilted'
    for raw in ('open','on','auf'): assert normalize_opening_state(raw)=='open'
    for raw in ('closed','off','zu'): assert normalize_opening_state(raw)=='closed'

def test_binary_long_open_compatibility_guard_is_preserved():
    from pathlib import Path
    text=(Path(__file__).parents[1]/'custom_components/freshairiq/consolidation.py').read_text()
    assert 'not bool(r.get("opening_state_explicit"))' in text
    assert 'max_duration + 10.0' in text

def test_mode_specific_learning_and_recommendation_are_wired():
    from pathlib import Path
    text=(Path(__file__).parents[1]/'custom_components/freshairiq/coordinator.py').read_text()
    assert 'session_opening_mode_mixed' in text
    assert 'session_mode in {"open", "tilted", "cross"}' in text
    assert 'action = "Open fully"' in text
    assert 'opening_learning' in text


def test_missing_entity_and_malformed_options_fail_safe():
    mode, proven = room_opening_mode(Hass({}), ['sensor.missing'])
    assert mode == 'unknown' and not proven
    state = st('closed', options='closed,open,tilted')
    assert not advertises_three_states('sensor.bad_options', state)
