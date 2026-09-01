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

## Documentation

- **[How the release logic works](docs/how-it-works.md)** — the hold/release/re-arm state machine
  and what each config value gates.
- **[Hardware & wiring](docs/hardware-and-wiring.md)** — parts list, wiring diagram, soldering
  steps, and a troubleshooting section for interference/dropouts.
- **[Installation](docs/installation.md)** — getting it onto the ESPHome Dashboard and flashed.
- **[Configuration reference](docs/configuration.md)** — the full YAML example, every option.
- **[Home Assistant entities](docs/home-assistant-entities.md)** — what every sensor, switch and
  number actually means.
- **[Protocol notes](docs/protocol-notes.md)** — the reverse-engineered JK RS485 byte layout.
- **[Development](docs/development.md)** — running the config validator and test suite.

## ⚠️ Safety notes

This controls a real signal in a real charging system. Before trusting it unattended:

- **Verify every entry in `pack_addresses`** against your BMS's actual dip switch settings. Wrong
  addresses mean the ghost never sees real data from that pack and never releases.
- **Watch the logs first.** With `logger: level: DEBUG`, confirm you see a `Pack 0x.. cells: ...`
  line for every pack you configured (`Pack 0x00 cells: ...`, `Pack 0x01 cells: ...`, and so on)
  before leaving it running unattended.
- **Tune `cell_full_low_mv` and `cell_balance_tolerance_mv` to your cells**, not the defaults
  here — they were reverse-engineered from one specific pack (see
  [Protocol notes](docs/protocol-notes.md)) and won't necessarily suit yours.
- Provided as-is, without warranty. You are responsible for your own battery system.

## Battery bank this was built/tested against

Yixiang 34kWh (EVE MB56 cells), JK PB2A16S30P V19A BMS.
