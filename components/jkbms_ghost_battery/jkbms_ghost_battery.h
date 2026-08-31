#pragma once

#include "esphome/core/component.h"
#include "esphome/core/hal.h"
#include "esphome/core/preferences.h"
#include "esphome/components/uart/uart.h"
#include "esphome/components/sensor/sensor.h"
#include "esphome/components/binary_sensor/binary_sensor.h"
#include "esphome/components/text_sensor/text_sensor.h"

namespace esphome {
namespace jkbms_ghost_battery {

// full JK RS485 frame size (4-byte header + payload + trailer/CRC), same on all frame types
static const uint16_t JK_FRAME_SIZE = 308;
// if no new byte arrives for this long, whatever is buffered is treated as one complete frame.
// The real JKBMS sends frames in bursts with brief pauses, so this must be longer than those
// intra-frame pauses (ported from the Arduino version's 10ms char timeout).
static const uint32_t JK_FRAME_GAP_MS = 10;

class JkBmsGhostBattery : public Component, public uart::UARTDevice {
 public:
  void setup() override;
  void loop() override;
  void dump_config() override;

  void set_de_pin(GPIOPin *pin) { this->de_pin_ = pin; }
  void set_ghost_address(uint8_t address) { this->ghost_address_ = address; }
  // 1 or 2. In single-pack mode, pack2_address_/pack2_* is ignored entirely everywhere - the
  // release/re-arm logic, the average sensors and the temperature fallback all work off pack1 alone.
  void set_pack_count(uint8_t count) { this->pack_count_ = count; }
  void set_pack1_address(uint8_t address) { this->pack1_address_ = address; }
  void set_pack2_address(uint8_t address) { this->pack2_address_ = address; }
  void set_cell_full_low_mv(uint16_t mv) { this->cell_full_low_mv_ = mv; }
  void set_cell_balance_tolerance_mv(uint16_t mv) { this->cell_balance_tolerance_mv_ = mv; }
  // release is refused if either pack is hotter than this, even if voltage/balance are otherwise
  // fine - 0 disables the check entirely
  void set_cell_full_max_temp_c(int16_t c) { this->cell_full_max_temp_c_ = c; }
  void set_reset_soc_percent(uint8_t percent) { this->reset_soc_percent_ = percent; }
  void set_hold_failsafe_ms(uint32_t ms) { this->hold_failsafe_ms_ = ms; }
  // if a configured pack hasn't produced a fresh status frame in this long, its cached
  // cell/SoC data is treated as unusable: release is refused, and an already-released hold
  // re-arms defensively (see evaluate_hold_())
  void set_pack_stale_timeout_ms(uint32_t ms) { this->pack_stale_timeout_ms_ = ms; }

  void set_pack1_min_cell_voltage_sensor(sensor::Sensor *s) { this->pack1_min_cell_voltage_sensor_ = s; }
  void set_pack1_max_cell_voltage_sensor(sensor::Sensor *s) { this->pack1_max_cell_voltage_sensor_ = s; }
  void set_pack2_min_cell_voltage_sensor(sensor::Sensor *s) { this->pack2_min_cell_voltage_sensor_ = s; }
  void set_pack2_max_cell_voltage_sensor(sensor::Sensor *s) { this->pack2_max_cell_voltage_sensor_ = s; }
  void set_pack1_soc_sensor(sensor::Sensor *s) { this->pack1_soc_sensor_ = s; }
  void set_pack2_soc_sensor(sensor::Sensor *s) { this->pack2_soc_sensor_ = s; }
  // reflects exactly what the ghost is currently telling the bus: 0 or 100
  void set_ghost_fake_soc_sensor(sensor::Sensor *s) { this->ghost_fake_soc_sensor_ = s; }

