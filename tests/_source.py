"""Source text of integration modules that were split into several files.

Contract tests pin source text. ``module_source("coordinator")`` returns the
text of ``coordinator.py`` followed by every module split off from it, so a
pinned line keeps matching after the code moved to a sibling module.
"""
from __future__ import annotations

import ast
from pathlib import Path

COMP = Path(__file__).resolve().parents[1] / "custom_components" / "freshairiq"

FAMILIES: dict[str, tuple[str, ...]] = {
    "coordinator": (
        "coordinator.py",
        "coordinator_sources.py",
        "coordinator_contacts.py",
        "room_recommendation.py",
        "coordinator_listeners.py",
        "coordinator_house.py",
        "coordinator_night.py",
        "coordinator_decision.py",
        "coordinator_room.py",
        "coordinator_room_contacts.py",
        "coordinator_room_session.py",
        "coordinator_room_model.py",
        "coordinator_room_result.py",
        "coordinator_sessions.py",
        "coordinator_session_validation.py",
        "coordinator_session_events.py",
    ),
    "config_flow": (
        "config_flow.py",
        "config_flow_fields.py",
        "config_flow_schemas.py",
        "config_flow_goals.py",
        "config_flow_rooms.py",
        "config_flow_subentry.py",
        "config_flow_options.py",
        "config_flow_options_rooms.py",
        "config_flow_options_settings.py",
    ),
    "diagnostic_transport": (
        "diagnostic_transport.py",
        "diagnostic_chunks.py",
    ),
    "storage": (
        "storage.py",
        "storage_defaults.py",
    ),
    "telemetry": (
        "telemetry.py",
        "telemetry_reports.py",
        "telemetry_hub.py",
    ),
    "diagnostics": (
        "diagnostics.py",
        "diagnostics_limits.py",
        "diagnostics_privacy.py",
        "diagnostics_records.py",
        "diagnostics_export.py",
    ),
}


def module_files(name: str) -> list[Path]:
    """Files of one module family, the original module first."""
    return [COMP / file for file in FAMILIES[name]]


def module_source(name: str) -> str:
    """Concatenated source of one module family."""
    return "\n".join(path.read_text(encoding="utf-8") for path in module_files(name))


def class_body(name: str, class_name: str) -> list[ast.stmt]:
    """Body of a class in a module family, followed by the bodies of its mixin bases."""
    classes = {
        node.name: node
        for node in ast.parse(module_source(name)).body
        if isinstance(node, ast.ClassDef)
    }
    body: list[ast.stmt] = []
    pending = [class_name]
    while pending:
        node = classes[pending.pop(0)]
        body.extend(node.body)
        pending.extend(base.id for base in node.bases if isinstance(base, ast.Name) and base.id in classes)
    return body
