#pragma once

#include "esphome/components/switch/switch.h"
#include "../jkbms_ghost_battery.h"

namespace esphome {
namespace jkbms_ghost_battery {

// Two-step interlock: this switch must be turned on before the "force SOC" number has any
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

}  // namespace jkbms_ghost_battery
}  // namespace esphome
