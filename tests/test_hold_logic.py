"""Tests for the ghost's hold/release/re-arm state machine.

C++ has no easy way to unit test on real hardware, so this is a deliberate 1:1 port of
evaluate_hold_() in components/jkbms_ghost_battery/jkbms_ghost_battery.cpp to plain Python,
parameterised on a fake clock instead of millis(). If evaluate_hold_() changes, update
HoldStateMachine.evaluate() to match - the two are meant to stay in lockstep.
"""
from dataclasses import dataclass


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

    pack1_seen: bool = False
    pack2_seen: bool = False
    pack1_last_update_ms: int = 0
    pack2_last_update_ms: int = 0
    pack1_min_mv: int = 0
    pack1_max_mv: int = 0
    pack2_min_mv: int = 0
    pack2_max_mv: int = 0
    pack1_soc: int = 0
    pack2_soc: int = 0
    pack1_temperature_c10: int = 0
    pack2_temperature_c10: int = 0
    # default True so existing callers that don't care about MOS state keep passing unchanged -
    # matches the component's own pack1_charge_mos_on_/pack2_charge_mos_on_ defaults
    pack1_charge_mos_on: bool = True
    pack2_charge_mos_on: bool = True

    # temp_c10/charge_mos_on default to "nothing wrong" (cool, charging allowed) so existing
    # callers that don't care about them keep passing without changes
    def see_pack1(self, now, min_mv, max_mv, soc, temp_c10=250, charge_mos_on=True):
        self.pack1_seen = True
        self.pack1_last_update_ms = now
        self.pack1_min_mv = min_mv
        self.pack1_max_mv = max_mv
        self.pack1_soc = soc
        self.pack1_temperature_c10 = temp_c10
        self.pack1_charge_mos_on = charge_mos_on
        self.evaluate(now)

    def see_pack2(self, now, min_mv, max_mv, soc, temp_c10=250, charge_mos_on=True):
        self.pack2_seen = True
        self.pack2_last_update_ms = now
        self.pack2_min_mv = min_mv
        self.pack2_max_mv = max_mv
        self.pack2_soc = soc
        self.pack2_temperature_c10 = temp_c10
        self.pack2_charge_mos_on = charge_mos_on
        self.evaluate(now)

    def evaluate(self, now):
        pack1_fresh = self.pack1_seen and (now - self.pack1_last_update_ms) < self.pack_stale_timeout_ms
        pack2_fresh = self.pack_count < 2 or (
            self.pack2_seen and (now - self.pack2_last_update_ms) < self.pack_stale_timeout_ms
        )

        if self.holding:
            pack1_temp_ok = (
                self.cell_full_max_temp_c == 0 or self.pack1_temperature_c10 <= self.cell_full_max_temp_c * 10
            )
            pack2_temp_ok = (
                self.cell_full_max_temp_c == 0 or self.pack2_temperature_c10 <= self.cell_full_max_temp_c * 10
            )
            pack1_ok = (
                pack1_fresh
                and pack1_temp_ok
                and self.pack1_min_mv >= self.cell_full_low_mv
                and (self.pack1_max_mv - self.pack1_min_mv) <= self.cell_balance_tolerance_mv
            )
            pack2_ok = self.pack_count < 2 or (
                pack2_fresh
                and pack2_temp_ok
                and self.pack2_min_mv >= self.cell_full_low_mv
                and (self.pack2_max_mv - self.pack2_min_mv) <= self.cell_balance_tolerance_mv
            )

            # if the real pack's own charge MOS is off, it can't accept more charge current right
            # now regardless of why - holding at 0% to chase a "confirmed full and balanced"
            # release that can't happen without current flowing serves no purpose
            pack1_charge_blocked = pack1_fresh and not self.pack1_charge_mos_on
            pack2_charge_blocked = self.pack_count >= 2 and pack2_fresh and not self.pack2_charge_mos_on

            if pack1_ok and pack2_ok:
                self.holding = False
            elif pack1_charge_blocked or pack2_charge_blocked:
                self.holding = False
            elif self.hold_failsafe_ms > 0 and (now - self.hold_start_time) >= self.hold_failsafe_ms:
                self.holding = False
        else:
            pack2_low = self.pack_count >= 2 and self.pack2_seen and self.pack2_soc <= self.reset_soc_percent
            went_stale = not pack1_fresh or not pack2_fresh
            if (self.pack1_seen and self.pack1_soc <= self.reset_soc_percent) or pack2_low or went_stale:
                self.holding = True
                self.hold_start_time = now


