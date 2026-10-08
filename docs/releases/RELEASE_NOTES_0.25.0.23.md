# FreshAirIQ 0.25.0.23 – Diagnostics Client Hardening

Hotfix scope: harden only the optional outbound diagnostics client introduced in 0.25.0.22. Ventilation physics, forecast coefficients, learning behaviour, recommendation priorities and the manual diagnostics export are intentionally unchanged.

## What changed

- The existing manual Home Assistant diagnostics export remains unchanged and available through `/api/freshairiq/diagnostics` and the dashboard export button.
- Outbound transport schema is now version 2 and no longer uses the 240-record trimming path.
- The first acknowledged Hub sync is prepared from every record present in the normal retained diagnostics export, preserving the same analysis-relevant technical evidence after local privacy filtering.
- Direct identifiers are removed or pseudonymised locally before transport. Room labels/keys, entity IDs, resident names, notification targets, network identifiers, URLs, e-mail addresses, exact device models and custom level labels are not sent in clear form.
- Large exports are split into bounded chunks instead of silently dropping older records.
- Every transported record has a stable content ID. Chunks carry batch/chunk IDs and an idempotency key for server-side deduplication.
- Progress is persisted after every acknowledged chunk. If a later chunk fails, the next retry resumes after the last acknowledged record cursor.
- After the initial full sync, only records newer than the last acknowledged cursor are selected. If nothing new exists, only a metadata snapshot is prepared.
- The public Diagnostics Hub endpoint remains intentionally empty in this release. Even with diagnostics sharing enabled, no outbound connection can occur yet.

## Compatibility and safety

The transport layer is isolated from the FreshAirIQ coordinator. Upload failures, malformed persisted transport state and an unavailable future Hub remain non-critical and cannot change the ventilation decision path.

## Local verification

- 679/679 local regression tests passed.
- Pure-logic coverage: 100.00% (5,311/5,311 statements).
- Robustness gate: 53/53 tests passed.
- Stability gate: 3,000 deterministic cycles passed.
- Performance gate passed.
- Frontend JavaScript syntax checks passed.
- Full Home Assistant runtime and browser E2E remain CI-only in this environment.
