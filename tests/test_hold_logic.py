"""Tests for the ghost's hold/release/re-arm state machine.

C++ has no easy way to unit test on real hardware, so this is a deliberate 1:1 port of
evaluate_hold_() in components/jkbms_ghost_battery/jkbms_ghost_battery.cpp to plain Python,
parameterised on a fake clock instead of millis(). If evaluate_hold_() changes, update
HoldStateMachine.evaluate() to match - the two are meant to stay in lockstep.

Pack indices are 0-based everywhere here, same as the C++ (pack_addresses_[0]/pack_seen_[0]/... -
"pack 1" in YAML/entity names is index 0). pack_count ranges from 1 up to MAX_PACKS (8 - see
jkbms_ghost_battery.h) in the real component; these tests exercise 1, 2 and 3-pack configurations
since the loop-based logic doesn't behave differently at higher counts, plus one test at the
MAX_PACKS boundary to catch an off-by-one in array sizing.
"""
from dataclasses import dataclass, field
from typing import List

MAX_PACKS = 8  # mirrors MAX_PACKS in jkbms_ghost_battery.h


@dataclass
class HoldStateMachine:
    pack_count: int = 2
    cell_full_low_mv: int = 3460
    cell_balance_tolerance_mv: int = 20
    # 0 disables the check - matches the component's own default (50 C)
    cell_full_max_temp_c: int = 50
    reset_soc_percent: int = 99
    hold_failsafe_ms: int = 240 * 60000
    pack_stale_timeout_ms: int = 30000

    holding: bool = True
    hold_start_time: int = 0

    pack_seen: List[bool] = field(default_factory=list)
    pack_last_update_ms: List[int] = field(default_factory=list)
    pack_min_mv: List[int] = field(default_factory=list)
    pack_max_mv: List[int] = field(default_factory=list)
    pack_soc: List[int] = field(default_factory=list)
    pack_temperature_c10: List[int] = field(default_factory=list)
    # defaults to True per pack so existing callers that don't care about MOS state keep passing
    # unchanged - matches the component's own pack_charge_mos_on_ default
    pack_charge_mos_on: List[bool] = field(default_factory=list)

    def __post_init__(self):
        for lst, default in (
            (self.pack_seen, False),
            (self.pack_last_update_ms, 0),
            (self.pack_min_mv, 0),
            (self.pack_max_mv, 0),
            (self.pack_soc, 0),
            (self.pack_temperature_c10, 0),
            (self.pack_charge_mos_on, True),
        ):
            if not lst:
                lst.extend([default] * self.pack_count)

    # temp_c10/charge_mos_on default to "nothing wrong" (cool, charging allowed) so existing
    # callers that don't care about them keep passing without changes
    def see_pack(self, index, now, min_mv, max_mv, soc, temp_c10=250, charge_mos_on=True):
        self.pack_seen[index] = True
        self.pack_last_update_ms[index] = now
        self.pack_min_mv[index] = min_mv
        self.pack_max_mv[index] = max_mv
        self.pack_soc[index] = soc
        self.pack_temperature_c10[index] = temp_c10
        self.pack_charge_mos_on[index] = charge_mos_on
        self.evaluate(now)

    def evaluate(self, now):
        fresh = [
            self.pack_seen[i] and (now - self.pack_last_update_ms[i]) < self.pack_stale_timeout_ms
            for i in range(self.pack_count)
        ]

        if self.holding:
            all_ok = True
            all_charge_mos_off = True
            for i in range(self.pack_count):
                temp_ok = (
                    self.cell_full_max_temp_c == 0 or self.pack_temperature_c10[i] <= self.cell_full_max_temp_c * 10
                )
                pack_ok = (
                    fresh[i]
                    and temp_ok
                    and self.pack_min_mv[i] >= self.cell_full_low_mv
                    and (self.pack_max_mv[i] - self.pack_min_mv[i]) <= self.cell_balance_tolerance_mv
                )
                if not pack_ok:
                    all_ok = False

                # only if EVERY configured pack's own charge MOS is off can none of them accept
                # more current - one pack finishing early must not force an array-wide release
                # while the others are still mid-charge and need the time to actually balance
                charge_mos_off = fresh[i] and not self.pack_charge_mos_on[i]
                if not charge_mos_off:
                    all_charge_mos_off = False

            if all_ok:
                self.holding = False
            elif all_charge_mos_off:
                self.holding = False
            elif self.hold_failsafe_ms > 0 and (now - self.hold_start_time) >= self.hold_failsafe_ms:
                self.holding = False
        else:
            any_pack_low = any(
                self.pack_seen[i] and self.pack_soc[i] <= self.reset_soc_percent for i in range(self.pack_count)
            )
            went_stale = any(not fresh[i] for i in range(self.pack_count))
            if any_pack_low or went_stale:
                self.holding = True
                self.hold_start_time = now


FULL_MIN_MV = 3465  # >= cell_full_low_mv default (3460)
FULL_MAX_MV = 3470  # spread of 5mV, within cell_balance_tolerance_mv default (20)


def test_starts_holding():
    assert HoldStateMachine().holding is True


