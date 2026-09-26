# FreshAirIQ 0.25.0.38 – GitHub Release Gate

Release-tooling hardening only. The ventilation, recommendation, learning and partial-accuracy logic from 0.25.0.36 is unchanged.

## Changed
- Added `tools/github_release_gate.py` as a fail-closed GitHub/HACS release prerequisite.
- The gate verifies repository structure, required Home Assistant integration files, `hacs.json`, canonical GitHub metadata, version consistency, release notes, ZIP integrity and absence of cache/build artifacts.
- `tools/build_release.py` now validates both the staged release tree and the final ZIP. A non-compliant ZIP is not accepted as a completed build.
- GitHub validation and release workflows run the same gate, so local release creation and GitHub CI enforce the same prerequisite.
