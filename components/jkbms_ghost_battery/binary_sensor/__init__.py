import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import binary_sensor
from esphome.const import DEVICE_CLASS_PLUG, DEVICE_CLASS_PROBLEM, ENTITY_CATEGORY_DIAGNOSTIC

from .. import CONF_JKBMS_GHOST_BATTERY_ID, JkBmsGhostBattery

DEPENDENCIES = ["jkbms_ghost_battery"]

# on = that pack hasn't sent a fresh status frame within pack_stale_timeout_seconds - grouped
# under Diagnostic since these are for troubleshooting, not everyday use
_STALE_KWARGS = dict(device_class=DEVICE_CLASS_PROBLEM, entity_category=ENTITY_CATEGORY_DIAGNOSTIC)
# on = the real pack's own MOS is currently allowing that direction of current - "plug" is the
# closest built-in device class for an on/off power path, so HA shows a plug icon rather than the
# alarm-style icon a "problem" class would imply (off here is a normal, expected state, not a fault)
_MOS_KWARGS = dict(device_class=DEVICE_CLASS_PLUG, entity_category=ENTITY_CATEGORY_DIAGNOSTIC)
# on = the real pack is reporting at least one of its own alarm/protection bits, independent of
# whatever SoC the ghost is currently telling the inverter
_PROTECTION_KWARGS = dict(device_class=DEVICE_CLASS_PROBLEM, entity_category=ENTITY_CATEGORY_DIAGNOSTIC)

# (config key, setter name on the parent, binary_sensor_schema kwargs)
BINARY_SENSORS = [
    ("pack1_data_stale", "set_pack1_data_stale_sensor", _STALE_KWARGS),
    ("pack2_data_stale", "set_pack2_data_stale_sensor", _STALE_KWARGS),
    ("pack1_charge_mos", "set_pack1_charge_mos_sensor", _MOS_KWARGS),
    ("pack2_charge_mos", "set_pack2_charge_mos_sensor", _MOS_KWARGS),
    ("pack1_discharge_mos", "set_pack1_discharge_mos_sensor", _MOS_KWARGS),
    ("pack2_discharge_mos", "set_pack2_discharge_mos_sensor", _MOS_KWARGS),
    ("pack1_protection_active", "set_pack1_protection_active_sensor", _PROTECTION_KWARGS),
    ("pack2_protection_active", "set_pack2_protection_active_sensor", _PROTECTION_KWARGS),
]

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_JKBMS_GHOST_BATTERY_ID): cv.use_id(JkBmsGhostBattery),
        **{
            cv.Optional(key): binary_sensor.binary_sensor_schema(**kwargs)
            for key, _setter, kwargs in BINARY_SENSORS
        },
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_JKBMS_GHOST_BATTERY_ID])

    for key, setter, _kwargs in BINARY_SENSORS:
        if key in config:
            sens = await binary_sensor.new_binary_sensor(config[key])
            cg.add(getattr(parent, setter)(sens))
