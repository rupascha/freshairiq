from pathlib import Path
import importlib.util
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('migration_replay',ROOT/'tools/migration_contract_replay.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

def test_historical_migration_fixtures_are_stable():
    assert mod.main()==0

def test_unknown_current_schema_data_is_preserved():
    data={'rooms':[],'future_key':{'x':1}}; opts={'future_option':'keep'}
    assert mod.migrate_v8(data,opts,8)==(data,opts,8)

def test_legacy_migration_is_idempotent():
    data={'rooms':[{'name':'Sensorlos','volume':22,'include_in_calculations':False}]}
    first=mod.migrate_v8(data,{},7)
    assert mod.migrate_v8(*first)==first
