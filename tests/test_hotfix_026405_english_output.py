"""0.26.4.5: FreshAirIQ is fully usable with an English Home Assistant.

Decisions are always computed in German; English is produced at the output
boundary (coordinator payload, push notifications, PDF, API errors, setup texts).
German installations must stay byte-identical.
"""
from __future__ import annotations

import asyncio
import ast
import json
import re
import subprocess
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

if "homeassistant" not in sys.modules:  # pure-logic CI runs without Home Assistant
    _ha = types.ModuleType("homeassistant")
    _core = types.ModuleType("homeassistant.core")

    class HomeAssistant:  # pragma: no cover
        pass

    _core.HomeAssistant = HomeAssistant
    _ha.core = _core
    sys.modules["homeassistant"] = _ha
    sys.modules["homeassistant.core"] = _core

from custom_components.freshairiq import localize
from custom_components.freshairiq.localize import Translator, is_german, protected_names, to_english
from custom_components.freshairiq.notifications import notification_translator, process_notifications
from custom_components.freshairiq.text_en import EXACT, TEMPLATES
from custom_components.freshairiq.ventilation_log import build_ventilation_pdf
from tests.frontend_source import card_text

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components/freshairiq"


# --------------------------------------------------------------------------- language rule

def test_only_german_stays_german_every_other_language_gets_english():
    assert is_german("de") and is_german("de-CH") and is_german(" DE ")
    assert is_german(None)  # unknown -> unchanged legacy behaviour
    assert not is_german("en") and not is_german("en-GB") and not is_german("fr") and not is_german("nl")


# --------------------------------------------------------------------------- table integrity

def test_translation_table_is_well_formed():
    assert len(EXACT) > 400 and len(TEMPLATES) > 150
    for de, en in EXACT.items():
        assert de and en and de != en or de == en == "Winter" or de.strip() == en.strip(), de
    for literals, en in TEMPLATES:
        groups = len(literals) - 1
        used = {int(x) for x in re.findall(r"\{(\d+)\}", en)}
        assert used == set(range(groups)), (literals, en)
        assert not re.search(r"[äöüßÄÖÜ]", en), en
    for en in EXACT.values():
        assert not re.search(r"[äöüßÄÖÜ]", en), en


# --------------------------------------------------------------------------- translator

def test_exact_lowercase_and_edge_variants():
    t = Translator()
    assert t.text("Jetzt lüften") == "Ventilate now"
    assert t.text("jetzt lüften") == "ventilate now"  # lower-case variant keeps the case
    assert t.text("Für das Stoßlüften sind noch etwa 12 Minuten Zeit") == "About 12 minutes are left for airing"
    # A fragment stored with a leading separator also works on its own.
    assert t.text("noch ca. 4 min") == "about 4 min left"
    assert t.text("  Jetzt lüften  ") == "  Ventilate now  "
    assert t.text("  Wohnzimmer  ") == "  Wohnzimmer  "
    assert t.text("") == "" and t.text("42 ml") == "42 ml"


def test_templates_protect_user_names_and_translate_nested_values():
    t = Translator({"Bad", "Flur EG"})
    # "Bad" would be "Bath" as a moisture-source label – as a room name it stays.
    assert t.text("Bad schließen") == "Close Bad"
    assert t.text("Bad + Flur EG schließen") == "Close Bad + Flur EG"
    assert t.text("Lernmodell passt die Dauer um 3 min länger an") == "Learning model makes the duration 3 min longer"
    assert t.text("Spring: no daily evidence yet") == "Spring: no daily evidence yet"


def test_untranslatable_values_never_produce_half_translations():
    t = Translator()
    unknown = "Ein völlig unbekannter Satz mit Wörtern, die nicht übersetzt sind"
    assert t.text(unknown) == unknown
    # Template matches whose interpolated value is untranslatable German are rejected.
    assert t.text(unknown + " schließen") == unknown + " schließen"


