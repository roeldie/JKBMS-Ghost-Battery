import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import binary_sensor
from esphome.const import DEVICE_CLASS_PLUG, DEVICE_CLASS_PROBLEM, ENTITY_CATEGORY_DIAGNOSTIC

from .. import CONF_JKBMS_GHOST_BATTERY_ID, MAX_PACKS, JkBmsGhostBattery

DEPENDENCIES = ["jkbms_ghost_battery"]

# on = that pack hasn't sent a fresh status frame within pack_stale_timeout_seconds - grouped
# under Diagnostic since these are for troubleshooting, not everyday use
_STALE_KWARGS = dict(device_class=DEVICE_CLASS_PROBLEM, entity_category=ENTITY_CATEGORY_DIAGNOSTIC)
# on = the real pack's own MOS is currently allowing that direction of current - "plug" is the
# closest built-in device class for an on/off power path, so HA shows a plug icon rather than the
# alarm-style icon a "problem" class would imply (off here is a normal, expected state, not a fault)
_MOS_KWARGS = dict(device_class=DEVICE_CLASS_PLUG, entity_category=ENTITY_CATEGORY_DIAGNOSTIC)
# on = that pack is reporting at least one of its own alarm/protection bits, independent of
# whatever SoC the ghost is currently telling the inverter
_PROTECTION_KWARGS = dict(device_class=DEVICE_CLASS_PROBLEM, entity_category=ENTITY_CATEGORY_DIAGNOSTIC)

# (binary sensor "kind", setter name on the parent - takes a 0-based pack index, kwargs). One of
# these exists per configured pack - see PACK_BINARY_SENSOR_KEYS below.
PACK_BINARY_SENSORS = [
    ("data_stale", "set_pack_data_stale_sensor", _STALE_KWARGS),
    ("charge_mos", "set_pack_charge_mos_sensor", _MOS_KWARGS),
    ("discharge_mos", "set_pack_discharge_mos_sensor", _MOS_KWARGS),
    ("protection_active", "set_pack_protection_active_sensor", _PROTECTION_KWARGS),
]

# (config key, setter, 0-based pack index, kwargs) - eg. pack1_data_stale, pack2_data_stale, ...
# up to MAX_PACKS
PACK_BINARY_SENSOR_KEYS = [
    (f"pack{pack}_{kind}", setter, pack - 1, kwargs)
    for kind, setter, kwargs in PACK_BINARY_SENSORS
    for pack in range(1, MAX_PACKS + 1)
]

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_JKBMS_GHOST_BATTERY_ID): cv.use_id(JkBmsGhostBattery),
        **{
            cv.Optional(key): binary_sensor.binary_sensor_schema(**kwargs)
            for key, _setter, _index, kwargs in PACK_BINARY_SENSOR_KEYS
        },
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_JKBMS_GHOST_BATTERY_ID])

    for key, setter, index, _kwargs in PACK_BINARY_SENSOR_KEYS:
        if key in config:
            sens = await binary_sensor.new_binary_sensor(config[key])
            cg.add(getattr(parent, setter)(index, sens))
