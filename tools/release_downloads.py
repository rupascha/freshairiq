"""Download statistics of the FreshAirIQ GitHub releases – from GitHub's own release data only.

Every release asset carries ``download_count``: how often that file was downloaded from GitHub.
This tool lists the counts per release and in total, separately for the installation asset
(``freshairiq.zip``), the CLEAN package and other assets. What it does not do, on purpose:

* It invents nothing. HACS and the Marketplace install a release from the asset named in the
  ``hacs.json`` of that tag (``zip_release``/``filename``, from 0.26.7.2 on) and otherwise from the
  automatic source archive. GitHub does not count source archive downloads, so those releases show
  "not counted" – never 0 installs.
* A download is not an installation: the asset count includes Marketplace/HACS installs and updates as
  well as manual and repeated downloads (reinstalls, several Home Assistant instances, CI runs, mirrors).
* No telemetry: it only reads public release data and the ``hacs.json`` of each tag; nothing is sent anywhere.

Use: ``python tools/release_downloads.py [--repository owner/name] [--markdown|--json]``
(``GITHUB_TOKEN`` in the environment raises GitHub's rate limit; it is not required).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_REPOSITORY = "rupascha/freshairiq"
INSTALL_ASSET = "freshairiq.zip"
CLEAN_SUFFIX = "-CLEAN.zip"
API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"


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


def fetch_hacs_manifests(repository: str, tags: list[str], opener=urllib.request.urlopen, token: str | None = None) -> dict[str, dict[str, Any] | None]:
    """``hacs.json`` of every tag, read where the Marketplace reads it (else through the API); ``None`` when it cannot be read."""
    def read(url: str, api: bool) -> dict[str, Any] | None:
        request = urllib.request.Request(url, headers={"User-Agent": "freshairiq-release-downloads"})
        if api:
            request.add_header("Accept", "application/vnd.github+json")
            if token:
                request.add_header("Authorization", f"Bearer {token}")
        try:
            with opener(request) as response:
                data = json.loads(response.read().decode("utf-8"))
            if api:
                data = json.loads(base64.b64decode(data["content"]).decode("utf-8")) if isinstance(data, dict) and "content" in data else None
        except (OSError, ValueError, KeyError):
            return None
        return data if isinstance(data, dict) else None

    manifests: dict[str, dict[str, Any] | None] = {}
    for tag in tags:
        ref = urllib.parse.quote(tag)
        manifests[tag] = read(f"{RAW}/{repository}/{ref}/hacs.json", False) or read(f"{API}/repos/{repository}/contents/hacs.json?ref={ref}", True)
    return manifests


def install_source(hacs: dict[str, Any] | None, install_asset: str = INSTALL_ASSET) -> str:
    """What HACS and the Marketplace install for a tag with this ``hacs.json``: asset, source archive or unknown."""
    if hacs is None:
        return "unknown"
    if hacs.get("zip_release") and hacs.get("filename"):
        return "asset" if hacs.get("filename") == install_asset else "other asset"
    return "source archive"


def summarize(releases: list[dict[str, Any]], manifests: dict[str, dict[str, Any] | None] | None = None,
              install_asset: str = INSTALL_ASSET) -> dict[str, Any]:
    """Per release and in total: installation asset, CLEAN package and other asset downloads, and where installs come from."""
    manifests = manifests or {}
    rows = []
    for release in releases:
        if release.get("draft"):
            continue                                   # not public: nobody could download it
        tag = release.get("tag_name")
        assets = [{"name": str(a.get("name", "")), "downloads": int(a.get("download_count") or 0)} for a in release.get("assets") or []]
        install = sum(a["downloads"] for a in assets if a["name"] == install_asset)
        clean = sum(a["downloads"] for a in assets if a["name"].endswith(CLEAN_SUFFIX))
        other = sum(a["downloads"] for a in assets if a["name"] != install_asset and not a["name"].endswith(CLEAN_SUFFIX))
        has_install = any(a["name"] == install_asset for a in assets)
        source = install_source(manifests.get(tag), install_asset)
        if source == "asset" and not has_install:
            source = "asset missing"                   # HACS and the Marketplace would fail to install this tag
        rows.append({
            "tag": tag, "published_at": release.get("published_at"), "prerelease": bool(release.get("prerelease")),
            "install_source": source, "has_install_asset": has_install, "install_downloads": install,
            "clean_downloads": clean, "other_downloads": other, "assets": assets, "counted": bool(assets),
        })
    return {
        "releases": rows,
        "total_install_downloads": sum(r["install_downloads"] for r in rows),
        "total_install_downloads_marketplace_releases": sum(r["install_downloads"] for r in rows if r["install_source"] == "asset"),
        "total_clean_downloads": sum(r["clean_downloads"] for r in rows),
        "total_other_downloads": sum(r["other_downloads"] for r in rows),
        "total_asset_downloads": sum(r["install_downloads"] + r["clean_downloads"] + r["other_downloads"] for r in rows),
        "releases_installed_from_source_archive": [r["tag"] for r in rows if r["install_source"] == "source archive"],
        "releases_with_missing_install_asset": [r["tag"] for r in rows if r["install_source"] == "asset missing"],
        "releases_without_counted_downloads": [r["tag"] for r in rows if not r["counted"]],
        "note": (f"Downloads of the installation asset {install_asset}: Marketplace/HACS installs and updates of releases that "
                 "install from it, plus manual and repeated downloads – a download is not an installation. Releases installed "
                 "from the source archive are not counted by GitHub (not zero)."),
    }


SOURCE_LABELS = {
    "asset": f"{INSTALL_ASSET}",
    "source archive": "source archive (not counted)",
    "asset missing": f"{INSTALL_ASSET} missing",
    "other asset": "other asset",
    "unknown": "unknown (hacs.json not readable)",
}


def markdown(summary: dict[str, Any]) -> str:
    """The summary as a Markdown table (for a workflow's job summary)."""
    lines = ["## FreshAirIQ release downloads", "",
             f"| Release | Published | Marketplace/HACS install from | {INSTALL_ASSET} | CLEAN package | Other assets |",
             "|---|---|---|---:|---:|---:|"]
    for r in summary["releases"]:
        tag = f"{r['tag']} (pre-release)" if r["prerelease"] else str(r["tag"])
        source = SOURCE_LABELS.get(r["install_source"], r["install_source"])
        install = str(r["install_downloads"]) if r["has_install_asset"] else "–"
        clean = str(r["clean_downloads"]) if any(a["name"].endswith(CLEAN_SUFFIX) for a in r["assets"]) else "–"
        other = str(r["other_downloads"]) if r["counted"] else "– (no assets: not counted by GitHub)"
        lines.append(f"| {tag} | {str(r['published_at'] or '')[:10]} | {source} | {install} | {clean} | {other} |")
    lines += ["", f"**Total:** {summary['total_install_downloads']} × {INSTALL_ASSET} (installation asset downloads, "
              f"{summary['total_install_downloads_marketplace_releases']} of them in releases the Marketplace/HACS install from), "
              f"{summary['total_clean_downloads']} × CLEAN package, {summary['total_other_downloads']} × other assets "
              f"({summary['total_asset_downloads']} asset downloads).", ""]
    if summary["releases_with_missing_install_asset"]:
        lines += [f"**Missing {INSTALL_ASSET}:** {', '.join(summary['releases_with_missing_install_asset'])}", ""]
    lines += [f"_{summary['note']}_", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None, opener=urllib.request.urlopen) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    out = parser.add_mutually_exclusive_group()
    out.add_argument("--json", action="store_true", help="machine-readable output")
    out.add_argument("--markdown", action="store_true", help="Markdown table (default)")
    args = parser.parse_args(argv)
    releases = fetch_releases(args.repository, os.environ.get("GITHUB_TOKEN"), opener)
    tags = [str(r.get("tag_name")) for r in releases if not r.get("draft") and r.get("tag_name")]
    summary = summarize(releases, fetch_hacs_manifests(args.repository, tags, opener, os.environ.get("GITHUB_TOKEN")))
    sys.stdout.write(json.dumps(summary, indent=2) + "\n" if args.json else markdown(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
