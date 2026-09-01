import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import sensor
from esphome.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_DURATION,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    ENTITY_CATEGORY_DIAGNOSTIC,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    UNIT_AMPERE,
    UNIT_CELSIUS,
    UNIT_KILOWATT,
    UNIT_KILOWATT_HOURS,
    UNIT_PERCENT,
    UNIT_SECOND,
    UNIT_VOLT,
)

from .. import CONF_JKBMS_GHOST_BATTERY_ID, MAX_PACKS, JkBmsGhostBattery

DEPENDENCIES = ["jkbms_ghost_battery"]

# (sensor "kind", setter name on the parent - takes a 0-based pack index, sensor_schema kwargs).
# One of these exists per configured pack: kind "soc" becomes config keys pack1_soc..pack8_soc,
# each wired to set_pack_soc_sensor(index, sensor) on the parent - see PACK_SENSOR_KEYS below.
PACK_SENSORS = [
    ("min_cell_voltage", "set_pack_min_cell_voltage_sensor",
     dict(unit_of_measurement=UNIT_VOLT, accuracy_decimals=3, device_class=DEVICE_CLASS_VOLTAGE,
          state_class=STATE_CLASS_MEASUREMENT)),
    ("max_cell_voltage", "set_pack_max_cell_voltage_sensor",
     dict(unit_of_measurement=UNIT_VOLT, accuracy_decimals=3, device_class=DEVICE_CLASS_VOLTAGE,
          state_class=STATE_CLASS_MEASUREMENT)),
    # highest cell - lowest cell within a pack, ie. how far out of balance that pack currently is
    ("cell_voltage_diff", "set_pack_cell_voltage_diff_sensor",
     dict(unit_of_measurement=UNIT_VOLT, accuracy_decimals=3, device_class=DEVICE_CLASS_VOLTAGE,
          state_class=STATE_CLASS_MEASUREMENT, icon="mdi:delta")),
    ("voltage", "set_pack_voltage_sensor",
     dict(unit_of_measurement=UNIT_VOLT, accuracy_decimals=2, device_class=DEVICE_CLASS_VOLTAGE,
          state_class=STATE_CLASS_MEASUREMENT)),
    # positive = charging, negative = discharging (matches the JK protocol's own sign convention)
    ("current", "set_pack_current_sensor",
     dict(unit_of_measurement=UNIT_AMPERE, accuracy_decimals=2, device_class=DEVICE_CLASS_CURRENT,
          state_class=STATE_CLASS_MEASUREMENT)),
    # voltage * current for that pack, in kW
    ("power", "set_pack_power_sensor",
     dict(unit_of_measurement=UNIT_KILOWATT, accuracy_decimals=3, device_class=DEVICE_CLASS_POWER,
          state_class=STATE_CLASS_MEASUREMENT)),
    ("temperature", "set_pack_temperature_sensor",
     dict(unit_of_measurement=UNIT_CELSIUS, accuracy_decimals=1, device_class=DEVICE_CLASS_TEMPERATURE,
          state_class=STATE_CLASS_MEASUREMENT)),
    ("soc", "set_pack_soc_sensor",
     dict(unit_of_measurement=UNIT_PERCENT, accuracy_decimals=0, device_class=DEVICE_CLASS_BATTERY,
          state_class=STATE_CLASS_MEASUREMENT)),
    # read-only, passive only - only updates if something else on the bus queries that pack's own
    # settings frame (we never query for it ourselves)
    ("rcv_voltage", "set_pack_rcv_voltage_sensor",
     dict(unit_of_measurement=UNIT_VOLT, accuracy_decimals=3, device_class=DEVICE_CLASS_VOLTAGE,
          state_class=STATE_CLASS_MEASUREMENT, icon="mdi:battery-charging-high")),
    # state of health, straight from the pack's own status frame - a slow long-term decline is
    # normal aging, a sudden drop is worth investigating regardless of what the ghost is doing
    ("soh", "set_pack_soh_sensor",
     dict(unit_of_measurement=UNIT_PERCENT, accuracy_decimals=0, device_class=DEVICE_CLASS_BATTERY,
          state_class=STATE_CLASS_MEASUREMENT, icon="mdi:heart-pulse",
          entity_category=ENTITY_CATEGORY_DIAGNOSTIC)),
    # rising count = that pack has logged a fault since power-up - a steady value is reassuring
    ("fault_count", "set_pack_fault_count_sensor",
     dict(icon="mdi:alert-circle-outline", state_class=STATE_CLASS_TOTAL_INCREASING,
          entity_category=ENTITY_CATEGORY_DIAGNOSTIC)),
    # full-cycle-equivalent count and cell-balancing current - smaller, deferred extras from the
    # same offset table as the protection/health sensors above
    ("cycle_count", "set_pack_cycle_count_sensor",
     dict(icon="mdi:battery-sync-outline", state_class=STATE_CLASS_TOTAL_INCREASING,
          entity_category=ENTITY_CATEGORY_DIAGNOSTIC)),
    ("balance_current", "set_pack_balance_current_sensor",
     dict(unit_of_measurement=UNIT_AMPERE, accuracy_decimals=3, device_class=DEVICE_CLASS_CURRENT,
          state_class=STATE_CLASS_MEASUREMENT, icon="mdi:scale-balance",
          entity_category=ENTITY_CATEGORY_DIAGNOSTIC)),
]