FULL_MIN_MV = 3465  # >= cell_full_low_mv default (3460)
FULL_MAX_MV = 3470  # spread of 5mV, within cell_balance_tolerance_mv default (20)


def test_starts_holding():
    assert HoldStateMachine().holding is True


def test_single_pack_releases_once_full_and_balanced():
    sm = HoldStateMachine(pack_count=1)
    sm.see_pack1(now=1000, min_mv=FULL_MIN_MV, max_mv=FULL_MAX_MV, soc=100)
    assert sm.holding is False


def test_two_pack_requires_both_packs_full_and_balanced():
    sm = HoldStateMachine(pack_count=2)
    sm.see_pack1(now=1000, min_mv=FULL_MIN_MV, max_mv=FULL_MAX_MV, soc=100)
    assert sm.holding is True, "must not release on pack1 alone in 2-pack mode"
    sm.see_pack2(now=1000, min_mv=FULL_MIN_MV, max_mv=FULL_MAX_MV, soc=100)
    assert sm.holding is False


def test_out_of_balance_pack_blocks_release():
    sm = HoldStateMachine(pack_count=1)
    # 30mV spread > cell_balance_tolerance_mv default (20)
    sm.see_pack1(now=1000, min_mv=3465, max_mv=3495, soc=100)
    assert sm.holding is True


def test_failsafe_releases_without_confirmed_balance():
    sm = HoldStateMachine(pack_count=1, hold_failsafe_ms=240 * 60000)
    # not full/balanced, but keeps reporting in so it isn't stale
    sm.see_pack1(now=0, min_mv=3000, max_mv=3000, soc=50)
    sm.see_pack1(now=240 * 60000, min_mv=3000, max_mv=3000, soc=50)
    assert sm.holding is False


def test_failsafe_disabled_when_zero():
    sm = HoldStateMachine(pack_count=1, hold_failsafe_ms=0)
    sm.see_pack1(now=0, min_mv=3000, max_mv=3000, soc=50)
    sm.see_pack1(now=10**9, min_mv=3000, max_mv=3000, soc=50)
    assert sm.holding is True


def test_rearms_when_soc_drops_to_reset_threshold():
    sm = HoldStateMachine(pack_count=1, reset_soc_percent=99)
    sm.see_pack1(now=1000, min_mv=FULL_MIN_MV, max_mv=FULL_MAX_MV, soc=100)
    assert sm.holding is False
    sm.see_pack1(now=2000, min_mv=FULL_MIN_MV, max_mv=FULL_MAX_MV, soc=99)
    assert sm.holding is True


def test_rearms_when_pack_goes_stale_after_release():
    sm = HoldStateMachine(pack_count=1, pack_stale_timeout_ms=30000)
    sm.see_pack1(now=0, min_mv=FULL_MIN_MV, max_mv=FULL_MAX_MV, soc=100)
    assert sm.holding is False
    # no further updates from pack1 - re-evaluate well past the staleness window
    sm.evaluate(now=30001)
    assert sm.holding is True


def test_does_not_rearm_before_stale_timeout_elapses():
    sm = HoldStateMachine(pack_count=1, pack_stale_timeout_ms=30000)
    sm.see_pack1(now=0, min_mv=FULL_MIN_MV, max_mv=FULL_MAX_MV, soc=100)
    assert sm.holding is False
    sm.evaluate(now=29999)
    assert sm.holding is False


