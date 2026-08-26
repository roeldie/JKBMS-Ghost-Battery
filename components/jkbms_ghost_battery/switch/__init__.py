import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import switch

from .. import CONF_JKBMS_GHOST_BATTERY_ID, JkBmsGhostBattery, jkbms_ghost_battery_ns

DEPENDENCIES = ["jkbms_ghost_battery"]

ManualOverrideArmedSwitch = jkbms_ghost_battery_ns.class_(
    "ManualOverrideArmedSwitch", switch.Switch
)
ManualForceFullSwitch = jkbms_ghost_battery_ns.class_(
    "ManualForceFullSwitch", switch.Switch
)

CONF_MANUAL_OVERRIDE_ARMED = "manual_override_armed"
CONF_MANUAL_FORCE_FULL = "manual_force_full"

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_JKBMS_GHOST_BATTERY_ID): cv.use_id(JkBmsGhostBattery),
        # arm this first - while off, manual_force_full has no effect and the automatic
        # cell-balance logic keeps running normally
        cv.Optional(CONF_MANUAL_OVERRIDE_ARMED): switch.switch_schema(
            ManualOverrideArmedSwitch,
            icon="mdi:lock-open-alert-outline",
        ),
        # only takes effect once manual_override_armed is on: on = force 100%, off = force 0%
        cv.Optional(CONF_MANUAL_FORCE_FULL): switch.switch_schema(
            ManualForceFullSwitch,
            icon="mdi:battery-charging-100",
        ),
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_JKBMS_GHOST_BATTERY_ID])

    if CONF_MANUAL_OVERRIDE_ARMED in config:
        conf = config[CONF_MANUAL_OVERRIDE_ARMED]
        var = await switch.new_switch(conf)
        cg.add(var.set_parent(parent))

    if CONF_MANUAL_FORCE_FULL in config:
        conf = config[CONF_MANUAL_FORCE_FULL]
        var = await switch.new_switch(conf)
        cg.add(var.set_parent(parent))
