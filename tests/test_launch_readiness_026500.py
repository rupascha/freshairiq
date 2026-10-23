"""0.26.5.0: one language per installation, English everywhere for English servers,
and a dead second contact no longer keeps a room "open" forever."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from tests._source import module_source

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components/freshairiq"
CARD = (COMP / "frontend/freshairiq-card.js").read_text(encoding="utf-8")
EN = (COMP / "frontend/freshairiq-card-i18n-en.js").read_text(encoding="utf-8")


# --- feedback FAIQ-FB-78614DD50929: German headings, English recommendations ----------
def test_card_speaks_the_language_of_the_freshairiq_texts():
    ui = CARD[CARD.index("    _uiLanguage() {"):]
    ui = ui[: ui.index("    _tx(text)")]
    assert "this._statusEntity()?.attributes?.output_language" in ui
    assert ui.index("output_language") < ui.index("this._hass.language")  # data language wins over the profile
    coordinator = module_source("coordinator")
    assert 'data["output_language"] = "de"' in coordinator and 'localized["output_language"] = "en"' in coordinator
    sensor = (COMP / "sensor.py").read_text(encoding="utf-8")
    assert sensor.count('"output_language": self.coordinator.data.get("output_language", "de")') == 2  # status + room entities


def test_live_updates_and_click_texts_stay_english():
    fresh = CARD[CARD.index("    _freshLiveNode(cacheKey, html, selector) {"):]
    assert "this._localizeLegacyFragment(template.content)" in fresh[: fresh.index("\n    }\n")]
    for text in ("PDF wird erstellt", "Export wird erstellt", "Export erstellt", "Bitte eine Beschreibung mit mindestens 3 Zeichen eingeben.",
                 "Wird sicher an den Diagnose-Hub übertragen …"):
        # 0.26.5.3: the ventilation log export lives in freshairiq-card-data.js
        source = CARD if text in CARD else (COMP / "frontend/freshairiq-card-data.js").read_text(encoding="utf-8")
        at = source.index(text)
        assert "this._tx(" in source[at - 120: at], text
    assert 'const diagnosisDE = value => FAIQ_NUMBER_LOCALE === "en"' in CARD
    assert 'navigator.language || "").toLowerCase().startsWith("de") ? "Intelligente' in CARD  # card picker text


def test_english_module_covers_the_strings_found_in_a_rendered_english_dashboard():
    # Found by rendering the real card with real FreshAirIQ English output (0.26.5.0 audit).
    for phrase in ("unterschiedliche Lerntage", "STRUKTURRAUM", "LANGZEITLERNEN", "WIEDERAUFHEIZEN", "WARUM?", "Strategie-IQ",
                   "HAUSLÜFTUNG AKTIV", "Querlüftung erkannt", "Shadow-Modelle", "Zeitmuster-Proben", "Luftstromfaktor",
                   "Bitte Verbindung zum Diagnose-Hub prüfen.", "Kleine Zusatztexte"):
        assert f'["{phrase}", "' in EN, phrase
    assert "export const FAIQ_EN_PATTERNS" in EN and "FAIQ_EN_PATTERNS = Array.isArray(mod.FAIQ_EN_PATTERNS)" in CARD
    assert '[/Prognose weitere (\\d+) Minuten/g, "Forecast for the next $1 minutes"]' in EN


def test_english_module_patterns_work_in_node():
    script = (
        "import('" + (COMP / "frontend/freshairiq-card-i18n-en.js").as_uri() + "').then(m => {"
        "let s = 'Prognose weitere 15 Minuten · 2 Erwachsene · 1 Kinder · Lernreife-Evidenz +1.00 (Proben 10, Rest 0.00)';"
        "for (const [re, en] of m.FAIQ_EN_PATTERNS) s = s.replace(re, en);"
        "for (const [de, en] of m.FAIQ_EN_RULES) s = typeof de === 'string' ? s.split(de).join(en) : s.replace(de, () => en);"
        "console.log(s); })"
    )
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    text = out.stdout.strip()
    assert text.startswith("Forecast for the next 15 minutes") and "1 child" in text and "2 adults" in text
    assert "learning maturity evidence +1.00 (samples 10, remainder 0.00)" in text


def test_backend_learning_diagnosis_is_fully_english():
    sys.path.insert(0, str(ROOT / "tools"))
    import coordinator_golden  # noqa: F401  (HA stub for the package import)
    from custom_components.freshairiq.localize import Translator

    text = Translator().text("Learned: evidence 10+0.00 · 9.0 min · rate 0.044→0.045 · qualitätsgewichtet (0.80) · "
                             "Lernreife-Evidenz +1.00 (Proben 10, Rest 0.00)")
    assert text.endswith("quality-weighted (0.80) · learning maturity evidence +1.00 (samples 10, remainder 0.00)")
    assert Translator().text("kWh Strom") == "kWh electricity"


def test_test_notification_follows_the_server_language():
    flow = module_source("config_flow")
    assert '"Test successful: FreshAirIQ can reach this notification target."' in flow
    assert '_txt(_flow_language(self.hass), "Test erfolgreich' in flow


# --- a dead second contact -----------------------------------------------------------
def test_unknown_contact_hold_is_bounded():
    from custom_components.freshairiq.const import CONTACT_UNKNOWN_HOLD_SECONDS
    sys.path.insert(0, str(ROOT / "tools"))
    import coordinator_golden  # noqa: F401
    from custom_components.freshairiq.coordinator import _contact_unknown_for

    now = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
    started = now - timedelta(hours=2)
    assert _contact_unknown_for(None, started, now) == 7200.0  # missing since the start
    fresh = SimpleNamespace(last_changed=now - timedelta(seconds=60))
    assert _contact_unknown_for(fresh, started, now) == 60.0 < CONTACT_UNKNOWN_HOLD_SECONDS  # start-up / short drop-out: hold
    assert _contact_unknown_for(SimpleNamespace(last_changed="x"), started, now) == 0.0
    assert _contact_unknown_for(SimpleNamespace(last_changed=now.replace(tzinfo=None)), started, now) == 0.0
    assert CONTACT_UNKNOWN_HOLD_SECONDS == 900.0


SCRIPT = r'''
import asyncio, copy, json, sys, types
sys.path.insert(0, sys.argv[1])
import coordinator_golden as g
from datetime import timedelta
ha = g.ha_stub

async def main():
    g._freeze_package_time()
    ha.Store._MEMORY.clear()
    start = g.datetime(2026, 10, 7, 12, 0, tzinfo=g.TZ)
    ha.CLOCK.now = start
    hass = ha.HomeAssistant()
    for entity, (state, attrs) in g._house_states().items():
        if entity != "binary_sensor.terrasse":   # second kitchen contact: battery dead / removed
            hass.states.async_set(entity, state, attrs)
    entry = types.SimpleNamespace(entry_id="dead-contact", title="FreshAirIQ", version=8, minor_version=1,
                                  data=copy.deepcopy(g.BASE_DATA), options=copy.deepcopy(g.BASE_OPTIONS), subentries={},
                                  runtime_data=None, async_on_unload=lambda f: None)
    store = g.LearningStore(hass, entry.entry_id); await store.async_load()
    coordinator = g.coord_mod.FreshAirIQCoordinator(hass, entry, store)
    trace = []
    async def cycle(minutes, **states):
        ha.CLOCK.advance(minutes * 60)
        for k, v in states.items():
            old = hass.states.get(k); hass.states.async_set(k, v, old.attributes if old else {})
        data = await coordinator._async_update_data(); coordinator.data = data
        trace.append(bool(data["rooms"]["kueche"].get("active")))
    for _ in range(20):
        await cycle(1)                                   # 20 min: the missing contact is long unknown
    await cycle(1, **{"binary_sensor.kueche_fenster": "on"})
    for _ in range(6):
        await cycle(1)
    await cycle(1, **{"binary_sensor.kueche_fenster": "off"})
    for _ in range(4):
        await cycle(1)
    log = store.data.get("ventilation_log") or []
    print(json.dumps({"trace": trace, "logged": [e.get("room_key") for e in log]}))

asyncio.run(main())
'''


def test_dead_second_contact_does_not_keep_the_room_open(tmp_path):
    script = tmp_path / "dead_contact.py"
    script.write_text(SCRIPT, encoding="utf-8")
    out = subprocess.run([sys.executable, str(script), str(ROOT / "tools")], cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stdout[-2000:] + out.stderr[-3000:]
    result = json.loads(out.stdout.strip().splitlines()[-1])
    trace = result["trace"]
    assert not any(trace[:20])                 # nothing open before
    assert all(trace[20:27])                   # window open -> airing
    assert not trace[-1]                       # closed again -> airing finished (was: open forever)
    assert "kueche" in result["logged"]        # and recorded as a finished ventilation


def test_airing_ended_by_a_dead_contact_is_not_learned():
    coordinator = module_source("coordinator")
    assert 'mem["session_learning_quarantine_code"] = "FAIQ-CONTACT-UNKNOWN-001"' in coordinator
    block = coordinator[coordinator.index('if mem.get("session_contact_unknown_expired"):'):]
    assert "self._finish_session_without_measurement(mem, cfg, session_ended_at)" in block[:500]
    assert 'missing_since.setdefault(contact_id, now)' in coordinator and 'missing_since.pop(contact_id, None)' in coordinator
    card = CARD[CARD.index("    _uiLanguage() {"):]
    assert "this._langHass !== this._hass" in card[:600]  # looked up once per Home Assistant update
