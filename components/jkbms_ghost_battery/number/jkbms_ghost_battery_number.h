#pragma once

#include "esphome/components/number/number.h"
#include "../jkbms_ghost_battery.h"

namespace esphome {
namespace jkbms_ghost_battery {

// Only takes effect while the "manual override armed" switch is on: this value (0 or 100,
// step-restricted to just those two positions) is what the ghost reports instead of its
// automatic evaluation. Harmless to move while disarmed - it just won't do anything until armed.
class ManualForceSocNumber : public number::Number {
 public:
  void set_parent(JkBmsGhostBattery *parent) { this->parent_ = parent; }

 protected:
  void control(float value) override {
    this->parent_->set_manual_force_soc((uint8_t) value);
    this->publish_state(value);
  }

  JkBmsGhostBattery *parent_;
};

}  // namespace jkbms_ghost_battery
}  // namespace esphome
