"""Sanity checks on the frozen FRAME1/2/3_RESPONSE capture templates in jkbms_ghost_battery.cpp.

These parse the actual committed byte arrays (via a small regex, not a hand-copied duplicate)
and cross-check them against the byte-offset table documented in the README's "Protocol notes"
section, so a change to either the capture data or the documented offsets that breaks the other
gets caught here instead of on real hardware.
"""
import re
from pathlib import Path

CPP_PATH = Path(__file__).parent.parent / "components" / "jkbms_ghost_battery" / "jkbms_ghost_battery.cpp"
CPP_SOURCE = CPP_PATH.read_text()

# byte offsets, mirrored from jkbms_ghost_battery.cpp / README.md "Protocol notes"
SOC_OFFSET = 173
CHECKSUM_OFFSET = 299
SOURCE_ADDRESS_OFFSET = 300
CELL_VOLTAGE_OFFSET = 6
CELL_COUNT = 16
TOTAL_VOLTAGE_OFFSET = 150
CURRENT_OFFSET = 158
TEMPERATURE_OFFSET = 162
DEFAULT_GHOST_ADDRESS = 15  # matches CONF_GHOST_ADDRESS's default in components/jkbms_ghost_battery/__init__.py


def _load_template(name):
    match = re.search(name + r"\[JK_FRAME_SIZE\] = \{([^}]+)\}", CPP_SOURCE)
    assert match, f"couldn't find {name} in {CPP_PATH}"
    values = [int(x.strip(), 16) for x in match.group(1).split(",")]
    assert len(values) == 308, f"{name} should be exactly 308 bytes (JK_FRAME_SIZE), got {len(values)}"
    return values


def _u16le(buf, offset):
    return buf[offset] | (buf[offset + 1] << 8)


def _u32le(buf, offset):
    return buf[offset] | (buf[offset + 1] << 8) | (buf[offset + 2] << 16) | (buf[offset + 3] << 24)


def test_templates_are_present_and_full_size():
    for name in ("FRAME1_RESPONSE", "FRAME2_RESPONSE", "FRAME3_RESPONSE"):
        _load_template(name)  # raises/asserts internally if missing or wrong size


def test_checksum_byte_is_sum_of_preceding_bytes_mod_256():
    # documented in README as "sum of bytes 0-298 mod 256" - this is what send_frame2_()
    # recomputes at runtime after patching SoC/capacity/temperature, so the *unpatched*
    # template must already satisfy it too, or a real (non-ghost) capture was recorded wrong
    for name in ("FRAME1_RESPONSE", "FRAME2_RESPONSE", "FRAME3_RESPONSE"):
        buf = _load_template(name)
        assert buf[CHECKSUM_OFFSET] == sum(buf[:CHECKSUM_OFFSET]) % 256, name


def test_source_address_byte_matches_default_ghost_address():
    # the templates were captured from a real battery at address 0x0F (15), which is also this
    # component's default ghost_address - send_frame1_/2_/3_() now patch this byte to whatever
    # ghost_address is actually configured, but the raw template itself should still read 15
    for name in ("FRAME1_RESPONSE", "FRAME2_RESPONSE", "FRAME3_RESPONSE"):
        buf = _load_template(name)
        assert buf[SOURCE_ADDRESS_OFFSET] == DEFAULT_GHOST_ADDRESS, name


def test_frame2_cell_voltages_sum_matches_total_voltage_within_1mv():
    # README: "The total-pack-voltage field was cross-checked by summing the 16 individual cell
    # voltages - they matched to within 1mV on the reference capture"
    buf = _load_template("FRAME2_RESPONSE")
    cells = [_u16le(buf, CELL_VOLTAGE_OFFSET + cell * 2) for cell in range(CELL_COUNT)]
    total_voltage_mv = _u32le(buf, TOTAL_VOLTAGE_OFFSET)
    assert abs(sum(cells) - total_voltage_mv) <= 1


def test_frame2_current_and_temperature_are_plausible():
    # README: "CURRENT_OFFSET/TEMPERATURE_OFFSET read plausible values (0.00A idle, ~27C)"
    buf = _load_template("FRAME2_RESPONSE")
    current_ma = _u32le(buf, CURRENT_OFFSET)
    if current_ma >= 2**31:
        current_ma -= 2**32
    temperature_c10 = _u16le(buf, TEMPERATURE_OFFSET)
    if temperature_c10 >= 2**15:
        temperature_c10 -= 2**16

    assert current_ma == 0
    assert 20 * 10 <= temperature_c10 <= 35 * 10  # sanity range, not a tight assertion
