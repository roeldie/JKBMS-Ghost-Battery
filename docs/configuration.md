# Configuration reference

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
    # protection/health sensors, sourced from the real pack's own status frame - see
    # docs/home-assistant-entities.md for what each one means and why they matter independent of
    # the ghost's own spoofed SoC
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
