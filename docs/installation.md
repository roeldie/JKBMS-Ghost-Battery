# Installation

1. Copy this whole folder (including `components/`) into your ESPHome Dashboard's config
   directory, eg. `/config/esphome/`, keeping the folder structure intact — `external_components`
   in the YAML resolves `path: components` relative to the YAML file.
2. Copy `secrets.yaml.example` to `secrets.yaml` alongside it (or merge its keys into your
   existing one) and fill in your real WiFi credentials, a generated API encryption key, an OTA
   password, and a fallback AP password (`ap_fallback_password`, min. 8 characters).
   `secrets.yaml` itself is gitignored - never commit your real credentials.
3. In the ESPHome Dashboard, open `jkbms-ghost-battery.yaml` and click **Validate** — it should
   list the full resolved config ending in `Configuration is valid!` with no errors. If it can't
   find the component, double check the folder name is exactly `components/jkbms_ghost_battery/`
   (case-sensitive on Linux).
4. Click **Install** for the first flash (USB required); later updates can go out over WiFi/OTA.
5. Once online, Home Assistant will show a discovery notification for the device automatically
   (**Settings → Devices & services**) — no manual YAML editing needed on the HA side.

If the device ever can't reach your WiFi (eg. you changed the password), it falls back to
broadcasting a **"JKBMS Ghost Battery Fallback"** hotspot. Connect to it with a phone using the
`ap_fallback_password` from your `secrets.yaml`, and a captive portal page lets you enter new
WiFi credentials — no reflashing needed.
