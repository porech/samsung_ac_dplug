# Samsung AC (DPLUG / 2878) — Home Assistant integration

Local control for **old Samsung air conditioners** (AR\*\*HSFS generation, ~2013–2015,
Wi-Fi modules like `SWL-B70F`) that speak the legacy **DPLUG / AC14K** protocol over
TLS on **port 2878**. These units were dropped by SmartThings — this brings them back,
fully local, with native entities and a guided setup.

Protocol layer: [`pysamsung-dplug`](https://github.com/porech/pysamsung-dplug).

## Features

- **Climate** entity: power, HVAC modes (cool/heat/dry/fan/auto), target & current
  temperature, fan speed, swing, presets (Quiet/Sleep/Smart/…).
- **Sensors**: outdoor temperature, operating time, filter use time, error code.
- **Switches**: Purify (SPi), Auto-clean.
- **Number**: Sleep timer.
- **Guided config flow** with on-screen instructions for getting the unit onto Wi-Fi
  (WPS) and for acquiring the token.
- **Automatic discovery** via DHCP when a unit joins the network.
- 100% local, no cloud.

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
See the library repo for the protocol write-up (including the undocumented
`APConnectionConfig` Wi-Fi provisioning command).

## License

MIT
