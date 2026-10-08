from custom_components.freshairiq.shadow_learning import process_shadow_feedback, ensure_shadow_defaults


def _room():
    room = {"outcome_removed_factor": 1.0, "outcome_feedback_samples": 20}
    ensure_shadow_defaults(room)
    return room


def test_shadow_does_not_change_production_on_single_sample():
    room = _room()
    result = process_shadow_feedback(room, predicted_removed_ml=100, actual_removed_ml=115)
    assert result["action"] == "observing"
    assert room["outcome_removed_factor"] == 1.0


def test_shadow_promotes_only_after_repeated_better_evidence():
    room = _room()
    actions = []
    for _ in range(8):
        actions.append(process_shadow_feedback(room, predicted_removed_ml=100, actual_removed_ml=115)["action"])
    assert actions[-1] == "promoted"
    assert room["outcome_removed_factor"] > 1.0
    assert room["shadow_rollback_active"] is True
    assert room["shadow_learning_promotions"] == 1


def test_shadow_does_not_promote_noise_around_correct_model():
    room = _room()
    for actual in (98, 102, 99, 101, 97, 103, 100, 101, 99, 102):
        process_shadow_feedback(room, predicted_removed_ml=100, actual_removed_ml=actual)
    assert room["outcome_removed_factor"] == 1.0
    assert room["shadow_learning_promotions"] == 0


def test_promoted_model_rolls_back_when_counterfactual_is_better():
    room = _room()
    for _ in range(8):
        process_shadow_feedback(room, predicted_removed_ml=100, actual_removed_ml=115)
    promoted = room["outcome_removed_factor"]
    assert promoted > 1.0
    # Following forecasts now embody the promoted factor (~108). Reality returns
    # to the previous-model level (~100), so counterfactual should win.
    actions = []
    for _ in range(5):
        actions.append(process_shadow_feedback(room, predicted_removed_ml=108, actual_removed_ml=100)["action"])
    assert actions[-1] == "rollback"
    assert room["outcome_removed_factor"] == 1.0
    assert room["shadow_learning_rollbacks"] == 1


def test_corrupt_shadow_container_is_repaired_by_defaults_path():
    room = _room()
    room["shadow_learning_candidates"] = None
    process_shadow_feedback(room, predicted_removed_ml=100, actual_removed_ml=110)
    assert isinstance(room["shadow_learning_candidates"], dict)


def test_rollback_guard_does_not_start_new_competition_in_parallel():
    room = _room()
    for _ in range(8):
        process_shadow_feedback(room, predicted_removed_ml=100, actual_removed_ml=115)
    assert room["shadow_rollback_active"] is True
    assert room["shadow_learning_samples"] == 0
    process_shadow_feedback(room, predicted_removed_ml=108, actual_removed_ml=100)
    assert room["shadow_learning_samples"] == 0
    assert room["shadow_rollback_samples"] == 1


def test_shadow_tracks_lifetime_evidence_separately_from_generation_samples():
    room = _room()
    for _ in range(8):
        process_shadow_feedback(room, predicted_removed_ml=100, actual_removed_ml=115)
    assert room["shadow_learning_total_samples"] == 8
    assert room["shadow_learning_samples"] == 0
