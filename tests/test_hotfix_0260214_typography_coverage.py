from pathlib import Path

CARD=Path("custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")

def test_every_goal_text_family_follows_goal_scale():
    expected=(
      ".decision-goal-overview .decision-goal-head>span{font-size:calc(14px * var(--faiq-font-goals,1))}",
      ".decision-goal-overview .decision-goal-head>strong{font-size:calc(11px * var(--faiq-font-goals,1))}",
      ".decision-goal-overview .decision-goal b{font-size:calc(11px * var(--faiq-font-goals,1))}",
      ".decision-goal-overview .decision-goal small,.decision-goal-overview.compact .decision-goal small{font-size:calc(10.5px * var(--faiq-font-goals,1))}",
      ".decision-goal-overview .decision-goal-rooms>summary{font-size:calc(10.5px * var(--faiq-font-goals,1))}",
      ".decision-goal-overview .decision-goal-room>summary>strong{font-size:calc(9.5px * var(--faiq-font-goals,1))}",
      ".decision-goal-overview .decision-goal-icon small{font-size:calc(9px * var(--faiq-font-goals,1))}",
    )
    for rule in expected: assert rule in CARD

def test_mobile_goal_baselines_are_preserved_at_100_percent():
    for rule in (
      ".decision-goal-overview .decision-goal-room-name{font-size:calc(11px * var(--faiq-font-goals,1))}",
      ".decision-goal-overview .decision-goal-room>summary>strong{font-size:calc(9px * var(--faiq-font-goals,1))}",
      ".decision-goal-overview .decision-goal-icon small{font-size:calc(8.5px * var(--faiq-font-goals,1))}",
    ): assert rule in CARD

def test_fixed_steps_and_other_categories_remain_intact():
    assert "FAIQ_FONT_SCALE_STEPS = Object.freeze([0.8,0.9,1,1.1,1.2,1.3,1.4,1.5])" in CARD
    for var in ("recommendation","rooms","metrics","details","meta"):
        assert f"--faiq-font-{var}" in CARD
