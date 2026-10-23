"""Analysis export and upload chunking of the diagnostics transport."""
from __future__ import annotations

import hashlib
from typing import Any, Mapping

from .diagnostic_transport import (
    CURSOR_SCHEMA_VERSION,
    UPLOAD_SCHEMA_VERSION,
    _DROP_KEYS,
    _canonical_json_bytes,
    _chunk_payload_size,
    _collect_room_keys,
    _record_transport_id,
    _redact_text,
    _safe_client_context,
    _timestamp_at_or_after,
    _version_literal_path,
    normalise_resident_names,
    room_token,
)


_CANONICAL_FLOORS = {"basement", "ground_floor", "upper_floor", "attic", "other", "custom"}


def _extend_room_label_map(value: Any, room_map: dict[str, str]) -> None:
    """Map room labels found beside a room key to the same stable pseudonym."""
    if isinstance(value, Mapping):
        raw_key = value.get("room_key") if isinstance(value.get("room_key"), str) else value.get("key")
        raw_name = value.get("room_name") if isinstance(value.get("room_name"), str) else value.get("name")
        if isinstance(raw_key, str) and raw_key in room_map and isinstance(raw_name, str) and raw_name:
            room_map[raw_name] = room_map[raw_key]
        for child in value.values():
            _extend_room_label_map(child, room_map)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _extend_room_label_map(child, room_map)


def _extend_private_label_map(
    value: Any, replacements: dict[str, str], installation_id: str
) -> None:
    """Collect private labels that can reappear inside diagnostic free text."""
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            if key_text in {"adult_resident_names", "child_resident_names"}:
                for name in normalise_resident_names(child):
                    replacements[name] = "<redacted_resident>"
            elif key_text == "levels" and isinstance(child, list):
                for level in child:
                    if isinstance(level, str) and level and level not in _CANONICAL_FLOORS:
                        token = hashlib.sha256(f"{installation_id}|level|{level}".encode("utf-8")).hexdigest()[:10]
                        replacements[level] = f"level-{token}"
            elif key_text in {"floor", "level", "floor_name", "level_name"} and isinstance(child, str):
                if child and child not in _CANONICAL_FLOORS:
                    token = hashlib.sha256(f"{installation_id}|level|{child}".encode("utf-8")).hexdigest()[:10]
                    replacements[child] = f"level-{token}"
            _extend_private_label_map(child, replacements, installation_id)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _extend_private_label_map(child, replacements, installation_id)


def _sanitize_analysis_tree(
    value: Any, room_map: Mapping[str, str], path: tuple[str, ...] = ()
) -> Any:
    """Sanitise an analysis tree while retaining non-identifying technical detail.

    This differs from the legacy minimiser: numeric model settings and diagnostic
    evidence are retained because the Hub needs analysis-equivalent information.
    Direct identifiers, raw room labels, entity IDs and custom floor labels are
    still removed locally before any network transfer.
    """
    if isinstance(value, Mapping):
        clean: dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            if key_text in _DROP_KEYS:
                continue
            safe_key = room_map.get(key_text, key_text)
            if key_text in {"floor", "level", "floor_name", "level_name"} and isinstance(child, str):
                child = child if child in _CANONICAL_FLOORS else "custom"
            clean[safe_key] = _sanitize_analysis_tree(child, room_map, path + (key_text,))
        return clean
    if isinstance(value, list):
        return [_sanitize_analysis_tree(item, room_map, path) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_analysis_tree(item, room_map, path) for item in value]
    if isinstance(value, str):
        return _redact_text(value, room_map, preserve_ipv4_shaped_version=_version_literal_path(path))
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _redact_text(str(value), room_map, preserve_ipv4_shaped_version=_version_literal_path(path))


def select_records_after_cursor(
    records: list[dict[str, Any]], cursor: Mapping[str, Any] | None
) -> list[dict[str, Any]]:
    """Return only records not known to be acknowledged by the Hub.

    Exact cursor matches are lossless. If the local 30-day retention window has
    already pruned the acknowledged record, timestamp fallback may resend the
    boundary timestamp; per-record IDs let the Hub deduplicate that safely.
    """
    if not isinstance(cursor, Mapping) or not cursor.get("record_id"):
        return list(records)
    cursor_id = str(cursor.get("record_id"))
    cursor_timestamp = cursor.get("timestamp")
    for index, record in enumerate(records):
        if _record_transport_id(record) == cursor_id and record.get("timestamp") == cursor_timestamp:
            return list(records[index + 1 :])
    return [
        record for record in records
        if _timestamp_at_or_after(record.get("timestamp"), cursor_timestamp)
    ]


