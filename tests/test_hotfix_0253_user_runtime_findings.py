from pathlib import Path
import json, importlib.util
from datetime import datetime, timezone, timedelta
ROOT=Path(__file__).resolve().parents[1]

def test_forum_instruction_and_visible_error_help_removed():
    s=(ROOT/"custom_components/freshairiq/frontend/freshairiq-card.js").read_text()
    assert "Bitte diesen Fehlercode bzw. einen Screenshot im Forum mitsenden." not in s
    assert "${this._supportStatusCard(st)}" not in s

def test_native_notifications_has_test_action():
    s=(ROOT/"custom_components/freshairiq/config_flow.py").read_text()
    assert 'vol.Optional("test_notification_now", default=False): bool' in s
    assert 'submitted.pop("test_notification_now", False)' in s
    assert "_send_targets(" in s

def test_native_room_add_and_subentry_explain_all_four_modes():
    for fn, words in [("de.json",("Mittelwert (empfohlen)","Median","Minimalwert","Maximalwert")),("en.json",("Mean (recommended)","Median","Minimum","Maximum"))]:
        d=json.loads((ROOT/"custom_components/freshairiq/translations"/fn).read_text())
        blob=json.dumps(d["config_subentries"]["room"]["step"]["user"],ensure_ascii=False)
        for word in words: assert word in blob
        assert "temperature_aggregation" in blob and "humidity_aggregation" in blob

def test_pdf_filter_and_build_survive_mixed_timezone_history():
    p=ROOT/"custom_components/freshairiq/ventilation_log.py"
    spec=importlib.util.spec_from_file_location("faiq_vlog",p); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    tz=timezone(timedelta(hours=2))
    h=[{"started_at":"2026-10-04T14:20:00","ended_at":"2026-10-04T14:24:00+02:00","room_name":"Arbeitszimmer"}]
    a=datetime(2026,10,4,0,0,tzinfo=tz); b=datetime(2026,10,4,23,59,tzinfo=tz)
    rows=m.filter_ventilation_log(h,a,b)
    assert len(rows)==1
    assert m.build_ventilation_pdf(rows,a,b).startswith(b"%PDF-1.4")