def test_release_refuses_stale_pack_even_if_last_reading_was_full():
    # pack1 reported full/balanced a long time ago and has gone silent since - a fresh
    # evaluate_hold_() tick (eg. from loop()) must not release on that stale reading
    sm = HoldStateMachine(pack_count=1, pack_stale_timeout_ms=30000)
    sm.pack1_seen = True
    sm.pack1_last_update_ms = 0
    sm.pack1_min_mv = FULL_MIN_MV
    sm.pack1_max_mv = FULL_MAX_MV
    sm.pack1_soc = 100
    sm.evaluate(now=30001)
    assert sm.holding is True


def test_hot_pack_blocks_release():
    sm = HoldStateMachine(pack_count=1, cell_full_max_temp_c=50)
    # full and balanced, but 55.0 C is over the 50 C limit
    sm.see_pack1(now=1000, min_mv=FULL_MIN_MV, max_mv=FULL_MAX_MV, soc=100, temp_c10=550)
    assert sm.holding is True


def test_pack_cools_down_then_releases():
    sm = HoldStateMachine(pack_count=1, cell_full_max_temp_c=50)
    sm.see_pack1(now=1000, min_mv=FULL_MIN_MV, max_mv=FULL_MAX_MV, soc=100, temp_c10=550)
    assert sm.holding is True, "still too hot"
    sm.see_pack1(now=2000, min_mv=FULL_MIN_MV, max_mv=FULL_MAX_MV, soc=100, temp_c10=450)
    assert sm.holding is False, "45.0 C is at/under the 50 C limit"


def test_temp_check_disabled_when_zero():
    sm = HoldStateMachine(pack_count=1, cell_full_max_temp_c=0)
    # would block release above with the check enabled (see test_hot_pack_blocks_release)
    sm.see_pack1(now=1000, min_mv=FULL_MIN_MV, max_mv=FULL_MAX_MV, soc=100, temp_c10=550)
    assert sm.holding is False


def test_charge_mos_off_forces_release_even_when_not_full_or_balanced():
    sm = HoldStateMachine(pack_count=1)
    # nowhere near full/balanced, but the real pack has cut off charging itself - holding
    # serves no purpose since no current can flow regardless of what the ghost reports
    sm.see_pack1(now=1000, min_mv=3000, max_mv=3000, soc=50, charge_mos_on=False)
    assert sm.holding is False


def test_charge_mos_on_does_not_release_by_itself():
    sm = HoldStateMachine(pack_count=1)
    # charge_mos_on=True (the default) alongside an out-of-balance pack must NOT release -
    # only an actual MOS cutoff (or full+balanced, or the failsafe) does
    sm.see_pack1(now=1000, min_mv=3000, max_mv=3000, soc=50, charge_mos_on=True)
    assert sm.holding is True


def test_two_pack_mode_either_packs_charge_mos_off_forces_release():
    sm = HoldStateMachine(pack_count=2)
    sm.see_pack1(now=1000, min_mv=3000, max_mv=3000, soc=50, charge_mos_on=True)
    assert sm.holding is True
    sm.see_pack2(now=1000, min_mv=3000, max_mv=3000, soc=50, charge_mos_on=False)
    assert sm.holding is False


def test_charge_mos_off_on_stale_pack_does_not_force_release():
    # a pack that's gone stale is never trusted for anything, including its last-known MOS state -
    # otherwise a disconnected/reset pack's final cached reading could force a release forever
    sm = HoldStateMachine(pack_count=1, pack_stale_timeout_ms=30000)
    sm.pack1_seen = True
    sm.pack1_last_update_ms = 0
    sm.pack1_min_mv = 3000
    sm.pack1_max_mv = 3000
    sm.pack1_soc = 50
    sm.pack1_charge_mos_on = False
    sm.evaluate(now=30001)
    assert sm.holding is True
