# Samsung AC (DPLUG / 2878) — Home Assistant integration

Local control for **old Samsung air conditioners** (AR\*\*HSFS generation, ~2013–2015,
Wi-Fi modules like `SWL-B70F`) that speak the legacy **DPLUG / AC14K** protocol over
TLS on **port 2878**. These units were dropped by SmartThings — this brings them back,
fully local, with native entities and a guided setup.

Protocol layer: [`pysamsung-dplug`](https://github.com/porech/pysamsung-dplug).

## Features

- **Climate** entity: power, HVAC modes (cool/heat/dry/fan/auto), target & current
  temperature, fan speed, swing, and presets (Quiet, Fast Turbo, Comfort, d'light
  Cool, Smart Saver, Color of Wind). Controls and presets are offered only when the
  unit actually supports them (decoded from its capability code).
- **Sensors**: indoor & outdoor temperature, humidity, operating time, filter use
  time, filter life %, error code, device clock, and a schedules overview.
- **Switches**: Purify (SPi), Auto-clean, Display light, Sterilize, Smart on, Weather.
- **Numbers**: Sleep / On / Off timers, Energy target.
- **Selects**: Occupancy, Beep volume, Front panel, Filter cleaning interval.
- **On-device scheduler** (services): read, create/edit and delete the unit's built-in
  on/off schedules — they run off the module's own clock, even while HA is offline.
- **Live push updates** with auto-reconnect (toggleable; falls back to polling).
- **Guided config flow** with on-screen instructions for getting the unit onto Wi-Fi
  (WPS) and for acquiring (and saving) the token; **DHCP discovery**.
- 100% local, no cloud.

## Scheduler services

The integration exposes the air conditioner's **built-in** scheduler — it runs off the
module's own clock and fires even when Home Assistant is offline, and it only switches
the unit **on or off** at a set time. For richer scenarios (temperature, mode, fan, …)
use Home Assistant automations.

- `samsung_ac_dplug.get_schedules` — list the schedules stored on the unit (returns data).
- `samsung_ac_dplug.set_schedule` — create or edit an on/off schedule (time, power,
  repeat once/daily/weekly, days, enabled). Times are entered in your local timezone.
- `samsung_ac_dplug.delete_schedule` — delete a schedule by id.

The current schedules are also shown by the **Schedules** diagnostic sensor.

## Install (HACS)

1. HACS → Integrations → ⋮ → *Custom repositories* → add
   `https://github.com/porech/samsung_ac_dplug` (category *Integration*).
2. Install **Samsung AC (DPLUG / 2878)** and restart Home Assistant.
3. *Settings → Devices & Services → Add Integration → Samsung AC (DPLUG)*.

## Setup

The config flow walks you through everything:

1. **Get the unit on Wi-Fi** (once, physically): hold **`Settings` 4 s** on the remote
   to start WPS (hidden function — the display just blinks), then press WPS on your
   router. *(No WPS router? Use the `provision.py` helper from the library repo while
   connected to the unit’s `SMARTAIRCON` network.)*
2. **Discovery**: once on the network the unit is auto-detected (DHCP); or enter its IP
   manually.
3. **Token**: turn the unit OFF (if on), submit, then turn it ON within ~30 s. The token
   is captured automatically (this is a Samsung proof-of-physical-access step — there is
   no way around it).

The device id (DUID) and capabilities are discovered automatically.

## Notes

- Outdoor temperature is reported by the firmware in °F and converted to °C.
- Each indoor unit is an independent device with its own token.

## Credits

Reverse-engineered from the official *Smart Air Conditioner* app and live devices.
See the library repo for the protocol write-up.

## License

MIT