# (config key, pack setter, 0-based pack index, kwargs) - one row per pack per PACK_SENSORS kind,
# eg. pack1_soc, pack2_soc, ... up to MAX_PACKS
PACK_SENSOR_KEYS = [
    (f"pack{pack}_{kind}", setter, pack - 1, kwargs)
    for kind, setter, kwargs in PACK_SENSORS
    for pack in range(1, MAX_PACKS + 1)
]

# sensors that exist once regardless of pack_count - combined/derived values, not per-pack
GLOBAL_SENSORS = [
    # what the ghost is actually telling the bus right now: 0 or 100 - the direct answer to
    # "what is the fake battery doing at this moment"
    ("ghost_fake_soc", "set_ghost_fake_soc_sensor",
     dict(unit_of_measurement=UNIT_PERCENT, accuracy_decimals=0, device_class=DEVICE_CLASS_BATTERY,
          state_class=STATE_CLASS_MEASUREMENT, icon="mdi:ghost")),
    # straight sums (not averages) of every configured pack - with one pack configured, just that
    # pack's own value
    ("total_power", "set_total_power_sensor",
     dict(unit_of_measurement=UNIT_KILOWATT, accuracy_decimals=3, device_class=DEVICE_CLASS_POWER,
          state_class=STATE_CLASS_MEASUREMENT, icon="mdi:lightning-bolt")),
    ("total_current", "set_total_current_sensor",
     dict(unit_of_measurement=UNIT_AMPERE, accuracy_decimals=2, device_class=DEVICE_CLASS_CURRENT,
          state_class=STATE_CLASS_MEASUREMENT, icon="mdi:lightning-bolt")),
    # highest cell minus lowest cell across ALL cells on ALL configured packs, not per-pack
    ("total_cell_voltage_diff", "set_total_cell_voltage_diff_sensor",
     dict(unit_of_measurement=UNIT_VOLT, accuracy_decimals=3, device_class=DEVICE_CLASS_VOLTAGE,
          state_class=STATE_CLASS_MEASUREMENT, icon="mdi:delta")),
    # average across every configured pack - only published once ALL of them have been seen at
    # least once
    ("average_soc", "set_average_soc_sensor",
     dict(unit_of_measurement=UNIT_PERCENT, accuracy_decimals=0, device_class=DEVICE_CLASS_BATTERY,
          state_class=STATE_CLASS_MEASUREMENT, icon="mdi:battery-charging-medium")),
    ("average_voltage", "set_average_voltage_sensor",
     dict(unit_of_measurement=UNIT_VOLT, accuracy_decimals=2, device_class=DEVICE_CLASS_VOLTAGE,
          state_class=STATE_CLASS_MEASUREMENT)),
    # counts CRC failures on frames that were otherwise structured like a query addressed to us -
    # a rising count points at RS485 wiring/termination/noise problems
    ("bus_error_count", "set_bus_error_count_sensor",
     dict(icon="mdi:alert-circle-outline", state_class=STATE_CLASS_TOTAL_INCREASING,
          entity_category=ENTITY_CATEGORY_DIAGNOSTIC)),
    # seconds left before hold_failsafe_minutes forces a release without confirmed balance - 0
    # while released, or while the failsafe is disabled
    ("hold_failsafe_remaining", "set_hold_failsafe_remaining_sensor",
     dict(unit_of_measurement=UNIT_SECOND, accuracy_decimals=0, device_class=DEVICE_CLASS_DURATION,
          state_class=STATE_CLASS_MEASUREMENT, icon="mdi:timer-sand",
          entity_category=ENTITY_CATEGORY_DIAGNOSTIC)),
    # running kWh totals for the Home Assistant Energy dashboard - energy into/out of the
    # battery. Reset to 0 on every reboot; HA's total_increasing state class treats a drop as a
    # normal meter reset.
    ("total_charge_energy", "set_total_charge_energy_sensor",
     dict(unit_of_measurement=UNIT_KILOWATT_HOURS, accuracy_decimals=3, device_class=DEVICE_CLASS_ENERGY,
          state_class=STATE_CLASS_TOTAL_INCREASING, icon="mdi:battery-arrow-up")),
    ("total_discharge_energy", "set_total_discharge_energy_sensor",
     dict(unit_of_measurement=UNIT_KILOWATT_HOURS, accuracy_decimals=3, device_class=DEVICE_CLASS_ENERGY,
          state_class=STATE_CLASS_TOTAL_INCREASING, icon="mdi:battery-arrow-down")),
]

