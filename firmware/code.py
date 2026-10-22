"""ESP32-S2 standalone Halloween show with USB controls and native Wi-Fi OTA."""
import json
import alarm
import os
import time
import board
import digitalio
import microcontroller
import mdns
import neopixel_write
import socketpool
import rtc
import supervisor
import usb_cdc
import wifi

import config
from show import Show, PixelOutput
from protocol import Lines, Outbox, dispatch
from webserver import WebControl
from board_status import BoardStatus
from schedule import SolarSchedule
from network_clock import NetworkClock

status = BoardStatus()

show = Show(config.DEFAULT_BRIGHTNESS, config.DEFAULT_SPEED,
            config.DEFAULT_MODE, config.BRIGHTNESS_LIMIT)
show.settings["automatic"] = config.AUTO_SCHEDULE
WOKE_BY_PIN = isinstance(alarm.wake_alarm, alarm.pin.PinAlarm)
WOKE_BY_TIME = isinstance(alarm.wake_alarm, alarm.time.TimeAlarm)


def save_defaults(settings):
    payload = json.dumps(settings).encode("utf-8")
    if len(payload) > 500:
        raise ValueError("settings too large")
    record = b"HW1" + bytes((len(payload) >> 8, len(payload) & 255)) + payload
    # Invalidate first so a power loss cannot make a partial write look valid.
    microcontroller.nvm[0:3] = b"\x00\x00\x00"
    microcontroller.nvm[3:len(record)] = record[3:]
    microcontroller.nvm[0:3] = record[:3]


try:
    if bytes(microcontroller.nvm[0:3]) == b"HW1":
        size = (microcontroller.nvm[3] << 8) | microcontroller.nvm[4]
        if 0 < size <= 500:
            show.update(json.loads(bytes(microcontroller.nvm[5:5 + size])))
except (ValueError, TypeError):
    print("Saved defaults invalid; using config.py")
if WOKE_BY_TIME and show.settings["automatic"]:
    show.settings["blackout"] = False

pin = digitalio.DigitalInOut(board.D6)
pin.switch_to_output(value=False)
pixel_output = PixelOutput(config.PIXEL_COUNT)
buffer = pixel_output.buffer
serial = usb_cdc.data
if serial is not None:
    serial.timeout = 0
    serial.write_timeout = 0
lines = Lines()
outbox = Outbox()
last_report = 0
was_connected = False
web = None
discovery = None
last_network_check = -10
frame_data = {}
solar = SolarSchedule(config.LATITUDE, config.LONGITUDE)
clock = None
network_pool = None
schedule_status = solar.evaluate(None, show.settings["automatic"], WOKE_BY_PIN)
schedule_status["timezone"] = config.TIMEZONE
last_schedule_check = -10
started_at = time.monotonic()
boot_grace = 0 if WOKE_BY_TIME else config.BOOT_GRACE_SECONDS
manual_wake = WOKE_BY_PIN
manual_wake_until = None
sleeping = False
effective_brightness = 0.0


def set_clock(epoch):
    rtc.RTC().datetime = time.localtime(epoch)
    print("UTC clock synchronized")


def sleep_until(epoch):
    global sleeping
    seconds = max(30, min(7200, epoch - time.time()))
    # Recheck long sleeps periodically, matching the timer safeguard in Mando.
    timer = alarm.time.TimeAlarm(monotonic_time=time.monotonic() + seconds)
    button = alarm.pin.PinAlarm(pin=board.BUTTON, value=False, pull=True)
    neopixel_write.neopixel_write(pin, bytearray(len(buffer)))
    pin.deinit()
    status.suspend()
    if clock is not None:
        clock.close()
    sleeping = True
    print("Lights off; sleep for %d seconds or press BOOT to wake" % seconds)
    alarm.exit_and_deep_sleep_until_alarms(timer, button)


def command(raw):
    response = dispatch(raw, show, save_defaults)
    if response.get("ok"):
        ip = wifi.radio.ipv4_address
        response["ota_url"] = ("http://%s:%s" % (ip, os.getenv("CIRCUITPY_WEB_API_PORT", 8080))) if ip else None
        response["schedule"] = schedule_status
        response["effective_brightness"] = effective_brightness
    return response


