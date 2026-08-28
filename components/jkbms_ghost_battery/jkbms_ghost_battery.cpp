#include "jkbms_ghost_battery.h"
#include "esphome/core/log.h"
#include <cstring>

namespace esphome {
namespace jkbms_ghost_battery {

static const char *const TAG = "jkbms_ghost_battery";

// Static, pre-captured response frames from a JK PB2A16S30P V19A (16S LiFePO4) battery at RS485
// address 0x0F. Ported unchanged from the Arduino JKModbusSlave library, including the 36Ah
// capacity patch (capacity fields = A0 8C 00 00 little-endian mAh). Everything else in these
// templates is a frozen snapshot from that one capture (eg. cell voltages, total voltage) except
// where send_frame2_() below patches it at runtime: SoC (byte 173), remaining-capacity (bytes
// 174-177), and temperature (bytes 162-163, set to the average of whichever real pack(s) have
// been seen so far).
static const uint8_t FRAME1_RESPONSE[JK_FRAME_SIZE] = {0x55, 0xAA, 0xEB, 0x90, 0x01, 0x05, 0xAC, 0x0D, 0x00, 0x00, 0x28, 0x0A, 0x00, 0x00, 0x5A, 0x0A, 0x00, 0x00, 0x10, 0x0E, 0x00, 0x00, 0x78, 0x0D, 0x00, 0x00, 0x0A, 0x00, 0x00, 0x00, 0x79, 0x0D, 0x00, 0x00, 0x50, 0x0A, 0x00, 0x00, 0x7A, 0x0D, 0x00, 0x00, 0x16, 0x0D, 0x00, 0x00, 0xC4, 0x09, 0x00, 0x00, 0xE8, 0x03, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00, 0x3C, 0x00, 0x00, 0x00, 0xE8, 0x03, 0x00, 0x00, 0x2C, 0x01, 0x00, 0x00, 0x3C, 0x00, 0x00, 0x00, 0x05, 0x00, 0x00, 0x00, 0xA0, 0x8C, 0x00, 0x00, 0xBC, 0x02, 0x00, 0x00, 0x58, 0x02, 0x00, 0x00, 0xBC, 0x02, 0x00, 0x00, 0x58, 0x02, 0x00, 0x00, 0x38, 0xFF, 0xFF, 0xFF, 0x9C, 0xFF, 0xFF, 0xFF, 0xE8, 0x03, 0x00, 0x00, 0x20, 0x03, 0x00, 0x00, 0x10, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0xA0, 0x8C, 0x00, 0x00, 0xDC, 0x05, 0x00, 0x00, 0x48, 0x0D, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0F, 0x00, 0x00, 0x00, 0x05, 0x00, 0x00, 0x00, 0x60, 0xE3, 0x16, 0x00, 0x00, 0x02, 0x3C, 0x32, 0x18, 0xFE, 0xFF, 0xFF, 0xFF, 0x9F, 0xE9, 0x05, 0x02, 0x00, 0x00, 0x00, 0x00, 0x82, 0x0F, 0x10, 0x16, 0x1E, 0x00, 0x01, 0x64, 0xA9};

static const uint8_t FRAME2_RESPONSE[JK_FRAME_SIZE] = {0x55, 0xAA, 0xEB, 0x90, 0x02, 0x05, 0x0D, 0x0D, 0x0D, 0x0D, 0x0E, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0C, 0x0D, 0x0E, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0E, 0x0D, 0x0E, 0x0D, 0x0E, 0x0D, 0x0D, 0x0D, 0x0E, 0x0D, 0x0E, 0x0D, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFF, 0xFF, 0x00, 0x00, 0x0D, 0x0D, 0x02, 0x00, 0x04, 0x07, 0x4A, 0x00, 0x49, 0x00, 0x4E, 0x00, 0x4C, 0x00, 0x50, 0x00, 0x49, 0x00, 0x4C, 0x00, 0x4A, 0x00, 0x4E, 0x00, 0x4A, 0x00, 0x4D, 0x00, 0x4B, 0x00, 0x50, 0x00, 0x4D, 0x00, 0x50, 0x00, 0x50, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x2F, 0x01, 0x00, 0x00, 0x00, 0x00, 0xD5, 0xD0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x13, 0x01, 0x12, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xA0, 0x8C, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x99, 0x05, 0x00, 0x00, 0x64, 0x00, 0x00, 0x00, 0x1A, 0xD7, 0x8E, 0x00, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFF, 0x00, 0x01, 0x00, 0x00, 0x00, 0x9D, 0x03, 0x00, 0x00, 0x00, 0x00, 0x40, 0x72, 0x40, 0x40, 0x00, 0x00, 0x00, 0x00, 0xE2, 0x14, 0x00, 0x00, 0x00, 0x01, 0x01, 0x01, 0x00, 0x06, 0x00, 0x00, 0x92, 0x31, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x2F, 0x01, 0x12, 0x01, 0x12, 0x01, 0x9D, 0x03, 0x1F, 0xB6, 0x8E, 0x08, 0x8E, 0x00, 0x00, 0x00, 0x80, 0x51, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFE, 0xFF, 0x7F, 0xDC, 0x2F, 0x01, 0x01, 0xB0, 0x07, 0x00, 0x00, 0x00, 0x55, 0x0F, 0x10, 0x16, 0x20, 0x00, 0x01, 0x05, 0x65};

static const uint8_t FRAME3_RESPONSE[JK_FRAME_SIZE] = {0x55, 0xAA, 0xEB, 0x90, 0x03, 0x05, 0x4A, 0x4B, 0x5F, 0x50, 0x42, 0x32, 0x41, 0x31, 0x36, 0x53, 0x32, 0x30, 0x50, 0x00, 0x00, 0x00, 0x31, 0x35, 0x41, 0x00, 0x00, 0x00, 0x00, 0x00, 0x31, 0x35, 0x2E, 0x32, 0x34, 0x00, 0x00, 0x00, 0x04, 0xD6, 0x8E, 0x00, 0x27, 0x00, 0x00, 0x00, 0x4A, 0x4B, 0x5F, 0x50, 0x42, 0x32, 0x41, 0x31, 0x36, 0x53, 0x32, 0x30, 0x50, 0x00, 0x00, 0x00, 0x31, 0x32, 0x33, 0x34, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x32, 0x34, 0x30, 0x32, 0x31, 0x39, 0x00, 0x00, 0x33, 0x31, 0x32, 0x31, 0x33, 0x34, 0x39, 0x30, 0x38, 0x39, 0x38, 0x00, 0x30, 0x30, 0x30, 0x00, 0x47, 0x68, 0x6F, 0x73, 0x74, 0x20, 0x42, 0x61, 0x74, 0x74, 0x65, 0x72, 0x79, 0x00, 0x00, 0x00, 0x33, 0x31, 0x34, 0x31, 0x35, 0x39, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFE, 0xFF, 0xFF, 0xFF, 0x8F, 0xE9, 0x05, 0x02, 0x00, 0x00, 0x00, 0x00, 0x90, 0x1F, 0x00, 0x00, 0x00, 0x00, 0xC0, 0xD8, 0xE7, 0xFE, 0x3F, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0B, 0xCF, 0x27, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xDF, 0x0F, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0xCF, 0x27, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x09, 0x08, 0x00, 0x01, 0x64, 0x00, 0x00, 0x00, 0x5F, 0x00, 0x00, 0x00, 0x3C, 0x00, 0x00, 0x00, 0x32, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x10, 0x0E, 0x00, 0x00, 0x0A, 0x0A, 0x01, 0x1E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFE, 0x9F, 0xE9, 0xFF, 0x0F, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x73, 0x0F, 0x10, 0x16, 0x1C, 0x00, 0x01, 0xC5, 0x69};

// byte offsets within a 308-byte frame2 status packet - see JKModbusSlave.cpp in the Arduino
// versions of this project for how these were reverse engineered / verified
static const uint16_t SOC_OFFSET = 173;
static const uint16_t REMAINING_CAPACITY_OFFSET = 174;
static const uint16_t CHECKSUM_OFFSET = 299;
static const uint16_t SOURCE_ADDRESS_OFFSET = 300;
static const uint16_t CELL_VOLTAGE_OFFSET = 6;
static const uint8_t CELL_COUNT = 16;
// cross-checked: sum of the 16 cell voltages matches TOTAL_VOLTAGE_OFFSET to within 1mV, and
// CURRENT_OFFSET/TEMPERATURE_OFFSET read plausible values (0.00A idle, ~27C) against a real capture
static const uint16_t TOTAL_VOLTAGE_OFFSET = 150;  // 4 bytes little-endian, mV
static const uint16_t CURRENT_OFFSET = 158;        // 4 bytes little-endian signed, mA
static const uint16_t TEMPERATURE_OFFSET = 162;    // 2 bytes little-endian signed, 0.1 degC (T1 probe)

// byte offset within a 308-byte frame1 (0x01, settings) packet - unlike frame2, frame1's data[]
// alignment matches the raw frame directly (verified: our capture's cell count field at raw114
// reads 16, and nominal capacity at raw130 reads 36000, both matching esphome-jk-bms's data[]
// offsets exactly with no shift needed)
static const uint16_t RCV_OFFSET = 38;  // "rated/requested charge voltage", 4 bytes little-endian, mV

void JkBmsGhostBattery::setup() {
  if (this->de_pin_ != nullptr) {
    this->de_pin_->setup();
    this->de_pin_->digital_write(false);
  }
  this->hold_start_time_ = millis();
  // starts holding (see holding_ default above) until a pack is seen and confirmed full/balanced
  this->publish_hold_status_("holding - waiting for pack data");
}

void JkBmsGhostBattery::dump_config() {
  ESP_LOGCONFIG(TAG, "JK BMS Ghost Battery:");
  ESP_LOGCONFIG(TAG, "  Ghost address: %u", this->ghost_address_);
  ESP_LOGCONFIG(TAG, "  Pack count: %u", this->pack_count_);
  ESP_LOGCONFIG(TAG, "  Pack 1 (master) address: %u", this->pack1_address_);
  if (this->pack_count_ >= 2) ESP_LOGCONFIG(TAG, "  Pack 2 address: %u", this->pack2_address_);
  ESP_LOGCONFIG(TAG, "  Cell full voltage: >= %u mV", this->cell_full_low_mv_);
  ESP_LOGCONFIG(TAG, "  Cell balance tolerance: %u mV", this->cell_balance_tolerance_mv_);
  ESP_LOGCONFIG(TAG, "  Reset SoC: %u%%", this->reset_soc_percent_);
  ESP_LOGCONFIG(TAG, "  Hold failsafe: %u min", (unsigned) (this->hold_failsafe_ms_ / 60000));
  ESP_LOGCONFIG(TAG, "  Pack data stale timeout: %u s", (unsigned) (this->pack_stale_timeout_ms_ / 1000));
  LOG_PIN("  DE Pin: ", this->de_pin_);
  LOG_SENSOR("  ", "Pack 1 min cell voltage", this->pack1_min_cell_voltage_sensor_);
  LOG_SENSOR("  ", "Pack 1 max cell voltage", this->pack1_max_cell_voltage_sensor_);
  LOG_SENSOR("  ", "Pack 2 min cell voltage", this->pack2_min_cell_voltage_sensor_);
  LOG_SENSOR("  ", "Pack 2 max cell voltage", this->pack2_max_cell_voltage_sensor_);
  LOG_SENSOR("  ", "Pack 1 SoC", this->pack1_soc_sensor_);
  LOG_SENSOR("  ", "Pack 2 SoC", this->pack2_soc_sensor_);
  LOG_SENSOR("  ", "Ghost fake SoC", this->ghost_fake_soc_sensor_);
  LOG_SENSOR("  ", "Pack 1 voltage", this->pack1_voltage_sensor_);
  LOG_SENSOR("  ", "Pack 2 voltage", this->pack2_voltage_sensor_);
  LOG_SENSOR("  ", "Pack 1 current", this->pack1_current_sensor_);
  LOG_SENSOR("  ", "Pack 2 current", this->pack2_current_sensor_);
  LOG_SENSOR("  ", "Pack 1 power", this->pack1_power_sensor_);
  LOG_SENSOR("  ", "Pack 2 power", this->pack2_power_sensor_);
  LOG_SENSOR("  ", "Total power", this->total_power_sensor_);
  LOG_SENSOR("  ", "Total current", this->total_current_sensor_);
  LOG_SENSOR("  ", "Total cell voltage diff", this->total_cell_voltage_diff_sensor_);
  LOG_SENSOR("  ", "Pack 1 temperature", this->pack1_temperature_sensor_);
  LOG_SENSOR("  ", "Pack 2 temperature", this->pack2_temperature_sensor_);
  LOG_SENSOR("  ", "Pack 1 cell voltage diff", this->pack1_cell_voltage_diff_sensor_);
  LOG_SENSOR("  ", "Pack 2 cell voltage diff", this->pack2_cell_voltage_diff_sensor_);
  LOG_SENSOR("  ", "Average SoC", this->average_soc_sensor_);
  LOG_SENSOR("  ", "Average voltage", this->average_voltage_sensor_);
  LOG_SENSOR("  ", "Pack 1 RCV (rated charge voltage)", this->pack1_rcv_voltage_sensor_);
  LOG_SENSOR("  ", "Pack 2 RCV (rated charge voltage)", this->pack2_rcv_voltage_sensor_);
  LOG_TEXT_SENSOR("  ", "Hold status", this->hold_status_text_sensor_);
  LOG_BINARY_SENSOR("  ", "Pack 1 data stale", this->pack1_data_stale_sensor_);
  LOG_BINARY_SENSOR("  ", "Pack 2 data stale", this->pack2_data_stale_sensor_);
}

void JkBmsGhostBattery::loop() {
  while (this->available()) {
    if (this->num_bytes_ >= JK_FRAME_SIZE) {
      // more bytes than a single frame holds without a gap - resync
      this->num_bytes_ = 0;
    }
    this->buf_[this->num_bytes_++] = this->read();
    this->last_byte_time_ = millis();
  }

  if (this->num_bytes_ > 0 && (millis() - this->last_byte_time_) >= JK_FRAME_GAP_MS) {
    this->handle_frame_();
    this->num_bytes_ = 0;
  }

  // Re-check staleness even when nothing arrived this tick: evaluate_hold_() is otherwise only
  // reached from sniff_real_pack_() below, ie. only when at least one real pack is still talking.
  // If ALL configured packs go completely silent while released (total bus/wiring failure), that
  // path would never fire again and the ghost would keep reporting 100% forever. This unconditional
  // call is cheap (a few integer comparisons, no I/O) and lets the staleness check in
  // evaluate_hold_() catch that case too.
  this->evaluate_hold_();
}

void JkBmsGhostBattery::handle_frame_() {
  // passively sniff every frame that goes by, regardless of who it's addressed to
  this->sniff_real_pack_();

  if (!this->is_query_for_us_()) return;

  switch (this->buf_[3]) {  // JK frame type byte
    case 0x1E:
      this->send_frame1_();
      break;
    case 0x20:
      this->send_frame2_();
      break;
    case 0x1C:
      this->send_frame3_();
      break;
    default:
      break;
  }
}

bool JkBmsGhostBattery::is_query_for_us_() {
  // a real query is: address, 0x10, 0x16, frame_type, 0x00, 0x01, 2-byte length, data, 2-byte CRC
  if (this->num_bytes_ < 11) return false;
  if (this->buf_[1] != 0x10 || this->buf_[2] != 0x16) return false;
  if (this->buf_[0] != this->ghost_address_ && this->buf_[0] != 0) return false;

  uint16_t expected = this->crc16_(this->num_bytes_ - 2);
  uint16_t actual = ((uint16_t) this->buf_[this->num_bytes_ - 1] << 8) | this->buf_[this->num_bytes_ - 2];
  return expected == actual;
}

void JkBmsGhostBattery::send_frame1_() {
  memcpy(this->buf_, FRAME1_RESPONSE, JK_FRAME_SIZE);
  // the captured template hardcodes its source pack's own address (0x0F) at this offset; patch
  // it to whatever ghost_address is actually configured so the frame is internally consistent
  this->buf_[SOURCE_ADDRESS_OFFSET] = this->ghost_address_;
  this->send_response_(JK_FRAME_SIZE);
}

void JkBmsGhostBattery::send_frame2_() {
  memcpy(this->buf_, FRAME2_RESPONSE, JK_FRAME_SIZE);

  // the captured template hardcodes its source pack's own address (0x0F) at this offset; patch
  // it to whatever ghost_address is actually configured. Only matters when ghost_address is set
  // to something other than the default 15 - otherwise this is a no-op, since 15 == 0x0F is
  // exactly what the template already contains. Must happen before the checksum recompute below.
  this->buf_[SOURCE_ADDRESS_OFFSET] = this->ghost_address_;

  // TEST: hold the ghost's reported SoC at 0% until both real packs are confirmed full and
  // balanced (see evaluate_hold_()); then switch to 100%/full so the inverter gets a genuine
  // full-charge signal and actually stops charging. is_holding_() lets an armed manual override
  // substitute its own forced value here instead of the automatic evaluation.
  bool holding_now = this->is_holding_();
  if (holding_now) {
    this->buf_[SOC_OFFSET] = 0;
    this->buf_[REMAINING_CAPACITY_OFFSET + 0] = 0x00;
    this->buf_[REMAINING_CAPACITY_OFFSET + 1] = 0x00;
    this->buf_[REMAINING_CAPACITY_OFFSET + 2] = 0x00;
    this->buf_[REMAINING_CAPACITY_OFFSET + 3] = 0x00;
  } else {
    this->buf_[SOC_OFFSET] = 100;
    this->buf_[REMAINING_CAPACITY_OFFSET + 0] = 0xA0;  // 36 Ah (36000 mAh, little-endian)
    this->buf_[REMAINING_CAPACITY_OFFSET + 1] = 0x8C;
    this->buf_[REMAINING_CAPACITY_OFFSET + 2] = 0x00;
    this->buf_[REMAINING_CAPACITY_OFFSET + 3] = 0x00;
  }
  if (this->ghost_fake_soc_sensor_ != nullptr) this->ghost_fake_soc_sensor_->publish_state(holding_now ? 0 : 100);

  // report the average of both real packs' temperature instead of the static ~27.5C baked into
  // the template. If only one pack has been seen so far, use that one; if neither has, leave the
  // template's static value in place (this also means the ghost works fine with just one real
  // pack connected - it just never gets to the "average of two" case).
  int16_t temp_c10;
  bool have_temp = true;
  if (this->pack1_seen_ && this->pack2_seen_) {
    temp_c10 = (int16_t) ((this->pack1_temperature_c10_ + this->pack2_temperature_c10_) / 2);
  } else if (this->pack1_seen_) {
    temp_c10 = this->pack1_temperature_c10_;
  } else if (this->pack2_seen_) {
    temp_c10 = this->pack2_temperature_c10_;
  } else {
    have_temp = false;
  }
  if (have_temp) {
    this->buf_[TEMPERATURE_OFFSET + 0] = (uint8_t) (temp_c10 & 0xFF);
    this->buf_[TEMPERATURE_OFFSET + 1] = (uint8_t) ((temp_c10 >> 8) & 0xFF);
  }

  // recompute the JK payload checksum (simple byte sum over bytes 0-298) since the SoC/capacity
  // fields above were just modified
  uint16_t sum = 0;
  for (uint16_t i = 0; i < CHECKSUM_OFFSET; i++) sum += this->buf_[i];
  this->buf_[CHECKSUM_OFFSET] = (uint8_t) (sum & 0xFF);

  this->send_response_(JK_FRAME_SIZE);
}

void JkBmsGhostBattery::send_frame3_() {
  memcpy(this->buf_, FRAME3_RESPONSE, JK_FRAME_SIZE);
  // the captured template hardcodes its source pack's own address (0x0F) at this offset; patch
  // it to whatever ghost_address is actually configured so the frame is internally consistent
  this->buf_[SOURCE_ADDRESS_OFFSET] = this->ghost_address_;
  this->send_response_(JK_FRAME_SIZE);
}

void JkBmsGhostBattery::send_response_(uint16_t len) {
  if (this->de_pin_ != nullptr) this->de_pin_->digital_write(true);
  this->write_array(this->buf_, len);
  this->flush();
  if (this->de_pin_ != nullptr) this->de_pin_->digital_write(false);
}

void JkBmsGhostBattery::sniff_real_pack_() {
  // only real JK responses (0x55 0xAA 0xEB 0x90) carry live data - covers both frame types below
  if (this->num_bytes_ < JK_FRAME_SIZE) return;
  if (!(this->buf_[0] == 0x55 && this->buf_[1] == 0xAA && this->buf_[2] == 0xEB && this->buf_[3] == 0x90))
    return;

  uint8_t source_address = this->buf_[SOURCE_ADDRESS_OFFSET];
  // in single-pack mode (pack_count_ == 1), pack2_address_ is ignored entirely - only pack1 exists
  bool matches_pack2 = this->pack_count_ >= 2 && source_address == this->pack2_address_;
  if (source_address != this->pack1_address_ && !matches_pack2) return;

  // settings frame (0x01) from either pack - this is where RCV (rated charge voltage) lives.
  // Passive only: we never query for this ourselves, so it only updates if something else on the
  // bus happens to request that pack's settings frame.
  if (this->buf_[4] == 0x01) {
    uint32_t rcv_mv = this->buf_[RCV_OFFSET] | ((uint32_t) this->buf_[RCV_OFFSET + 1] << 8) |
                      ((uint32_t) this->buf_[RCV_OFFSET + 2] << 16) | ((uint32_t) this->buf_[RCV_OFFSET + 3] << 24);
    if (source_address == this->pack1_address_) {
      this->pack1_rcv_voltage_mv_ = rcv_mv;
      if (this->pack1_rcv_voltage_sensor_ != nullptr) this->pack1_rcv_voltage_sensor_->publish_state(rcv_mv / 1000.0f);
    } else {
      this->pack2_rcv_voltage_mv_ = rcv_mv;
      if (this->pack2_rcv_voltage_sensor_ != nullptr) this->pack2_rcv_voltage_sensor_->publish_state(rcv_mv / 1000.0f);
    }
    ESP_LOGD(TAG, "Pack 0x%02X settings: RCV %.3fV", source_address, rcv_mv / 1000.0f);
    return;
  }

  if (this->buf_[4] != 0x02) return;  // only frame2 (status) carries cell/current/temp data

  uint16_t min_mv = 0xFFFF;
  uint16_t max_mv = 0;
  uint16_t cell_mv[CELL_COUNT];
  for (uint8_t cell = 0; cell < CELL_COUNT; cell++) {
    uint16_t idx = CELL_VOLTAGE_OFFSET + cell * 2;
    uint16_t mv = this->buf_[idx] | ((uint16_t) this->buf_[idx + 1] << 8);
    cell_mv[cell] = mv;
    if (mv < min_mv) min_mv = mv;
    if (mv > max_mv) max_mv = mv;
  }
  uint8_t soc = this->buf_[SOC_OFFSET];
  uint32_t voltage_mv = this->buf_[TOTAL_VOLTAGE_OFFSET] | ((uint32_t) this->buf_[TOTAL_VOLTAGE_OFFSET + 1] << 8) |
                        ((uint32_t) this->buf_[TOTAL_VOLTAGE_OFFSET + 2] << 16) | ((uint32_t) this->buf_[TOTAL_VOLTAGE_OFFSET + 3] << 24);
  int32_t current_ma = (int32_t) (this->buf_[CURRENT_OFFSET] | ((uint32_t) this->buf_[CURRENT_OFFSET + 1] << 8) |
                        ((uint32_t) this->buf_[CURRENT_OFFSET + 2] << 16) | ((uint32_t) this->buf_[CURRENT_OFFSET + 3] << 24));
  int16_t temperature_c10 = (int16_t) (this->buf_[TEMPERATURE_OFFSET] | ((uint16_t) this->buf_[TEMPERATURE_OFFSET + 1] << 8));

  if (source_address == this->pack1_address_) {
    this->pack1_min_mv_ = min_mv;
    this->pack1_max_mv_ = max_mv;
    this->pack1_soc_ = soc;
    this->pack1_voltage_mv_ = voltage_mv;
    this->pack1_current_ma_ = current_ma;
    this->pack1_temperature_c10_ = temperature_c10;
    this->pack1_seen_ = true;
    this->pack1_last_update_ms_ = millis();
    if (this->pack1_min_cell_voltage_sensor_ != nullptr) this->pack1_min_cell_voltage_sensor_->publish_state(min_mv / 1000.0f);
    if (this->pack1_max_cell_voltage_sensor_ != nullptr) this->pack1_max_cell_voltage_sensor_->publish_state(max_mv / 1000.0f);
    if (this->pack1_cell_voltage_diff_sensor_ != nullptr) this->pack1_cell_voltage_diff_sensor_->publish_state((max_mv - min_mv) / 1000.0f);
    if (this->pack1_soc_sensor_ != nullptr) this->pack1_soc_sensor_->publish_state(soc);
    if (this->pack1_voltage_sensor_ != nullptr) this->pack1_voltage_sensor_->publish_state(voltage_mv / 1000.0f);
    if (this->pack1_current_sensor_ != nullptr) this->pack1_current_sensor_->publish_state(current_ma / 1000.0f);
    if (this->pack1_temperature_sensor_ != nullptr) this->pack1_temperature_sensor_->publish_state(temperature_c10 / 10.0f);
    if (this->pack1_power_sensor_ != nullptr)
      this->pack1_power_sensor_->publish_state((voltage_mv / 1000.0f) * (current_ma / 1000.0f) / 1000.0f);
    for (uint8_t c = 0; c < CELL_COUNT; c++) {
      this->pack1_cell_mv_[c] = cell_mv[c];
      if (this->pack1_cell_sensors_[c] != nullptr) this->pack1_cell_sensors_[c]->publish_state(cell_mv[c] / 1000.0f);
    }
  } else {
    this->pack2_min_mv_ = min_mv;
    this->pack2_max_mv_ = max_mv;
    this->pack2_soc_ = soc;
    this->pack2_voltage_mv_ = voltage_mv;
    this->pack2_current_ma_ = current_ma;
    this->pack2_temperature_c10_ = temperature_c10;
    this->pack2_seen_ = true;
    this->pack2_last_update_ms_ = millis();
    if (this->pack2_min_cell_voltage_sensor_ != nullptr) this->pack2_min_cell_voltage_sensor_->publish_state(min_mv / 1000.0f);
    if (this->pack2_max_cell_voltage_sensor_ != nullptr) this->pack2_max_cell_voltage_sensor_->publish_state(max_mv / 1000.0f);
    if (this->pack2_cell_voltage_diff_sensor_ != nullptr) this->pack2_cell_voltage_diff_sensor_->publish_state((max_mv - min_mv) / 1000.0f);
    if (this->pack2_soc_sensor_ != nullptr) this->pack2_soc_sensor_->publish_state(soc);
    if (this->pack2_voltage_sensor_ != nullptr) this->pack2_voltage_sensor_->publish_state(voltage_mv / 1000.0f);
    if (this->pack2_current_sensor_ != nullptr) this->pack2_current_sensor_->publish_state(current_ma / 1000.0f);
    if (this->pack2_temperature_sensor_ != nullptr) this->pack2_temperature_sensor_->publish_state(temperature_c10 / 10.0f);
    if (this->pack2_power_sensor_ != nullptr)
      this->pack2_power_sensor_->publish_state((voltage_mv / 1000.0f) * (current_ma / 1000.0f) / 1000.0f);
    for (uint8_t c = 0; c < CELL_COUNT; c++) {
      this->pack2_cell_mv_[c] = cell_mv[c];
      if (this->pack2_cell_sensors_[c] != nullptr) this->pack2_cell_sensors_[c]->publish_state(cell_mv[c] / 1000.0f);
    }
  }

  // in single-pack mode, the "average" is just pack1's own value
  if (this->pack1_seen_ && (this->pack_count_ < 2 || this->pack2_seen_)) {
    float divisor = this->pack_count_ >= 2 ? 2.0f : 1.0f;
    float soc_total = this->pack1_soc_ + (this->pack_count_ >= 2 ? this->pack2_soc_ : 0);
    float voltage_total_mv = this->pack1_voltage_mv_ + (this->pack_count_ >= 2 ? this->pack2_voltage_mv_ : 0);
    if (this->average_soc_sensor_ != nullptr) this->average_soc_sensor_->publish_state(soc_total / divisor);
    if (this->average_voltage_sensor_ != nullptr) this->average_voltage_sensor_->publish_state(voltage_total_mv / divisor / 1000.0f);

    // totals are a straight sum, not an average - in single-pack mode this is just pack1's own value
    float total_current_a = this->pack1_current_ma_ / 1000.0f + (this->pack_count_ >= 2 ? this->pack2_current_ma_ / 1000.0f : 0.0f);
    float pack1_power_kw = (this->pack1_voltage_mv_ / 1000.0f) * (this->pack1_current_ma_ / 1000.0f) / 1000.0f;
    float pack2_power_kw = this->pack_count_ >= 2 ? (this->pack2_voltage_mv_ / 1000.0f) * (this->pack2_current_ma_ / 1000.0f) / 1000.0f : 0.0f;
    if (this->total_current_sensor_ != nullptr) this->total_current_sensor_->publish_state(total_current_a);
    if (this->total_power_sensor_ != nullptr) this->total_power_sensor_->publish_state(pack1_power_kw + pack2_power_kw);

    // highest cell minus lowest cell across ALL cells on ALL configured packs (not per-pack)
    uint16_t total_min_mv = this->pack1_min_mv_;
    uint16_t total_max_mv = this->pack1_max_mv_;
    if (this->pack_count_ >= 2) {
      if (this->pack2_min_mv_ < total_min_mv) total_min_mv = this->pack2_min_mv_;
      if (this->pack2_max_mv_ > total_max_mv) total_max_mv = this->pack2_max_mv_;
    }
    if (this->total_cell_voltage_diff_sensor_ != nullptr)
      this->total_cell_voltage_diff_sensor_->publish_state((total_max_mv - total_min_mv) / 1000.0f);
  }

  ESP_LOGD(TAG, "Pack 0x%02X cells: %u-%u mV, SoC %u%%, %.2fV, %.2fA, %.1fC",
           source_address, min_mv, max_mv, soc, voltage_mv / 1000.0f, current_ma / 1000.0f, temperature_c10 / 10.0f);

  // evaluate_hold_() is also called unconditionally at the end of loop() (so total silence from
  // every pack is caught too) - no need to call it again here as well.
}

void JkBmsGhostBattery::evaluate_hold_() {
  uint32_t now = millis();
  // "fresh" means we've seen this pack at least once AND its last update wasn't too long ago -
  // guards against evaluating full/balanced (or re-arm) decisions off a stale cached reading from
  // a pack that has since gone silent (wiring fault, BMS reset, pack physically disconnected).
  bool pack1_fresh = this->pack1_seen_ && (now - this->pack1_last_update_ms_) < this->pack_stale_timeout_ms_;
  // in single-pack mode (pack_count_ == 1), pack2 is never required, so it's vacuously "fresh"
  bool pack2_fresh = this->pack_count_ < 2 ||
                      (this->pack2_seen_ && (now - this->pack2_last_update_ms_) < this->pack_stale_timeout_ms_);

  // dedicated stale sensors, one per pack - only publish on change so this doesn't spam the
  // Home Assistant entity history on every single loop() tick
  bool pack1_stale = this->pack1_seen_ && !pack1_fresh;
  if (this->pack1_data_stale_sensor_ != nullptr && pack1_stale != this->pack1_stale_published_) {
    this->pack1_data_stale_sensor_->publish_state(pack1_stale);
    this->pack1_stale_published_ = pack1_stale;
  }
  bool pack2_stale = this->pack_count_ >= 2 && this->pack2_seen_ && !pack2_fresh;
  if (this->pack2_data_stale_sensor_ != nullptr && pack2_stale != this->pack2_stale_published_) {
    this->pack2_data_stale_sensor_->publish_state(pack2_stale);
    this->pack2_stale_published_ = pack2_stale;
  }

  if (this->holding_) {
    bool pack1_ok = pack1_fresh && this->pack1_min_mv_ >= this->cell_full_low_mv_ &&
                     (this->pack1_max_mv_ - this->pack1_min_mv_) <= this->cell_balance_tolerance_mv_;
    bool pack2_ok = this->pack_count_ < 2 ||
                    (pack2_fresh && this->pack2_min_mv_ >= this->cell_full_low_mv_ &&
                     (this->pack2_max_mv_ - this->pack2_min_mv_) <= this->cell_balance_tolerance_mv_);

    if (pack1_ok && pack2_ok) {
      this->holding_ = false;
      ESP_LOGI(TAG, "Pack(s) balanced (<=%u mV spread) and full (>=%u mV) - releasing ghost SoC to 100%%",
               this->cell_balance_tolerance_mv_, this->cell_full_low_mv_);
      this->publish_hold_status_("released - balanced and full");
    } else if (this->hold_failsafe_ms_ > 0 && (now - this->hold_start_time_) >= this->hold_failsafe_ms_) {
      this->holding_ = false;
      ESP_LOGW(TAG, "SoC hold failsafe reached - releasing to 100%% without confirmed balance");
      this->publish_hold_status_("released - failsafe (balance not confirmed)");
    }
  } else {
    bool pack2_low = this->pack_count_ >= 2 && this->pack2_seen_ && this->pack2_soc_ <= this->reset_soc_percent_;
    bool went_stale = !pack1_fresh || !pack2_fresh;
    if ((this->pack1_seen_ && this->pack1_soc_ <= this->reset_soc_percent_) || pack2_low || went_stale) {
      this->holding_ = true;
      this->hold_start_time_ = now;
      if (went_stale) {
        // defensive re-arm: we can no longer confirm the pack(s) are actually still full/balanced,
        // so don't keep telling the bus 100% on the strength of a reading that's no longer trusted
        ESP_LOGW(TAG, "Real pack data went stale (no update for >=%u ms) - re-arming ghost SoC hold to 0%% as a precaution",
                 (unsigned) this->pack_stale_timeout_ms_);
        this->publish_hold_status_("holding - re-armed (data stale)");
      } else {
        ESP_LOGI(TAG, "Real pack SoC reached %u%% - re-arming ghost SoC hold to 0%%", this->reset_soc_percent_);
        this->publish_hold_status_("holding - re-armed (SoC dropped)");
      }
    }
  }
}

void JkBmsGhostBattery::publish_hold_status_(const char *status) {
  if (this->hold_status_text_sensor_ != nullptr)
    this->hold_status_text_sensor_->publish_state(status);
}

uint16_t JkBmsGhostBattery::crc16_(uint16_t len) {
  uint16_t value = 0xFFFF;
  for (uint16_t i = 0; i < len; i++) {
    value ^= (uint16_t) this->buf_[i];
    for (uint8_t j = 0; j < 8; j++) {
      bool lsb = value & 1;
      value >>= 1;
      if (lsb) value ^= 0xA001;
    }
  }
  return value;
}

}  // namespace jkbms_ghost_battery
}  // namespace esphome
