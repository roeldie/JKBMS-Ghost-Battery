import esphome.codegen as cg
import esphome.config_validation as cv
from esphome import pins
from esphome.components import uart
from esphome.const import CONF_ID

DEPENDENCIES = ["uart"]
CODEOWNERS = ["@roeldie"]

jkbms_ghost_battery_ns = cg.esphome_ns.namespace("jkbms_ghost_battery")
JkBmsGhostBattery = jkbms_ghost_battery_ns.class_(
    "JkBmsGhostBattery", cg.Component, uart.UARTDevice
)

CONF_JKBMS_GHOST_BATTERY_ID = "jkbms_ghost_battery_id"

CONF_DE_PIN = "de_pin"
CONF_GHOST_ADDRESS = "ghost_address"
CONF_PACK1_ADDRESS = "pack1_address"
CONF_PACK2_ADDRESS = "pack2_address"
CONF_CELL_FULL_LOW_MV = "cell_full_low_mv"
CONF_CELL_BALANCE_TOLERANCE_MV = "cell_balance_tolerance_mv"
CONF_RESET_SOC_PERCENT = "reset_soc_percent"
CONF_HOLD_FAILSAFE_MINUTES = "hold_failsafe_minutes"

CONFIG_SCHEMA = (
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(JkBmsGhostBattery),
            cv.Optional(CONF_DE_PIN): pins.gpio_output_pin_schema,
            cv.Optional(CONF_GHOST_ADDRESS, default=15): cv.int_range(min=1, max=247),
            cv.Optional(CONF_PACK1_ADDRESS, default=0): cv.int_range(min=0, max=247),
            cv.Optional(CONF_PACK2_ADDRESS, default=1): cv.int_range(min=0, max=247),
            # every cell on both packs must be at/above this voltage (mV)...
            cv.Optional(CONF_CELL_FULL_LOW_MV, default=3460): cv.int_range(min=2500, max=4200),
            # ...AND each pack's own highest-lowest cell spread must be within this many mV -
            # together these two conditions mean "full and balanced"
            cv.Optional(CONF_CELL_BALANCE_TOLERANCE_MV, default=20): cv.int_range(min=1, max=200),
            # once released to 100%, the ghost drops back to 0% as soon as pack1 or pack2's own
            # reported SoC falls to (or below) this percentage
            cv.Optional(CONF_RESET_SOC_PERCENT, default=99): cv.int_range(min=0, max=100),
            # safety backstop: release the hold after this many minutes even without confirmed
            # cell balance, so a wiring/address mistake can't cause indefinite overcharge.
            # set to 0 to disable.
            cv.Optional(CONF_HOLD_FAILSAFE_MINUTES, default=240): cv.int_range(min=0, max=1440),
        }
    )
    .extend(uart.UART_DEVICE_SCHEMA)
    .extend(cv.COMPONENT_SCHEMA)
)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    await uart.register_uart_device(var, config)

    if CONF_DE_PIN in config:
        de_pin = await cg.gpio_pin_expression(config[CONF_DE_PIN])
        cg.add(var.set_de_pin(de_pin))

    cg.add(var.set_ghost_address(config[CONF_GHOST_ADDRESS]))
    cg.add(var.set_pack1_address(config[CONF_PACK1_ADDRESS]))
    cg.add(var.set_pack2_address(config[CONF_PACK2_ADDRESS]))
    cg.add(var.set_cell_full_low_mv(config[CONF_CELL_FULL_LOW_MV]))
    cg.add(var.set_cell_balance_tolerance_mv(config[CONF_CELL_BALANCE_TOLERANCE_MV]))
    cg.add(var.set_reset_soc_percent(config[CONF_RESET_SOC_PERCENT]))
    cg.add(var.set_hold_failsafe_ms(config[CONF_HOLD_FAILSAFE_MINUTES] * 60000))