  void set_pack1_voltage_sensor(sensor::Sensor *s) { this->pack1_voltage_sensor_ = s; }
  void set_pack2_voltage_sensor(sensor::Sensor *s) { this->pack2_voltage_sensor_ = s; }
  void set_pack1_current_sensor(sensor::Sensor *s) { this->pack1_current_sensor_ = s; }
  void set_pack2_current_sensor(sensor::Sensor *s) { this->pack2_current_sensor_ = s; }
  void set_pack1_power_sensor(sensor::Sensor *s) { this->pack1_power_sensor_ = s; }
  void set_pack2_power_sensor(sensor::Sensor *s) { this->pack2_power_sensor_ = s; }
  // straight sums, not averages - in single-pack mode these are just pack1's own value
  void set_total_power_sensor(sensor::Sensor *s) { this->total_power_sensor_ = s; }
  void set_total_current_sensor(sensor::Sensor *s) { this->total_current_sensor_ = s; }
  // highest cell minus lowest cell across ALL cells on ALL configured packs, not per-pack
  void set_total_cell_voltage_diff_sensor(sensor::Sensor *s) { this->total_cell_voltage_diff_sensor_ = s; }
  void set_pack1_temperature_sensor(sensor::Sensor *s) { this->pack1_temperature_sensor_ = s; }
  void set_pack2_temperature_sensor(sensor::Sensor *s) { this->pack2_temperature_sensor_ = s; }
  void set_pack1_cell_voltage_diff_sensor(sensor::Sensor *s) { this->pack1_cell_voltage_diff_sensor_ = s; }
  void set_pack2_cell_voltage_diff_sensor(sensor::Sensor *s) { this->pack2_cell_voltage_diff_sensor_ = s; }
  // averages of pack1+pack2, only published once both packs have been seen at least once
  void set_average_soc_sensor(sensor::Sensor *s) { this->average_soc_sensor_ = s; }
  void set_average_voltage_sensor(sensor::Sensor *s) { this->average_voltage_sensor_ = s; }
  // read-only, passive only: only updates if something else on the bus queries that pack's
  // settings frame - see RCV_OFFSET in jkbms_ghost_battery.cpp
  void set_pack1_rcv_voltage_sensor(sensor::Sensor *s) { this->pack1_rcv_voltage_sensor_ = s; }
  void set_pack2_rcv_voltage_sensor(sensor::Sensor *s) { this->pack2_rcv_voltage_sensor_ = s; }
  // counts CRC failures on frames that were otherwise structured like a query addressed to us -
  // a rising count points at RS485 wiring/termination/noise problems
  void set_bus_error_count_sensor(sensor::Sensor *s) { this->bus_error_count_sensor_ = s; }
  // seconds left before hold_failsafe_ms_ forces a release without confirmed balance - 0 while
  // released, or while the failsafe is disabled
  void set_hold_failsafe_remaining_sensor(sensor::Sensor *s) { this->hold_failsafe_remaining_sensor_ = s; }
  // running kWh totals for the Home Assistant Energy dashboard, split into energy into/out of the
  // battery. Integrated from total_power, so they reset to 0 on every reboot like any other
  // in-memory counter - HA's total_increasing state class treats that as a normal meter reset.
  void set_total_charge_energy_sensor(sensor::Sensor *s) { this->total_charge_energy_sensor_ = s; }
  void set_total_discharge_energy_sensor(sensor::Sensor *s) { this->total_discharge_energy_sensor_ = s; }

  // human-readable reason for the ghost's current hold/release decision (see evaluate_hold_()) -
  // this is the "why", complementing ghost_fake_soc's raw "what" (0 or 100)
  void set_hold_status_text_sensor(text_sensor::TextSensor *s) { this->hold_status_text_sensor_ = s; }
  // on = that pack hasn't sent a fresh status frame within pack_stale_timeout_seconds
  void set_pack1_data_stale_sensor(binary_sensor::BinarySensor *s) { this->pack1_data_stale_sensor_ = s; }
  void set_pack2_data_stale_sensor(binary_sensor::BinarySensor *s) { this->pack2_data_stale_sensor_ = s; }

  // protection/health sensors sourced from the real pack's own status frame - these reflect what
  // the actual BMS is reporting, independent of whatever SoC the ghost is currently telling the
  // inverter, so they stay meaningful for safety/assurance even while the ghost is holding or
  // spoofing. See ALARM_BITS_OFFSET etc in jkbms_ghost_battery.cpp for where they come from.
  void set_pack1_charge_mos_sensor(binary_sensor::BinarySensor *s) { this->pack1_charge_mos_sensor_ = s; }
  void set_pack2_charge_mos_sensor(binary_sensor::BinarySensor *s) { this->pack2_charge_mos_sensor_ = s; }
  void set_pack1_discharge_mos_sensor(binary_sensor::BinarySensor *s) { this->pack1_discharge_mos_sensor_ = s; }
  void set_pack2_discharge_mos_sensor(binary_sensor::BinarySensor *s) { this->pack2_discharge_mos_sensor_ = s; }
  // on = the real pack is currently reporting at least one active alarm/protection bit of its own
  void set_pack1_protection_active_sensor(binary_sensor::BinarySensor *s) { this->pack1_protection_active_sensor_ = s; }
  void set_pack2_protection_active_sensor(binary_sensor::BinarySensor *s) { this->pack2_protection_active_sensor_ = s; }
  // "none", or a comma-separated list of which fault(s) are set - see decode_protection_flags_()
  void set_pack1_protection_flags_text_sensor(text_sensor::TextSensor *s) { this->pack1_protection_flags_text_sensor_ = s; }
  void set_pack2_protection_flags_text_sensor(text_sensor::TextSensor *s) { this->pack2_protection_flags_text_sensor_ = s; }
  void set_pack1_soh_sensor(sensor::Sensor *s) { this->pack1_soh_sensor_ = s; }
  void set_pack2_soh_sensor(sensor::Sensor *s) { this->pack2_soh_sensor_ = s; }
  // rising count = the pack has logged a fault since power-up - a steady value is reassuring, a
  // jump means something tripped even if the condition has since cleared
  void set_pack1_fault_count_sensor(sensor::Sensor *s) { this->pack1_fault_count_sensor_ = s; }
  void set_pack2_fault_count_sensor(sensor::Sensor *s) { this->pack2_fault_count_sensor_ = s; }

