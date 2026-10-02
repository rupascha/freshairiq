# FreshAirIQ 0.25.2.12

## Settings Language & Contact Ownership Hotfix

This hotfix cleans up the complete settings surface without changing FreshAirIQ's ventilation, forecast or learning physics.

- German and English configuration keys are kept in exact parity.
- Field labels no longer repeat a default value everywhere; the configured defaults themselves remain unchanged.
- English settings no longer contain German `leer` residues.
- Room reference selectors use concise labels with the detailed explanation kept below the field.
- The passage-door option is now shown directly for each individual window/door contact in Home Assistant, next to that contact's reference and blind/shutter settings.
- Existing `contact_passage_doors` data remains compatible and is preserved per contact.
- Dynamic contact labels are German when Home Assistant uses German and English otherwise.
- Dashboard contact cards retain the same per-contact passage-door ownership.

