#pragma once

#include "esphome/core/component.h"
#include "esphome/core/hal.h"
#include "esphome/components/uart/uart.h"
#include "esphome/components/sensor/sensor.h"

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
  void set_reset_soc_percent(uint8_t percent) { this->reset_soc_percent_ = percent; }
  void set_hold_failsafe_ms(uint32_t ms) { this->hold_failsafe_ms_ = ms; }

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
  bool is_holding_() { return this->manual_override_armed_ ? (this->manual_force_soc_ < 50) : this->holding_; }
  uint16_t crc16_(uint16_t len);

  GPIOPin *de_pin_{nullptr};
  uint8_t ghost_address_{15};
  uint8_t pack_count_{2};
  uint8_t pack1_address_{0};
  uint8_t pack2_address_{1};
  uint16_t cell_full_low_mv_{3460};
  uint16_t cell_balance_tolerance_mv_{20};
  uint8_t reset_soc_percent_{99};
  uint32_t hold_failsafe_ms_{0};

  uint8_t buf_[JK_FRAME_SIZE];
  uint16_t num_bytes_{0};
  uint32_t last_byte_time_{0};

  // true while the ghost is actively blocking (reporting 0% SoC / 0 Ah remaining).
  // Starts true: until we've actually confirmed both real packs are full and balanced, don't
  // let the array ever read 100%.
  bool holding_{true};
  uint32_t hold_start_time_{0};

  bool pack1_seen_{false}, pack2_seen_{false};
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
  sensor::Sensor *pack1_cell_sensors_[16]{};
  sensor::Sensor *pack2_cell_sensors_[16]{};

  // both default to a disarmed/safe state, and are never persisted/restored across reboots by
  // this component - every boot starts fully automatic and disarmed, same as holding_ starting true
  bool manual_override_armed_{false};
  uint8_t manual_force_soc_{0};
};

}  // namespace jkbms_ghost_battery
}  // namespace esphome
