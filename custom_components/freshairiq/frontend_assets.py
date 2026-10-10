"""Pre-compressed dashboard files (0.26.4.8).

Home Assistant serves FreshAirIQ's dashboard files through aiohttp's
``FileResponse``. When a ``<file>.br`` or ``<file>.gz`` sibling exists and the
browser accepts that encoding, aiohttp sends the compressed sibling instead
(``Content-Encoding`` set, content type taken from the original file). Without
siblings every phone downloaded the full card (about 400 kB) uncompressed.

``ensure_precompressed`` writes those siblings once per file version:

* a sibling is rewritten only when the SHA-256 of its source changed
  (recorded in ``.precompressed.json``);
* a sibling that could not be refreshed is deleted, so an outdated compressed
  file can never be served for a newer source;
* siblings without a source are removed;
* any file-system error (read-only installation, full disk) is reported and
  never raised – the uncompressed files keep working.

Pure logic apart from file I/O: no Home Assistant imports.
"""
from __future__ import annotations

from collections.abc import Callable
import gzip
import hashlib
import json
import os
from pathlib import Path
from typing import Any

SOURCE_SUFFIXES = (".js",)
MANIFEST_NAME = ".precompressed.json"
ENCODINGS = (".gz", ".br")


def _gzip(data: bytes) -> bytes:
    # mtime=0: identical input gives byte-identical output (reproducible).
    return gzip.compress(data, compresslevel=9, mtime=0)


def _read_manifest(path: Path) -> dict[str, str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(k): str(v) for k, v in value.items()} if isinstance(value, dict) else {}


def _write_atomic(target: Path, data: bytes) -> None:
    tmp = target.with_name(target.name + ".tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()


def _remove(path: Path, result: dict[str, Any]) -> None:
    try:
        if path.exists():
            path.unlink()
            result["removed"].append(path.name)
    except OSError as err:
        result["errors"].append(f"{path.name}: {err}")


def ensure_precompressed(directory: Path, brotli_compress: Callable[[bytes], bytes] | None = None) -> dict[str, Any]:
    """Create or refresh ``.gz`` (and ``.br`` when available) siblings."""
    result: dict[str, Any] = {"written": [], "kept": [], "removed": [], "errors": []}
    directory = Path(directory)
    manifest_path = directory / MANIFEST_NAME
    manifest = _read_manifest(manifest_path)
    compressors: dict[str, Callable[[bytes], bytes]] = {".gz": _gzip}
    if brotli_compress is not None:
        compressors[".br"] = brotli_compress
    try:
        sources = sorted(p for p in directory.iterdir() if p.is_file() and p.suffix in SOURCE_SUFFIXES)
    except OSError as err:
        result["errors"].append(f"{directory.name}: {err}")
        return result
    new_manifest: dict[str, str] = {}
    for source in sources:
        try:
            data = source.read_bytes()
        except OSError as err:
            result["errors"].append(f"{source.name}: {err}")
            for suffix in ENCODINGS:
                _remove(source.with_name(source.name + suffix), result)
            continue
        digest = hashlib.sha256(data).hexdigest()
        for suffix in ENCODINGS:
            target = source.with_name(source.name + suffix)
            compress = compressors.get(suffix)
            if compress is None:
                # No compressor for this encoding: keep a sibling only if it still matches.
                if manifest.get(target.name) == digest and target.is_file():
                    new_manifest[target.name] = digest
                    result["kept"].append(target.name)
                else:
                    _remove(target, result)
                continue
            if manifest.get(target.name) == digest and target.is_file():
                new_manifest[target.name] = digest
                result["kept"].append(target.name)
                continue
            try:
                _write_atomic(target, compress(data))
            except Exception as err:  # noqa: BLE001 - never break HA setup over a cache file
                result["errors"].append(f"{target.name}: {err}")
                _remove(target, result)
                continue
            new_manifest[target.name] = digest
            result["written"].append(target.name)
    # Compressed files whose source no longer exists.
    known = {s.name for s in sources}
    for path in sorted(directory.iterdir()):
        for suffix in ENCODINGS:
            if path.name.endswith(suffix) and path.name[: -len(suffix)].endswith(SOURCE_SUFFIXES) and path.name[: -len(suffix)] not in known:
                _remove(path, result)
    if new_manifest != manifest:
        try:
            _write_atomic(manifest_path, json.dumps(new_manifest, indent=1, sort_keys=True).encode("utf-8"))
        except OSError as err:
            result["errors"].append(f"{MANIFEST_NAME}: {err}")
    return result
