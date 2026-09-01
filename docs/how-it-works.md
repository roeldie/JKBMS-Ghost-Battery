# How the release logic works

This variant gates the SoC release on real per-cell data instead of a fixed timer. Works with
anywhere from 1 to 8 real packs — just list one RS485 address per pack in `pack_addresses` (see
[Configuration reference](configuration.md)); everything below just says "every configured
pack" since the logic is identical no matter how many that ends up being:

1. The ghost starts **holding** (reports 0% SoC, 0 Ah remaining) — this blocks the array from
   ever reading 100%.
2. It passively sniffs the real packs' own status responses as they pass by on the bus and
   tracks each pack's min/max cell voltage and reported SoC.
3. Once **every cell on every configured pack** is at or above `cell_full_low_mv` (default 3.46V)
   **and** each pack's own highest-lowest cell spread is within `cell_balance_tolerance_mv`
   (default 20mV) **and** no configured pack is hotter than `cell_full_max_temp_c` (default 50°C),
   the ghost releases: it reports 100% SoC and full capacity, so the inverter gets a genuine
   full-charge signal and stops charging.
4. It also releases immediately, regardless of balance, once **every** configured pack's own
   **charge MOS is off** (`pack1_charge_mos`, `pack2_charge_mos`, ... — see [Home Assistant
   entities](home-assistant-entities.md)). Once all of them have cut off charging themselves (cell
   OVP, over-temp, whatever tripped each one), no current can flow into any of them no matter what
   the ghost reports, so holding at 0% to chase a "confirmed full and balanced" release that can't
   happen serves no purpose — the inverter should be told to stop trying. This requires *all*
   packs, not just one: the whole point of a multi-pack array is for every pack to reach a genuine
   full charge, so one pack finishing early (a normal, expected event - packs don't all hit their
   own cutoff at the same moment) must not force an array-wide release while the others are still
   mid-charge and need the time at voltage to actually balance. This also deliberately only looks
   at the charge MOS state, not the full protection/alarm bitfield (`pack1_protection_flags` etc.
   stay informational-only) - see the code comment on this check in `evaluate_hold_()` for why.
5. As soon as any configured pack's own reported SoC drops to `reset_soc_percent` (default 99%) —
   ie. discharging has started — the ghost re-arms back to holding, ready for the next cycle.
6. `hold_failsafe_minutes` (default 240) is a safety backstop: if balance/full can never be
   confirmed (wrong address, wiring problem), the hold releases anyway after this long, so a
   configuration mistake can't cause indefinite overcharge. Set to `0` to disable.
7. `pack_stale_timeout_seconds` (default 30) guards against acting on stale data: if a configured
   pack hasn't sent a fresh status frame within this window (BMS reset, wiring fault, pack
   physically disconnected), its last cached reading is no longer trusted — the ghost won't
   release on the strength of it, and if it had already released, it re-arms back to holding as a
   precaution. Real packs are normally polled every few seconds, so this should stay well above
   that under normal conditions.
8. The hold/release state (step 1 vs step 3) is saved to flash every time it changes, and
   restored on boot. A routine restart (OTA update, brownout, crash) doesn't force a fresh
   `hold_failsafe_minutes` wait if the pack(s) were already confirmed full and balanced moments
   earlier — the ghost comes back up already released instead of re-holding from scratch. A
   first-ever boot with nothing saved yet still starts holding, same as always.