def build_analysis_export(
    exported: Mapping[str, Any], *, include_client_context: bool = False
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Create a locally anonymised, analysis-equivalent export.

    The manual Home Assistant export is not modified. This function creates a
    separate transport representation from it, retaining the full technical
    dossier and all retained records while removing direct identifiers.
    """
    exported = exported if isinstance(exported, Mapping) else {}
    field = exported.get("field_test") if isinstance(exported.get("field_test"), Mapping) else {}
    installation_id = str(field.get("anonymous_installation_id") or "")
    if not installation_id:
        raise ValueError("diagnostics export has no anonymous installation id")

    records = exported.get("records") if isinstance(exported.get("records"), list) else []
    room_keys = _collect_room_keys(exported)
    room_map = {key: room_token(key, installation_id) for key in room_keys}
    _extend_room_label_map(exported, room_map)
    _extend_private_label_map(exported, room_map, installation_id)

    # The sanitiser is functional: it builds new dict/list containers and never
    # mutates the diagnostics export. Avoiding a redundant deepcopy here cuts
    # both CPU time and peak memory for large 30-day field-test exports.
    sanitized_records = [
        _sanitize_analysis_tree(record, room_map)
        for record in records
        if isinstance(record, Mapping)
    ]
    metadata_source = {key: value for key, value in exported.items() if key != "records"}
    metadata = _sanitize_analysis_tree(metadata_source, room_map)
    metadata["anonymous_installation_id"] = installation_id
    metadata["privacy"] = (
        "FreshAirIQ Hub transport is locally redacted before upload; direct identifiers, "
        "raw room labels, entity IDs, network identifiers and exact device models are removed."
    )
    metadata["transport"] = {
        "upload_schema_version": UPLOAD_SCHEMA_VERSION,
        "cursor_schema_version": CURSOR_SCHEMA_VERSION,
        "analysis_equivalent": True,
        "full_retained_history": True,
        "incremental_after_first_ack": True,
    }
    metadata["transport_privacy"] = {
        "local_redaction_before_upload": True,
        "room_labels_removed": True,
        "room_keys_pseudonymised": True,
        "entity_ids_redacted": True,
        "resident_names_removed": True,
        "notification_targets_removed": True,
        "network_identifiers_removed": True,
        "exact_device_models_removed": True,
        "client_context_included": bool(include_client_context),
    }
    if include_client_context:
        metadata["client_context"] = _sanitize_analysis_tree(_safe_client_context(field), room_map)
    return metadata, sanitized_records


def _build_chunk_document(
    *,
    metadata: Mapping[str, Any],
    installation_id: str,
    batch_id: str,
    records: list[dict[str, Any]],
    record_ids: list[str],
    cursor_before: Mapping[str, Any] | None,
    chunk_index: int,
    chunk_count: int,
    initial_snapshot: bool,
) -> dict[str, Any]:
    cursor_after = (
        {
            "schema_version": CURSOR_SCHEMA_VERSION,
            "timestamp": records[-1].get("timestamp"),
            "record_id": record_ids[-1],
        }
        if records and record_ids
        else (dict(cursor_before) if isinstance(cursor_before, Mapping) else None)
    )
    document: dict[str, Any] = {
        "upload_schema_version": UPLOAD_SCHEMA_VERSION,
        "diagnostics_schema_version": metadata.get("schema_version"),
        "freshairiq_version": metadata.get("freshairiq_version"),
        "anonymous_installation_id": installation_id,
        "batch_id": batch_id,
        "chunk_index": chunk_index,
        "chunk_count": chunk_count,
        "initial_snapshot": bool(initial_snapshot),
        "incremental": not bool(initial_snapshot),
        "cursor_before": dict(cursor_before) if isinstance(cursor_before, Mapping) else None,
        "cursor_after": cursor_after,
        "record_ids": list(record_ids),
        "records": list(records),
        "metadata": dict(metadata),
    }
    digest_basis = dict(document)
    canonical = _canonical_json_bytes(digest_basis)
    document["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    document["chunk_id"] = "chunk-" + hashlib.sha256(
        _canonical_json_bytes({
            "batch_id": batch_id,
            "chunk_index": chunk_index,
            "record_ids": record_ids,
            "content_sha256": document["content_sha256"],
        })
    ).hexdigest()[:24]
    return document


def build_upload_chunks(
    exported: Mapping[str, Any],
    *,
    include_client_context: bool = False,
    after_cursor: Mapping[str, Any] | None = None,
    max_chunk_bytes: int = 2 * 1024 * 1024,
) -> list[dict[str, Any]]:
    """Build deterministic, resumable chunks without discarding retained history.

    The first successful transfer contains every record present in the normal
    30-day diagnostics export. Subsequent transfers select only records after
    the last acknowledged cursor. Each record also receives a stable content ID
    so the Hub can deduplicate a boundary resend after uncertain network errors.
    """
    try:
        byte_limit = int(max_chunk_bytes)
    except (TypeError, ValueError, OverflowError):
        byte_limit = 2 * 1024 * 1024
    if byte_limit < 4096:
        raise ValueError("diagnostics chunk limit is too small")

    metadata, all_records = build_analysis_export(
        exported, include_client_context=include_client_context
    )
    installation_id = str(metadata.get("anonymous_installation_id") or "")
    selected = select_records_after_cursor(all_records, after_cursor)
    selected_ids = [_record_transport_id(record) for record in selected]
    initial_snapshot = not (isinstance(after_cursor, Mapping) and after_cursor.get("record_id"))
    batch_basis = {
        "installation_id": installation_id,
        "upload_schema_version": UPLOAD_SCHEMA_VERSION,
        "generated_at": metadata.get("exported_at"),
        "cursor_before": dict(after_cursor) if isinstance(after_cursor, Mapping) else None,
        "record_ids": selected_ids,
    }
    batch_id = "batch-" + hashlib.sha256(_canonical_json_bytes(batch_basis)).hexdigest()[:24]

    # Partition in linear time. v0.25.0.24 rebuilt and canonicalised the whole
    # growing candidate chunk once per record, which made a large 30-day export
    # effectively quadratic. Here the fixed metadata cost is measured once and
    # each already-sanitised record contributes only its own canonical byte
    # weight. Final chunks are still measured exactly before they can leave HA.
    empty_probe = _build_chunk_document(
        metadata=metadata,
        installation_id=installation_id,
        batch_id=batch_id,
        records=[],
        record_ids=[],
        cursor_before=after_cursor,
        chunk_index=0,
        chunk_count=1,
        initial_snapshot=initial_snapshot,
    )
    empty_size = _chunk_payload_size(empty_probe)
    if empty_size > byte_limit:
        raise ValueError("diagnostics metadata exceeds chunk upload limit")

    if not selected:
        return [empty_probe]

    # Keep generous headroom for cursor changes, counters and hashes. The final
    # exact-size guard below remains authoritative, so estimation can never
    # allow an oversized payload to be uploaded.
    partition_limit = max(empty_size + 1, byte_limit - 4 * 1024)
    groups: list[tuple[list[dict[str, Any]], list[str]]] = []
    current_records: list[dict[str, Any]] = []
    current_ids: list[str] = []
    current_size = empty_size
    for record, record_id in zip(selected, selected_ids):
        record_weight = len(_canonical_json_bytes(record)) + len(_canonical_json_bytes(record_id)) + 2
        if current_records and current_size + record_weight > partition_limit:
            groups.append((current_records, current_ids))
            current_records = []
            current_ids = []
            current_size = empty_size
        current_records.append(record)
        current_ids.append(record_id)
        current_size += record_weight
    if current_records:
        groups.append((current_records, current_ids))

    chunks: list[dict[str, Any]] = []
    cursor_before_chunk = dict(after_cursor) if isinstance(after_cursor, Mapping) else None
    total = len(groups)
    for index, (group_records, group_ids) in enumerate(groups):
        chunk = _build_chunk_document(
            metadata=metadata,
            installation_id=installation_id,
            batch_id=batch_id,
            records=group_records,
            record_ids=group_ids,
            cursor_before=cursor_before_chunk,
            chunk_index=index,
            chunk_count=total,
            initial_snapshot=initial_snapshot,
        )
        if _chunk_payload_size(chunk) > byte_limit:
            raise ValueError("one diagnostics record exceeds chunk upload limit")
        chunks.append(chunk)
        cursor_before_chunk = chunk.get("cursor_after")
    return chunks
