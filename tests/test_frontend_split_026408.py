"""0.26.4.8: smaller dashboard download – English texts on demand, compressed copies."""
from __future__ import annotations

import gzip
import json
from pathlib import Path

from custom_components.freshairiq import frontend_assets
from custom_components.freshairiq.frontend_assets import MANIFEST_NAME, ensure_precompressed

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "custom_components/freshairiq/frontend"
CARD = (FRONTEND / "freshairiq-card.js").read_text(encoding="utf-8")
ENGLISH = (FRONTEND / "freshairiq-card-i18n-en.js").read_text(encoding="utf-8")
INIT = (ROOT / "custom_components/freshairiq/__init__.py").read_text(encoding="utf-8")


# --- English tables as their own module ---------------------------------------------------
def test_english_tables_moved_out_of_the_card():
    assert "const FAIQ_NATIVE_EN = [" not in CARD and "const FAIQ_UI_EN = [" not in CARD
    assert ENGLISH.count("const FAIQ_NATIVE_EN = [") == 1 and "export const FAIQ_EN_RULES =" in ENGLISH
    assert len(CARD.encode("utf-8")) < 430_000  # 0.26.4.7: 553 kB
    assert len(ENGLISH.encode("utf-8")) > 150_000


def test_card_loads_english_on_demand_and_waits_only_for_the_first_paint():
    assert 'const FAIQ_EN_MODULE = "freshairiq-card-i18n-en.js";' in CARD
    assert "import(url).then(mod => {" in CARD
    assert "new URL(`./${FAIQ_EN_MODULE}?v=${FAIQ_VERSION}`, import.meta.url).href" in CARD
    assert "if (faiqLikelyEnglish()) faiqLoadEnglish().catch(() => {});" in CARD
    assert "for (const [de, en] of (FAIQ_EN_RULES || []))" in CARD
    render = CARD[CARD.index("    _render() {"):CARD.index("    _handleRenderFailure(")]
    assert 'if (FAIQ_NUMBER_LOCALE === "en" && !faiqEnglishReady() && !this._englishFailed) {' in render
    assert "if (!this._hasRendered) return;" in render and "this._hasRendered = true;" in render
    # 0.26.4.8 review: bounded first-paint wait, retry backoff, re-render when the texts arrive
    assert "faiqWaitForEnglish()" in render and "const FAIQ_EN_FIRST_PAINT_WAIT_MS = 2500;" in CARD
    assert "Date.now() - faiqEnglishFailedAt < FAIQ_EN_RETRY_MS" in CARD
    assert "window.addEventListener(FAIQ_EN_READY_EVENT, this._onEnglishReady)" in CARD
    assert "faiqLoadEnglish().then(() => faiqLocalizeTree(this.shadowRoot))" in CARD  # editor


def test_every_frontend_file_carries_the_release_version():
    version = json.loads((ROOT / "custom_components/freshairiq/manifest.json").read_text(encoding="utf-8"))["version"]
    assert f'const FAIQ_VERSION = "{version}";' in CARD
    # the English module is fetched with ?v=<card version>; it has no version of its own to drift


