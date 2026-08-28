import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import switch

from .. import CONF_JKBMS_GHOST_BATTERY_ID, JkBmsGhostBattery, jkbms_ghost_battery_ns

DEPENDENCIES = ["jkbms_ghost_battery"]

ManualOverrideArmedSwitch = jkbms_ghost_battery_ns.class_(
    "ManualOverrideArmedSwitch", switch.Switch
)

CONF_MANUAL_OVERRIDE_ARMED = "manual_override_armed"

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_JKBMS_GHOST_BATTERY_ID): cv.use_id(JkBmsGhostBattery),
        # arm this first - while off, the "force SOC" number has no effect and the automatic
        # cell-balance logic keeps running normally
        cv.Optional(CONF_MANUAL_OVERRIDE_ARMED): switch.switch_schema(
            ManualOverrideArmedSwitch,
            icon="mdi:lock-open-alert-outline",
        ),
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_JKBMS_GHOST_BATTERY_ID])

    if CONF_MANUAL_OVERRIDE_ARMED in config:
        conf = config[CONF_MANUAL_OVERRIDE_ARMED]
        var = await switch.new_switch(conf)
        cg.add(var.set_parent(parent))
