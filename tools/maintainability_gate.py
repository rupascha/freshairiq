"""Maintainability gate: keep modules and functions small enough to change safely.

Rules (owner request 2026-10-19):
- every Python file under ``custom_components/`` and ``tools/`` has at most
  ``MAX_FILE_LINES`` lines,
- every function or method has at most ``MAX_FUNCTION_LINES`` lines
  (``end_lineno - lineno + 1``, nested functions count on their own),
- every frontend module ``custom_components/freshairiq/frontend/*.js`` has at
  most ``MAX_FRONTEND_BYTES`` bytes.

Existing exceptions are listed in ``quality/maintainability_baseline.json`` with
their current size and a reason. The gate fails when an unlisted file or
function exceeds a limit or when a listed one grows. Listed entries that are
now within the limits (or gone) are reported. ``--update-baseline`` only
lowers or removes entries; it never adds or raises one.

    python tools/maintainability_gate.py
    python tools/maintainability_gate.py --update-baseline
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "quality" / "maintainability_baseline.json"
PYTHON_DIRS = ("custom_components", "tools")
FRONTEND_GLOB = "custom_components/freshairiq/frontend/*.js"
MAX_FILE_LINES = 800
MAX_FUNCTION_LINES = 150
MAX_FRONTEND_BYTES = 200_000
_SKIP_PARTS = {"__pycache__", ".venv", "node_modules"}


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.within_limits: list[str] = []
        self.stale: list[str] = []
        self.counts: dict[str, int] = {}

    @property
    def ok(self) -> bool:
        return not self.failures


def python_files(root: Path) -> Iterator[Path]:
    for base in PYTHON_DIRS:
        for path in sorted((root / base).rglob("*.py")):
            if not _SKIP_PARTS.intersection(path.parts):
                yield path


def function_sizes(tree: ast.AST) -> dict[str, int]:
    """Qualified name (``Class.method``, ``outer.inner``) -> line count."""
    sizes: dict[str, int] = {}

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{prefix}{child.name}"
                sizes[name] = child.end_lineno - child.lineno + 1
                visit(child, f"{name}.")
            elif isinstance(child, ast.ClassDef):
                visit(child, f"{prefix}{child.name}.")
            else:
                visit(child, prefix)

    visit(tree, "")
    return sizes


def measure(root: Path) -> dict[str, dict[str, int]]:
    files: dict[str, int] = {}
    functions: dict[str, int] = {}
    for path in python_files(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        files[rel] = len(text.splitlines())
        for name, size in function_sizes(ast.parse(text, filename=rel)).items():
            functions[f"{rel}::{name}"] = size
    frontend = {
        path.relative_to(root).as_posix(): path.stat().st_size
        for path in sorted(root.glob(FRONTEND_GLOB))
    }
    return {"files": files, "functions": functions, "frontend": frontend}


_SECTIONS = (
    ("files", "lines", MAX_FILE_LINES, "file"),
    ("functions", "lines", MAX_FUNCTION_LINES, "function"),
    ("frontend", "bytes", MAX_FRONTEND_BYTES, "frontend module"),
)


def check(measured: dict[str, dict[str, int]], baseline: dict) -> Report:
    report = Report()
    for section, unit, limit, label in _SECTIONS:
        listed = baseline.get(section, {})
        current = measured[section]
        report.counts[section] = len(current)
        for key, size in sorted(current.items()):
            entry = listed.get(key)
            if entry is None:
                if size > limit:
                    report.failures.append(f"{label} {key}: {size} {unit} > {limit} (not in the baseline)")
            elif size > int(entry[unit]):
                report.failures.append(f"{label} {key}: grew to {size} {unit} (baseline {entry[unit]})")
            elif size <= limit:
                report.within_limits.append(f"{label} {key}: {size} {unit} is within {limit}; remove it from the baseline")
        for key in sorted(set(listed) - set(current)):
            report.stale.append(f"{label} {key}: no longer exists; remove it from the baseline")
    return report


def lowered(measured: dict[str, dict[str, int]], baseline: dict) -> dict:
    """Baseline with entries lowered to their current size; entries within limits or gone are dropped."""
    updated = dict(baseline)
    for section, unit, limit, _label in _SECTIONS:
        entries = {}
        for key, entry in baseline.get(section, {}).items():
            size = measured[section].get(key)
            if size is None or size <= limit:
                continue
            entries[key] = dict(entry, **{unit: min(size, int(entry[unit]))})
        updated[section] = dict(sorted(entries.items()))
    return updated


def load_baseline(path: Path = BASELINE) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--update-baseline", action="store_true", help="lower/remove baseline entries only")
    args = parser.parse_args(argv)
    baseline = load_baseline(args.baseline)
    measured = measure(args.root)
    if args.update_baseline:
        updated = lowered(measured, baseline)
        args.baseline.write_text(json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        baseline = updated
        print(f"Baseline updated: {args.baseline}")
    report = check(measured, baseline)
    for line in report.within_limits + report.stale:
        print("NOTE:", line)
    if not report.ok:
        print("Maintainability gate: FAIL")
        for line in report.failures:
            print(" -", line)
        return 1
    print(
        "Maintainability gate: PASS "
        f"({report.counts['files']} Python files, {report.counts['functions']} functions, "
        f"{report.counts['frontend']} frontend modules; "
        f"{sum(len(baseline.get(s, {})) for s, *_ in _SECTIONS)} baseline exceptions)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
