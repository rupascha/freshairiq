"""Take a start model recommended by the diagnostics hub into the integration.

    python tools/apply_start_model.py <start-model-candidate.json> [--check]

The hub (Admin → Ausgangsmodell, ``GET /admin/api/start-model``) derives
starting exchange rates from real airings and checks every value against
installations it has not seen. This tool takes over only the cells the hub
marked ``recommended`` and writes them to
``custom_components/freshairiq/start_model_data.py``; it refuses anything
else. ``--check`` only validates and prints what would be written.

Run the full test suite and the golden master afterwards: a start model
changes the starting values of rooms that have not learned yet.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import pprint

ROOT = Path(__file__).resolve().parents[1]


def _start_model_module():
    """The pure module itself – importing the package would need Home Assistant."""
    spec = importlib.util.spec_from_file_location("freshairiq_start_model", ROOT / "custom_components/freshairiq/start_model.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MODEL = _start_model_module()
FORMAT, FORMAT_VERSION, validate = _MODEL.FORMAT, _MODEL.FORMAT_VERSION, _MODEL.validate

TARGET = ROOT / "custom_components/freshairiq/start_model_data.py"
CANDIDATE_FORMAT = "freshairiq-start-model-candidate"


def shipped_model(candidate: dict) -> dict:
    """The start model to ship: only recommended cells; raises ValueError otherwise."""
    if not isinstance(candidate, dict) or candidate.get("format") != CANDIDATE_FORMAT:
        raise ValueError(f"not a hub start-model candidate (format {CANDIDATE_FORMAT!r} expected)")
    cells = [c for c in candidate.get("cells") or [] if isinstance(c, dict) and c.get("recommended") is True]
    if not cells:
        raise ValueError("the candidate has no recommended value – nothing to take over")
    model = {
        "format": FORMAT, "format_version": FORMAT_VERSION, "version": candidate.get("version"),
        "source": {"hub_version": candidate.get("hub_version"), "generated_at": candidate.get("generated_at"),
                   "rule": candidate.get("rule")},
        "cells": [{"mode": c.get("mode"), "size": c.get("size"), "rate_per_min": c.get("rate_per_min")} for c in cells],
    }
    clean = validate(model)
    if len(clean["cells"]) != len(cells) or not clean["version"]:
        raise ValueError("the candidate contains invalid cells or no version")
    return {**clean, "source": model["source"]}


def render(model: dict) -> str:
    return (
        '"""Shipped start model (written by ``tools/apply_start_model.py``; see ``start_model``)."""\n'
        f"START_MODEL = {pprint.pformat(model, width=110, sort_dicts=False)}\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        model = shipped_model(json.loads(args.candidate.read_text(encoding="utf-8")))
    except (OSError, ValueError) as err:
        print(f"start model refused: {err}")
        return 1
    for cell in model["cells"]:
        print(f"  {cell['mode']:<20} {cell['size']:<6} {cell['rate_per_min']:.4f}/min")
    if args.check:
        print(f"start model {model['version']}: {len(model['cells'])} values valid (not written)")
        return 0
    TARGET.write_text(render(model), encoding="utf-8")
    print(f"start model {model['version']}: {len(model['cells'])} values written to {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
