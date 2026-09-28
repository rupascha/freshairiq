# FreshAirIQ 0.25.1.23

## Local Runtime Health & Early-Warning Diagnostics

FreshAirIQ now analyses selected runtime-health signals locally before diagnostics leave Home Assistant. Large own entity payloads are measured locally, recorder-exposed oversize payloads become bounded technical incidents, repeated occurrences are aggregated, and unknown FreshAirIQ runtime exceptions can be fingerprinted without retaining exception messages or raw log lines.

The existing diagnostics sharing mode and consent remain authoritative. No raw Home Assistant log is uploaded by this feature. Recorder-protected live dashboard payloads remain available and are not falsely reported as recorder incidents.
