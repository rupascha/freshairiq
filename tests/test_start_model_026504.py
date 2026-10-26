"""0.26.5.4: start model – better starting exchange rates for rooms that have not learned yet.

The learning moves a room's rate by at most 15 % per airing, so the starting
value decides how long new rooms forecast badly. The hub derives a start model
from real airings of other homes; only recommended values are shipped
(``tools/apply_start_model.py``). The shipped model is empty: nothing changes
until one is taken over.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from custom_components.freshairiq.model import update_learning
from custom_components.freshairiq.start_model import (
    DEFAULT_RATES, FORMAT, learning_observation, observed_exchange_rate, seed_room, size_bucket, start_rate, validate,
)
from custom_components.freshairiq.start_model_data import START_MODEL
from custom_components.freshairiq.storage_defaults import _room_defaults

ROOT = Path(__file__).resolve().parents[1]
MODEL = validate({"format": FORMAT, "format_version": 1, "version": "2026-11", "cells": [
    {"mode": "open", "size": "<15", "rate_per_min": 0.06}, {"mode": "open", "size": "all", "rate_per_min": 0.045},
    {"mode": "tilted", "size": "all", "rate_per_min": 0.02}, {"mode": "mechanical_exhaust", "size": "<15", "rate_per_min": 0.05},
]})


def test_the_shipped_model_is_empty_and_changes_nothing() -> None:
    shipped = validate(START_MODEL)
    assert shipped["cells"] == [] and shipped["version"] is None
    mem = _room_defaults()
    assert seed_room(mem, shipped, 12) is False and mem == _room_defaults()


@pytest.mark.parametrize(("volume", "bucket"), [(9, "<15"), (15, "15-30"), (45, "30-60"), (60, ">=60"), (0, None), ("x", None), (float("nan"), None)])
def test_size_buckets(volume, bucket) -> None:
    assert size_bucket(volume) == bucket


def test_validation_drops_everything_malformed() -> None:
    assert validate(None)["cells"] == [] and validate({"format": "x"})["cells"] == []
    assert validate({"format": FORMAT, "format_version": 2, "cells": [{}]})["cells"] == []
    dirty = validate({"format": FORMAT, "format_version": 1, "version": "", "cells": [
        {"mode": "open", "size": "all", "rate_per_min": 0.5}, {"mode": "door", "size": "all", "rate_per_min": 0.03},
        {"mode": "open", "size": "huge", "rate_per_min": 0.03}, "x", {"mode": "cross", "size": ">=60", "rate_per_min": "0.031234567"},
    ]})
    assert dirty == {"format": FORMAT, "format_version": 1, "version": None, "cells": [{"mode": "cross", "size": ">=60", "rate_per_min": 0.03123}]}
    assert validate({**MODEL, "cells": "x"})["cells"] == []


def test_lookup_prefers_the_size_cell() -> None:
    assert start_rate(MODEL, "open", 9) == 0.06
    assert start_rate(MODEL, "open", 40) == 0.045
    assert start_rate(MODEL, "tilted", 9) == 0.02
    assert start_rate(MODEL, "cross", 9) is None
    assert start_rate(MODEL, "open", None) == 0.045


def test_a_new_room_starts_from_the_model_and_a_learned_room_is_never_touched() -> None:
    mem = _room_defaults()
    assert seed_room(mem, MODEL, 9) is True
    assert mem["learning_rate"] == 0.06
    assert mem["opening_learning"]["open"]["rate"] == 0.06 and mem["opening_learning"]["tilted"]["rate"] == 0.02
    assert mem["opening_learning"]["cross"]["rate"] == DEFAULT_RATES["cross"]  # no value: built-in
    assert mem["opening_learning"]["mechanical_exhaust"] == {"rate": 0.05, "samples": 0, "credit": 0.0}  # created for its first airing
    assert mem["start_model"] == {"version": "2026-11", "rates": {"open": 0.06, "tilted": 0.02, "mechanical_exhaust": 0.05}}
    assert seed_room(mem, MODEL, 9) is False  # idempotent

    learned = _room_defaults()
    learned.update(learning_rate=0.08, learning_samples=3)
    learned["opening_learning"]["tilted"] = {"rate": 0.011, "samples": 2, "credit": 0.0}
    seed_room(learned, MODEL, 9)
    assert learned["learning_rate"] == 0.08 and learned["opening_learning"]["tilted"]["rate"] == 0.011
    assert learned["start_model"]["rates"] == {"open": 0.06, "mechanical_exhaust": 0.05}

    migrated = _room_defaults()
    migrated["learning_rate"] = 0.05  # a value set elsewhere without samples is kept
    seed_room(migrated, MODEL, 9)
    assert migrated["learning_rate"] == 0.05


def test_a_withdrawn_model_returns_unlearned_values_to_the_built_in_start() -> None:
    mem = _room_defaults()
    seed_room(mem, MODEL, 9)
    mem["opening_learning"]["tilted"].update(rate=0.013, samples=1)  # tilted has learned meanwhile
    empty = validate(START_MODEL)
    assert seed_room(mem, empty, 9) is True
    assert mem["learning_rate"] == 0.03 and mem["opening_learning"]["open"]["rate"] == 0.03
    assert mem["opening_learning"]["mechanical_exhaust"]["rate"] == 0.02
    assert mem["opening_learning"]["tilted"]["rate"] == 0.013 and "start_model" not in mem
    no_rows = {"learning_rate": 0.03, "learning_samples": 0}
    assert seed_room(no_rows, MODEL, 40) is True and no_rows["learning_rate"] == 0.045


@pytest.mark.parametrize(("start", "end", "source", "elapsed"), [
    (12.0, 10.0, 7.0, 10.0), (12.0, 11.0, 9.0, 30.0), (10.0, 9.9, 9.0, 5.0), (10.0, 9.0, 9.8, 5.0),
    (12.0, 10.0, 7.0, 1.0), (12.0, 10.0, 7.0, 200.0), (12.0, 2.0, 7.0, 3.0), (12.0, 11.99, 7.0, 60.0),
])
def test_observed_rate_follows_the_learning_rules(start, end, source, elapsed) -> None:
    observed = observed_exchange_rate(start_ah=start, end_ah=end, source_ah=source, elapsed_min=elapsed, max_duration_min=120)
    _rate, _samples, _diag, valid = update_learning(old_rate=0.03, old_samples=0, elapsed_min=elapsed, start_ah=start, end_ah=end,
                                                    source_ah=source, learning_enabled=True, max_duration_min=120)
    assert (observed is not None) == valid
    if valid:
        assert observed == round((start - end) / (start - source) / elapsed, 5)


def test_learning_observation_record() -> None:
    row = learning_observation(start_ah=12.0, end_ah=10.0, source_ah=7.0, elapsed_min=10.0, max_duration_min=120,
                               rate_before=0.03, samples_before=2, usable=True)
    assert row == {"observed_rate_per_min": 0.04, "usable": True, "start_ah": 12.0, "end_ah": 10.0, "source_ah": 7.0,
                   "elapsed_min": 10.0, "rate_before": 0.03, "samples_before": 2}
    blocked = learning_observation(start_ah=12.0, end_ah=10.0, source_ah=None, elapsed_min="x", max_duration_min=None,
                                   rate_before=None, samples_before=None, usable=False)
    assert blocked["observed_rate_per_min"] is None and blocked["source_ah"] is None and blocked["samples_before"] == 0


# --------------------------------------------------------------------------- tools/apply_start_model.py

def _tool():
    spec = importlib.util.spec_from_file_location("apply_start_model", ROOT / "tools/apply_start_model.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CANDIDATE = {"format": "freshairiq-start-model-candidate", "version": "2026-11-01", "hub_version": "0.3.3.92",
             "generated_at": "2026-11-01T00:00:00+00:00", "rule": "leave-one-installation-out",
             "cells": [{"mode": "open", "size": "<15", "rate_per_min": 0.06, "recommended": True},
                       {"mode": "tilted", "size": "all", "rate_per_min": 0.02, "recommended": False}]}


def test_only_recommended_values_are_taken_over(tmp_path, monkeypatch, capsys) -> None:
    tool = _tool()
    model = tool.shipped_model(CANDIDATE)
    assert model["cells"] == [{"mode": "open", "size": "<15", "rate_per_min": 0.06}] and model["version"] == "2026-11-01"
    for bad in ({"format": "x"}, {**CANDIDATE, "cells": [{**CANDIDATE["cells"][1]}]},
                {**CANDIDATE, "cells": [{"mode": "open", "size": "<15", "rate_per_min": 9, "recommended": True}]},
                {**CANDIDATE, "version": None}):
        with pytest.raises(ValueError):
            tool.shipped_model(bad)
    source = tmp_path / "candidate.json"
    source.write_text(json.dumps(CANDIDATE))
    target = tmp_path / "start_model_data.py"
    monkeypatch.setattr(tool, "TARGET", target)
    monkeypatch.setattr(tool, "ROOT", tmp_path)
    assert tool.main([str(source), "--check"]) == 0 and not target.exists()
    assert tool.main([str(source)]) == 0
    namespace: dict = {}
    exec(target.read_text(), namespace)  # noqa: S102 - the generated file is plain data
    assert validate(namespace["START_MODEL"])["cells"] == model["cells"]
    assert tool.main([str(tmp_path / "missing.json")]) == 1
    assert "refused" in capsys.readouterr().out


def test_a_real_hub_candidate_is_taken_over_with_only_its_recommended_values() -> None:
    """Cross-repository contract: candidate produced by the hub (freshairiq_hub.start_model, 0.3.3.92)."""
    candidate = json.loads((ROOT / "tests/fixtures/hub_start_model_candidate.json").read_text(encoding="utf-8"))
    assert candidate["defaults"] == DEFAULT_RATES  # the hub compares with the integration's built-in start values
    model = _tool().shipped_model(candidate)
    recommended = {(c["mode"], c["size"]) for c in candidate["cells"] if c["recommended"]}
    assert {(c["mode"], c["size"]) for c in model["cells"]} == recommended
    assert ("tilted", "all") not in recommended  # no benefit there: stays at the built-in value
    mem = _room_defaults()
    seed_room(mem, validate(model), 9)
    assert mem["learning_rate"] == start_rate(model, "open", 9) and mem["opening_learning"]["tilted"]["rate"] == 0.015
    assert mem["opening_learning"]["mechanical_exhaust"]["rate"] == start_rate(model, "mechanical_exhaust", 9)


def test_the_tool_runs_as_a_plain_command_without_home_assistant(tmp_path) -> None:
    """The release step runs outside Home Assistant (the test stub must not hide an import of the package)."""
    source = tmp_path / "candidate.json"
    source.write_text((ROOT / "tests/fixtures/hub_start_model_candidate.json").read_text(encoding="utf-8"), encoding="utf-8")
    result = subprocess.run([sys.executable, "-I", str(ROOT / "tools/apply_start_model.py"), str(source), "--check"],
                            capture_output=True, text=True, timeout=60, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "values valid (not written)" in result.stdout and "homeassistant" not in result.stderr


def test_the_diagnostics_hint_names_the_benefit_in_both_languages() -> None:
    """0.26.5.4 (owner): asking for diagnostics says what they are good for – card hint and settings page."""
    data = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card-data.js").read_text(encoding="utf-8")
    for text in ("neue Räume schneller", "Prognosen werden für alle genauer", "ohne Zustimmung wird nichts gesendet",
                 "new rooms learn faster", "forecasts more accurate for everyone", "nothing is sent without consent"):
        assert text in data
    for language, words in (("de", ("Neue Räume lernen schneller", "Ohne Zustimmung wird nichts gesendet", "HTTPS")),
                            ("en", ("New rooms learn faster", "Nothing is sent without your consent", "HTTPS"))):
        translations = json.loads((ROOT / f"custom_components/freshairiq/translations/{language}.json").read_text(encoding="utf-8"))
        step = translations["options"]["step"]["diagnostics_sharing"]
        assert all(word in step["description"] for word in words)
        # the former text claimed sharing was on by default and went to a local hub – neither is true
        assert "standardmäßig täglich nachts aktiv" not in step["description"] and "staging" not in step["description"].lower()
