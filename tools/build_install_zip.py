"""Build and check the installation ZIP attached to every release (``freshairiq.zip``).

It is the manual installation package: extracted into ``custom_components/freshairiq/`` it gives an
install, and GitHub counts its downloads. HACS and the Marketplace keep installing from the source
archive (``hacs.json`` sets no ``zip_release``, A-236). The layout is the one HACS and the Marketplace
would use with ``zip_release`` (``zipfile.ZipFile.extractall(<integration folder>)``), so the archive
can later serve them unchanged. It holds the files of the integration folder at its root – exactly the files of ``custom_components/freshairiq`` in the
release without generated files (see GENERATED_*) – so an install from the asset gives the same files
as an install from the source archive did before.

The archive is reproducible: files in sorted order, a fixed timestamp and fixed permissions, so the
same source gives the same bytes (and the same SHA-256) on every build.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = "custom_components/freshairiq"
DOMAIN = "freshairiq"
ASSET_NAME = "freshairiq.zip"          # must equal ``filename`` in hacs.json
FIXED_DATE = (1980, 1, 1, 0, 0, 0)     # the earliest date a ZIP can hold – reproducible builds
GENERATED_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".git", "node_modules",
                   "test-results", "playwright-report", "blob-report", ".hypothesis", "htmlcov", ".tox", ".nox", ".cache"}
# Same exclusions as the CLEAN package (quality/quality_policy.json "release"): the dashboard's .gz/.br
# siblings and their .precompressed.json are written by Home Assistant itself on the first start
# (frontend_assets.ensure_precompressed) – an install from the source archive never contained them.
GENERATED_NAMES = {".coverage", "coverage.xml", ".DS_Store", "Thumbs.db", ".precompressed.json", ".last-run.json", ".coverage.xml"}
GENERATED_SUFFIXES = {".pyc", ".pyo", ".gz", ".br", ".tmp", ".swp", ".rej"}
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:\.\d+)?$")
REQUIRED = ("__init__.py", "manifest.json", "config_flow.py", "brand/icon.png")
# The Marketplace refuses a download or unpacked ZIP larger than 100 MiB or with more than 50,000 files
MAX_UNPACKED = 100 * 1024 * 1024
MAX_FILES = 50_000


def _generated(rel: str) -> bool:
    p = PurePosixPath(rel)
    return any(part in GENERATED_PARTS for part in p.parts) or p.name in GENERATED_NAMES or p.suffix in GENERATED_SUFFIXES


def component_files(root: Path) -> list[str]:
    """The files of the integration folder, relative to it: the ones Git tracks, or all non-generated ones."""
    base = root / COMPONENT
    names: list[str] | None = None
    if (root / ".git").exists():
        tracked = subprocess.run(["git", "ls-files", "-z", "--", COMPONENT], cwd=root, capture_output=True, check=False)
        if tracked.returncode == 0:
            names = [n[len(COMPONENT) + 1:] for n in tracked.stdout.decode("utf-8").split("\0") if n.startswith(COMPONENT + "/")]
    if names is None:
        names = [p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file()]
    return sorted(n for n in names if n and not _generated(n) and (base / n).is_file())


def build(root: Path, output: Path) -> str:
    """Write the installation ZIP for the source tree ``root``; return its SHA-256."""
    base = root / COMPONENT
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for rel in component_files(root):
            info = zipfile.ZipInfo(rel, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            archive.writestr(info, (base / rel).read_bytes(), compresslevel=9)
    return hashlib.sha256(output.read_bytes()).hexdigest()


def check(archive_path: Path, expected_version: str | None = None) -> tuple[str | None, list[str]]:
    """Check an installation ZIP the way an install uses it; return (version, errors)."""
    errors: list[str] = []
    try:
        with zipfile.ZipFile(archive_path) as zf:
            if (bad := zf.testzip()) is not None:
                errors.append(f"ZIP CRC/integrity failure: {bad}")
            infos = [i for i in zf.infolist() if not i.is_dir()]
            names = {i.filename for i in infos}
            for name in sorted(names):
                p = PurePosixPath(name)
                if p.is_absolute() or ".." in p.parts or "\\" in name:
                    errors.append(f"unsafe path in installation ZIP: {name}")
                if _generated(name):
                    errors.append(f"generated/cache file in installation ZIP: {name}")
                if p.parts and p.parts[0] == "custom_components":
                    errors.append(f"installation ZIP must hold the integration folder's files at its root, not {name}")
            for required in REQUIRED:
                if required not in names:
                    errors.append(f"installation ZIP is missing {required}")
            if len(infos) > MAX_FILES:
                errors.append(f"installation ZIP has more than {MAX_FILES} files")
            if sum(i.file_size for i in infos) > MAX_UNPACKED:
                errors.append("installation ZIP unpacks to more than 100 MiB")
            version = None
            if "manifest.json" in names:
                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
                if manifest.get("domain") != DOMAIN:
                    errors.append(f"manifest domain must be {DOMAIN!r}, got {manifest.get('domain')!r}")
                version = manifest.get("version")
                if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
                    errors.append(f"manifest version is missing or invalid: {version!r}")
                elif expected_version is not None and version != expected_version:
                    errors.append(f"manifest version {version} does not match the release {expected_version}")
            return version, errors
    except (OSError, zipfile.BadZipFile, ValueError) as exc:
        return None, [f"cannot read installation ZIP: {exc}"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, default=ROOT, help="source tree (default: this repository)")
    parser.add_argument("--output", type=Path, help=f"write the installation ZIP here (asset name: {ASSET_NAME})")
    parser.add_argument("--check", type=Path, help="only check an existing installation ZIP")
    parser.add_argument("--version", help="the release version the ZIP must carry")
    args = parser.parse_args(argv)
    if args.check is None and args.output is None:
        parser.error("--output or --check is required")
    target = args.check
    if args.output is not None:
        digest = build(args.source.resolve(), args.output.resolve())
        print(f"Installation ZIP: {args.output} sha256={digest}")
        target = args.output
    version, errors = check(target.resolve(), args.version)
    if errors:
        print("Installation ZIP check: FAIL", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1
    print(f"Installation ZIP check: PASS (FreshAirIQ {version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
