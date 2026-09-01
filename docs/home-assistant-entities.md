# Home Assistant entities

**`sensor:`** — 68 sensors in this README's 2-pack example config (13 per-pack sensors × 2 packs +
16 cells × 2 packs + 4 global ones); every per-pack sensor scales up automatically to
`pack3_*` .. `pack8_*` if you list more addresses in `pack_addresses`, read passively off real
traffic already on the bus (the ghost never queries anything itself for these):
- Per configured pack (`pack1_*`, `pack2_*`, ... up to `pack8_*` depending on how many addresses
  you listed in `pack_addresses`): min/max cell voltage, cell voltage diff (max - min, ie. how far
  out of balance that pack currently is), total voltage, current (positive = charging, negative =
  discharging), power (voltage × current, kW), temperature, real SoC, and all 16 individual
  cell voltages (`entity_category: diagnostic`, grouped into Home Assistant's collapsible
  "Diagnostic" section on the device page instead of cluttering the main sensor list). Sourced
  from the packs' own status responses, which something on the bus already polls every few
  seconds.
- **`average_soc`** and **`average_voltage`** — the mean across every configured pack, only
  published once all of them have been seen at least once.
- **`total_power`** and **`total_current`** — the straight sum of every configured pack (not an
  average), same "once every pack has been seen" gating.
- **`total_cell_voltage_diff`** — highest cell minus lowest cell across **all** cells on **all**
  configured packs (not per-pack like the diffs above) — the single number that tells you how
  out of balance the whole array is.
- **`ghost_fake_soc`** — the direct answer to "what is the fake battery doing right now": exactly
  the 0 or 100 the ghost is telling the bus at that moment, updated every time it answers a status
  request.
- **`pack1_rcv_voltage`**, **`pack2_rcv_voltage`**, ... — each pack's own RCV (rated charge
  voltage) setting. Read-only and truly passive: the ghost never requests a settings frame itself,
  so these only update if something else on your bus (eg. the JK app, Solar Assistant) happens to
  query that pack's settings. They may simply never update on your setup - that's expected, not
  a bug.
- **`bus_error_count`** — counts CRC failures on frames that were otherwise structured like a
  query addressed to the ghost. A count that's rising (rather than staying at 0) points at an
  RS485 wiring, termination or noise problem worth investigating. `entity_category: diagnostic`.
- **`hold_failsafe_remaining`** — seconds left before `hold_failsafe_minutes` forces a release
  without confirmed balance. Reads 0 while released, or while the failsafe is disabled
  (`hold_failsafe_minutes: 0`). Lets you build an automation that warns you before the failsafe
  actually fires instead of only finding out afterwards. `entity_category: diagnostic`.
- **`total_charge_energy`** / **`total_discharge_energy`** — running kWh totals (energy into /
  out of the battery), integrated from `total_power` over time, ready to feed straight into Home
  Assistant's Energy dashboard as battery storage sensors. Like any in-memory counter on this
  device, both reset to 0 on every reboot — HA's `total_increasing` state class treats that as a
  normal meter reset, the same way a real energy meter behaves after a power cut.
- **`pack1_soh`**, **`pack2_soh`**, ... — each pack's own state-of-health percentage, straight off
  its status frame. A slow decline over months/years is normal aging; a sudden drop is worth
  investigating regardless of what the ghost is doing. `entity_category: diagnostic`.
- **`pack1_fault_count`**, **`pack2_fault_count`**, ... — a rising count the pack itself keeps of
  faults it has logged since power-up. A steady value is reassuring; a jump means something
  tripped even if the condition has since cleared. `entity_category: diagnostic`.
- **`pack1_cycle_count`**, **`pack2_cycle_count`**, ... — full-cycle-equivalent count, straight off
  the pack's own status frame. `entity_category: diagnostic`.
- **`pack1_balance_current`**, **`pack2_balance_current`**, ... — current currently being shunted
  between cells within that pack to balance them. `entity_category: diagnostic`.

**`text_sensor:`**
- **`hold_status`** — the "why" behind `ghost_fake_soc`'s raw "what". Reports a short reason
  string each time the hold/release decision changes, eg. `"released - balanced and full"`,
  `"released - failsafe (balance not confirmed)"`, `"holding - re-armed (SoC dropped)"`, or
  `"holding - re-armed (data stale)"`. Starts as `"holding - waiting for pack data"` on a
  first-ever boot, or `"released (restored from flash)"` if the saved state from before a reboot
  was already released.
- **`pack1_protection_flags`**, **`pack2_protection_flags`**, ... (one per configured pack) —
  `"none"`, or a comma-separated list of whichever of that pack's own alarm/protection bits are
  currently set (eg. `"cell OVP, discharge OCP"`). This comes straight from the real BMS and has
  nothing to do with what the ghost is telling the inverter, so it stays meaningful as a "is my
  real battery actually okay" check even while the ghost is holding at 0% or forcing 100%.
  `entity_category: diagnostic`.

**`binary_sensor:`** (one of each per configured pack)
- **`pack1_data_stale`**, **`pack2_data_stale`**, ... — on when that pack hasn't sent a fresh
  status frame within `pack_stale_timeout_seconds`. `entity_category: diagnostic`, so these show
  up in the device's collapsible "Diagnostic" section - a good target for a Home Assistant
  notification if you want to be alerted to a wiring or address problem instead of just watching
  the log.
- **`pack1_charge_mos`** / **`pack1_discharge_mos`** (and `pack2_*`, ... for every other configured
  pack) — on when the real pack's own MOS is currently allowing that direction of current. Off is
  a normal, expected state on its own (eg. discharge MOS off with nothing drawing current) -
  cross-check against `protection_active`/`protection_flags` below rather than treating "off" as
  an alarm by itself. `entity_category: diagnostic`.
- **`pack1_protection_active`**, **`pack2_protection_active`**, ... — on when that pack is
  reporting at least one of its own alarm/protection bits (see `protection_flags` above).
  Independent of `ghost_fake_soc`, so this is a genuine "is something actually wrong with the real
  battery" check regardless of what the ghost is currently telling the bus.
  `entity_category: diagnostic`.

**`switch:` + `number:`** — a manual override, deliberately built as a two-step interlock so it
can't be triggered by accident:
- **`manual_override_armed`** ("Ghost forced SOC enabled") must be switched on first. While off,
  the automatic cell-balance logic keeps running exactly as described above, untouched.
- **`manual_force_soc`** ("Ghost force SOC") only does anything once armed: a slider from 0-100,
  fixed to a step of 100 so it only ever has two positions — 100 forces the ghost to report
  100%, 0 forces it to report 0%. Moving it while disarmed does nothing.

`manual_override_armed` uses `restore_mode: ALWAYS_OFF` in the example config, and
`manual_force_soc` isn't persisted at all — every reboot always comes back up disarmed and fully
automatic, the same way `holding_` itself always starts at 0% on boot.
