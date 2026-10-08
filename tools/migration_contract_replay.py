"""Replay historical FreshAirIQ configuration shapes through the v8 migration contract.

This intentionally mirrors the pure data transformation in async_migrate_entry so the
upgrade contract is testable without importing Home Assistant. Any production migration
change must update this replay and its fixtures together, making user-data changes explicit.
"""
from __future__ import annotations
import copy, json, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIXTURES=ROOT/'quality/migration_fixtures'


def migrate_v8(data: dict, options: dict, version: int) -> tuple[dict,dict,int]:
    if version >= 8:
        return copy.deepcopy(data), copy.deepcopy(options), version
    out=copy.deepcopy(data); rooms=[]
    raw=out.get('rooms', [])
    if not isinstance(raw,list): raw=[]
    for old in raw:
        if not isinstance(old,dict): continue
        room=copy.deepcopy(old)
        if 'contacts' not in room:
            legacy=room.get('contact'); room['contacts']=[legacy] if legacy else []
        room.setdefault('contact_mode','any'); room.pop('contact',None)
        if 'volume_mode' not in room:
            has_dims=all(room.get(k) not in (None,'') for k in ('length','width','height'))
            room['volume_mode']='dimensions' if has_dims else 'direct'
        room.setdefault('floor','ground_floor')
        room.setdefault('sort_order',len(rooms))
        room.setdefault('include_in_calculations',True)
        room.setdefault('window_orientation','unknown')
        contacts=room.get('contacts') or []
        if isinstance(contacts,str): contacts=[contacts]
        try: delay=int(float(room.get('contact_delay_seconds',0)))
        except (TypeError,ValueError,OverflowError): delay=0
        delay=max(0,min(300,delay))
        room.setdefault('contact_delays',{c:delay for c in contacts})
        room.setdefault('contact_orientations',{c:room.get('window_orientation','unknown') for c in contacts})
        rooms.append(room)
    out['rooms']=rooms
    opts=copy.deepcopy(options)
    try: pct=float(opts.get('min_potential_percent_total_water',10.0))
    except (TypeError,ValueError,OverflowError): pct=10.0
    if opts.get('threshold_mode','percent_total_water')=='percent_total_water' and pct==10.0:
        opts['threshold_mode']='adaptive_home_size'
    out['levels']=list(dict.fromkeys(str(r.get('floor','Unzugeordnet')) for r in rooms))
    return out,opts,8


def main()->int:
    failures=[]; count=0
    for path in sorted(FIXTURES.glob('*.json')):
        spec=json.loads(path.read_text(encoding='utf-8')); count+=1
        got=migrate_v8(spec['input']['data'],spec['input'].get('options',{}),spec['input']['version'])
        exp=(spec['expected']['data'],spec['expected'].get('options',{}),spec['expected']['version'])
        if got != exp: failures.append(path.name)
        # Migration must be idempotent once at current schema.
        if migrate_v8(*got) != got: failures.append(path.name+' (not idempotent)')
    if failures:
        print('Migration contract replay: FAIL'); [print(' - '+x) for x in failures]; return 1
    print(f'Migration contract replay: PASS ({count} historical configurations)'); return 0
if __name__=='__main__': raise SystemExit(main())