  // individual cell voltages, index 0-15 (cell 1-16)
  void set_pack1_cell_voltage_sensor(uint8_t index, sensor::Sensor *s) { this->pack1_cell_sensors_[index] = s; }
  void set_pack2_cell_voltage_sensor(uint8_t index, sensor::Sensor *s) { this->pack2_cell_sensors_[index] = s; }

  // Manual override: a two-step interlock. manual_override_armed_ must be switched on first;
  // only then does manual_force_soc_ actually decide what the ghost reports (0 or 100). While
  // disarmed, the automatic cell-balance logic keeps running as normal, so disarming always
  // drops straight back into a known-good, evaluated state instead of a stale one.
  void set_manual_override_armed(bool armed) { this->manual_override_armed_ = armed; }
  void set_manual_force_soc(uint8_t soc) { this->manual_force_soc_ = soc; }

 protected:
  void handle_frame_();
  bool is_query_for_us_();
  void send_frame1_();
  void send_frame2_();
  void send_frame3_();
  void send_response_(uint16_t len);
  void sniff_real_pack_();
  void evaluate_hold_();
  void publish_hold_status_(const char *status);
  bool is_holding_() { return this->manual_override_armed_ ? (this->manual_force_soc_ < 50) : this->holding_; }
  uint16_t crc16_(uint16_t len);
  void patch_source_address_();

  GPIOPin *de_pin_{nullptr};
  uint8_t ghost_address_{15};
  uint8_t pack_count_{2};
  uint8_t pack1_address_{0};
  uint8_t pack2_address_{1};
  uint16_t cell_full_low_mv_{3460};
  uint16_t cell_balance_tolerance_mv_{20};
  // 0 disables the check; matches the YAML schema's own default (50 C) for the same reason
  // hold_failsafe_ms_ has a hardcoded default above
  int16_t cell_full_max_temp_c_{50};
  uint8_t reset_soc_percent_{99};
  // matches the YAML schema's own default (240 min) so a build that somehow skips codegen's
  // set_hold_failsafe_ms() call still gets the safe default instead of the failsafe silently
  // being disabled
  uint32_t hold_failsafe_ms_{240 * 60000};
  uint32_t pack_stale_timeout_ms_{30000};

  uint8_t buf_[JK_FRAME_SIZE];
  uint16_t num_bytes_{0};
  uint32_t last_byte_time_{0};
  // count of CRC failures on frames that were otherwise structured like a query addressed to us
  // (right header bytes, right address) - see is_query_for_us_()
  uint32_t bus_error_count_{0};

  // running kWh totals for the energy dashboard sensors, integrated from total_power each time a
  // new status frame updates it (see sniff_real_pack_()). Reset to 0 on every reboot.
  float total_charge_energy_kwh_{0};
  float total_discharge_energy_kwh_{0};
  uint32_t energy_last_update_ms_{0};

  // true while the ghost is actively blocking (reporting 0% SoC / 0 Ah remaining).
  // Starts true: until we've actually confirmed both real packs are full and balanced, don't
  // let the array ever read 100%.
  bool holding_{true};
  uint32_t hold_start_time_{0};
  // remembers holding_ in flash across reboots (OTA, brownout, crash) so a routine restart
  // doesn't force a full failsafe wait even though the pack(s) were already confirmed
  // full/balanced moments earlier. See setup() and evaluate_hold_().
  ESPPreferenceObject hold_state_pref_;
  // last value actually sent to hold_failsafe_remaining_sensor_ - starts at an otherwise
  // impossible value so the real first reading (often 0) still gets published instead of being
  // swallowed by the "only publish on change" check
  uint32_t hold_failsafe_remaining_published_s_{0xFFFFFFFF};

