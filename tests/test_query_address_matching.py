"""Regression test for the address-0 broadcast bug in is_query_for_us_().

is_query_for_us_() in jkbms_ghost_battery.cpp used to treat a query addressed to 0x00 as also
being "for us" (the ghost), on top of matching ghost_address. That was leftover from this frame
handling's single-BMS Arduino origin, where the master BMS is the only device and its own address
doesn't matter. On this project's shared RS485 bus it was wrong: address 0 is the real master
pack's own address (pack1_address defaults to 0 - see README's "problem this solves"), so the
ghost was answering every single poll of the real master pack too, colliding with pack1's own
response on the bus.

is_matching_address() below is a 1:1 port of the (fixed) address check in is_query_for_us_() -
just the address comparison, not the surrounding length/header/CRC checks, which aren't address-0
specific and don't need a Python mirror of their own.
"""
import re
from pathlib import Path

CPP_PATH = Path(__file__).parent.parent / "components" / "jkbms_ghost_battery" / "jkbms_ghost_battery.cpp"
CPP_SOURCE = CPP_PATH.read_text()


def is_matching_address(destination_address, ghost_address):
    return destination_address == ghost_address


def test_default_pack1_address_is_not_treated_as_the_ghost():
    # pack1_address defaults to 0 - a query to address 0 must be left for the real pack1 to
    # answer, never the ghost
    assert is_matching_address(destination_address=0, ghost_address=15) is False


def test_query_to_ghost_address_matches():
    assert is_matching_address(destination_address=15, ghost_address=15) is True


def test_query_to_pack2_address_does_not_match():
    assert is_matching_address(destination_address=1, ghost_address=15) is False


def test_non_default_ghost_address_still_ignores_zero():
    # changing ghost_address away from the default must not resurrect the address-0 special case
    assert is_matching_address(destination_address=0, ghost_address=20) is False


def test_source_does_not_special_case_address_zero():
    # regression guard: the address check itself must be the single, precise comparison below -
    # not the old "or address == 0" fallback (see this test's module docstring for why that was
    # wrong). Matched on the actual source line rather than the surrounding function body, so
    # unrelated code elsewhere in is_query_for_us_() (eg. the CRC check) can't trip this up.
    match = re.search(r"bool JkBmsGhostBattery::is_query_for_us_\(\) \{(.*?)\n\}", CPP_SOURCE, re.S)
    assert match, "couldn't find is_query_for_us_() in jkbms_ghost_battery.cpp"
    body = match.group(1)
    assert "if (this->buf_[0] != this->ghost_address_) return false;" in body, (
        "is_query_for_us_()'s address check no longer matches the expected fixed form - if it "
        "was intentionally changed, update this test to match; if address 0 got special-cased "
        "again, see this test's module docstring for why that's wrong"
    )
