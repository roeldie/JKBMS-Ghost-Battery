import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import number
from esphome.const import UNIT_PERCENT

from .. import CONF_JKBMS_GHOST_BATTERY_ID, JkBmsGhostBattery, jkbms_ghost_battery_ns

DEPENDENCIES = ["jkbms_ghost_battery"]

ManualForceSocNumber = jkbms_ghost_battery_ns.class_(
    "ManualForceSocNumber", number.Number
)

CONF_MANUAL_FORCE_SOC = "manual_force_soc"

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_JKBMS_GHOST_BATTERY_ID): cv.use_id(JkBmsGhostBattery),
        # only takes effect once manual_override_armed is on. Step is 100 so the slider only
        # has two positions: 0 (force empty) and 100 (force full).
        cv.Optional(CONF_MANUAL_FORCE_SOC): number.number_schema(
            ManualForceSocNumber,
            unit_of_measurement=UNIT_PERCENT,
            icon="mdi:ghost",
        ),
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_JKBMS_GHOST_BATTERY_ID])

    if CONF_MANUAL_FORCE_SOC in config:
        conf = config[CONF_MANUAL_FORCE_SOC]
        var = await number.new_number(conf, min_value=0, max_value=100, step=100)
        cg.add(var.set_parent(parent))