def test_sentences_segments_and_glued_texts():
    t = Translator()
    assert t.text("Jetzt lüften. Sensoren prüfen.") == "Ventilate now. Check sensors."
    assert t.text("JETZT LÜFTEN") == "VENTILATE NOW" and t.text("jetzt") == "now"
    assert t.text("aktuelle außenbedingungen") == "current outdoor conditions"
    assert t.text("SENSOREN PRÜFEN") == "CHECK SENSORS"
    assert t.text("Aktuelle Außenbedingungen") == "Current outdoor conditions"
    glued_unknown = "Hinweis Lüftung beendet: noch nicht bekannt ml entfernt"
    assert t.text(glued_unknown) == glued_unknown
    assert t.text("Jetzt lüften · Sensoren prüfen") == "Ventilate now · Check sensors"
    glued = ("Ist-Verlauf entspricht dem gelernten Lüftungsmodell FreshAirIQ arbeitet hier noch "
             "überwiegend mit Gebäudephysik und aktuellen Messdaten.")
    assert t.text(glued) == ("Actual trend matches the learned ventilation model FreshAirIQ is still "
                             "working mainly with building physics and current readings here.")
    mixed = "Jetzt lüften · völlig unbekannter Rest ohne Übersetzung"
    assert t.text(mixed) == "Ventilate now · völlig unbekannter Rest ohne Übersetzung"


def test_depth_limit_and_bounded_cache(monkeypatch):
    t = Translator()
    assert t._translate("Jetzt lüften", localize._MAX_DEPTH + 1) == "Jetzt lüften"
    monkeypatch.setattr(localize, "_CACHE_LIMIT", 2)
    for text in ("Jetzt lüften", "Sensoren prüfen", "Jetzt schließen"):
        t.text(text)
    assert len(t._cache) == 1
    assert t.text("Jetzt schließen") == "Close now"  # served from cache


def test_payload_copy_skips_user_data_and_machine_values():
    t = Translator({"Küche"})
    payload = {
        "status": "close_windows",
        "kind": "Lüften",
        "title": "Jetzt lüften",
        "rooms": {"kueche": {"name": "Küche", "reasons": ["Sensoren prüfen", 3, None], "pair": ("Jetzt lüften", 1.5)}},
        "learning_components": {"components": [{"status": "Lernt", "label": "Nachtmodell"}]},
        7: "Jetzt schließen",
    }
    out = t.payload(payload)
    assert out["status"] == "close_windows" and out["kind"] == "Lüften"
    assert out["title"] == "Ventilate now"
    assert out["rooms"]["kueche"]["name"] == "Küche"
    assert out["rooms"]["kueche"]["reasons"] == ["Check sensors", 3, None]
    assert out["rooms"]["kueche"]["pair"] == ("Ventilate now", 1.5)
    assert out["learning_components"]["components"][0] == {"status": "Learning", "label": "Night model"}
    assert out[7] == "Close now"
    assert payload["title"] == "Jetzt lüften"  # input untouched


def test_protected_names_cover_rooms_floors_and_residents():
    names = protected_names(
        {"rooms": [{"name": "Bad", "key": "bad", "floor": "Unzugeordnet"}, "broken", {"name": "Büro", "floor": "ground_floor"}],
         "levels": ["Dachgeschoss", "upper_floor"]},
        {"adult_resident_names": "Anna; Ben\nCarla", "child_resident_names": ["Dora", " "]},
    )
    assert names == {"Bad", "bad", "Büro", "Dachgeschoss", "Anna", "Ben", "Carla", "Dora"}
    assert protected_names(None, None) == set()
    assert to_english("Fenster schließen", {"Fenster"}) == "Close Fenster"


def test_template_variants_only_trim_real_fragments():
    assert localize._template_variants(("x",), "y") == [(("x",), "y")]
    assert localize._template_variants(("", " schließen"), "Close {0}") == [(("", " schließen"), "Close {0}")]
    variants = localize._template_variants((" · noch ca. ", " min"), " · about {0} min left")
    assert (("noch ca. ", " min"), "about {0} min left") in variants
    assert (("· noch ca. ", " min"), "· about {0} min left") in variants
    assert (("", " passt."), "{0} fits.") in localize._template_variants(("", " passt. "), "{0} fits. ")
    assert len(localize._template_variants(("Ziel etwa ", " min"), "Target about {0} min")) == 1


# --------------------------------------------------------------------------- coordinator

def test_english_home_assistant_gets_english_payload_with_identical_learning_state():
    result = subprocess.run([sys.executable, "tools/coordinator_golden.py", "--english"],
                            cwd=ROOT, capture_output=True, text=True, timeout=900)
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]
    assert "english output OK" in result.stdout


