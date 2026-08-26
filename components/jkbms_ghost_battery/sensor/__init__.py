import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import sensor
from esphome.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_VOLTAGE,
    STATE_CLASS_MEASUREMENT,
    UNIT_PERCENT,
    UNIT_VOLT,
)

from .. import CONF_JKBMS_GHOST_BATTERY_ID, JkBmsGhostBattery

DEPENDENCIES = ["jkbms_ghost_battery"]

CONF_PACK1_MIN_CELL_VOLTAGE = "pack1_min_cell_voltage"
CONF_PACK1_MAX_CELL_VOLTAGE = "pack1_max_cell_voltage"
CONF_PACK2_MIN_CELL_VOLTAGE = "pack2_min_cell_voltage"
CONF_PACK2_MAX_CELL_VOLTAGE = "pack2_max_cell_voltage"
CONF_PACK1_SOC = "pack1_soc"
CONF_PACK2_SOC = "pack2_soc"
CONF_GHOST_FAKE_SOC = "ghost_fake_soc"

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_JKBMS_GHOST_BATTERY_ID): cv.use_id(JkBmsGhostBattery),
        cv.Optional(CONF_PACK1_MIN_CELL_VOLTAGE): sensor.sensor_schema(
            unit_of_measurement=UNIT_VOLT,
            accuracy_decimals=3,
            device_class=DEVICE_CLASS_VOLTAGE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        cv.Optional(CONF_PACK1_MAX_CELL_VOLTAGE): sensor.sensor_schema(
            unit_of_measurement=UNIT_VOLT,
            accuracy_decimals=3,
            device_class=DEVICE_CLASS_VOLTAGE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        cv.Optional(CONF_PACK2_MIN_CELL_VOLTAGE): sensor.sensor_schema(
            unit_of_measurement=UNIT_VOLT,
            accuracy_decimals=3,
            device_class=DEVICE_CLASS_VOLTAGE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        cv.Optional(CONF_PACK2_MAX_CELL_VOLTAGE): sensor.sensor_schema(
            unit_of_measurement=UNIT_VOLT,
            accuracy_decimals=3,
            device_class=DEVICE_CLASS_VOLTAGE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        cv.Optional(CONF_PACK1_SOC): sensor.sensor_schema(
            unit_of_measurement=UNIT_PERCENT,
            accuracy_decimals=0,
            device_class=DEVICE_CLASS_BATTERY,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        cv.Optional(CONF_PACK2_SOC): sensor.sensor_schema(
            unit_of_measurement=UNIT_PERCENT,
            accuracy_decimals=0,
            device_class=DEVICE_CLASS_BATTERY,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        # what the ghost is actually telling the bus right now: 0 or 100 - the direct answer to
        # "what is the fake battery doing at this moment"
        cv.Optional(CONF_GHOST_FAKE_SOC): sensor.sensor_schema(
            unit_of_measurement=UNIT_PERCENT,
            accuracy_decimals=0,
            device_class=DEVICE_CLASS_BATTERY,
            state_class=STATE_CLASS_MEASUREMENT,
            icon="mdi:ghost",
        ),
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_JKBMS_GHOST_BATTERY_ID])

    if CONF_PACK1_MIN_CELL_VOLTAGE in config:
        sens = await sensor.new_sensor(config[CONF_PACK1_MIN_CELL_VOLTAGE])
        cg.add(parent.set_pack1_min_cell_voltage_sensor(sens))
    if CONF_PACK1_MAX_CELL_VOLTAGE in config:
        sens = await sensor.new_sensor(config[CONF_PACK1_MAX_CELL_VOLTAGE])
        cg.add(parent.set_pack1_max_cell_voltage_sensor(sens))
    if CONF_PACK2_MIN_CELL_VOLTAGE in config:
        sens = await sensor.new_sensor(config[CONF_PACK2_MIN_CELL_VOLTAGE])
        cg.add(parent.set_pack2_min_cell_voltage_sensor(sens))
    if CONF_PACK2_MAX_CELL_VOLTAGE in config:
        sens = await sensor.new_sensor(config[CONF_PACK2_MAX_CELL_VOLTAGE])
        cg.add(parent.set_pack2_max_cell_voltage_sensor(sens))
    if CONF_PACK1_SOC in config:
        sens = await sensor.new_sensor(config[CONF_PACK1_SOC])
        cg.add(parent.set_pack1_soc_sensor(sens))
    if CONF_PACK2_SOC in config:
        sens = await sensor.new_sensor(config[CONF_PACK2_SOC])
        cg.add(parent.set_pack2_soc_sensor(sens))
    if CONF_GHOST_FAKE_SOC in config:
        sens = await sensor.new_sensor(config[CONF_GHOST_FAKE_SOC])
        cg.add(parent.set_ghost_fake_soc_sensor(sens))
