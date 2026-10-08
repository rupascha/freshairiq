from custom_components.freshairiq.goals import evaluate_goals, normalise_priorities


def test_unavailable_co2_never_becomes_priority_or_goal():
    state = evaluate_goals(humidity=61, target_rh=55, co2=None, co2_warn=1000,
        temperature=22, temperature_target=None, priorities=["co2","humidity","temperature"],
        available_goals=["humidity"])
    assert state["priorities"] == ["humidity"]
    assert [g["id"] for g in state["goals"] if g["active"]] == ["humidity"]


def test_only_configured_goals_are_prioritised():
    assert normalise_priorities(["co2","temperature","humidity"], ["humidity","temperature"]) == ["temperature","humidity"]


def test_co2_becomes_goal_when_available():
    state = evaluate_goals(humidity=55, target_rh=55, co2=1400, co2_warn=1000,
        temperature=22, temperature_target=None, priorities=["co2","humidity"],
        available_goals=["humidity","co2"])
    assert state["priorities"] == ["co2","humidity"]
    assert state["highest_open_goal"] == "co2"