def test_coordinator_translates_only_the_published_copy():
    source = (COMP / "coordinator.py").read_text(encoding="utf-8")
    assert "return self._localize_output(data)" in source
    assert 'localized["output_language"] = "en"' in source
    assert "if not isinstance(language, str) or is_german(language):" in source


# --------------------------------------------------------------------------- notifications

class _Services:
    def __init__(self):
        self.calls = []

    def has_service(self, domain, service):
        return domain == "notify" and service == "phone"

    async def async_call(self, domain, service, data, blocking=False):
        self.calls.append(data)


class _Hass:
    def __init__(self, language):
        self.services = _Services()
        self.config = types.SimpleNamespace(language=language)


class _Store:
    def __init__(self):
        self.data, self.rooms = {}, {}

    def room(self, key):
        return self.rooms.setdefault(key, {})


def _notify(language):
    hass, store = _Hass(language), _Store()
    rooms = {
        "v": {"key": "v", "name": "Bad", "action": "Ventilate", "data_quality": "ok", "mould_level": "Low"},
        "x": {"key": "x", "name": "Schlafzimmer", "action": "Close", "data_quality": "ok", "mould_level": "Low", "forecast_horizon_min": 5},
        "s": {"key": "s", "name": "Büro", "action": "Wait", "data_quality": "stale", "mould_level": "Low"},
    }
    options = {"notifications_enabled": True, "notification_targets": ["notify.phone"], "notification_scope": "room",
               "notification_cooldown_min": 90, "notification_room_keys": [], "notify_ventilate": True,
               "notify_close": True, "notify_sensor": True, "night_start_hour": "22:00", "night_end_hour": "07:00"}
    now = datetime(2026, 10, 8, 18, 0, tzinfo=timezone.utc)
    asyncio.run(process_notifications(hass, store, {"rooms": rooms, "intelligent_recommendation": {}}, options, now, []))
    return hass.services.calls


def test_push_notifications_follow_the_home_assistant_language():
    english = _notify("en")
    text = "\n".join(f"{c.get('title', '')} {c['message']}" for c in english)
    assert "Ventilate now" in text and "Check sensors" in text
    assert localize._german_score(text, {"Bad", "Schlafzimmer", "Büro"}) == 0, text
    german = "\n".join(c["message"] for c in _notify("de"))
    assert "Jetzt lüften" in german and "Sensoren prüfen" in german


def test_notification_translator_only_for_non_german_string_languages():
    assert notification_translator(_Hass("de"), {}, {}) is None
    assert notification_translator(types.SimpleNamespace(config=types.SimpleNamespace(language=object())), {}, {}) is None
    assert notification_translator(types.SimpleNamespace(), {}, {}) is None
    translator = notification_translator(_Hass("fr"), {"rooms": {"a": {"name": "Bad"}, "b": "x"}, "levels": ["OG"]}, {})
    assert translator.text("Bad schließen") == "Close Bad"


# --------------------------------------------------------------------------- PDF / APIs / repairs

def _pdf_text(pdf: bytes) -> str:
    return pdf.decode("latin1")


def test_ventilation_log_pdf_is_english_for_english_installations():
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 8, tzinfo=timezone.utc)
    events = [{"room_name": "Kitchen", "started_at": "2026-10-02T08:00:00+00:00", "ended_at": "2026-10-02T08:10:00+00:00",
               "duration_min": 10, "start_temperature_c": 21.5, "end_temperature_c": 20.1, "removed_ml": 120.4,
               "measurement_valid": True, "recommendation_followed": True}]
    english = _pdf_text(build_ventilation_pdf(events, start, end, "en"))
    assert "Ventilation log" in english and "Summary" in english and "Yes" in english and "2026-10-01" in english
    assert "21.5 -> 20.1" in english
    assert "Lueftungsprotokoll" not in english and "Zusammenfassung" not in english
    german = _pdf_text(build_ventilation_pdf(events, start, end))
    assert "Lueftungsprotokoll" in german and "21,5 -> 20,1" in german and "01.10.2026" in german
    empty = _pdf_text(build_ventilation_pdf([], start, end, "en-GB"))
    assert "No recorded ventilations in the selected period." in empty


