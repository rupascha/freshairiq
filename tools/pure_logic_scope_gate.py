"""Fail closed if the pure-logic coverage boundary drifts.

Every top-level FreshAirIQ Python module is classified mechanically:
modules importing Home Assistant/aiohttp belong to the HA-runtime scope;
all others belong to the 100% pure-logic line-coverage scope.
"""
from __future__ import annotations
import ast
import configparser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components/freshairiq"
CONFIG = ROOT / ".coveragerc-pure"
ADAPTER_PREFIXES = ("homeassistant", "aiohttp")


def _imports_adapter(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        if any(name.startswith(ADAPTER_PREFIXES) for name in names):
            return True
    return False


def main() -> int:
    parser = configparser.ConfigParser()
    parser.read(CONFIG, encoding="utf-8")
    raw = parser.get("run", "omit", fallback="")
    omitted = {Path(line.strip()).name for line in raw.splitlines() if line.strip()}
    modules = {path.name: path for path in COMP.glob("*.py")}
    failures: list[str] = []
    stale = sorted(omitted - set(modules))
    if stale:
        failures.append("stale/nonexistent omit entries: " + ", ".join(stale))
    for name, path in sorted(modules.items()):
        adapter = _imports_adapter(path)
        if adapter and name not in omitted:
            failures.append(f"HA/aiohttp adapter missing from omit scope: {name}")
        elif not adapter and name in omitted:
            failures.append(f"pure module incorrectly omitted from 100% scope: {name}")
    if parser.getboolean("run", "branch", fallback=True):
        failures.append("pure-logic contract is line coverage; branch must be False")
    if parser.getfloat("report", "fail_under", fallback=0) != 100.0:
        failures.append("pure-logic fail_under must remain exactly 100")
    if failures:
        print("Pure-logic scope gate: FAIL")
        for failure in failures:
            print(" -", failure)
        return 1
    pure_count = sum(1 for p in modules.values() if not _imports_adapter(p))
    adapter_count = len(modules) - pure_count
    print(f"Pure-logic scope gate: PASS ({pure_count} pure modules, {adapter_count} HA/aiohttp adapters)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
