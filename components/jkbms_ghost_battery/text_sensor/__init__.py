import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import text_sensor

from .. import CONF_JKBMS_GHOST_BATTERY_ID, JkBmsGhostBattery

DEPENDENCIES = ["jkbms_ghost_battery"]

CONF_HOLD_STATUS = "hold_status"

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_JKBMS_GHOST_BATTERY_ID): cv.use_id(JkBmsGhostBattery),
        # human-readable reason for the ghost's current hold/release decision - complements
        # ghost_fake_soc's raw "what" (0 or 100) with the "why"
        cv.Optional(CONF_HOLD_STATUS): text_sensor.text_sensor_schema(
            icon="mdi:message-text-outline"
        ),
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_JKBMS_GHOST_BATTERY_ID])

    if CONF_HOLD_STATUS in config:
        sens = await text_sensor.new_text_sensor(config[CONF_HOLD_STATUS])
        cg.add(parent.set_hold_status_text_sensor(sens))
