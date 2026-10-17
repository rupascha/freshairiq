from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js"


# test_threshold_detail_uses_local_mode_override_and_conditional_controls: retired — dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services); intent now covered by ha_tests/test_retired_replacements_20261016.py::test_threshold_pages_show_only_the_control_of_the_chosen_mode


# test_threshold_apply_only_writes_active_value: retired — dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services); intent now covered by ha_tests/test_retired_replacements_20261016.py::test_threshold_save_writes_only_the_active_value
