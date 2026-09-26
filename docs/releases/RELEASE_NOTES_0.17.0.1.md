# FreshAirIQ v0.17.0.1 – Problem-room selection hotfix

- Fixes a recommendation bug where a non-critical high-humidity/problem room
  could bypass the configured physical usefulness thresholds.
- Non-critical problem rooms now require at least `min_potential_room_ml`
  removable moisture and a positive house-wide ventilation balance.
- Critical mould/CO2 situations remain authoritative and may still override
  the usefulness threshold.
- Cross-ventilation pair selection follows the same physical rule.
- When a humid room needs attention but current ventilation benefit is too low,
  FreshAirIQ explicitly recommends waiting and explains why.
- No unrelated UI, room-card, room-detail, scroll/touch or learning changes.