def test_single_pack_releases_once_full_and_balanced():
    sm = HoldStateMachine(pack_count=1)
    sm.see_pack(0, now=1000, min_mv=FULL_MIN_MV, max_mv=FULL_MAX_MV, soc=100)
    assert sm.holding is False


def test_two_pack_requires_both_packs_full_and_balanced():
    sm = HoldStateMachine(pack_count=2)
    sm.see_pack(0, now=1000, min_mv=FULL_MIN_MV, max_mv=FULL_MAX_MV, soc=100)
    assert sm.holding is True, "must not release on pack 1 alone in 2-pack mode"
    sm.see_pack(1, now=1000, min_mv=FULL_MIN_MV, max_mv=FULL_MAX_MV, soc=100)
    assert sm.holding is False


def test_three_pack_requires_every_pack_full_and_balanced():
    sm = HoldStateMachine(pack_count=3)
    sm.see_pack(0, now=1000, min_mv=FULL_MIN_MV, max_mv=FULL_MAX_MV, soc=100)
    sm.see_pack(1, now=1000, min_mv=FULL_MIN_MV, max_mv=FULL_MAX_MV, soc=100)
    assert sm.holding is True, "must not release with pack 3 still unaccounted for"
    sm.see_pack(2, now=1000, min_mv=FULL_MIN_MV, max_mv=FULL_MAX_MV, soc=100)
    assert sm.holding is False


def test_out_of_balance_pack_blocks_release():
    sm = HoldStateMachine(pack_count=1)
    # 30mV spread > cell_balance_tolerance_mv default (20)
    sm.see_pack(0, now=1000, min_mv=3465, max_mv=3495, soc=100)
    assert sm.holding is True


def test_failsafe_releases_without_confirmed_balance():
    sm = HoldStateMachine(pack_count=1, hold_failsafe_ms=240 * 60000)
    # not full/balanced, but keeps reporting in so it isn't stale
    sm.see_pack(0, now=0, min_mv=3000, max_mv=3000, soc=50)
    sm.see_pack(0, now=240 * 60000, min_mv=3000, max_mv=3000, soc=50)
    assert sm.holding is False


def test_failsafe_disabled_when_zero():
    sm = HoldStateMachine(pack_count=1, hold_failsafe_ms=0)
    sm.see_pack(0, now=0, min_mv=3000, max_mv=3000, soc=50)
    sm.see_pack(0, now=10**9, min_mv=3000, max_mv=3000, soc=50)
    assert sm.holding is True


def test_rearms_when_soc_drops_to_reset_threshold():
    sm = HoldStateMachine(pack_count=1, reset_soc_percent=99)
    sm.see_pack(0, now=1000, min_mv=FULL_MIN_MV, max_mv=FULL_MAX_MV, soc=100)
    assert sm.holding is False
    sm.see_pack(0, now=2000, min_mv=FULL_MIN_MV, max_mv=FULL_MAX_MV, soc=99)
    assert sm.holding is True


def test_rearms_when_pack_goes_stale_after_release():
    sm = HoldStateMachine(pack_count=1, pack_stale_timeout_ms=30000)
    sm.see_pack(0, now=0, min_mv=FULL_MIN_MV, max_mv=FULL_MAX_MV, soc=100)
    assert sm.holding is False
    # no further updates from the pack - re-evaluate well past the staleness window
    sm.evaluate(now=30001)
    assert sm.holding is True


def test_does_not_rearm_before_stale_timeout_elapses():
    sm = HoldStateMachine(pack_count=1, pack_stale_timeout_ms=30000)
    sm.see_pack(0, now=0, min_mv=FULL_MIN_MV, max_mv=FULL_MAX_MV, soc=100)
    assert sm.holding is False
    sm.evaluate(now=29999)
    assert sm.holding is False


def test_release_refuses_stale_pack_even_if_last_reading_was_full():
    # pack reported full/balanced a long time ago and has gone silent since - a fresh
    # evaluate_hold_() tick (eg. from loop()) must not release on that stale reading
    sm = HoldStateMachine(pack_count=1, pack_stale_timeout_ms=30000)
    sm.pack_seen[0] = True
    sm.pack_last_update_ms[0] = 0
    sm.pack_min_mv[0] = FULL_MIN_MV
    sm.pack_max_mv[0] = FULL_MAX_MV
    sm.pack_soc[0] = 100
    sm.evaluate(now=30001)
    assert sm.holding is True


def test_hot_pack_blocks_release():
    sm = HoldStateMachine(pack_count=1, cell_full_max_temp_c=50)
    # full and balanced, but 55.0 C is over the 50 C limit
    sm.see_pack(0, now=1000, min_mv=FULL_MIN_MV, max_mv=FULL_MAX_MV, soc=100, temp_c10=550)
    assert sm.holding is True


def test_pack_cools_down_then_releases():
    sm = HoldStateMachine(pack_count=1, cell_full_max_temp_c=50)
    sm.see_pack(0, now=1000, min_mv=FULL_MIN_MV, max_mv=FULL_MAX_MV, soc=100, temp_c10=550)
    assert sm.holding is True, "still too hot"
    sm.see_pack(0, now=2000, min_mv=FULL_MIN_MV, max_mv=FULL_MAX_MV, soc=100, temp_c10=450)
    assert sm.holding is False, "45.0 C is at/under the 50 C limit"