def test_api_errors_and_repairs_follow_the_language():
    for name in ("ventilation_log_api.py", "feedback_api.py"):
        source = (COMP / name).read_text(encoding="utf-8")
        assert "_msg(hass," in source
        assert not re.search(r'"error":\s*"[^"]*[äöüß]', source), name
    from collections.abc import Mapping
    from typing import Any

    from custom_components.freshairiq import const
    from custom_components.freshairiq.climate_sources import entity_ids

    repairs = (COMP / "repairs.py").read_text(encoding="utf-8")
    tree = ast.parse(repairs)
    wanted = [ast.get_source_segment(repairs, n) for n in tree.body
              if getattr(n, "name", None) == "_required_entity_references"
              or (isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "_CONTEXT_EN")]
    ns = {"Mapping": Mapping, "Any": Any, "FreshAirIQConfigEntry": object, "entity_ids": entity_ids,
          **{k: v for k, v in vars(const).items() if k.startswith("CONF_")}}
    exec(compile("from __future__ import annotations\n" + "\n".join(wanted), "repairs", "exec"), ns)
    _required_entity_references = ns["_required_entity_references"]
    assert 'language = language if isinstance(language, str) else "de"' in repairs

    entry = types.SimpleNamespace(data={"outdoor_weather": "weather.home", "rooms": [
        {"name": "Kitchen", "temperature": "sensor.t", "humidity": "sensor.h", "contacts": ["binary_sensor.w"]}]})
    english = dict((e, c) for e, c in _required_entity_references(entry, "en"))
    assert english == {"weather.home": "Outdoor weather", "sensor.t": "Kitchen: Temperature",
                       "sensor.h": "Kitchen: Humidity", "binary_sensor.w": "Kitchen: Window/door"}
    german = dict((e, c) for e, c in _required_entity_references(entry))
    assert german["weather.home"] == "Außenwetter" and german["sensor.h"] == "Kitchen: Luftfeuchte"


# --------------------------------------------------------------------------- setup flow

def _load(names, extra=""):
    flow = (COMP / "config_flow.py").read_text(encoding="utf-8")
    tree = ast.parse(flow)
    src = []
    for node in tree.body:
        target = getattr(node, "name", None) or (node.targets[0].id if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) else None)
        if target in names:
            src.append(ast.get_source_segment(flow, node))
    ns: dict = {}
    exec(compile("from typing import Any\n" + extra + "\n".join(src), "flow", "exec"), ns)
    return ns


def test_setup_flow_labels_follow_the_home_assistant_language():
    ns = _load({"_LEGACY_LEVEL_LABELS", "_LEGACY_LEVEL_LABELS_EN", "_is_de", "_flow_language", "_txt", "_level_label", "_level_options"})
    assert ns["_level_label"]("ground_floor") == "Erdgeschoss"
    assert ns["_level_label"]("ground_floor", "en") == "Ground floor"
    assert ns["_level_label"]("Unzugeordnet", "fr") == "Unassigned"
    assert ns["_level_label"]("", "en") == "Unassigned" and ns["_level_label"]("") == "Nicht zugeordnet"
    assert ns["_level_options"](["attic"], "en") == [{"value": "attic", "label": "Attic"}]
    assert ns["_txt"]("en", "Raum", "Room") == "Room" and ns["_txt"]("de-AT", "Raum", "Room") == "Raum"
    assert ns["_flow_language"](None) == "de"
    assert ns["_flow_language"](types.SimpleNamespace()) == "de"
    assert ns["_flow_language"](types.SimpleNamespace(config=types.SimpleNamespace(language="en"))) == "en"


def test_resident_slots_are_english_for_other_languages_too():
    ns = _load({"_resident_name_list", "_resident_slot_placeholders"}, "import re\n")
    assert ns["_resident_slot_placeholders"]({}, "fr")["adult_1"] == "Adult 1"
    assert ns["_resident_slot_placeholders"]({}, "de")["child_2"] == "Kind 2"


