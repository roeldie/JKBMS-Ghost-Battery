# Development

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
