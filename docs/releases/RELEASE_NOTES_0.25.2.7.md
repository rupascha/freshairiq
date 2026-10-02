# FreshAirIQ 0.25.2.7 — Three-State Unknown Hold Hotfix

Temporary `unknown` or `unavailable` states on already proven three-state contacts no longer count as physical handle/window transitions. FreshAirIQ keeps the last confirmed physical state and timestamp until real `closed`, `open`, or `tilted` evidence returns. The gap remains visible in diagnostics and session audit data.
