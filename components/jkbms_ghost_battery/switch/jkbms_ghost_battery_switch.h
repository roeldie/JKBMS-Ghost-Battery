#pragma once

#include "esphome/components/switch/switch.h"
#include "../jkbms_ghost_battery.h"

namespace esphome {
namespace jkbms_ghost_battery {

// Two-step interlock: this switch must be turned on before ManualForceFullSwitch has any
// effect. Not persisted/restored by this component - always starts off after a reboot.
class ManualOverrideArmedSwitch : public switch_::Switch {
 public:
  void set_parent(JkBmsGhostBattery *parent) { this->parent_ = parent; }
  void write_state(bool state) override {
    this->parent_->set_manual_override_armed(state);
    this->publish_state(state);
  }

 protected:
  JkBmsGhostBattery *parent_;
};

// Only takes effect while ManualOverrideArmedSwitch is on: true forces the ghost to report
// 100%, false forces it to report 0%. Harmless to flip while disarmed - it just won't do
// anything until armed.
class ManualForceFullSwitch : public switch_::Switch {
 public:
  void set_parent(JkBmsGhostBattery *parent) { this->parent_ = parent; }
  void write_state(bool state) override {
    this->parent_->set_manual_force_full(state);
    this->publish_state(state);
  }

 protected:
  JkBmsGhostBattery *parent_;
};

}  // namespace jkbms_ghost_battery
}  // namespace esphome