def test_select_options_use_translated_selectors_instead_of_german_labels():
    flow = (COMP / "config_flow.py").read_text(encoding="utf-8")
    for key in ("diagnostics_consent", "diagnostics_reporting_mode", "level_action"):
        assert f'translation_key="{key}"' in flow
    for german in ("Noch nicht entschieden (nichts wird gesendet)", "Nur bei erkannten Problemen", "Bereich hinzufügen"):
        assert f'"label": "{german}"' not in flow
    for path in ("strings.json", "translations/en.json", "translations/de.json"):
        data = json.loads((COMP / path).read_text(encoding="utf-8"))
        assert set(data["selector"]["diagnostics_consent"]["options"]) == {"unset", "granted", "declined"}
        assert set(data["selector"]["diagnostics_reporting_mode"]["options"]) == {"off", "errors", "daily", "weekly"}
        assert set(data["selector"]["level_action"]["options"]) == {"add", "reorder", "remove", "back"}
        assert "close_windows" in data["entity"]["sensor"]["status"]["state"]
    en = json.loads((COMP / "translations/en.json").read_text(encoding="utf-8"))
    assert en["selector"]["diagnostics_reporting_mode"]["options"]["daily"] == "Daily at night"
    assert en["entity"]["sensor"]["status"]["state"]["close_windows"] == "Close windows"


# --------------------------------------------------------------------------- dashboard card

def test_card_understands_english_backend_texts_and_room_names():
    card = card_text()
    assert '/Raumluftfeuchte|Oberflächenfeuchte|Room humidity|Surface humidity|CO₂/.test' in card
    assert 'heroTitle.includes("long opening")' in card and 'heroTitle.includes("do not ventilate")' in card
    for word in ("bedroom", "bath", "hall", "office", "guest", "nursery"):
        assert f'name.includes("{word}")' in card
    assert '["Personen", "people"]' in card


# --------------------------------------------------------------------------- regression guard

# Modules whose German literals never reach an English user through the translator:
# setup texts (translations/*.json), diagnostics for the Hub, entity fallback names
# (entities use translation keys), and modules with their own language switch.
_GUARD_SKIP = {
    "config_flow.py", "flow_errors.py", "flow_error_signature.py", "const.py", "__init__.py",
    "text_en.py", "localize.py", "diagnostics.py", "diagnostic_transport.py", "telemetry.py",
    "support_incident.py", "support_replay.py", "guardian.py", "runtime_health.py",
    "ventilation_log.py", "ventilation_log_api.py", "feedback_api.py", "repairs.py",
    "number.py", "select.py", "energy.py",
}
# Fragments that are glued to room names; checked in their assembled form below.
_GUARD_FRAGMENTS = {" schließen", " und ", " öffnen · ca. 7 min", " schließen · CO₂ neu bewerten",
                    " schließen · CO₂ unmittelbar neu bewerten"}


def _german_literals(path: Path):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    skip: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and body \
                and isinstance(body[0], ast.Expr) and isinstance(body[0].value, (ast.Constant, ast.JoinedStr)):
            skip.update(id(n) for n in ast.walk(body[0]))
        if isinstance(node, ast.Call) and re.search(r"(LOGGER|logger)\.", ast.get_source_segment(source, node.func) or ""):
            skip.update(id(n) for n in ast.walk(node))
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if key is not None:
                    skip.update(id(n) for n in ast.walk(key))
        if isinstance(node, (ast.Compare, ast.Set)):
            skip.update(id(n) for n in ast.walk(node))
        if isinstance(node, ast.JoinedStr):
            skip.update(id(v) for v in node.values if isinstance(v, ast.Constant))
    for node in ast.walk(tree):
        if id(node) in skip:
            continue
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            sample = node.value
        elif isinstance(node, ast.JoinedStr):
            sample = "".join(v.value if isinstance(v, ast.Constant) else "7" for v in node.values)
        else:
            continue
        if localize._german_score(sample):
            yield node.lineno, sample


def test_every_user_facing_german_text_has_an_english_translation():
    translator = Translator()
    missing = []
    for path in sorted(COMP.glob("*.py")):
        if path.name in _GUARD_SKIP:
            continue
        for line, sample in _german_literals(path):
            if sample in _GUARD_FRAGMENTS:
                continue
            if localize._german_score(translator.text(sample)):
                missing.append(f"{path.name}:{line}: {sample[:100]!r}")
    assert not missing, "German text without English translation (add it to text_en.py):\n" + "\n".join(missing)
    assembled = Translator({"Bad", "Flur"})
    for fragment in _GUARD_FRAGMENTS:
        text = ("Bad" + fragment + "Flur") if fragment == " und " else ("Bad" + fragment)
        assert not localize._german_score(assembled.text(text), {"Bad", "Flur"}), text
