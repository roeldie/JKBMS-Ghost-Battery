# Protocol notes

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