# --- compressed copies --------------------------------------------------------------------
def test_gzip_and_brotli_siblings_are_written_once_per_version(tmp_path):
    (tmp_path / "a.js").write_text("console.log('a');" * 200, encoding="utf-8")
    (tmp_path / "b.js").write_text("export const b = 1;", encoding="utf-8")
    (tmp_path / "icon.png").write_bytes(b"\x89PNG")
    fake_br = lambda data: b"BR" + data[:10]  # noqa: E731
    first = ensure_precompressed(tmp_path, fake_br)
    assert sorted(first["written"]) == ["a.js.br", "a.js.gz", "b.js.br", "b.js.gz"] and not first["errors"]
    assert gzip.decompress((tmp_path / "a.js.gz").read_bytes()) == (tmp_path / "a.js").read_bytes()
    assert not (tmp_path / "icon.png.gz").exists()
    manifest = json.loads((tmp_path / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert set(manifest) == {"a.js.gz", "a.js.br", "b.js.gz", "b.js.br"}
    again = ensure_precompressed(tmp_path, fake_br)
    assert again["written"] == [] and len(again["kept"]) == 4
    # deterministic gzip output
    before = (tmp_path / "a.js.gz").read_bytes()
    (tmp_path / MANIFEST_NAME).unlink()
    ensure_precompressed(tmp_path, fake_br)
    assert (tmp_path / "a.js.gz").read_bytes() == before


def test_an_update_never_leaves_an_outdated_compressed_copy(tmp_path):
    src = tmp_path / "card.js"
    src.write_text("old", encoding="utf-8")
    ensure_precompressed(tmp_path, lambda d: b"br-" + d)
    src.write_text("new version", encoding="utf-8")
    # brotli no longer available: the old .br must go, .gz is refreshed
    result = ensure_precompressed(tmp_path, None)
    assert "card.js.br" in result["removed"] and not (tmp_path / "card.js.br").exists()
    assert gzip.decompress((tmp_path / "card.js.gz").read_bytes()) == b"new version"
    # unchanged source + brotli missing: a matching .br would be kept
    ensure_precompressed(tmp_path, lambda d: b"br-" + d)
    kept = ensure_precompressed(tmp_path, None)
    assert "card.js.br" in kept["kept"]
    # failing compressor: stale sibling removed, error reported, nothing raised
    src.write_text("newest", encoding="utf-8")

    def broken(_data):
        raise RuntimeError("no brotli today")

    failed = ensure_precompressed(tmp_path, broken)
    assert any("no brotli today" in e for e in failed["errors"])
    assert not (tmp_path / "card.js.br").exists() and gzip.decompress((tmp_path / "card.js.gz").read_bytes()) == b"newest"
    assert not list(tmp_path.glob("*.tmp"))


def test_orphans_unreadable_sources_and_read_only_folders(tmp_path, monkeypatch):
    (tmp_path / "gone.js.gz").write_bytes(b"x")
    (tmp_path / "gone.js.br").write_bytes(b"x")
    (tmp_path / "keep.txt.gz").write_bytes(b"x")  # not a dashboard source: untouched
    (tmp_path / MANIFEST_NAME).write_text("[1, 2]", encoding="utf-8")  # unexpected content
    result = ensure_precompressed(tmp_path)
    assert sorted(result["removed"]) == ["gone.js.br", "gone.js.gz"] and (tmp_path / "keep.txt.gz").exists()
    (tmp_path / MANIFEST_NAME).write_text("not json", encoding="utf-8")
    assert ensure_precompressed(tmp_path)["errors"] == []
    # missing folder
    assert ensure_precompressed(tmp_path / "missing")["errors"]
    # unreadable source: its siblings are removed
    src = tmp_path / "x.js"
    src.write_text("x", encoding="utf-8")
    ensure_precompressed(tmp_path)
    original = Path.read_bytes

    def deny(self):
        if self.name == "x.js":
            raise PermissionError("denied")
        return original(self)

    monkeypatch.setattr(Path, "read_bytes", deny)
    unreadable = ensure_precompressed(tmp_path)
    assert any("x.js: denied" in e for e in unreadable["errors"]) and not (tmp_path / "x.js.gz").exists()
    monkeypatch.undo()
    # read-only: writing the manifest and removing files fail -> reported, not raised
    src.write_text("changed", encoding="utf-8")
    real_replace = frontend_assets.os.replace

    def fail_manifest(a, b):
        if Path(b).name == MANIFEST_NAME:
            raise OSError("read-only")
        return real_replace(a, b)

    monkeypatch.setattr(frontend_assets.os, "replace", fail_manifest)
    assert any("read-only" in e for e in ensure_precompressed(tmp_path)["errors"])
    monkeypatch.undo()

    def no_unlink(self, missing_ok=False):
        raise OSError("busy")

    (tmp_path / "orphan.js.gz").write_bytes(b"x")
    monkeypatch.setattr(Path, "unlink", no_unlink)
    assert any("orphan.js.gz: busy" in e for e in ensure_precompressed(tmp_path)["errors"])


def test_setup_compresses_before_the_files_are_served():
    setup = INIT[INIT.index("async def async_setup("):]
    assert setup.index("hass.async_add_executor_job(_precompress_frontend)") < setup.index("async_register_static_paths")
    helper = INIT[INIT.index("def _precompress_frontend()"):INIT.index("async def async_setup(")]
    assert "import brotli" in helper and "return ensure_precompressed(_FRONTEND_DIR, brotli_compress)" in helper
    policy = json.loads((ROOT / "quality/quality_policy.json").read_text(encoding="utf-8"))["release"]
    assert {".gz", ".br"} <= set(policy["forbidden_suffixes"]) and ".precompressed.json" in policy["forbidden_file_names"]
