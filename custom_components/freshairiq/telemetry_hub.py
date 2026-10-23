"""Diagnostics Hub transport helpers: safe Hub base URL and chunk encoding."""
from __future__ import annotations

import gzip
import ipaddress
import json
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit


_GZIP_COMPRESSLEVEL = 4


def _normalise_hub_base(endpoint: str) -> str:
    """Return a safe Hub base URL or an empty string.

    HTTPS is accepted for normal deployments. Plain HTTP is accepted only for
    loopback/private IP addresses so this local staging release cannot silently
    turn into an Internet-facing clear-text diagnostics transport.
    """
    value = str(endpoint or "").strip()
    if not value:
        return ""
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        return ""
    host = parsed.hostname
    if not host:
        return ""
    if parsed.scheme == "http":
        if host.lower() != "localhost":
            try:
                address = ipaddress.ip_address(host)
            except ValueError:
                return ""
            if not (address.is_private or address.is_loopback):
                return ""

    path = parsed.path.rstrip("/")
    for suffix in ("/v1/diagnostics/chunks", "/v1/diagnostics", "/v1/enroll"):
        if path.endswith(suffix):
            path = path[: -len(suffix)].rstrip("/")
            break
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", "")).rstrip("/")


def _encode_chunk_for_upload(chunk: Mapping[str, Any]) -> bytes:
    """Encode and compress one chunk outside the Home Assistant event loop."""
    raw = json.dumps(chunk, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return gzip.compress(raw, compresslevel=_GZIP_COMPRESSLEVEL)
