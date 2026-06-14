"""Constants and attribute mappings for the Samsung AC (DPLUG/2878) integration."""
from __future__ import annotations

DOMAIN = "samsung_ac_dplug"
DEFAULT_PORT = 2878
MANUFACTURER = "Samsung"

CONF_HOST = "host"
CONF_TOKEN = "token"
CONF_DUID = "duid"
CONF_NAME = "name"
CONF_LIVE_UPDATES = "live_updates"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_LIVE_UPDATES = False
DEFAULT_SCAN_INTERVAL = 30  # seconds (polling, or fallback poll when live)

# Samsung Electronics OUIs used by the Wi-Fi modules (for DHCP discovery)
SAMSUNG_OUIS = ("f8042e", "f47b5e", "8425db", "5cf6dc")

# DeviceState attribute IDs
ATTR_POWER = "AC_FUN_POWER"
ATTR_OPMODE = "AC_FUN_OPMODE"
ATTR_TEMPSET = "AC_FUN_TEMPSET"
ATTR_TEMPNOW = "AC_FUN_TEMPNOW"
ATTR_WINDLEVEL = "AC_FUN_WINDLEVEL"
ATTR_DIRECTION = "AC_FUN_DIRECTION"
ATTR_COMODE = "AC_FUN_COMODE"
ATTR_SLEEP = "AC_FUN_SLEEP"
ATTR_ERROR = "AC_FUN_ERROR"
ATTR_OUTDOOR_TEMP = "AC_OUTDOOR_TEMP"
ATTR_SPI = "AC_ADD_SPI"
ATTR_AUTOCLEAN = "AC_ADD_AUTOCLEAN"
ATTR_USED_TIME = "AC_ADD2_USEDTIME"
ATTR_USED_POWER = "AC_ADD2_USEDPOWER"
ATTR_FILTER_TIME = "AC_ADD2_FILTER_USE_TIME"
ATTR_COOL_CAP = "AC_COOL_CAPABILITY"
ATTR_WARM_CAP = "AC_WARM_CAPABILITY"

# Value maps (HA <-> device)
HVAC_TO_DEVICE = {
    "cool": "Cool",
    "heat": "Heat",
    "dry": "Dry",
    "fan_only": "Wind",
    "auto": "Auto",
}
DEVICE_TO_HVAC = {v: k for k, v in HVAC_TO_DEVICE.items()}

FAN_TO_DEVICE = {"auto": "Auto", "low": "Low", "medium": "Mid", "high": "High", "turbo": "Turbo"}
DEVICE_TO_FAN = {v: k for k, v in FAN_TO_DEVICE.items()}

# Full map; horizontal (SwingLR) is only offered when the OptionCode declares it
# (the device accepts any value without reporting its real capabilities).
SWING_TO_DEVICE = {"off": "Fixed", "vertical": "SwingUD", "horizontal": "SwingLR", "both": "Rotation"}
DEVICE_TO_SWING = {v: k for k, v in SWING_TO_DEVICE.items()}

# Preset (AC_FUN_COMODE). Keep device value as the HA preset name for clarity.
PRESETS = ["Off", "Quiet", "Sleep", "Smart", "SoftCool", "TurboMode", "WindMode1", "WindMode2", "WindMode3"]

MIN_TEMP = 16
MAX_TEMP = 30
