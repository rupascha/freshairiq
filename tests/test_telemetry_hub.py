"""Diagnostics Hub transport helpers (telemetry_hub): safe base URL and chunk encoding."""
from __future__ import annotations

import gzip
import json

from custom_components.freshairiq.telemetry_hub import _encode_chunk_for_upload, _normalise_hub_base


def test_hub_base_accepts_https_and_private_http_only():
    assert _normalise_hub_base("") == ""
    assert _normalise_hub_base(None) == ""
    assert _normalise_hub_base("http://[broken") == ""
    assert _normalise_hub_base("ftp://hub.example") == ""
    assert _normalise_hub_base("https://user:secret@hub.example") == ""
    assert _normalise_hub_base("https://:443") == ""
    assert _normalise_hub_base("http://hub.example") == ""
    assert _normalise_hub_base("http://8.8.8.8") == ""
    assert _normalise_hub_base("http://localhost:8000/") == "http://localhost:8000"
    assert _normalise_hub_base("http://192.168.1.5:8080/v1/diagnostics/chunks/") == "http://192.168.1.5:8080"
    assert _normalise_hub_base(" https://hub.example/base/v1/enroll ") == "https://hub.example/base"
    assert _normalise_hub_base("https://hub.example/base/v1/diagnostics?x=1") == "https://hub.example/base"
    assert _normalise_hub_base("https://hub.example/other/") == "https://hub.example/other"


def test_chunk_encoding_is_compact_gzip_json():
    chunk = {"records": [{"room": "Bad", "rh": 61.5}], "schema": 2}
    encoded = _encode_chunk_for_upload(chunk)
    assert json.loads(gzip.decompress(encoded)) == chunk
    assert b" " not in gzip.decompress(encoded)