def test_temp_check_disabled_when_zero():
    sm = HoldStateMachine(pack_count=1, cell_full_max_temp_c=0)
    # would block release above with the check enabled (see test_hot_pack_blocks_release)
    sm.see_pack(0, now=1000, min_mv=FULL_MIN_MV, max_mv=FULL_MAX_MV, soc=100, temp_c10=550)
    assert sm.holding is False


def test_charge_mos_off_forces_release_even_when_not_full_or_balanced():
    sm = HoldStateMachine(pack_count=1)
    # nowhere near full/balanced, but the real pack has cut off charging itself - holding
    # serves no purpose since no current can flow regardless of what the ghost reports
    sm.see_pack(0, now=1000, min_mv=3000, max_mv=3000, soc=50, charge_mos_on=False)
    assert sm.holding is False


def test_charge_mos_on_does_not_release_by_itself():
    sm = HoldStateMachine(pack_count=1)
    # charge_mos_on=True (the default) alongside an out-of-balance pack must NOT release -
    # only an actual MOS cutoff (or full+balanced, or the failsafe) does
    sm.see_pack(0, now=1000, min_mv=3000, max_mv=3000, soc=50, charge_mos_on=True)
    assert sm.holding is True


def test_two_pack_mode_one_pack_charge_mos_off_does_not_release():
    # one pack finishing (its own BMS cuts charging) while the other is still mid-charge must NOT
    # force an array-wide release - the other pack still needs the time at voltage to balance
    sm = HoldStateMachine(pack_count=2)
    sm.see_pack(0, now=1000, min_mv=3000, max_mv=3000, soc=50, charge_mos_on=True)
    sm.see_pack(1, now=1000, min_mv=3000, max_mv=3000, soc=50, charge_mos_on=False)
    assert sm.holding is True


def test_two_pack_mode_both_packs_charge_mos_off_forces_release():
    sm = HoldStateMachine(pack_count=2)
    sm.see_pack(0, now=1000, min_mv=3000, max_mv=3000, soc=50, charge_mos_on=False)
    assert sm.holding is True, "pack 2 hasn't reported its MOS state as off yet"
    sm.see_pack(1, now=1000, min_mv=3000, max_mv=3000, soc=50, charge_mos_on=False)
    assert sm.holding is False


def test_three_pack_mode_all_but_one_charge_mos_off_does_not_release():
    # generalization check: with more than 2 packs, EVERY one of them needs its charge MOS off -
    # a single pack still mid-charge is enough to keep holding, no matter how many others are done
    sm = HoldStateMachine(pack_count=3)
    sm.see_pack(0, now=1000, min_mv=3000, max_mv=3000, soc=50, charge_mos_on=False)
    sm.see_pack(1, now=1000, min_mv=3000, max_mv=3000, soc=50, charge_mos_on=False)
    sm.see_pack(2, now=1000, min_mv=3000, max_mv=3000, soc=50, charge_mos_on=True)
    assert sm.holding is True


def test_three_pack_mode_all_packs_charge_mos_off_forces_release():
    sm = HoldStateMachine(pack_count=3)
    sm.see_pack(0, now=1000, min_mv=3000, max_mv=3000, soc=50, charge_mos_on=False)
    sm.see_pack(1, now=1000, min_mv=3000, max_mv=3000, soc=50, charge_mos_on=False)
    assert sm.holding is True, "pack 3 hasn't reported its MOS state as off yet"
    sm.see_pack(2, now=1000, min_mv=3000, max_mv=3000, soc=50, charge_mos_on=False)
    assert sm.holding is False


def test_charge_mos_off_on_stale_pack_does_not_force_release():
    # a pack that's gone stale is never trusted for anything, including its last-known MOS state -
    # otherwise a disconnected/reset pack's final cached reading could force a release forever
    sm = HoldStateMachine(pack_count=1, pack_stale_timeout_ms=30000)
    sm.pack_seen[0] = True
    sm.pack_last_update_ms[0] = 0
    sm.pack_min_mv[0] = 3000
    sm.pack_max_mv[0] = 3000
    sm.pack_soc[0] = 50
    sm.pack_charge_mos_on[0] = False
    sm.evaluate(now=30001)
    assert sm.holding is True


def test_max_packs_boundary_all_full_and_balanced_releases():
    # exercise the full MAX_PACKS (8) count to catch an off-by-one in array sizing - every pack
    # must still be accounted for before release, same as the 2 and 3-pack cases above
    sm = HoldStateMachine(pack_count=MAX_PACKS)
    for i in range(MAX_PACKS - 1):
        sm.see_pack(i, now=1000, min_mv=FULL_MIN_MV, max_mv=FULL_MAX_MV, soc=100)
    assert sm.holding is True, "must not release with the last pack still unaccounted for"
    sm.see_pack(MAX_PACKS - 1, now=1000, min_mv=FULL_MIN_MV, max_mv=FULL_MAX_MV, soc=100)
    assert sm.holding is False
