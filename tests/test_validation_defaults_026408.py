"""Pure-logic coverage: default options pass the relationship check (no HA needed)."""
from custom_components.freshairiq.validation import option_relationship_error


def test_default_options_have_no_relationship_error():
    assert option_relationship_error({}) is None
    assert option_relationship_error({"co2_warn": 1500, "co2_critical": 1400}) == "invalid_co2_order"
