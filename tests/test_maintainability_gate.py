"""Maintainability gate (owner request 2026-10-19): small files and functions, shrinking baseline."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from tests._source import FAMILIES, module_files

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("maintainability_gate", ROOT / "tools/maintainability_gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def _tree(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    (tmp_path / "tools").mkdir(exist_ok=True)
    return tmp_path


def _function(name: str, body_lines: int, indent: str = "") -> str:
    return f"{indent}def {name}():\n" + "".join(f"{indent}    x = {i}\n" for i in range(body_lines - 1))


def _baseline(**sections) -> dict:
    return {"schema": 1, "files": {}, "functions": {}, "frontend": {}, **sections}


def test_repository_passes_the_gate_and_the_quality_gate_runs_it():
    report = gate.check(gate.measure(ROOT), gate.load_baseline())
    assert report.ok, report.failures
    assert report.counts["files"] > 100 and report.counts["functions"] > 1000
    quality_gate = (ROOT / "tools/quality_gate.py").read_text(encoding="utf-8")
    assert '"tools/maintainability_gate.py"' in quality_gate
    assert gate.MAX_FILE_LINES == 800 and gate.MAX_FUNCTION_LINES == 150 and gate.MAX_FRONTEND_BYTES == 200_000


def test_every_baseline_entry_has_a_reason_and_is_still_over_its_limit():
    baseline = gate.load_baseline()
    measured = gate.measure(ROOT)
    for section, unit, limit, _label in gate._SECTIONS:
        for key, entry in baseline[section].items():
            assert entry.get("reason"), key
            assert key in measured[section], key
            assert limit < measured[section][key] <= entry[unit], key


def test_split_modules_stay_within_the_limits():
    measured = gate.measure(ROOT)
    split = [path.relative_to(ROOT).as_posix() for family in FAMILIES for path in module_files(family)]
    assert len(split) >= 35
    for rel in split:
        assert measured["files"][rel] <= gate.MAX_FILE_LINES, rel
    for key, size in measured["functions"].items():
        if key.split("::")[0] in split:
            assert size <= gate.MAX_FUNCTION_LINES, key


def test_unlisted_oversized_file_function_and_frontend_module_fail(tmp_path):
    root = _tree(tmp_path, {
        "custom_components/freshairiq/big.py": "x = 1\n" * 801,
        "custom_components/freshairiq/long.py": _function("long", 151),
        "custom_components/freshairiq/ok.py": _function("ok", 150),
        "custom_components/freshairiq/frontend/card.js": "a" * 200_001,
        "custom_components/freshairiq/frontend/small.js": "a" * 200_000,
    })
    report = gate.check(gate.measure(root), _baseline())
    assert not report.ok
    joined = "\n".join(report.failures)
    assert "custom_components/freshairiq/big.py: 801 lines > 800" in joined
    assert "custom_components/freshairiq/long.py::long: 151 lines > 150" in joined
    assert "custom_components/freshairiq/frontend/card.js: 200001 bytes > 200000" in joined
    assert "ok.py" not in joined and "small.js" not in joined


def test_nested_functions_and_methods_are_measured_on_their_own(tmp_path):
    source = "class Flow:\n" + _function("step", 3, "    ") + "def outer():\n" + _function("inner", 160, "    ")
    root = _tree(tmp_path, {"tools/sample.py": source})
    functions = gate.measure(root)["functions"]
    assert functions["tools/sample.py::Flow.step"] == 3
    assert functions["tools/sample.py::outer.inner"] == 160
    assert functions["tools/sample.py::outer"] == 161


def test_listed_entries_may_shrink_but_never_grow(tmp_path):
    root = _tree(tmp_path, {"tools/legacy.py": _function("legacy", 200)})
    key = "tools/legacy.py::legacy"
    same = _baseline(functions={key: {"lines": 200, "reason": "legacy"}})
    assert gate.check(gate.measure(root), same).ok
    smaller = _baseline(functions={key: {"lines": 199, "reason": "legacy"}})
    report = gate.check(gate.measure(root), smaller)
    assert report.failures == [f"function {key}: grew to 200 lines (baseline 199)"]


def test_entries_within_limits_or_gone_are_reported(tmp_path):
    root = _tree(tmp_path, {"tools/small.py": _function("small", 10)})
    baseline = _baseline(
        functions={"tools/small.py::small": {"lines": 300, "reason": "was long"},
                   "tools/gone.py::gone": {"lines": 300, "reason": "removed"}},
    )
    report = gate.check(gate.measure(root), baseline)
    assert report.ok
    assert report.within_limits == ["function tools/small.py::small: 10 lines is within 150; remove it from the baseline"]
    assert report.stale == ["function tools/gone.py::gone: no longer exists; remove it from the baseline"]


def test_update_baseline_only_lowers_or_removes(tmp_path):
    root = _tree(tmp_path, {
        "tools/shrunk.py": _function("shrunk", 180),
        "tools/grown.py": _function("grown", 400),
        "tools/fixed.py": _function("fixed", 20),
        "tools/new.py": _function("new", 999),
    })
    baseline = _baseline(functions={
        "tools/shrunk.py::shrunk": {"lines": 250, "reason": "a"},
        "tools/grown.py::grown": {"lines": 300, "reason": "b"},
        "tools/fixed.py::fixed": {"lines": 220, "reason": "c"},
        "tools/gone.py::gone": {"lines": 220, "reason": "d"},
    })
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(baseline), encoding="utf-8")
    assert gate.main(["--root", str(root), "--baseline", str(path), "--update-baseline"]) == 1
    updated = json.loads(path.read_text(encoding="utf-8"))["functions"]
    assert updated == {
        "tools/grown.py::grown": {"lines": 300, "reason": "b"},
        "tools/shrunk.py::shrunk": {"lines": 180, "reason": "a"},
    }


def test_command_line_passes_on_the_repository(capsys):
    assert gate.main([]) == 0
    assert "Maintainability gate: PASS" in capsys.readouterr().out
