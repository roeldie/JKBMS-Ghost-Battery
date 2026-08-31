import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import text_sensor
from esphome.const import ENTITY_CATEGORY_DIAGNOSTIC

from .. import CONF_JKBMS_GHOST_BATTERY_ID, JkBmsGhostBattery

DEPENDENCIES = ["jkbms_ghost_battery"]

# (config key, setter name on the parent, text_sensor_schema kwargs)
TEXT_SENSORS = [
    # human-readable reason for the ghost's current hold/release decision - complements
    # ghost_fake_soc's raw "what" (0 or 100) with the "why"
    ("hold_status", "set_hold_status_text_sensor", dict(icon="mdi:message-text-outline")),
    # "none", or a comma-separated list of which of the real pack's own alarm/protection bits are
    # currently set - independent of whatever SoC the ghost is telling the inverter
    ("pack1_protection_flags", "set_pack1_protection_flags_text_sensor",
     dict(icon="mdi:shield-alert-outline", entity_category=ENTITY_CATEGORY_DIAGNOSTIC)),
    ("pack2_protection_flags", "set_pack2_protection_flags_text_sensor",
     dict(icon="mdi:shield-alert-outline", entity_category=ENTITY_CATEGORY_DIAGNOSTIC)),
]

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_JKBMS_GHOST_BATTERY_ID): cv.use_id(JkBmsGhostBattery),
        **{
            cv.Optional(key): text_sensor.text_sensor_schema(**kwargs)
            for key, _setter, kwargs in TEXT_SENSORS
        },
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_JKBMS_GHOST_BATTERY_ID])

    for key, setter, _kwargs in TEXT_SENSORS:
        if key in config:
            sens = await text_sensor.new_text_sensor(config[key])
            cg.add(getattr(parent, setter)(sens))
