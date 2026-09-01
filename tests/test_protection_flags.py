"""Tests for the new protection/health sensors added on top of the frame2 status packet.

decode_protection_flags() below is a deliberate 1:1 port of decode_protection_flags_() in
components/jkbms_ghost_battery/jkbms_ghost_battery.cpp, same pattern as test_hold_logic.py's
HoldStateMachine - C++ has no easy way to unit test on real hardware, so the bit-decoding logic is
mirrored here in plain Python. If decode_protection_flags_() changes, update this to match.

The offset/plausibility checks reuse the frozen FRAME2_RESPONSE capture template the same way
test_frame_templates.py does, so a change to the capture data or the offsets that breaks either
gets caught here too.
"""
import re
from pathlib import Path

CPP_PATH = Path(__file__).parent.parent / "components" / "jkbms_ghost_battery" / "jkbms_ghost_battery.cpp"
CPP_SOURCE = CPP_PATH.read_text()

# offsets, mirrored from jkbms_ghost_battery.cpp
ALARM_BITS_OFFSET = 166
SOH_OFFSET = 190
CHARGE_MOS_OFFSET = 198
DISCHARGE_MOS_OFFSET = 199
FAULT_COUNT_OFFSET = 266

NAMES = [
    "battery SCP", "MOS over-temp", "cell qty mismatch", "cell OVP", "cell UVP", "battery OVP",
    "battery UVP", "charge OCP", "discharge OCP", "charge over-temp", "aux CPU comm fault",
    "cell UVP (2nd)", "battery OVP (2nd)", "battery UVP (2nd)", "charge OCP (2nd)",
    "discharge OCP (2nd)", "charge low-temp", "discharge over-temp", "GPS disconnected",
    "password reminder", "discharge activate failure", "battery temp sensor anomaly",
    "temp sensor anomaly", "parallel module fault",
]


def decode_protection_flags(bits):
    if bits == 0:
        return "none"
    parts = []
    for bit in range(24):
        if bits & (1 << bit):
            parts.append(NAMES[bit])
    for bit in range(24, 32):
        if bits & (1 << bit):
            parts.append(f"other (bit {bit})")
    return ", ".join(parts)


def _load_template(name):
    match = re.search(name + r"\[JK_FRAME_SIZE\] = \{([^}]+)\}", CPP_SOURCE)
    assert match, f"couldn't find {name} in {CPP_PATH}"
    values = [int(x.strip(), 16) for x in match.group(1).split(",")]
    assert len(values) == 308, f"{name} should be exactly 308 bytes (JK_FRAME_SIZE), got {len(values)}"
    return values


def test_no_bits_set_reports_none():
    assert decode_protection_flags(0) == "none"


def test_single_known_bit_is_named():
    assert decode_protection_flags(1 << 3) == "cell OVP"  # bit 3
    assert decode_protection_flags(1 << 8) == "discharge OCP"  # bit 8


def test_multiple_bits_are_comma_joined_in_bit_order():
    bits = (1 << 8) | (1 << 3)  # discharge OCP (bit 8) + cell OVP (bit 3)
    assert decode_protection_flags(bits) == "cell OVP, discharge OCP"


def test_last_documented_bit_is_named():
    assert decode_protection_flags(1 << 23) == "parallel module fault"


def test_undocumented_high_bit_still_shows_up():
    # bits 24-31 aren't documented by the protocol reference, but an active one should still be
    # reported as *something* rather than silently dropped
    assert decode_protection_flags(1 << 27) == "other (bit 27)"


def test_known_and_undocumented_bits_together():
    bits = (1 << 0) | (1 << 30)
    assert decode_protection_flags(bits) == "battery SCP, other (bit 30)"


def test_frame2_alarm_bits_are_zero_on_the_healthy_idle_capture():
    # FRAME2_RESPONSE is a frozen snapshot from a real, healthy, idle pack - it shouldn't be
    # reporting any faults of its own
    buf = _load_template("FRAME2_RESPONSE")
    alarm_bits = (buf[ALARM_BITS_OFFSET] | (buf[ALARM_BITS_OFFSET + 1] << 8) |
                  (buf[ALARM_BITS_OFFSET + 2] << 16) | (buf[ALARM_BITS_OFFSET + 3] << 24))
    assert alarm_bits == 0
    assert decode_protection_flags(alarm_bits) == "none"


def test_frame2_soh_and_mos_states_are_plausible():
    # README/test_frame_templates.py: same "plausible, not tight" sanity-checking approach as the
    # existing current/temperature test - a healthy idle pack should read close to 100% SOH with
    # both MOSes on (nothing blocking charge or discharge)
    buf = _load_template("FRAME2_RESPONSE")
    assert 0 <= buf[SOH_OFFSET] <= 100
    assert buf[CHARGE_MOS_OFFSET] in (0, 1)
    assert buf[DISCHARGE_MOS_OFFSET] in (0, 1)
    assert buf[CHARGE_MOS_OFFSET] == 1
    assert buf[DISCHARGE_MOS_OFFSET] == 1