  bool pack1_seen_{false}, pack2_seen_{false};
  // millis() timestamp of the last frame2 status packet seen from each pack - used to detect a
  // pack that has gone silent (wiring fault, BMS reset, pack physically removed) so its last
  // cached reading isn't trusted indefinitely. See evaluate_hold_().
  uint32_t pack1_last_update_ms_{0}, pack2_last_update_ms_{0};
  // last-published value of each pack's data-stale binary sensor, so publish_state() is only
  // called on an actual change instead of every evaluate_hold_() tick
  bool pack1_stale_published_{false}, pack2_stale_published_{false};
  uint16_t pack1_min_mv_{0}, pack1_max_mv_{0};
  uint16_t pack2_min_mv_{0}, pack2_max_mv_{0};
  uint8_t pack1_soc_{0}, pack2_soc_{0};
  uint32_t pack1_voltage_mv_{0}, pack2_voltage_mv_{0};
  int32_t pack1_current_ma_{0}, pack2_current_ma_{0};
  int16_t pack1_temperature_c10_{0}, pack2_temperature_c10_{0};
  uint32_t pack1_rcv_voltage_mv_{0}, pack2_rcv_voltage_mv_{0};
  uint16_t pack1_cell_mv_[16]{};
  uint16_t pack2_cell_mv_[16]{};

  sensor::Sensor *pack1_min_cell_voltage_sensor_{nullptr};
  sensor::Sensor *pack1_max_cell_voltage_sensor_{nullptr};
  sensor::Sensor *pack2_min_cell_voltage_sensor_{nullptr};
  sensor::Sensor *pack2_max_cell_voltage_sensor_{nullptr};
  sensor::Sensor *pack1_soc_sensor_{nullptr};
  sensor::Sensor *pack2_soc_sensor_{nullptr};
  sensor::Sensor *ghost_fake_soc_sensor_{nullptr};
  sensor::Sensor *pack1_voltage_sensor_{nullptr};
  sensor::Sensor *pack2_voltage_sensor_{nullptr};
  sensor::Sensor *pack1_current_sensor_{nullptr};
  sensor::Sensor *pack2_current_sensor_{nullptr};
  sensor::Sensor *pack1_power_sensor_{nullptr};
  sensor::Sensor *pack2_power_sensor_{nullptr};
  sensor::Sensor *total_power_sensor_{nullptr};
  sensor::Sensor *total_current_sensor_{nullptr};
  sensor::Sensor *total_cell_voltage_diff_sensor_{nullptr};
  sensor::Sensor *pack1_temperature_sensor_{nullptr};
  sensor::Sensor *pack2_temperature_sensor_{nullptr};
  sensor::Sensor *pack1_cell_voltage_diff_sensor_{nullptr};
  sensor::Sensor *pack2_cell_voltage_diff_sensor_{nullptr};
  sensor::Sensor *average_soc_sensor_{nullptr};
  sensor::Sensor *average_voltage_sensor_{nullptr};
  sensor::Sensor *pack1_rcv_voltage_sensor_{nullptr};
  sensor::Sensor *pack2_rcv_voltage_sensor_{nullptr};
  sensor::Sensor *bus_error_count_sensor_{nullptr};
  sensor::Sensor *hold_failsafe_remaining_sensor_{nullptr};
  sensor::Sensor *total_charge_energy_sensor_{nullptr};
  sensor::Sensor *total_discharge_energy_sensor_{nullptr};
  sensor::Sensor *pack1_soh_sensor_{nullptr};
  sensor::Sensor *pack2_soh_sensor_{nullptr};
  sensor::Sensor *pack1_fault_count_sensor_{nullptr};
  sensor::Sensor *pack2_fault_count_sensor_{nullptr};
  sensor::Sensor *pack1_cell_sensors_[16]{};
  sensor::Sensor *pack2_cell_sensors_[16]{};

  text_sensor::TextSensor *hold_status_text_sensor_{nullptr};
  text_sensor::TextSensor *pack1_protection_flags_text_sensor_{nullptr};
  text_sensor::TextSensor *pack2_protection_flags_text_sensor_{nullptr};
  binary_sensor::BinarySensor *pack1_data_stale_sensor_{nullptr};
  binary_sensor::BinarySensor *pack2_data_stale_sensor_{nullptr};
  binary_sensor::BinarySensor *pack1_charge_mos_sensor_{nullptr};
  binary_sensor::BinarySensor *pack2_charge_mos_sensor_{nullptr};
  binary_sensor::BinarySensor *pack1_discharge_mos_sensor_{nullptr};
  binary_sensor::BinarySensor *pack2_discharge_mos_sensor_{nullptr};
  binary_sensor::BinarySensor *pack1_protection_active_sensor_{nullptr};
  binary_sensor::BinarySensor *pack2_protection_active_sensor_{nullptr};

  // both default to a disarmed/safe state, and are never persisted/restored across reboots by
  // this component - every boot starts fully automatic and disarmed, same as holding_ starting true
  bool manual_override_armed_{false};
  uint8_t manual_force_soc_{0};
};

}  // namespace jkbms_ghost_battery
}  // namespace esphome
