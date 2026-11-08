"""Marketplace/HACS release contract (0.26.7.0): installation ZIP, hacs.json, workflows, download statistics.

Every release carries ``freshairiq.zip`` (manual install, downloads counted by GitHub). HACS and the
Marketplace keep installing from the source archive: with ``zip_release`` both would look for the asset
in every release a user picks, also older ones without it (HACS ``repositories/base.py``
``download_zip_files`` with the current ``repository_manifest``; Marketplace API path the same), so going
back to an older version would fail (A-236). The ZIP has the layout they would extract with
``zipfile.ZipFile.extractall`` into ``custom_components/<domain>/``; these tests extract it that way and
require the files of the integration folder as released.
"""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import sys
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


def test_hacs_json_keeps_the_source_archive_install_so_older_releases_stay_installable(tmp_path):
    """Changed expectation (review before publication, A-236): no zip_release – hacs.json as published so far."""
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    assert hacs == {"name": "FreshAirIQ", "render_readme": True, "homeassistant": "2026.8.0"}
    assert biz.ASSET_NAME == rd.INSTALL_ASSET == "freshairiq.zip"
    # the gate refuses zip_release/filename, so it cannot come back unnoticed
    shutil.copytree(ROOT, tmp_path / "src", ignore=shutil.ignore_patterns(".git", "node_modules", "__pycache__", "*.zip", "test-results"))
    (tmp_path / "src/hacs.json").write_text(json.dumps({**hacs, "zip_release": True, "filename": "freshairiq.zip"}), encoding="utf-8")
    result = subprocess.run([sys.executable, "tools/github_release_gate.py", "--source", "."], cwd=tmp_path / "src", text=True, capture_output=True)
    assert result.returncode != 0 and "must not set zip_release" in result.stdout + result.stderr


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
     "assets": [{"name": "freshairiq.zip", "download_count": 3}]},
    {"tag_name": "v0.26.7.0", "published_at": "2026-11-10T10:00:00Z", "prerelease": False, "draft": False,
     "assets": [{"name": "freshairiq.zip", "download_count": 120}, {"name": "FreshAirIQ-v0.26.7.0-CLEAN.zip", "download_count": 7}]},
    {"tag_name": "v0.26.6.0", "published_at": "2026-11-03T10:00:00Z", "prerelease": False, "draft": False, "assets": []},
    {"tag_name": "v9.9.9", "published_at": None, "prerelease": False, "draft": True, "assets": [{"name": "freshairiq.zip", "download_count": 99}]},
]


def test_download_summary_counts_only_what_github_counts():
    s = rd.summarize(RELEASES)
    assert [r["tag"] for r in s["releases"]] == ["v0.26.8.0", "v0.26.7.0", "v0.26.6.0"]       # drafts are not public
    assert (s["total_install_downloads"], s["total_other_downloads"], s["total_asset_downloads"]) == (123, 7, 130)
    assert s["releases_without_counted_downloads"] == ["v0.26.6.0"]                          # nothing invented
    assert "not an installation" in s["note"]
    md = rd.markdown(s)
    assert "| v0.26.8.0 (pre-release) | 2026-12-01 | 3 | 0 |" in md
    assert "| v0.26.6.0 | 2026-11-03 | – | – (no assets: not counted by GitHub) |" in md
    assert "**Total:** 123 × freshairiq.zip, 7 × other assets (130 asset downloads)." in md


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
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    one = lambda request: _Response(json.dumps(RELEASES).encode())  # noqa: E731
    assert rd.main(["--json"], opener=one) == 0
    assert json.loads(capsys.readouterr().out)["total_install_downloads"] == 123
    assert rd.main([], opener=one) == 0
    assert "## FreshAirIQ release downloads" in capsys.readouterr().out


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
