import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import binary_sensor
from esphome.const import DEVICE_CLASS_PROBLEM, ENTITY_CATEGORY_DIAGNOSTIC

from .. import CONF_JKBMS_GHOST_BATTERY_ID, JkBmsGhostBattery

DEPENDENCIES = ["jkbms_ghost_battery"]

# (config key, setter name on the parent)
BINARY_SENSORS = [
    ("pack1_data_stale", "set_pack1_data_stale_sensor"),
    ("pack2_data_stale", "set_pack2_data_stale_sensor"),
]

# on = that pack hasn't sent a fresh status frame within pack_stale_timeout_seconds - grouped
# under Diagnostic since these are for troubleshooting, not everyday use
BINARY_SENSOR_KWARGS = dict(
    device_class=DEVICE_CLASS_PROBLEM, entity_category=ENTITY_CATEGORY_DIAGNOSTIC
)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_JKBMS_GHOST_BATTERY_ID): cv.use_id(JkBmsGhostBattery),
        **{
            cv.Optional(key): binary_sensor.binary_sensor_schema(**BINARY_SENSOR_KWARGS)
            for key, _setter in BINARY_SENSORS
        },
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_JKBMS_GHOST_BATTERY_ID])

    for key, setter in BINARY_SENSORS:
        if key in config:
            sens = await binary_sensor.new_binary_sensor(config[key])
            cg.add(getattr(parent, setter)(sens))
