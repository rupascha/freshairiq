"""0.26.6.0 (7): all four mould risk limits are settings ("Advanced model parameters" → "Mould & CO₂").

Defaults stay 60 / 70 / 80 / 90 % estimated surface humidity, so existing installations keep their levels.
New input must rise strictly (``invalid_mould_order``); an older setup whose "high" limit lies at or below the
new lower defaults is repaired once at load (only the two new keys move, the stored limits stay).
"""
from __future__ import annotations

import pytest

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.model import _mould_level
from custom_components.freshairiq.settings_contract import NATIVE_OPTION_KEYS
from custom_components.freshairiq.validation import RELATION_OPTION_KEYS, option_relationship_error, repair_option_relationships

KEYS = ("mould_slight_surface_rh", "mould_elevated_surface_rh", "mould_warn_surface_rh", "mould_critical_surface_rh")


def test_defaults_are_unchanged_and_the_keys_belong_to_every_contract() -> None:
    assert [DEFAULT_OPTIONS[k] for k in KEYS] == [60.0, 70.0, 80.0, 90.0]
    assert set(KEYS) <= NATIVE_OPTION_KEYS and set(KEYS) <= RELATION_OPTION_KEYS


@pytest.mark.parametrize(("rh", "level"), [(59.9, "Low"), (60, "Slightly elevated"), (69.9, "Slightly elevated"),
                                           (70, "Elevated"), (80, "High"), (89.9, "High"), (90, "Very high")])
def test_default_limits_give_the_known_levels(rh: float, level: str) -> None:
    assert _mould_level(rh, 80, 90) == level
    assert _mould_level(rh, 80, 90, 60, 70) == level


@pytest.mark.parametrize(("rh", "level"), [(49.9, "Low"), (50, "Slightly elevated"), (55, "Elevated"),
                                           (65, "High"), (75, "Very high")])
def test_custom_limits_are_used_at_their_exact_edges(rh: float, level: str) -> None:
    assert _mould_level(rh, 65, 75, 50, 55) == level


@pytest.mark.parametrize("values", [(70, 70, 80, 90), (60, 80, 80, 90), (60, 70, 90, 90), (75, 70, 80, 90), (60, 70, 85, 80)])
def test_limits_that_do_not_rise_strictly_are_rejected(values) -> None:
    assert option_relationship_error(dict(zip(KEYS, values))) == "invalid_mould_order"


def test_strictly_rising_limits_and_older_settings_without_the_new_keys_are_accepted() -> None:
    assert option_relationship_error(dict(zip(KEYS, (50, 55, 65, 75)))) is None
    assert option_relationship_error({"mould_warn_surface_rh": 65, "mould_critical_surface_rh": 75}) is None   # older setup
    assert option_relationship_error({"mould_warn_surface_rh": 61, "mould_critical_surface_rh": 70}) is None


def test_an_older_setup_keeps_its_limits_and_only_the_new_ones_move_below() -> None:
    legacy = {**DEFAULT_OPTIONS, "mould_warn_surface_rh": 65.0, "mould_critical_surface_rh": 75.0}
    repaired = repair_option_relationships(legacy)
    assert (repaired["mould_warn_surface_rh"], repaired["mould_critical_surface_rh"]) == (65.0, 75.0)
    assert (repaired["mould_slight_surface_rh"], repaired["mould_elevated_surface_rh"]) == (60.0, 64.0)
    assert option_relationship_error(repaired) is None
    tight = repair_option_relationships({**DEFAULT_OPTIONS, "mould_warn_surface_rh": 60.0})
    assert (tight["mould_slight_surface_rh"], tight["mould_elevated_surface_rh"]) == (58.0, 59.0)
    assert option_relationship_error(tight) is None


def test_valid_and_untouched_settings_are_never_repaired() -> None:
    assert repair_option_relationships(dict(DEFAULT_OPTIONS)) == dict(DEFAULT_OPTIONS)
    own = {**DEFAULT_OPTIONS, **dict(zip(KEYS, (50.0, 55.0, 65.0, 75.0)))}
    assert repair_option_relationships(own) == own
    assert repair_option_relationships({"mould_warn_surface_rh": 65.0}) == {"mould_warn_surface_rh": 65.0}
