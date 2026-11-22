"""Marketplace/HACS release contract (0.26.7.0, install asset from 0.26.7.2): installation ZIP, hacs.json, workflows, download statistics.

Every release carries ``freshairiq.zip``. From 0.26.7.2 on ``hacs.json`` sets ``zip_release``/``filename``:
HACS (``async_download_repository`` → ``async_get_hacs_json(ref=version_to_download())``) and the
Marketplace (``async_get_repository_manifest(params={"ref": version_to_install()})``, catalog path
``get_repository_manifest(version=...)``) read ``hacs.json`` at the tag they install and download the asset
only when that tag asks for it (A-243). Older tags have no ``zip_release`` and keep installing from their
source archive. The ZIP has the layout they extract with ``zipfile.ZipFile.extractall`` into
``custom_components/<domain>/``; these tests extract it that way and require the files of the integration
folder as released.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import shutil
import subprocess
import sys
import urllib.error
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_install_zip as biz  # noqa: E402
import release_downloads as rd  # noqa: E402

COMP = ROOT / "custom_components/freshairiq"
WORKFLOWS = ROOT / ".github/workflows"


POLICY = json.loads((ROOT / "quality/quality_policy.json").read_text(encoding="utf-8"))["release"]


def _released(rel: str) -> bool:
    """A file the CLEAN package (and so every install from the source archive) carries."""
    name = rel.rsplit("/", 1)[-1]
    return ("__pycache__" not in rel and name not in POLICY["forbidden_file_names"]
            and not any(name.endswith(s) for s in POLICY["forbidden_suffixes"]))


def _tracked() -> list[str]:
    """Files of the integration folder as released: Git's list in a checkout, else (unpacked CLEAN package) the files on disk.

    Changed expectation (review before publication): the dashboard's runtime-generated .gz siblings and
    .precompressed.json are tracked in this repository but excluded from the CLEAN package by the release
    policy; the installation ZIP follows the same policy, so it equals the previous install path exactly.
    """
    run = subprocess.run(["git", "ls-files", "--", "custom_components/freshairiq"], cwd=ROOT, text=True, capture_output=True, check=False)
    if run.returncode == 0 and (ROOT / ".git").exists():
        names = [line[len("custom_components/freshairiq/"):] for line in run.stdout.splitlines() if (ROOT / line).is_file()]
    else:
        names = [p.relative_to(COMP).as_posix() for p in COMP.rglob("*") if p.is_file()]
    return sorted(n for n in names if _released(n))


HACS_0267X = {"name": "FreshAirIQ", "render_readme": True, "homeassistant": "2026.8.0"}   # hacs.json of v0.26.7.1 and older


def _gate(tmp_path, hacs=None, release=None):
    src = tmp_path / "src"
    shutil.copytree(ROOT, src, ignore=shutil.ignore_patterns(".git", "node_modules", "__pycache__", "*.zip", "test-results"))
    if hacs is not None:
        (src / "hacs.json").write_text(json.dumps(hacs), encoding="utf-8")
    if release is not None:
        (src / ".github/workflows/release.yml").write_text(release, encoding="utf-8")
    result = subprocess.run([sys.executable, "tools/github_release_gate.py", "--source", "."], cwd=src, text=True, capture_output=True)
    return result.returncode, result.stdout + result.stderr


def _install(config: Path, hacs: dict, assets: dict[str, Path], source: Path) -> Path:
    """What HACS and the Marketplace write for one tag: the asset its hacs.json names, else the source archive's folder."""
    target = config / "custom_components" / "freshairiq"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    if rd.install_source(hacs) == "asset":
        if hacs["filename"] not in assets:
            raise FileNotFoundError(f"releases/download/<tag>/{hacs['filename']}")
        with zipfile.ZipFile(assets[hacs["filename"]]) as zf:
            zf.extractall(target)
    else:
        shutil.copytree(source / "custom_components/freshairiq", target, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.gz", "*.br", ".precompressed.json"))
    return target


def test_hacs_json_installs_the_counted_asset():
    """Changed expectation (A-243, 0.26.7.2): zip_release with the asset every release carries."""
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    assert hacs == {**HACS_0267X, "zip_release": True, "filename": "freshairiq.zip"}
    assert biz.ASSET_NAME == rd.INSTALL_ASSET == hacs["filename"]
    assert rd.install_source(hacs) == "asset"


def test_install_with_the_asset_gives_the_released_integration_folder(tmp_path):
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    asset = tmp_path / "release" / "freshairiq.zip"
    biz.build(ROOT, asset)
    version = json.loads((COMP / "manifest.json").read_text(encoding="utf-8"))["version"]
    assert biz.check(asset, version) == (version, [])
    target = _install(tmp_path / "config", hacs, {"freshairiq.zip": asset}, ROOT)
    got = sorted(p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file())
    assert got == _tracked()
    assert json.loads((target / "manifest.json").read_text(encoding="utf-8"))["version"] == version


def test_missing_or_wrongly_built_asset_never_reaches_a_public_release(tmp_path):
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    with pytest.raises(FileNotFoundError):
        _install(tmp_path / "config", hacs, {}, ROOT)
    s = rd.summarize([{"tag_name": "v0.26.7.2", "published_at": "2026-11-21T10:00:00Z", "assets": []}], {"v0.26.7.2": hacs})
    assert s["releases_with_missing_install_asset"] == ["v0.26.7.2"]
    assert "**Missing freshairiq.zip:** v0.26.7.2" in rd.markdown(s)
    wrong = tmp_path / "wrong.zip"
    with zipfile.ZipFile(wrong, "w") as zf:                                    # folder inside the ZIP: would nest on install
        for name in _tracked()[:20] + ["manifest.json"]:
            zf.writestr(f"freshairiq/{name}", (COMP / name).read_bytes())
    assert any("missing manifest.json" in e for e in biz.check(wrong)[1])
    publish = _wf("release.yml")
    publish = publish[publish.index("  publish:"):]
    assert publish.index("build_install_zip.py --check") < publish.index("--draft") < publish.index("grep -qx freshairiq.zip") < publish.index("--draft=false")
    unchecked = _wf("release.yml").replace("grep -qx freshairiq.zip draft-assets.txt\n", "")
    code, out = _gate(tmp_path / "a", release=unchecked)
    assert code != 0 and "on the draft before publishing" in out
    for bad in ({**hacs, "filename": "other.zip"}, {**hacs, "zip_release": False}, {k: v for k, v in hacs.items() if k != "filename"}, HACS_0267X):
        code, out = _gate(tmp_path / str(len(str(bad))), hacs=bad)
        assert code != 0 and "zip_release: true and filename: freshairiq.zip" in out


def test_older_version_without_asset_installs_from_its_source_archive(tmp_path):
    """Going back: the tag's own hacs.json has no zip_release, so the installers use its source archive."""
    assert rd.install_source(HACS_0267X) == "source archive"
    assert rd.install_source(None) == "unknown"
    old = tmp_path / "v0.26.6.0"
    (old / "custom_components/freshairiq").mkdir(parents=True)
    (old / "custom_components/freshairiq/manifest.json").write_text(json.dumps({"domain": "freshairiq", "version": "0.26.6.0"}))
    (old / "custom_components/freshairiq/__init__.py").write_text("")
    config = tmp_path / "config"
    asset = tmp_path / "freshairiq.zip"
    biz.build(ROOT, asset)
    _install(config, json.loads((ROOT / "hacs.json").read_text(encoding="utf-8")), {"freshairiq.zip": asset}, ROOT)
    target = _install(config, HACS_0267X, {}, old)                              # no asset in the old release
    assert sorted(p.name for p in target.iterdir()) == ["__init__.py", "manifest.json"]
    assert json.loads((target / "manifest.json").read_text())["version"] == "0.26.6.0"


def test_manifest_meets_hassfest_and_the_catalog():
    text = (COMP / "manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(text)
    keys = list(manifest)
    assert keys[:2] == ["domain", "name"] and keys[2:] == sorted(keys[2:])         # hassfest: domain, name, then alphabetical
    for key in ("domain", "name", "version", "documentation", "issue_tracker", "codeowners"):   # catalog check "Manifest"
        assert manifest[key]
    assert manifest["categories"] == ["climate.fans_ventilation", "sensors.air_quality"]    # known core categories, 1–3, unique
    assert manifest["documentation"].startswith("https://") and "home-assistant.io" not in manifest["documentation"]
    assert text.endswith("\n")


def test_installation_zip_is_reproducible_and_holds_exactly_the_integration_folder(tmp_path):
    first, second = tmp_path / "a" / "freshairiq.zip", tmp_path / "b" / "freshairiq.zip"
    assert biz.build(ROOT, first) == biz.build(ROOT, second) == hashlib.sha256(first.read_bytes()).hexdigest()
    with zipfile.ZipFile(first) as zf:
        names = zf.namelist()
        assert names == sorted(names) == _tracked()
        assert all(i.date_time == biz.FIXED_DATE for i in zf.infolist())
        assert "manifest.json" in names and not any(n.startswith("custom_components/") for n in names)
    version, errors = biz.check(first, json.loads((COMP / "manifest.json").read_text())["version"])
    assert errors == [] and version


def test_extracting_like_hacs_and_the_marketplace_gives_the_same_files_as_the_repository(tmp_path):
    archive = tmp_path / "freshairiq.zip"
    biz.build(ROOT, archive)
    target = tmp_path / "config" / "custom_components" / "freshairiq"
    target.mkdir(parents=True)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(target)
    got = sorted(p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file())
    assert got == _tracked()
    for rel in got:
        assert (target / rel).read_bytes() == (COMP / rel).read_bytes(), rel
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["domain"] == "freshairiq" and biz.VERSION_RE.fullmatch(manifest["version"])


def _zip(path: Path, files: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return path


def test_installation_zip_check_refuses_what_would_break_an_install(tmp_path):
    good = {"__init__.py": b"", "config_flow.py": b"", "brand/icon.png": b"x",
            "manifest.json": json.dumps({"domain": "freshairiq", "version": "1.2.3.4"}).encode()}
    assert biz.check(_zip(tmp_path / "ok.zip", good)) == ("1.2.3.4", [])
    nested = {f"custom_components/freshairiq/{k}": v for k, v in good.items()}
    assert any("at its root" in e for e in biz.check(_zip(tmp_path / "nested.zip", nested))[1])
    assert any("missing manifest.json" in e for e in biz.check(_zip(tmp_path / "nomanifest.zip", {k: v for k, v in good.items() if k != "manifest.json"}))[1])
    assert any("does not match" in e for e in biz.check(_zip(tmp_path / "v.zip", good), "9.9.9")[1])
    assert any("generated" in e for e in biz.check(_zip(tmp_path / "pyc.zip", {**good, "x.pyc": b""}))[1])
    assert any("unsafe" in e for e in biz.check(_zip(tmp_path / "unsafe.zip", {**good, "../evil.py": b""}))[1])
    other = {**good, "manifest.json": json.dumps({"domain": "other", "version": "x"}).encode()}
    errors = biz.check(_zip(tmp_path / "other.zip", other))[1]
    assert any("domain" in e for e in errors) and any("version" in e for e in errors)
    assert biz.check(tmp_path / "missing.zip")[1][0].startswith("cannot read")


def test_installation_zip_command_line(tmp_path, capsys):
    out = tmp_path / "freshairiq.zip"
    assert biz.main(["--output", str(out), "--version", json.loads((COMP / "manifest.json").read_text())["version"]]) == 0
    assert "PASS" in capsys.readouterr().out
    assert biz.main(["--check", str(out), "--version", "0.0.0"]) == 1
    with pytest.raises(SystemExit):
        biz.main([])


def test_source_gate_ties_hacs_json_to_the_release_workflow(tmp_path):
    gate = (ROOT / "tools/github_release_gate.py").read_text(encoding="utf-8")
    assert 'INSTALL_ASSET = "freshairiq.zip"' in gate and "release workflow must build and attach" in gate
    result = subprocess.run([sys.executable, "tools/github_release_gate.py", "--source", "."], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def _wf(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def test_release_workflow_publishes_only_after_the_checks_with_the_installation_zip():
    text = _wf("release.yml")
    assert "permissions:\n  contents: read" in text                         # read-only by default
    publish = text[text.index("  publish:"):]
    assert "needs: verify-release" in publish and "contents: write" in publish
    at = 0
    for step in ("build_install_zip.py --check", 'gh release create "$GITHUB_REF_NAME" "$RELEASE_ASSET" freshairiq.zip --draft',
                 "grep -qx freshairiq.zip", "--draft=false"):                 # draft with both assets → verified → published
        at = publish.index(step, at) + len(step)
    assert "cmp release-artifact/freshairiq.zip rebuilt/freshairiq.zip" in publish
    assert "build_install_zip.py --output release-artifact/freshairiq.zip" in _wf("quality.yml")


@pytest.mark.parametrize("name", ["hacs.yml", "hassfest.yml", "downloads.yml"])
def test_public_repository_workflows_are_least_privilege_and_skip_the_private_repository(name):
    text = _wf(name)
    assert "if: github.repository == 'rupascha/freshairiq'" in text
    assert text.count("contents: write") == 0
    assert "permissions: {}" in text or "permissions:\n  contents: read" in text


def test_hacs_and_hassfest_actions_run_without_ignored_checks():
    hacs = _wf("hacs.yml")
    assert "uses: hacs/action@main" in hacs and "category: integration" in hacs and "ignore:" not in hacs
    for event in ("push:", "pull_request:", "schedule:", "workflow_dispatch:"):
        assert event in hacs and event in _wf("hassfest.yml")
    assert "uses: home-assistant/actions/hassfest@master" in _wf("hassfest.yml")
    assert "ignore: brands" not in _wf("quality.yml")


def test_no_workflow_changes_an_existing_release():
    """Replaces the withdrawn backfill workflow (A-236): existing releases are never touched by automation."""
    assert not (WORKFLOWS / "release-assets.yml").exists()
    for wf in WORKFLOWS.glob("*.yml"):
        text = wf.read_text(encoding="utf-8")
        assert "gh release upload" not in text and "--clobber" not in text and "gh release delete" not in text, wf.name
    release = _wf("release.yml")
    assert "--verify-tag" in release and release.count("gh release create") == 1      # only the new tag's release


RELEASES = [
    {"tag_name": "v0.26.8.0", "published_at": "2026-12-01T10:00:00Z", "prerelease": True, "draft": False,
     "assets": [{"name": "freshairiq.zip", "download_count": 3}, {"name": "notes.txt", "download_count": 2}]},
    {"tag_name": "v0.26.7.0", "published_at": "2026-11-10T10:00:00Z", "prerelease": False, "draft": False,
     "assets": [{"name": "freshairiq.zip", "download_count": 120}, {"name": "FreshAirIQ-v0.26.7.0-CLEAN.zip", "download_count": 7}]},
    {"tag_name": "v0.26.6.0", "published_at": "2026-11-03T10:00:00Z", "prerelease": False, "draft": False, "assets": []},
    {"tag_name": "v9.9.9", "published_at": None, "prerelease": False, "draft": True, "assets": [{"name": "freshairiq.zip", "download_count": 99}]},
]


MANIFESTS = {"v0.26.8.0": {**HACS_0267X, "zip_release": True, "filename": "freshairiq.zip"}, "v0.26.7.0": HACS_0267X, "v0.26.6.0": HACS_0267X}


def test_download_summary_counts_only_what_github_counts():
    s = rd.summarize(RELEASES, MANIFESTS)
    assert [r["tag"] for r in s["releases"]] == ["v0.26.8.0", "v0.26.7.0", "v0.26.6.0"]       # drafts are not public
    assert [r["install_source"] for r in s["releases"]] == ["asset", "source archive", "source archive"]
    assert (s["total_install_downloads"], s["total_install_downloads_marketplace_releases"]) == (123, 3)
    assert (s["total_clean_downloads"], s["total_other_downloads"], s["total_asset_downloads"]) == (7, 2, 132)
    assert s["releases_installed_from_source_archive"] == ["v0.26.7.0", "v0.26.6.0"]
    assert s["releases_without_counted_downloads"] == ["v0.26.6.0"] and s["releases_with_missing_install_asset"] == []
    assert "not an installation" in s["note"] and "manual and repeated downloads" in s["note"] and "not zero" in s["note"]
    md = rd.markdown(s)
    assert "| v0.26.8.0 (pre-release) | 2026-12-01 | freshairiq.zip | 3 | – | 2 |" in md
    assert "| v0.26.7.0 | 2026-11-10 | source archive (not counted) | 120 | 7 | 0 |" in md
    assert "| v0.26.6.0 | 2026-11-03 | source archive (not counted) | – | – | – (no assets: not counted by GitHub) |" in md
    assert ("**Total:** 123 × freshairiq.zip (installation asset downloads, 3 of them in releases the Marketplace/HACS install from), "
            "7 × CLEAN package, 2 × other assets (132 asset downloads).") in md
    assert "| 0 |" not in md.split("v0.26.6.0", 1)[1].splitlines()[0]          # source archive installs never read as 0
    assert rd.summarize(RELEASES)["releases"][0]["install_source"] == "unknown"


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_download_fetch_reads_every_page_and_the_command_line(capsys, monkeypatch):
    seen = []
    pages = {1: [RELEASES[1]] * 100, 2: [RELEASES[2]]}

    def opener(request):
        seen.append((request.full_url, request.get_header("Authorization")))
        page = int(request.full_url.rsplit("page=", 1)[1])
        return _Response(json.dumps(pages[page]).encode())

    assert len(rd.fetch_releases("o/r", "tok", opener)) == 101
    assert seen[0] == ("https://api.github.com/repos/o/r/releases?per_page=100&page=1", "Bearer tok") and len(seen) == 2
    with pytest.raises(ValueError):
        rd.fetch_releases("o/r", None, lambda request: _Response(b'{"message": "Not Found"}'))

    asked = []

    def raw(request):
        asked.append((request.full_url, request.get_header("Authorization")))
        if "/v0.26.6.0/" in request.full_url or "ref=v0.26.6.0" in request.full_url:
            raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)
        if "/contents/hacs.json?ref=" in request.full_url:                    # the API: base64 content
            tag = request.full_url.rsplit("ref=", 1)[1]
            return _Response(json.dumps({"content": base64.b64encode(json.dumps(MANIFESTS[tag]).encode()).decode()} if tag in MANIFESTS else {}).encode())
        if "/v0.26.7.0/" in request.full_url:                                  # raw host not reachable: the API answers
            raise urllib.error.URLError("tunnel refused")
        tag = request.full_url.split("/")[-2]
        return _Response(json.dumps(MANIFESTS.get(tag, [])).encode())

    got = rd.fetch_hacs_manifests("o/r", ["v0.26.8.0", "v0.26.7.0", "v0.26.6.0", "v1"], raw, "tok")
    assert got == {"v0.26.8.0": MANIFESTS["v0.26.8.0"], "v0.26.7.0": HACS_0267X, "v0.26.6.0": None, "v1": None}
    assert asked[0] == ("https://raw.githubusercontent.com/o/r/v0.26.8.0/hacs.json", None)               # no token to the raw host
    assert ("https://api.github.com/repos/o/r/contents/hacs.json?ref=v0.26.7.0", "Bearer tok") in asked
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    urls = []

    def one(request):
        urls.append(request.full_url)
        if request.full_url.startswith("https://raw.githubusercontent.com/"):
            return raw(request)
        return _Response(json.dumps(RELEASES).encode())

    assert rd.main(["--json"], opener=one) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["total_install_downloads"] == 123 and out["total_install_downloads_marketplace_releases"] == 3
    assert "https://raw.githubusercontent.com/rupascha/freshairiq/v0.26.8.0/hacs.json" in urls
    assert not any("v9.9.9" in u for u in urls)                                 # drafts: no lookup
    assert rd.main([], opener=one) == 0
    md = capsys.readouterr().out
    assert "## FreshAirIQ release downloads" in md and "| v0.26.6.0 | 2026-11-03 | unknown (hacs.json not readable) |" in md
    summary = json.loads(json.dumps(rd.summarize(RELEASES, MANIFESTS)))           # the workflow renders the JSON artefact
    assert rd.markdown(summary) == rd.markdown(rd.summarize(RELEASES, MANIFESTS))
    downloads = _wf("downloads.yml")
    assert "--json > release-downloads.json" in downloads and "rd.markdown(json.load(open('release-downloads.json')))" in downloads


def test_installation_zip_follows_the_clean_policy_and_home_assistant_writes_the_compressed_files(tmp_path):
    """Same exclusions as the CLEAN package; on the first start the integration writes the .gz siblings itself."""
    assert set(POLICY["forbidden_suffixes"]) <= biz.GENERATED_SUFFIXES
    assert set(POLICY["forbidden_file_names"]) <= biz.GENERATED_NAMES
    archive = tmp_path / "freshairiq.zip"
    biz.build(ROOT, archive)
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        assert not any(n.endswith((".gz", ".br")) or n.endswith(".precompressed.json") for n in names)
        target = tmp_path / "custom_components" / "freshairiq"
        zf.extractall(target)
    sys.path.insert(0, str(ROOT))
    from custom_components.freshairiq.frontend_assets import ensure_precompressed
    first = ensure_precompressed(target / "frontend")
    sources = sorted(n for n in names if n.startswith("frontend/") and n.endswith(".js"))
    assert first["errors"] == [] and len(first["written"]) == len(sources)
    for src in sources:
        assert (target / (src + ".gz")).is_file()
    again = ensure_precompressed(target / "frontend")
    assert again["written"] == [] and again["revision"] == first["revision"]          # once per file version
    assert (target / "frontend/.precompressed.json").is_file()


def test_release_checks_tag_against_manifest_and_uses_the_versions_release_notes():
    """Closes two gaps found by mutation checks before publication: tag = manifest, notes of that version."""
    text = _wf("release.yml")
    verify = text[text.index("  verify-release:"):text.index("  publish:")]
    assert 'TAG_VERSION="${GITHUB_REF_NAME#v}"' in verify and "['version']" in verify
    assert 'if [ "$TAG_VERSION" != "$MANIFEST_VERSION" ]; then' in verify and "exit 1" in verify
    assert '--notes-file "docs/releases/RELEASE_NOTES_${VERSION}.md"' in text
    version = json.loads((COMP / "manifest.json").read_text(encoding="utf-8"))["version"]
    assert (ROOT / f"docs/releases/RELEASE_NOTES_{version}.md").is_file()
