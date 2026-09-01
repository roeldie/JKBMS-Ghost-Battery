# JKBMS Ghost Battery (ESPHome)

An ESPHome external component that spoofs a "ghost" battery on a JK BMS RS485 parallel bus, so
the master BMS's own SoC/coulomb-counter logic can run to completion instead of the inverter
cutting charging short the moment SoC first (and often incorrectly) reads 100%.

Runs on a generic ESP32 + a TTL-to-RS485 transceiver (this build uses a JZK STKS auto-direction
module — an old-style MAX485 module with manual DE/RE control works too), flashes and updates
through the [ESPHome](https://esphome.io) Dashboard, and integrates natively with Home Assistant.

## The problem this solves

A JK master BMS (RS485 address `0`) aggregates the whole parallel battery array and reports a
combined SoC to the inverter. If the inverter stops charging the instant it sees 100%, the pack
never reaches a true full-charge condition — which is exactly the condition the JK BMS needs to
reset coulomb-counting drift and let its cells top-balance. Over time this drift means SoC can
report 100% when the pack is actually far from full.

The fix: add a "ghost" battery at an unused RS485 address (`15` by default). Its presence in the
array's SoC calculation keeps the reported SoC below 100% until the real packs are genuinely
full and balanced — at which point the ghost releases the 100% signal for real, and the inverter
stops charging on a signal that's actually true.

Based on the [JKBMS Inverter BMS SoC Fixer — "Ghost Battery" — Open Hardware
Project](https://diysolarforum.com/threads/jkbms-inverter-bms-soc-fixer-ghost-battery-open-hardware-project.88554/)
on DIY Solar Forum. RS485 frame handling inspired by
[ModbusRTUSlave](https://github.com/CMB27/ModbusRTUSlave); frame-format details cross-referenced
against [txubelaxu/esphome-jk-bms](https://github.com/txubelaxu/esphome-jk-bms).

## How the release logic works

This variant gates the SoC release on real per-cell data instead of a fixed timer. Works with
anywhere from 1 to 8 real packs — just list one RS485 address per pack in `pack_addresses` (see
[Configuration reference](#configuration-reference)); everything below just says "every configured
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
   entities](#home-assistant-entities)). Once all of them have cut off charging themselves (cell
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

## ⚠️ Safety notes

This controls a real signal in a real charging system. Before trusting it unattended:

- **Verify every entry in `pack_addresses`** against your BMS's actual dip switch settings. Wrong
  addresses mean the ghost never sees real data from that pack and never releases.
- **Watch the logs first.** With `logger: level: DEBUG`, confirm you see a `Pack 0x.. cells: ...`
  line for every pack you configured (`Pack 0x00 cells: ...`, `Pack 0x01 cells: ...`, and so on)
  before leaving it running unattended.
- **Tune `cell_full_low_mv` and `cell_balance_tolerance_mv` to your cells**, not the defaults
  here — they were reverse-engineered from one specific pack (see
  [Protocol notes](#protocol-notes)) and won't necessarily suit yours.
- Provided as-is, without warranty. You are responsible for your own battery system.

## Hardware

- Any ESP32 dev board.
- A TTL-to-RS485 transceiver. This build uses a **JZK STKS** module, which senses transmit/receive
  direction automatically — no `de_pin` needed. An old-style MAX485/SP3485 breakout with separate
  DE/RE pins (tied together, driven from a GPIO) works too; see `de_pin` in the config reference.
- Wired onto the JK RS485 parallel bus, at an address with **no physical battery** (`15` by
  default).
- 115200 baud, 8N1.

### Wiring

```mermaid
flowchart LR
    subgraph ESP32
        TX[GPIO17 · TX]
        RX[GPIO16 · RX]
    end
    subgraph RS485["TTL-to-RS485 module (JZK STKS, auto-direction)"]
        RXD[RXD]
        TXD[TXD]
        A[A]
        B[B]
        GNDm[GND]
    end
    subgraph Cable["Cat5 cable, cut in half"]
        P1["pin 1 · orange"]
        P2["pin 2 · orange/white"]
        P3["pin 3 · green"]
    end
    BMS["JK BMS RS485 port (RJ45)"]

    TX -->|TX → RXD| RXD
    TXD -->|TXD → RX| RX
    A --> P1
    B --> P2
    GNDm --> P3
    P1 & P2 & P3 -.->|standard RJ45 plug| BMS
```

| ESP32 | Module | Cat5 pin | Wire |
|---|---|---|---|
| GPIO17 (TX) | RXD | — | — |
| GPIO16 (RX) | TXD | — | — |
| 3V3/5V | VCC | — | — |
| GND | GND | — | — |
| — | A | pin 1 | orange |
| — | B | pin 2 | orange/white |
| — | GND | pin 3 | green |

Note the crossover: ESP32 **TX** goes to the module's **RXD**, and ESP32 **RX** goes to the
module's **TXD** — same as wiring up any two UART devices. Some modules label these pins `DI`/`RO`
instead (from the RS485 driver chip's own perspective rather than the UART side) — if yours does,
`DI` is what's labeled `RXD` here and `RO` is `TXD`. Either way: connect TX to whichever pin feeds
into the module, and RX to whichever pin comes out of it.

Using an old-style MAX485 module instead? Add a `GPIO4 → DE + RE (tied together)` connection and
set `de_pin: GPIO4` in the YAML (see [Configuration reference](#configuration-reference)).

The Cat5 cable's other end is a standard, unmodified RJ45 plug into the BMS's RS485 port — same
connector the JK Windows tool or Solar Assistant would use.

> Check your specific module's datasheet before tying VCC to 3.3V — most read RXD/TXD (and DE/RE,
> if present) fine at 3.3V logic even when VCC itself needs 5V, but that varies by board.
>
> Unlike the M5Stack RS485 base (which has internal pulldowns), a bare RS485 module needs the
> ground wire (pin 3, green) connected for reliable communication.

### Soldering / assembly

Tools: soldering iron + solder, wire strippers, heat-shrink tubing (or electrical tape), a
multimeter for continuity checks, and a lighter/heat gun for the heat-shrink.

1. **ESP32 → module.** If your module only has bare through-hole pads for RXD/TXD/VCC/GND
   (labeled `DI`/`RO` on some boards), solder short wires (or a 4-pin header, if you'd rather use
   Dupont jumpers) onto those four pads. Solder the other ends to the ESP32's GPIO17 (TX) →
   module RXD/DI, GPIO16 (RX) → module TXD/RO, 3V3/5V → VCC and GND → GND — or to headers on the
   dev board if it has them already, no need to solder straight to the board itself.
2. **Prepare the Cat5 cable.** Cut a Cat5/Cat5e cable roughly in half. On the BMS end, leave the
   factory RJ45 plug untouched. On the module end, strip ~3cm of outer jacket, untwist the pairs,
   and identify pins 1 (orange), 2 (orange/white) and 3 (green) by the standard T568 colors. You
   only need these three wires — trim the other five short so they can't short anything.
3. **Connect A/B/GND to the module.** Strip ~5mm of insulation off pins 1, 2 and 3 and tin them
   with a light coat of solder.
   - **Screw-terminal module:** loosen the terminal screws, insert pin 1 → `A`, pin 2 → `B`,
     tighten. No soldering needed here.
   - **Solder-pad module:** solder pin 1 to the `A` pad and pin 2 to the `B` pad directly.
   - Either way, solder (or terminal-connect) pin 3 to the module's `GND` pad/terminal.
4. **Insulate every joint.** Slide heat-shrink over each solder joint before soldering the next
   one (easy to forget), then shrink it once cool. This sits next to a battery bank — a stray
   strand shorting `A` to `GND`, or two 5V/GND wires touching, is worth the extra minute.
5. **Check before powering on.** With everything unpowered, use a multimeter in continuity mode
   to confirm: `A` and `B` aren't shorted to each other or to `GND`, and there's no continuity
   between your 5V/VCC wire and `GND`. Then power up and plug the RJ45 end into the BMS.

## Installation

1. Copy this whole folder (including `components/`) into your ESPHome Dashboard's config
   directory, eg. `/config/esphome/`, keeping the folder structure intact — `external_components`
   in the YAML resolves `path: components` relative to the YAML file.
2. Copy `secrets.yaml.example` to `secrets.yaml` alongside it (or merge its keys into your
   existing one) and fill in your real WiFi credentials, a generated API encryption key, an OTA
   password, and a fallback AP password (`ap_fallback_password`, min. 8 characters).
   `secrets.yaml` itself is gitignored - never commit your real credentials.
3. In the ESPHome Dashboard, open `jkbms-ghost-battery.yaml` and click **Validate** — it should
   list the full resolved config ending in `Configuration is valid!` with no errors. If it can't
   find the component, double check the folder name is exactly `components/jkbms_ghost_battery/`
   (case-sensitive on Linux).
4. Click **Install** for the first flash (USB required); later updates can go out over WiFi/OTA.
5. Once online, Home Assistant will show a discovery notification for the device automatically
   (**Settings → Devices & services**) — no manual YAML editing needed on the HA side.

If the device ever can't reach your WiFi (eg. you changed the password), it falls back to
broadcasting a **"JKBMS Ghost Battery Fallback"** hotspot. Connect to it with a phone using the
`ap_fallback_password` from your `secrets.yaml`, and a captive portal page lets you enter new
WiFi credentials — no reflashing needed.

## Configuration reference

```yaml
jkbms_ghost_battery:
  uart_id: jkbms_uart
  # de_pin is optional - omit it for an auto-direction module (eg. JZK STKS). Only needed for an
  # old-style MAX485 module with separate DE+RE pins tied together:
  # de_pin: GPIO4
  ghost_address: 15       # must be an address with no physical battery
  ghost_capacity_ah: 36   # reported nominal/remaining capacity once released - match your real
                           # bank's actual capacity
  pack_addresses: [0, 1]  # one RS485 address per real pack, in order - verify each pack's dip
                           # switches. How many packs you have is just how many addresses you list
                           # here (1 up to MAX_PACKS, 8): `[0]` for a single pack, `[0, 1, 2, 3]`
                           # for four, etc. Pack 1 (index 0) is always the RS485 master.
  cell_full_low_mv: 3460        # every cell, every configured pack, must be at/above this voltage
                                 # (mV)...
  cell_balance_tolerance_mv: 20 # ...AND each pack's own max-min cell spread must be within this
                                 # many mV - together, "full" and "balanced"
  cell_full_max_temp_c: 50      # ...AND no configured pack may be hotter than this (C). 0 disables it
  reset_soc_percent: 99   # re-arms the hold once any configured pack's real SoC drops to this value
  hold_failsafe_minutes: 240  # safety backstop; releases anyway if balance is never confirmed. 0 disables it
  pack_stale_timeout_seconds: 30  # a pack with no fresh data for this long is treated as unusable -
                                   # release is refused, and an already-released hold re-arms

sensor:
  - platform: jkbms_ghost_battery
    pack1_min_cell_voltage:
      name: "Pack 1 min cell voltage"
    pack1_max_cell_voltage:
      name: "Pack 1 max cell voltage"
    pack2_min_cell_voltage:
      name: "Pack 2 min cell voltage"
    pack2_max_cell_voltage:
      name: "Pack 2 max cell voltage"
    pack1_cell_voltage_diff:
      name: "Pack 1 cell voltage diff"   # highest cell minus lowest cell in pack 1
    pack2_cell_voltage_diff:
      name: "Pack 2 cell voltage diff"   # highest cell minus lowest cell in pack 2
    pack1_voltage:
      name: "Pack 1 voltage"
    pack2_voltage:
      name: "Pack 2 voltage"
    pack1_current:
      name: "Pack 1 current"   # positive = charging, negative = discharging
    pack2_current:
      name: "Pack 2 current"
    pack1_power:
      name: "Pack 1 power"
    pack2_power:
      name: "Pack 2 power"
    total_power:
      name: "Total power"   # every configured pack's power, straight sum
    total_current:
      name: "Total current"   # every configured pack's current, straight sum
    total_cell_voltage_diff:
      name: "Total cell voltage diff"   # highest cell minus lowest cell across ALL cells, all packs
    pack1_temperature:
      name: "Pack 1 temperature"
    pack2_temperature:
      name: "Pack 2 temperature"
    pack1_soc:
      name: "Pack 1 SoC"
    pack2_soc:
      name: "Pack 2 SoC"
    average_soc:
      name: "Average SoC"   # average across every configured pack
    average_voltage:
      name: "Average voltage"   # average across every configured pack
    ghost_fake_soc:
      name: "Ghost fake SoC"   # what the ghost is currently telling the bus: 0 or 100
    pack1_rcv_voltage:
      name: "Pack 1 RCV"   # rated charge voltage from that pack's settings - read-only, passive
                             # only (updates only if something else on the bus queries it)
    pack2_rcv_voltage:
      name: "Pack 2 RCV"
    bus_error_count:
      name: "Bus CRC error count"   # rising count = RS485 wiring/termination/noise problem
    hold_failsafe_remaining:
      name: "Hold failsafe remaining"   # seconds until hold_failsafe_minutes forces a release
    total_charge_energy:
      name: "Total charge energy"     # for the Home Assistant Energy dashboard - resets on reboot
    total_discharge_energy:
      name: "Total discharge energy"
    # protection/health sensors, sourced from the real pack's own status frame - see "Home
    # Assistant entities" below for what each one means and why they matter independent of the
    # ghost's own spoofed SoC
    pack1_soh:
      name: "Pack 1 SOH"
    pack2_soh:
      name: "Pack 2 SOH"
    pack1_fault_count:
      name: "Pack 1 fault count"
    pack2_fault_count:
      name: "Pack 2 fault count"
    pack1_cycle_count:
      name: "Pack 1 cycle count"
    pack2_cycle_count:
      name: "Pack 2 cycle count"
    pack1_balance_current:
      name: "Pack 1 balance current"
    pack2_balance_current:
      name: "Pack 2 balance current"
    # individual cell voltages - pack1_cell_1 .. pack1_cell_16, pack2_cell_1 .. pack2_cell_16, and
    # so on for every pack up to pack8_cell_16 (all optional, whether or not you've actually
    # configured that many packs - unused ones just have nothing to publish to). This 2-pack
    # example only lists pack1/pack2; see jkbms-ghost-battery.yaml for the full list.
    # These are entity_category: diagnostic, so Home Assistant groups them into the device's
    # collapsible "Diagnostic" section instead of the main sensor list.
    pack1_cell_1:
      name: "Pack 1 Cell 1"
    pack1_cell_2:
      name: "Pack 1 Cell 2"
    # ...

text_sensor:
  - platform: jkbms_ghost_battery
    hold_status:
      name: "Ghost hold status"   # why the ghost is currently holding or released
    pack1_protection_flags:
      name: "Pack 1 protection flags"
    pack2_protection_flags:
      name: "Pack 2 protection flags"

binary_sensor:
  - platform: jkbms_ghost_battery
    pack1_data_stale:
      name: "Pack 1 data stale"   # on = no fresh reading within pack_stale_timeout_seconds
    pack2_data_stale:
      name: "Pack 2 data stale"
    pack1_charge_mos:
      name: "Pack 1 charge MOS"
    pack2_charge_mos:
      name: "Pack 2 charge MOS"
    pack1_discharge_mos:
      name: "Pack 1 discharge MOS"
    pack2_discharge_mos:
      name: "Pack 2 discharge MOS"
    pack1_protection_active:
      name: "Pack 1 protection active"
    pack2_protection_active:
      name: "Pack 2 protection active"

switch:
  - platform: jkbms_ghost_battery
    manual_override_armed:
      name: "Ghost forced SOC enabled"
      restore_mode: ALWAYS_OFF

number:
  - platform: jkbms_ghost_battery
    manual_force_soc:
      name: "Ghost force SOC"
```

All `sensor:`, `text_sensor:`, `binary_sensor:` and `switch:` entries are optional individually —
omit any you don't want.

## Home Assistant entities

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

## Protocol notes

Every JK RS485 status frame (`0x20`) is a fixed 308-byte packet. The fields this component reads
and/or patches were reverse engineered directly from a real capture (a JK PB2A16S30P V19A, 16S
LiFePO4, address `0x0F`) and cross-checked against
[esphome-jk-bms](https://github.com/txubelaxu/esphome-jk-bms):

| Field | Byte offset | Format |
|---|---|---|
| Cell voltages (16 cells) | 6–37 | 2 bytes little-endian, mV, one pair per cell |
| Total pack voltage | 150–153 | 4 bytes little-endian, mV |
| Current | 158–161 | 4 bytes little-endian signed, mA (+ charging, - discharging) |
| Temperature (T1 probe) | 162–163 | 2 bytes little-endian signed, 0.1°C |
| SoC | 173 | 1 byte, percent |
| Remaining capacity | 174–177 | 4 bytes little-endian, mAh |
| Total capacity | 178–181 | 4 bytes little-endian, mAh |
| Alarm/protection bits | 166–169 | 4 bytes little-endian, one bit per fault, 1 = active |
| Balance current | 170–171 | 2 bytes little-endian signed, mA |
| Cycle count | 182–185 | 4 bytes little-endian, full-cycle-equivalent count |
| State of health (SOH) | 190 | 1 byte, percent |
| Charge MOS | 198 | 1 byte, 0 = off (charge cut off), 1 = on |
| Discharge MOS | 199 | 1 byte, 0 = off (discharge cut off), 1 = on |
| Fault count | 266 | 1 byte, rising count = a fault has been logged |
| Internal payload checksum | 299 | 1 byte, sum of bytes 0–298 mod 256 |
| Source address (trailer echo) | 300 | 1 byte |
| Trailer CRC16 | 306–307 | Modbus CRC16 over bytes 300–305 only (not the whole frame) |

The total-pack-voltage field was cross-checked by summing the 16 individual cell voltages — they
matched to within 1mV on the reference capture, confirming both fields.

The alarm/protection bits, SOH, MOS status, fault-count, cycle-count and balance-current offsets
above were cross-checked against a third-party JK 55AA protocol reference
([Gobel-Battery-HA-Addon](https://github.com/fancyui/Gobel-Battery-HA-Addon/blob/main/JK-BMS-55AA-Protocol_EN.md)),
which independently documents this project's own already-verified offsets (150/158/162/173)
identically - that agreement is what gives confidence in the previously-unused ones too. As with
the rest of this table, these haven't been individually re-verified against a live capture from
every pack model, so treat a genuinely surprising reading (eg. a fault count that jumps constantly)
as worth double-checking rather than gospel.

Bit 0-23 of the alarm field are individually named (battery/cell over/under-voltage, over-current,
over-temperature, etc. - see `decode_protection_flags_()` in `jkbms_ghost_battery.cpp` for the
full list); any set bit above 23 isn't in the reference doc but is still reported as
`"other (bit N)"` rather than silently dropped.

Bytes 300–305 are an echo of the query that was sent (address, function, subfunction, frame type,
`0x00`, `0x01`), and bytes 306–307 are a Modbus CRC16 over just those 6 bytes — a completely
separate checksum from the payload one at byte 299. Any time byte 300 (the source address) is
patched — eg. to make the ghost's responses reflect a non-default `ghost_address` — this trailer
CRC has to be recomputed too, or a master that validates response CRCs will reject the frame.

The internal payload checksum at byte 299 is a much simpler plain byte sum (see
`recompute_checksum_()`), but needs the same discipline: any time a byte inside 0-298 is patched
at runtime - SoC, remaining/total capacity, temperature - it has to be recomputed too, or a master
that validates response checksums will reject the frame outright. `ghost_capacity_ah`'s runtime
patch (remaining capacity in frame2, total/nominal capacity in both frame1 and frame2) is the
newest thing that touches this range, alongside the existing SoC/temperature patches.

The settings frame (`0x1E`, response type `0x01`) has a different, unshifted byte layout:

| Field | Byte offset | Format |
|---|---|---|
| RCV (rated charge voltage) | 38–41 | 4 bytes little-endian, mV |
| Cell count | 114–117 | 4 bytes little-endian |
| Nominal capacity | 130–133 | 4 bytes little-endian, mAh |

Verified against the reference capture: cell count reads exactly 16, and nominal capacity reads
exactly 36000 (matching the 36Ah patch) at these offsets with no shift applied - unlike the
status frame's fields above, which are shifted +32 bytes relative to the equivalent offsets in
[esphome-jk-bms](https://github.com/txubelaxu/esphome-jk-bms) (that project's frame layout
reserves extra space for a 32-cell variant that this one doesn't use).

Any time the SoC/capacity bytes are patched, byte 299 is recomputed — otherwise the frame gets
silently rejected downstream.

## Battery bank this was built/tested against

Yixiang 34kWh (EVE MB56 cells), JK PB2A16S30P V19A BMS.

## Development

`esphome config jkbms-ghost-battery.yaml` (with a `secrets.yaml` in place) validates the YAML
and the component's own config schema - this also runs in CI on every push/PR.

`tests/` holds host-side Python tests that don't need any ESP32 hardware:
- `test_frame_templates.py` cross-checks the frozen capture bytes against the offsets documented
  above (checksum byte, cell-voltage-sum-vs-total-voltage, plausible current/temperature).
- `test_address_validation.py` exercises the real `_validate_unique_addresses()` config
  validator directly.
- `test_hold_logic.py` is a plain-Python port of `evaluate_hold_()`'s hold/release/re-arm state
  machine, parameterised on a fake clock instead of `millis()` - keep it in sync with the C++
  if that function changes.

Run them with:

```
pip install esphome pytest
pytest tests/
```