def state():
    response = command(b'{"command":"state"}')
    response.update(frame_data)
    return response


def send(message):
    outbox.send(message)


print("Halloween LEDs: D6, %d pixels; USB data ready" % config.PIXEL_COUNT)
try:
    while True:
        now = time.monotonic()
        ip = wifi.radio.ipv4_address
        valid_clock = time.localtime().tm_year >= 2025
        if now - last_schedule_check >= 1:
            epoch = time.time() if valid_clock else None
            if manual_wake_until is not None and epoch is not None and epoch >= manual_wake_until:
                manual_wake = False
            previous_phase = schedule_status["phase"]
            schedule_status = solar.evaluate(epoch, show.settings["automatic"], manual_wake)
            schedule_status["timezone"] = config.TIMEZONE
            if manual_wake and manual_wake_until is None:
                manual_wake_until = schedule_status["next_sunrise"]
            if previous_phase == "day" and schedule_status["phase"] == "night":
                show.settings["blackout"] = False
                show.elapsed = 0
            last_schedule_check = now
        effective_brightness = min(show.settings["brightness"], config.BRIGHTNESS_LIMIT) * schedule_status["factor"]
        if show.settings["blackout"]:
            effective_brightness = 0
        status.tick("offline" if not ip else ("blackout" if effective_brightness == 0 else "online"), now)
        usb_active = (supervisor.runtime.usb_connected
                      or (serial is not None and serial.connected)
                      or (usb_cdc.console is not None and usb_cdc.console.connected))
        if config.LOCATION_CONFIGURED and config.DAYTIME_DEEP_SLEEP and show.settings["automatic"] and not manual_wake and not usb_active and now - started_at >= boot_grace:
            if schedule_status["can_sleep"]:
                sleep_until(schedule_status["next_sunset"])
            if not valid_clock:
                sleep_until(time.time() + config.CLOCK_RETRY_SLEEP_SECONDS)
        if web is None and now - last_network_check > 10:
            last_network_check = now
            if ip:
                try:
                    if network_pool is None:
                        network_pool = socketpool.SocketPool(wifi.radio)
                    if clock is None:
                        clock = NetworkClock(network_pool, set_clock)
                    web = WebControl(network_pool, command, state,
                                     hosts=lambda: ("halloween.local", str(wifi.radio.ipv4_address)))
                    discovery = mdns.Server(wifi.radio)
                    discovery.hostname = "halloween"
                    discovery.advertise_service(service_type="_http", protocol="_tcp", port=80)
                    print("Lighting controls: http://halloween.local")
                except (OSError, RuntimeError) as error:
                    print("Web startup:", error)
        if web is not None:
            web.poll()
        if clock is not None and ip:
            clock.poll(now)
        connected = serial is not None and serial.connected
        if not connected and was_connected:
            lines = Lines()
            outbox = Outbox()
        was_connected = connected
        if connected and serial.in_waiting:
            for raw in lines.feed(serial.read(min(256, serial.in_waiting)) or b""):
                send(command(raw))
        frame = show.frame(now, config.PIXEL_COUNT)
        brightness = effective_brightness
        breathing = show.settings["mode"] == "breathing"
        pixel_output.encode(frame, brightness, smooth=breathing)
        neopixel_write.neopixel_write(pin, buffer)
        active, _, remaining = show.active()
        frame_data = {"active": active,
                      "remaining": remaining / show.settings["speed"]}
        if connected and not outbox.buffer and now - last_report >= 1:
            send({"event": "frame", "active": active,
                  "remaining": remaining / show.settings["speed"],
                  "settings": show.settings, "schedule": schedule_status,
                  "effective_brightness": effective_brightness})
            last_report = now
        if connected:
            outbox.flush(serial)
        time.sleep(0.008 if breathing else 0.02)
finally:
    if not sleeping:
        neopixel_write.neopixel_write(pin, bytearray(len(buffer)))
        pin.deinit()
        status.restore()
