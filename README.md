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

## Supported devices

Old Samsung split air conditioners with a `SWL-Bxxx` Wi-Fi module that speak the
DPLUG / AC14K protocol on TCP port 2878 (AR\*\*HSFS generation, roughly 2013–2015),
e.g. AR09/12HSFS. The exact controls offered depend on the unit's capability code,
which the integration reads automatically. Newer SmartThings-based models are not
supported (they use a different protocol).

## Services

These are exposed as actions targeting the climate entity.

**Built-in scheduler** — runs off the module's own clock and fires even when Home
Assistant is offline; it only switches the unit **on or off** at a set time. For richer
scenarios (temperature, mode, fan, …) use Home Assistant automations.

- `samsung_ac_dplug.get_schedules` — list the schedules stored on the unit (returns data).
- `samsung_ac_dplug.set_schedule` — create or edit an on/off schedule (time, power,
  repeat once/daily/weekly, days, enabled). Times are entered in your local timezone.
- `samsung_ac_dplug.delete_schedule` — delete a schedule by id.

The current schedules are also shown by the **Schedules** diagnostic sensor.

**Other device actions** (offered by the protocol; availability depends on the unit):

- `samsung_ac_dplug.get_power_usage` — return recorded power-usage history for a range
  (hourly/daily); requires the unit's power logging.
- `samsung_ac_dplug.set_power_logging` / `reset_power_logging` — turn usage logging on/off
  or clear it.
- `samsung_ac_dplug.set_nickname` — set the nickname stored on the unit.
- `samsung_ac_dplug.get_region_code` / `set_region_code` — read or set the region code.

### Example automation

```yaml
# Turn the living-room AC on at 07:00 on weekdays, on the unit's own scheduler.
automation:
  - alias: AC on at 7 on weekdays
    triggers:
      - trigger: homeassistant
        event: start
    actions:
      - action: samsung_ac_dplug.set_schedule
        target:
          entity_id: climate.ac_soggiorno
        data:
          time: "07:00:00"
          power: "on"
          repeat: weekly
          days: [mon, tue, wed, thu, fri]
```

## Install (HACS)

1. HACS → Integrations → ⋮ → *Custom repositories* → add
   `https://github.com/porech/samsung_ac_dplug` (category *Integration*).
2. Install **Samsung AC (DPLUG / 2878)** and restart Home Assistant.
3. *Settings → Devices & Services → Add Integration → Samsung AC (DPLUG)*.

## Setup

The config flow walks you through everything:

1. **Get the unit on Wi-Fi** (once, physically): hold **`Settings` 4 s** on the remote
   to start WPS (hidden function — the display just blinks), then press WPS on your
   router. *(No WPS button on your router? Use the self-contained
   [`scripts/provision.py`](scripts/provision.py) helper — only needs Python 3 — from a
   computer connected to the unit’s `SMARTAIRCON` network; run `python3 provision.py`
   and enter your Wi-Fi name and password when asked.)*
2. **Discovery**: once on the network the unit is auto-detected (DHCP); or enter its IP
   manually.
3. **Token**: turn the unit OFF (if on), submit, then turn it ON within ~30 s. The token
   is captured automatically (this is a Samsung proof-of-physical-access step — there is
   no way around it).

The device id (DUID) and capabilities are discovered automatically.

## Options

*Settings → Devices & Services → Samsung AC → Configure*:

- **Live updates** (default on): keep one persistent connection for instant push
  updates. When off, the integration polls instead (no persistent connection — more
  resilient on flaky networks).
- **Refresh interval** (seconds): the polling interval when live updates are off, or the
  keepalive/fallback poll interval when they are on.

## Removing the integration

*Settings → Devices & Services → Samsung AC → ⋮ → Delete*. No changes are made on the
unit, so it keeps working with the remote; the token stays valid if you add it back later.

## Known limitations

- Only **power on/off** can be scheduled on the unit's built-in scheduler (matching the
  official app); use Home Assistant automations for anything richer.
- Some functions are purely local on the remote (e.g. beep, display, filter-counter reset)
  and have no representation in the protocol, so they cannot be controlled or read.
- Power usage, nickname and region-code actions exist in the protocol but are not
  available on every unit.

## Troubleshooting

- **Can't connect / "unable to install"**: the unit accepts a single connection at a
  time, and after a library update PyPI can take a minute to propagate — a second restart
  usually resolves it.
- **Token rejected** after a module reset: the integration will start a re-authentication
  flow; acquire a new token (unit OFF → submit → ON within ~30 s).

## Notes

- Outdoor temperature is reported by the firmware in °F and converted to °C.
- Each indoor unit is an independent device with its own token.

## Credits

Reverse-engineered from the official *Smart Air Conditioner* app and live devices.
See the library repo for the protocol write-up.

## License

MIT
