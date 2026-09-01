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

# must match MAX_PACKS in jkbms_ghost_battery.cpp/.h - both sides are hardcoded compile/schema
# bounds rather than shared constants, since the C++ array sizes are fixed at compile time anyway
MAX_PACKS = 8

CONF_DE_PIN = "de_pin"
CONF_GHOST_ADDRESS = "ghost_address"
CONF_GHOST_CAPACITY_AH = "ghost_capacity_ah"
CONF_PACK_ADDRESSES = "pack_addresses"
CONF_CELL_FULL_LOW_MV = "cell_full_low_mv"
CONF_CELL_BALANCE_TOLERANCE_MV = "cell_balance_tolerance_mv"
CONF_CELL_FULL_MAX_TEMP_C = "cell_full_max_temp_c"
CONF_RESET_SOC_PERCENT = "reset_soc_percent"
CONF_HOLD_FAILSAFE_MINUTES = "hold_failsafe_minutes"
CONF_PACK_STALE_TIMEOUT_SECONDS = "pack_stale_timeout_seconds"


def _validate_unique_addresses(config):
    # (label, address) pairs - the ghost plus every configured real pack, in order. Every one of
    # these has to be a distinct RS485 address, or two devices will answer the same poll and
    # collide on the bus (this is exactly the bug fixed for address 0 - see is_query_for_us_()).
    addresses = [(CONF_GHOST_ADDRESS, config[CONF_GHOST_ADDRESS])]
    for i, address in enumerate(config[CONF_PACK_ADDRESSES]):
        addresses.append((f"{CONF_PACK_ADDRESSES}[{i}] (pack {i + 1})", address))

    seen = {}
    for key, address in addresses:
        if address in seen:
            raise cv.Invalid(
                f"'{key}' and '{seen[address]}' are both set to address {address} - the "
                "ghost and every real pack each need their own unique RS485 address, or two "
                "of them will collide on the bus"
            )
        seen[address] = key
    return config


CONFIG_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(JkBmsGhostBattery),
            cv.Optional(CONF_DE_PIN): pins.gpio_output_pin_schema,
            cv.Optional(CONF_GHOST_ADDRESS, default=15): cv.int_range(min=1, max=247),
            # nominal/remaining capacity the ghost reports once released - match your real bank's
            # actual capacity instead of the reference battery's own 36Ah
            cv.Optional(CONF_GHOST_CAPACITY_AH, default=36): cv.int_range(min=1, max=2000),
            # one RS485 address per real pack, in order - pack_addresses[0] is "pack 1" everywhere
            # else (entity names, dump_config, log messages), pack_addresses[1] is "pack 2", and so
            # on. How many packs you have is simply how many addresses you list here - up to
            # MAX_PACKS (8); the release/re-arm/averaging logic and every per-pack sensor all work
            # the same way regardless of how many that ends up being.
            cv.Optional(CONF_PACK_ADDRESSES, default=[0, 1]): cv.All(
                cv.ensure_list(cv.int_range(min=0, max=247)),
                cv.Length(
                    min=1,
                    max=MAX_PACKS,
                    msg=f"pack_addresses must list between 1 and {MAX_PACKS} real pack addresses",
                ),
            ),
            # every cell on every configured pack must be at/above this voltage (mV)...
            cv.Optional(CONF_CELL_FULL_LOW_MV, default=3460): cv.int_range(min=2500, max=4200),
            # ...AND each pack's own highest-lowest cell spread must be within this many mV -
            # together these two conditions mean "full and balanced"
            cv.Optional(CONF_CELL_BALANCE_TOLERANCE_MV, default=20): cv.int_range(min=1, max=200),
            # release is refused if any configured pack is hotter than this, even if
            # voltage/balance are otherwise fine. Set to 0 to disable this check.
            cv.Optional(CONF_CELL_FULL_MAX_TEMP_C, default=50): cv.int_range(min=0, max=100),
            # once released to 100%, the ghost drops back to 0% as soon as any configured pack's
            # own reported SoC falls to (or below) this percentage
            cv.Optional(CONF_RESET_SOC_PERCENT, default=99): cv.int_range(min=0, max=100),
            # safety backstop: release the hold after this many minutes even without confirmed
            # cell balance, so a wiring/address mistake can't cause indefinite overcharge.
            # set to 0 to disable.
            cv.Optional(CONF_HOLD_FAILSAFE_MINUTES, default=240): cv.int_range(min=0, max=1440),
            # if a configured pack hasn't sent a fresh status frame in this long, its cached
            # reading is no longer trusted: release is refused, and an already-released hold
            # re-arms as a precaution (wiring fault, BMS reset, pack physically disconnected).
            # Real packs are normally polled every few seconds, so this should stay well above
            # that under normal conditions.
            cv.Optional(CONF_PACK_STALE_TIMEOUT_SECONDS, default=30): cv.int_range(min=5, max=600),
        }
    )
    .extend(uart.UART_DEVICE_SCHEMA)
    .extend(cv.COMPONENT_SCHEMA),
    _validate_unique_addresses,
)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    await uart.register_uart_device(var, config)

    if CONF_DE_PIN in config:
        de_pin = await cg.gpio_pin_expression(config[CONF_DE_PIN])
        cg.add(var.set_de_pin(de_pin))

    cg.add(var.set_ghost_address(config[CONF_GHOST_ADDRESS]))
    cg.add(var.set_ghost_capacity_ah(config[CONF_GHOST_CAPACITY_AH]))
    pack_addresses = config[CONF_PACK_ADDRESSES]
    cg.add(var.set_pack_count(len(pack_addresses)))
    for i, address in enumerate(pack_addresses):
        cg.add(var.set_pack_address(i, address))
    cg.add(var.set_cell_full_low_mv(config[CONF_CELL_FULL_LOW_MV]))
    cg.add(var.set_cell_balance_tolerance_mv(config[CONF_CELL_BALANCE_TOLERANCE_MV]))
    cg.add(var.set_cell_full_max_temp_c(config[CONF_CELL_FULL_MAX_TEMP_C]))
    cg.add(var.set_reset_soc_percent(config[CONF_RESET_SOC_PERCENT]))
    cg.add(var.set_hold_failsafe_ms(config[CONF_HOLD_FAILSAFE_MINUTES] * 60000))
    cg.add(var.set_pack_stale_timeout_ms(config[CONF_PACK_STALE_TIMEOUT_SECONDS] * 1000))
