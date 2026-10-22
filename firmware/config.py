"""Startup defaults. Pin 6 feeds two chained Adafruit 1426 RGB sticks."""
import os

PIXEL_COUNT = 16
BRIGHTNESS_LIMIT = 1.0
DEFAULT_BRIGHTNESS = 0.15
DEFAULT_SPEED = 1.0
DEFAULT_MODE = "embers"

def coordinate(name, limit):
    try:
        value = float(os.getenv(name, ""))
    except (ValueError, TypeError):
        return None
    return value if -limit <= value <= limit else None


# Device-specific values live in CIRCUITPY/settings.toml.
AUTO_SCHEDULE = True
if os.getenv("LATITUDE") is None and os.getenv("LONGITUDE") is None:
    LATITUDE, LONGITUDE = 37.7749, -122.4194
else:
    LATITUDE = coordinate("LATITUDE", 90)
    LONGITUDE = coordinate("LONGITUDE", 180)
LOCATION_CONFIGURED = LATITUDE is not None and LONGITUDE is not None
TIMEZONE = os.getenv("TIMEZONE", "America/Los_Angeles").strip() or "America/Los_Angeles"
DAYTIME_DEEP_SLEEP = True
BOOT_GRACE_SECONDS = 60
CLOCK_RETRY_SLEEP_SECONDS = 600