# entity_category=diagnostic groups all of these into the device's collapsible "Diagnostic"
# section in Home Assistant, instead of cluttering the main sensor list
CELL_VOLTAGE_KWARGS = dict(unit_of_measurement=UNIT_VOLT, accuracy_decimals=3, device_class=DEVICE_CLASS_VOLTAGE,
                           state_class=STATE_CLASS_MEASUREMENT, entity_category=ENTITY_CATEGORY_DIAGNOSTIC)

# every individual cell, every pack - (config key, 0-based pack index, 0-based cell index)
CELL_SENSORS = [
    (f"pack{pack}_cell_{cell}", pack - 1, cell - 1)
    for pack in range(1, MAX_PACKS + 1)
    for cell in range(1, 17)
]

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_JKBMS_GHOST_BATTERY_ID): cv.use_id(JkBmsGhostBattery),
        **{
            cv.Optional(key): sensor.sensor_schema(**kwargs)
            for key, _setter, _index, kwargs in PACK_SENSOR_KEYS
        },
        **{
            cv.Optional(key): sensor.sensor_schema(**kwargs)
            for key, _setter, kwargs in GLOBAL_SENSORS
        },
        **{
            cv.Optional(key): sensor.sensor_schema(**CELL_VOLTAGE_KWARGS)
            for key, _pack, _index in CELL_SENSORS
        },
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_JKBMS_GHOST_BATTERY_ID])

    for key, setter, index, _kwargs in PACK_SENSOR_KEYS:
        if key in config:
            sens = await sensor.new_sensor(config[key])
            cg.add(getattr(parent, setter)(index, sens))

    for key, setter, _kwargs in GLOBAL_SENSORS:
        if key in config:
            sens = await sensor.new_sensor(config[key])
            cg.add(getattr(parent, setter)(sens))

    for key, pack_index, cell_index in CELL_SENSORS:
        if key in config:
            sens = await sensor.new_sensor(config[key])
            cg.add(parent.set_pack_cell_voltage_sensor(pack_index, cell_index, sens))
