"""Hotfix 0.26.5.5 (31.10.): formula-test section missing in the iOS detail view.

Cause shown in the real loading path: every 0.26.5.5 build used the resource URL ``?v=0.26.5.5`` and
every module imported its parts with the same fixed ``?v=`` – an older cached
``freshairiq-card-data.js`` (from before the section existed) kept running under the unchanged URL.
Fix: the resource URL carries the content revision of all dashboard modules (``&b=``) and every module
passes its own query on to the modules it imports. A failed download of the section shows a message.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from custom_components.freshairiq.frontend_assets import ensure_precompressed

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "custom_components" / "freshairiq" / "frontend"
INIT = (ROOT / "custom_components" / "freshairiq" / "__init__.py").read_text(encoding="utf-8")
# Legacy first-stage files Home Assistant no longer registers (kept for old YAML set-ups).
LEGACY = {"freshairiq-loader.js", "freshairiq-panel.js"}


def _copy(tmp_path: Path) -> Path:
    target = tmp_path / "frontend"
    target.mkdir()
    for source in FRONTEND.glob("*.js"):
        (target / source.name).write_bytes(source.read_bytes())
    return target


def test_the_revision_follows_the_content_of_every_module(tmp_path) -> None:
    directory = _copy(tmp_path)
    first = ensure_precompressed(directory)["revision"]
    assert re.fullmatch(r"[0-9a-f]{12}", first)
    assert ensure_precompressed(directory)["revision"] == first  # unchanged files, same revision
    shadow = directory / "freshairiq-card-shadow.js"
    shadow.write_text(shadow.read_text(encoding="utf-8") + "\n// new build\n", encoding="utf-8")
    second = ensure_precompressed(directory)["revision"]
    assert second != first  # a changed sub-module alone gives a new revision
    (directory / "freshairiq-card-new.js").write_text("export const x = 1;\n", encoding="utf-8")
    assert ensure_precompressed(directory)["revision"] not in {first, second}


def test_the_resource_url_carries_version_and_revision() -> None:
    assert "def _frontend_module_url(revision: object) -> str:" in INIT
    assert 'f"{_FRONTEND_MODULE_BASE}?v={VERSION}&b={revision}"' in INIT
    assert '_FRONTEND_MODULE = _frontend_module_url(precompressed.get("revision"))' in INIT
    setup = INIT[INIT.index("async def async_setup("):]
    assert setup.index("_FRONTEND_MODULE = _frontend_module_url(") < setup.index("await _async_register_lovelace_resource(hass)")


def test_every_module_passes_its_own_query_on() -> None:
    for path in sorted(FRONTEND.glob("*.js")):
        if path.name in LEGACY:
            continue
        source = path.read_text(encoding="utf-8")
        assert "?v=${FAIQ_VERSION}`, import.meta.url" not in source, path.name
        for spec in re.findall(r"new URL\(`\./([^`]+)`, import\.meta\.url\)", source):
            assert "?v=" not in spec, (path.name, spec)
            assert spec.endswith(("${FAIQ_Q}", "${Q}", "${VERSION_QUERY}", "${new URL(import.meta.url).search}")), (path.name, spec)
    # the product version shown to the user stays the plain version
    card = (FRONTEND / "freshairiq-card.js").read_text(encoding="utf-8")
    # 0.26.6.0: compared with the manifest version instead of a fixed number (a version bump is no build suffix)
    version = json.loads((FRONTEND.parent / "manifest.json").read_text(encoding="utf-8"))["version"]
    assert f'const FAIQ_VERSION = "{version}";' in card and "freshairiq_frontend_version: FAIQ_VERSION" in card


def test_a_failed_section_download_is_visible() -> None:
    data = (FRONTEND / "freshairiq-card-data.js").read_text(encoding="utf-8")
    block = data[data.index("freshairiq-card-shadow.js"):]
    assert "shadowLoadFailed(customElements.get(\"freshairiq-card\"), error)" in block
    assert "FAIQ-UI-SHADOW-001" in block and 'role="alert"' in block
