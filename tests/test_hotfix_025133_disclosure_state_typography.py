from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
JS=(ROOT/'custom_components/freshairiq/frontend/freshairiq-card.js').read_text(encoding='utf-8')

def test_live_patch_preserves_native_details_open_state():
    block=JS[JS.index('    _patchLiveNode(current, fresh) {'):JS.index('    _liveViewStateSnapshot(key) {')]
    assert 'preserveDetailsOpen' in block
    assert 'current.open = detailsWasOpen' in block
    assert 'attr.name === "open"' in block

def test_classic_readability_override_is_material_not_cosmetic():
    assert '.decision-main h2{font-size:22px;line-height:27px}' in JS
    assert '.decision-action{font-size:15px;line-height:20px}' in JS
    assert '.decision-impact b,.night-context b{font-size:14px;line-height:19px}' in JS
    assert '.decision-more-content .decision-summary,.decision-more-content .decision-why span,.decision-more-content .iq-process-text{font-size:13px;line-height:18px}' in JS
    assert '.decision-room-reason span{font-size:13px;line-height:18px}' in JS

def test_mobile_keeps_larger_text_and_existing_overflow_guards():
    assert '@media(max-width:520px){.decision-main h2{font-size:21px;line-height:26px}' in JS
    assert 'overflow-wrap:anywhere' in JS
    assert 'minmax(0,1fr)' in JS
