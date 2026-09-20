"""Fail closed unless a FreshAirIQ source tree or ZIP is GitHub/HACS release ready."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

REQUIRED_ROOT = ("README.md", "LICENSE", "hacs.json", ".github/workflows/validate.yml", ".github/workflows/release.yml")
REQUIRED_COMPONENT = ("__init__.py", "manifest.json", "config_flow.py")
REQUIRED_BRAND = ("icon.png", "icon@2x.png", "dark_icon.png", "dark_icon@2x.png", "logo.png", "logo@2x.png", "dark_logo.png", "dark_logo@2x.png")
FORBIDDEN_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".git", "node_modules", "quality_reports"}
FORBIDDEN_NAMES = {".coverage", "coverage.xml", ".DS_Store", "Thumbs.db"}
FORBIDDEN_SUFFIXES = {".pyc", ".pyo"}
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:\.\d+)?(?:[-+][0-9A-Za-z.-]+)?$")


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def _check_common(paths: set[str], read_text, errors: list[str]) -> str | None:
    for required in REQUIRED_ROOT:
        if required not in paths:
            fail(errors, f"missing required repository file: {required}")
    component = "custom_components/freshairiq"
    for name in REQUIRED_COMPONENT:
        path = f"{component}/{name}"
        if path not in paths:
            fail(errors, f"missing required integration file: {path}")
    # Home Assistant 2026.3+ serves custom-integration branding from this local
    # directory. HACS 2.0.x may still show its placeholder in the Downloads
    # view because that frontend currently uses the legacy public brands CDN.
    # We nevertheless fail closed if a FreshAirIQ release loses any local brand
    # asset, so the repository is ready as soon as HACS consumes the local API.
    for name in REQUIRED_BRAND:
        path = f"{component}/brand/{name}"
        if path not in paths:
            fail(errors, f"missing required local brand asset: {path}")

    for raw in sorted(paths):
        p = PurePosixPath(raw)
        if any(part in FORBIDDEN_PARTS for part in p.parts):
            fail(errors, f"forbidden generated/cache path in release: {raw}")
        if p.name in FORBIDDEN_NAMES or p.suffix in FORBIDDEN_SUFFIXES:
            fail(errors, f"forbidden generated/cache file in release: {raw}")
        if p.is_absolute() or ".." in p.parts:
            fail(errors, f"unsafe archive/repository path: {raw}")

    manifest_path = f"{component}/manifest.json"
    if manifest_path not in paths:
        return None
    try:
        manifest = json.loads(read_text(manifest_path))
    except Exception as exc:
        fail(errors, f"invalid manifest.json: {exc}")
        return None

    expected = {
        "domain": "freshairiq",
        "name": "FreshAirIQ",
        "config_flow": True,
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            fail(errors, f"manifest {key!r} must be {value!r}, got {manifest.get(key)!r}")
    version = manifest.get("version")
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
        fail(errors, f"manifest version is missing or invalid: {version!r}")
        return None
    if manifest.get("codeowners") != ["@rupascha"]:
        fail(errors, "manifest codeowners must contain @rupascha")
    for key, suffix in (("documentation", "/rupascha/freshairiq"), ("issue_tracker", "/rupascha/freshairiq/issues")):
        value = str(manifest.get(key, "")).rstrip("/")
        if not value.startswith("https://github.com") or not value.endswith(suffix):
            fail(errors, f"manifest {key} does not point to the canonical GitHub repository")

    try:
        hacs = json.loads(read_text("hacs.json"))
        if hacs.get("name") != "FreshAirIQ":
            fail(errors, "hacs.json name must be FreshAirIQ")
        if not hacs.get("homeassistant"):
            fail(errors, "hacs.json must declare the minimum Home Assistant version")
    except Exception as exc:
        fail(errors, f"invalid hacs.json: {exc}")

    version_sources = {
        "custom_components/freshairiq/const.py": f'VERSION = "{version}"',
        "custom_components/freshairiq/frontend/freshairiq-card.js": f'const FAIQ_VERSION = "{version}";',
        "custom_components/freshairiq/frontend/freshairiq-panel.js": f'const FAIQ_VERSION = "{version}";',
        "custom_components/freshairiq/frontend/freshairiq-loader.js": f'const FAIQ_VERSION = "{version}";',
        "quality/quality_policy.json": f'"version": "{version}"',
        "package.json": f'"version": "{version}"',
    }
    for path, needle in version_sources.items():
        if path not in paths:
            fail(errors, f"missing version-bearing file: {path}")
        elif needle not in read_text(path):
            fail(errors, f"version mismatch in {path}; expected {version}")

    notes = f"RELEASE_NOTES_{version}.md"
    if notes not in paths:
        fail(errors, f"missing release notes for manifest version: {notes}")
    return version


def check_tree(root: Path) -> tuple[str | None, list[str]]:
    errors: list[str] = []
    all_paths = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    # Local test/compile runs legitimately create ignored caches. For a real Git checkout,
    # reject such files only if Git says they are tracked. The final ZIP is always strict.
    if (root / ".git").exists():
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=root, text=True, capture_output=True, check=False
        )
        if tracked.returncode == 0:
            for raw in tracked.stdout.splitlines():
                p = PurePosixPath(raw)
                if any(part in FORBIDDEN_PARTS for part in p.parts) or p.name in FORBIDDEN_NAMES or p.suffix in FORBIDDEN_SUFFIXES:
                    fail(errors, f"forbidden generated/cache file is tracked by Git: {raw}")
    def is_generated(raw: str) -> bool:
        p = PurePosixPath(raw)
        return any(part in FORBIDDEN_PARTS for part in p.parts) or p.name in FORBIDDEN_NAMES or p.suffix in FORBIDDEN_SUFFIXES
    paths = {raw for raw in all_paths if not is_generated(raw)}
    def read_text(path: str) -> str:
        return (root / path).read_text(encoding="utf-8")
    version = _check_common(paths, read_text, errors)
    return version, errors


def check_zip(archive_path: Path) -> tuple[str | None, list[str]]:
    errors: list[str] = []
    try:
        with zipfile.ZipFile(archive_path) as zf:
            bad = zf.testzip()
            if bad:
                fail(errors, f"ZIP CRC/integrity failure: {bad}")
            files = [n for n in zf.namelist() if n and not n.endswith("/")]
            roots = {PurePosixPath(n).parts[0] for n in files if PurePosixPath(n).parts}
            prefix = ""
            if "custom_components" not in roots:
                if len(roots) != 1:
                    fail(errors, "ZIP must contain repository files at root or exactly one enclosing release directory")
                elif roots:
                    prefix = next(iter(roots)) + "/"
            normalized = {n[len(prefix):] for n in files if n.startswith(prefix)}
            if any(not n for n in normalized):
                fail(errors, "ZIP contains an invalid empty normalized path")
            def read_text(path: str) -> str:
                return zf.read(prefix + path).decode("utf-8")
            version = _check_common(normalized, read_text, errors)
            return version, errors
    except (OSError, zipfile.BadZipFile) as exc:
        return None, [f"cannot read ZIP: {exc}"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--source", type=Path)
    group.add_argument("--zip", dest="zip_path", type=Path)
    args = parser.parse_args()
    version, errors = check_tree(args.source.resolve()) if args.source else check_zip(args.zip_path.resolve())
    if errors:
        print("GitHub/HACS release gate: FAIL", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1
    print(f"GitHub/HACS release gate: PASS (FreshAirIQ {version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
