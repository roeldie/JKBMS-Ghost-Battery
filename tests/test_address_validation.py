"""Tests for the ghost/pack1/pack2 address collision validator.

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


def _config(ghost=15, pack_count=2, pack1=0, pack2=1):
    return {
        component.CONF_GHOST_ADDRESS: ghost,
        component.CONF_PACK_COUNT: pack_count,
        component.CONF_PACK1_ADDRESS: pack1,
        component.CONF_PACK2_ADDRESS: pack2,
    }


def test_default_addresses_are_accepted():
    config = _config()
    assert component._validate_unique_addresses(config) == config


def test_ghost_same_as_pack1_is_rejected():
    with pytest.raises(cv.Invalid):
        component._validate_unique_addresses(_config(ghost=0, pack1=0))


def test_ghost_same_as_pack2_is_rejected():
    with pytest.raises(cv.Invalid):
        component._validate_unique_addresses(_config(ghost=1, pack2=1))


def test_pack1_same_as_pack2_is_rejected():
    with pytest.raises(cv.Invalid):
        component._validate_unique_addresses(_config(pack1=5, pack2=5))


def test_single_pack_mode_ignores_pack2_collision():
    # pack2_address is meaningless when pack_count == 1 (the component ignores it entirely),
    # so a "collision" against it must not be flagged
    config = _config(pack_count=1, ghost=1, pack2=1)
    assert component._validate_unique_addresses(config) == config


def test_single_pack_mode_still_rejects_ghost_pack1_collision():
    with pytest.raises(cv.Invalid):
        component._validate_unique_addresses(_config(pack_count=1, ghost=0, pack1=0))
