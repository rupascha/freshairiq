# FreshAirIQ 0.25.0.14 — Measurement Quality & Learning Maturity Hotfix

- Uses Home Assistant `last_reported` (with `last_updated` fallback) as the report-freshness timestamp.
- Tightens objective validation freshness: room T/RH frames older than 10 minutes are no longer A/B validation frames.
- Adds A–D measurement-frame grades and explicit quality-weighted adaptive learning (A 1.00, B 0.75, held C 0.35, unsuitable 0).
- Keeps the existing two-new-report/15-minute close-decision safety gate unchanged.
- Makes learning maturity substantially more conservative: component maturity is capped by independent evidence depth.
- Objective forecast validation now needs 100 comparable room samples for full evidence maturity.
- Overall Intelligence maturity is capped while objective validation is sparse; “Auf deine Bedürfnisse optimiert” additionally requires >=100 validation samples, >=85% validation quality, >=90% core evidence and >=90% personal-context maturity.
- Existing learned coefficients and stored samples are preserved; only their influence/presentation is re-evaluated more conservatively.
