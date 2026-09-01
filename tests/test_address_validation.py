"""Tests for the ghost/pack address collision validator.

This loads the actual _validate_unique_addresses() function straight out of
components/jkbms_ghost_battery/__init__.py, so these tests exercise the real shipped
validation logic rather than a re-implementation of it that could drift out of sync.
"""
import importlib.util
from pathlib import Path

import pytest
from esphome import config_validation as cv

COMPONENT_INIT = Path(__file__).parent.parent / "components" / "jkbms_ghost_battery" / "__init__.py"


def _load_component_module():
    spec = importlib.util.spec_from_file_location("jkbms_ghost_battery_init", COMPONENT_INIT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


component = _load_component_module()


def _config(ghost=15, pack_addresses=(0, 1)):
    return {
        component.CONF_GHOST_ADDRESS: ghost,
        component.CONF_PACK_ADDRESSES: list(pack_addresses),
    }


def test_default_addresses_are_accepted():
    config = _config()
    assert component._validate_unique_addresses(config) == config


def test_ghost_same_as_pack1_is_rejected():
    with pytest.raises(cv.Invalid):
        component._validate_unique_addresses(_config(ghost=0, pack_addresses=(0, 1)))


def test_ghost_same_as_pack2_is_rejected():
    with pytest.raises(cv.Invalid):
        component._validate_unique_addresses(_config(ghost=1, pack_addresses=(0, 1)))


def test_pack1_same_as_pack2_is_rejected():
    with pytest.raises(cv.Invalid):
        component._validate_unique_addresses(_config(pack_addresses=(5, 5)))


def test_single_pack_mode_is_accepted():
    # a single pack_addresses entry is a valid 1-pack config
    config = _config(ghost=15, pack_addresses=(0,))
    assert component._validate_unique_addresses(config) == config


def test_single_pack_mode_still_rejects_ghost_pack1_collision():
    with pytest.raises(cv.Invalid):
        component._validate_unique_addresses(_config(ghost=0, pack_addresses=(0,)))


def test_many_pack_addresses_all_unique_is_accepted():
    # this is the whole point of pack_addresses being a list rather than a fixed pack1/pack2 pair -
    # an arbitrary number of packs (up to MAX_PACKS), as long as every address is distinct
    config = _config(ghost=15, pack_addresses=(0, 1, 2, 3, 4, 5, 6, 7))
    assert component._validate_unique_addresses(config) == config


def test_collision_between_two_non_adjacent_packs_is_rejected():
    # the collision isn't always between "pack 1" and "pack 2" specifically - any two entries in
    # the list matching is a bus collision, wherever they are in the list
    with pytest.raises(cv.Invalid):
        component._validate_unique_addresses(_config(ghost=15, pack_addresses=(0, 1, 2, 1, 4)))
