import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import text_sensor
from esphome.const import ENTITY_CATEGORY_DIAGNOSTIC

from .. import CONF_JKBMS_GHOST_BATTERY_ID, MAX_PACKS, JkBmsGhostBattery

DEPENDENCIES = ["jkbms_ghost_battery"]

# "none", or a comma-separated list of which of that pack's own alarm/protection bits are
# currently set - independent of whatever SoC the ghost is telling the inverter. One of these
# exists per configured pack: pack1_protection_flags, pack2_protection_flags, ... up to MAX_PACKS
PACK_TEXT_SENSOR_KEYS = [
    (f"pack{pack}_protection_flags", "set_pack_protection_flags_text_sensor", pack - 1)
    for pack in range(1, MAX_PACKS + 1)
]

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_JKBMS_GHOST_BATTERY_ID): cv.use_id(JkBmsGhostBattery),
        # human-readable reason for the ghost's current hold/release decision - complements
        # ghost_fake_soc's raw "what" (0 or 100) with the "why". Exists once, not per-pack.
        cv.Optional("hold_status"): text_sensor.text_sensor_schema(icon="mdi:message-text-outline"),
        **{
            cv.Optional(key): text_sensor.text_sensor_schema(
                icon="mdi:shield-alert-outline", entity_category=ENTITY_CATEGORY_DIAGNOSTIC
            )
            for key, _setter, _index in PACK_TEXT_SENSOR_KEYS
        },
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_JKBMS_GHOST_BATTERY_ID])

    if "hold_status" in config:
        sens = await text_sensor.new_text_sensor(config["hold_status"])
        cg.add(parent.set_hold_status_text_sensor(sens))

    for key, setter, index in PACK_TEXT_SENSOR_KEYS:
        if key in config:
            sens = await text_sensor.new_text_sensor(config[key])
            cg.add(getattr(parent, setter)(index, sens))
