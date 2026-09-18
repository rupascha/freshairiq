# FreshAirIQ 0.1.2 – Multi-opening & room geometry preview

This preview addresses three setup limitations found during first real-world configuration:

1. Rooms can now have multiple window/door contacts.
2. Room volume can be entered directly in m³ or calculated from length × width × height.
3. Rooms without their own exterior opening can be linked to ventilation contacts in other rooms.

### Contact modes
- `any`: session is active when at least one selected contact is open. Best for multiple equivalent windows.
- `all`: session is active only when every selected contact is open. Best for an indirect path such as interior door + neighbouring-room window.

Existing v0.1.0/v0.1.1 entries are migrated from a single `contact` field to a `contacts` list automatically.
