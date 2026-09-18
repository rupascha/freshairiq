"""Build a clean FreshAirIQ release ZIP only after quality gates pass."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXCLUDED_TOP_LEVEL = {"quality_reports"}


def _excluded(path: Path, policy: dict) -> bool:
    rel = path.relative_to(ROOT)
    if rel.parts and rel.parts[0] in EXCLUDED_TOP_LEVEL:
        return True
    release = policy["release"]
    forbidden_parts = set(release["forbidden_path_parts"])
    forbidden_names = set(release["forbidden_file_names"])
    forbidden_suffixes = set(release["forbidden_suffixes"])
    if any(part in forbidden_parts for part in rel.parts):
        return True
    if path.is_file() and (path.name in forbidden_names or path.suffix in forbidden_suffixes):
        return True
    if path.suffix == ".zip":
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=None)
    parser.add_argument("--skip-quality", action="store_true", help="Only for an already verified workspace")
    args = parser.parse_args()

    policy = json.loads((ROOT / "quality/quality_policy.json").read_text(encoding="utf-8"))
    version = policy["version"]
    suffix = str(policy.get("release", {}).get("artifact_suffix") or "Continuous-Quality-System")
    release_name = f"FreshAirIQ-v{version}-{suffix}"
    output = Path(args.output).resolve() if args.output else ROOT.parent / f"{release_name}.zip"

    if not args.skip_quality:
        proc = subprocess.run([sys.executable, "tools/quality_gate.py", "--profile", "local"], cwd=ROOT)
        if proc.returncode:
            print("Release build aborted: quality gate failed.")
            return proc.returncode

    with tempfile.TemporaryDirectory(prefix="freshairiq-release-") as temp:
        stage = Path(temp) / release_name
        stage.mkdir(parents=True)
        for source in ROOT.rglob("*"):
            if _excluded(source, policy):
                continue
            rel = source.relative_to(ROOT)
            target = stage / rel
            if source.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            elif source.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)

        hygiene = subprocess.run(
            [
                sys.executable, str(ROOT / "tools/quality_gate.py"), "--profile", "hygiene",
                "--release-tree", str(stage), "--report", "quality_reports/release-hygiene.json",
            ],
            cwd=ROOT,
        )
        if hygiene.returncode:
            print("Release build aborted: staged release hygiene failed.")
            return hygiene.returncode

        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            output.unlink()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted(stage.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(stage.parent).as_posix())

    with zipfile.ZipFile(output, "r") as archive:
        bad = archive.testzip()
        if bad:
            print(f"ZIP integrity failure: {bad}")
            return 1
        print(f"Release ZIP: {output}")
        print(f"Files: {len(archive.infolist())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
