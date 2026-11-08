"""Download statistics of the FreshAirIQ GitHub releases – from GitHub's own release data only.

Every release asset carries ``download_count``: how often that file was downloaded from GitHub.
This tool lists the counts per release and in total, separately for the installation ZIP
(``freshairiq.zip``, the manual installation package) and for other assets (the CLEAN package). What it does not do, on purpose:

* It invents nothing: releases without assets have no counted downloads. GitHub does not count
  downloads of the automatic source archives (``Source code (zip/tar.gz)``), from which HACS and the
  Marketplace install – installs through them are not in these numbers.
* A download is not an installation: updates, reinstalls, several Home Assistant instances, CI
  runs and mirrors count again.
* No telemetry: it only reads public release data of the repository; nothing is sent anywhere.

Use: ``python tools/release_downloads.py [--repository owner/name] [--markdown|--json]``
(``GITHUB_TOKEN`` in the environment raises GitHub's rate limit; it is not required).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from typing import Any

DEFAULT_REPOSITORY = "rupascha/freshairiq"
INSTALL_ASSET = "freshairiq.zip"
API = "https://api.github.com"


def fetch_releases(repository: str, token: str | None = None, opener=urllib.request.urlopen) -> list[dict[str, Any]]:
    """All releases of ``repository`` (every page), newest first, as GitHub returns them."""
    releases: list[dict[str, Any]] = []
    page = 1
    while True:
        request = urllib.request.Request(f"{API}/repos/{repository}/releases?per_page=100&page={page}",
                                         headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                                                  "User-Agent": "freshairiq-release-downloads"})
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        with opener(request) as response:
            batch = json.loads(response.read().decode("utf-8"))
        if not isinstance(batch, list):
            raise ValueError(f"unexpected answer from GitHub: {batch!r}"[:300])
        releases.extend(batch)
        if len(batch) < 100:
            return releases
        page += 1


def summarize(releases: list[dict[str, Any]], install_asset: str = INSTALL_ASSET) -> dict[str, Any]:
    """Per release and in total: downloads of the installation ZIP, of other assets, and which releases have no counted downloads."""
    rows = []
    for release in releases:
        if release.get("draft"):
            continue                                   # not public: nobody could download it
        assets = [{"name": str(a.get("name", "")), "downloads": int(a.get("download_count") or 0)} for a in release.get("assets") or []]
        install = sum(a["downloads"] for a in assets if a["name"] == install_asset)
        other = sum(a["downloads"] for a in assets if a["name"] != install_asset)
        rows.append({
            "tag": release.get("tag_name"), "published_at": release.get("published_at"), "prerelease": bool(release.get("prerelease")),
            "has_install_asset": any(a["name"] == install_asset for a in assets), "install_downloads": install,
            "other_downloads": other, "assets": assets, "counted": bool(assets),
        })
    return {
        "releases": rows,
        "total_install_downloads": sum(r["install_downloads"] for r in rows),
        "total_other_downloads": sum(r["other_downloads"] for r in rows),
        "total_asset_downloads": sum(r["install_downloads"] + r["other_downloads"] for r in rows),
        "releases_without_counted_downloads": [r["tag"] for r in rows if not r["counted"]],
        "note": ("GitHub counts downloads of release assets only, not of the source archives; a download is not an "
                 "installation (updates, reinstalls and several instances count again)."),
    }


def markdown(summary: dict[str, Any]) -> str:
    """The summary as a Markdown table (for a workflow's job summary)."""
    lines = ["## FreshAirIQ release downloads", "",
             f"| Release | Published | {INSTALL_ASSET} | Other assets |", "|---|---|---:|---:|"]
    for r in summary["releases"]:
        tag = f"{r['tag']} (pre-release)" if r["prerelease"] else str(r["tag"])
        install = str(r["install_downloads"]) if r["has_install_asset"] else "–"
        other = str(r["other_downloads"]) if r["counted"] else "– (no assets: not counted by GitHub)"
        lines.append(f"| {tag} | {str(r['published_at'] or '')[:10]} | {install} | {other} |")
    lines += ["", f"**Total:** {summary['total_install_downloads']} × {INSTALL_ASSET}, {summary['total_other_downloads']} × other assets "
              f"({summary['total_asset_downloads']} asset downloads).", "", f"_{summary['note']}_", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None, opener=urllib.request.urlopen) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    out = parser.add_mutually_exclusive_group()
    out.add_argument("--json", action="store_true", help="machine-readable output")
    out.add_argument("--markdown", action="store_true", help="Markdown table (default)")
    args = parser.parse_args(argv)
    summary = summarize(fetch_releases(args.repository, os.environ.get("GITHUB_TOKEN"), opener))
    sys.stdout.write(json.dumps(summary, indent=2) + "\n" if args.json else markdown(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
