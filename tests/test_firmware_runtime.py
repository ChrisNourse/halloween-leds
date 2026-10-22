"""Execute the actual entry point with host substitutes for board peripherals."""
import json
from pathlib import Path
import sys
import time as host_time
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "firmware"))
import config as defaults
from schedule import sun_events
from test_schedule import epoch


class Finished(BaseException):
    pass


class Slept(BaseException):
    pass


class RuntimeTests(unittest.TestCase):
    def run_board(self, timestamp, wake=None, automatic=True, grace=60, wifi=True, usb_connected=False, selection=None, location=True, coordinates=None):
        modules = {name: ModuleType(name) for name in ("alarm", "board", "digitalio", "microcontroller", "mdns", "neopixel_write", "socketpool", "rtc", "supervisor", "usb_cdc", "wifi", "time", "config", "board_status", "network_clock", "webserver")}
        result = {"frames": [], "statuses": [], "sleep": None, "restored": False, "suspended": False}
        tick = [0.0]
        def pause(seconds):
            tick[0] += seconds
            if tick[0] >= .12:
                raise Finished()
        modules["time"].time = lambda: timestamp + tick[0]
        modules["time"].monotonic = lambda: tick[0]
        modules["time"].localtime = lambda value=None: host_time.gmtime(timestamp + tick[0] if value is None else value)
        modules["time"].sleep = pause
        for key in dir(defaults):
            if key.isupper():
                setattr(modules["config"], key, getattr(defaults, key))
        modules["config"].LATITUDE = 37.7749 if location else None
        modules["config"].LONGITUDE = -122.4194 if location else None
        if coordinates is not None:
            modules["config"].LATITUDE, modules["config"].LONGITUDE = coordinates
        modules["config"].LOCATION_CONFIGURED = location
        modules["config"].BOOT_GRACE_SECONDS = grace
        class Alarm:
            def __init__(self, **kwargs):
                self.arguments = kwargs
        class PinAlarm(Alarm):
            pass
        class TimeAlarm(Alarm):
            pass
        modules["alarm"].pin = SimpleNamespace(PinAlarm=PinAlarm)
        modules["alarm"].time = SimpleNamespace(TimeAlarm=TimeAlarm)
        modules["alarm"].wake_alarm = PinAlarm() if wake == "button" else TimeAlarm() if wake == "timer" else None
        def sleep(*alarms):
            result["sleep"] = alarms
            raise Slept()
        modules["alarm"].exit_and_deep_sleep_until_alarms = sleep
        modules["board"].D6 = "D6"
        modules["board"].BUTTON = "BOOT"
        class Pin:
            def __init__(self, pin):
                self.name = pin
            def switch_to_output(self, **kwargs):
                pass
            def deinit(self):
                pass
        modules["digitalio"].DigitalInOut = Pin
        modules["neopixel_write"].neopixel_write = lambda pin, data: result["frames"].append(bytes(data))
        nvm = bytearray(512)
        settings = {"mode": "solid", "brightness": .2, "color": [255, 255, 255], "automatic": automatic}
        settings.update(selection or {})
        payload = json.dumps(settings).encode()
        nvm[:5 + len(payload)] = b"HW1" + bytes((len(payload) >> 8, len(payload) & 255)) + payload
        modules["microcontroller"].nvm = nvm
        modules["usb_cdc"].data = None
        modules["usb_cdc"].console = None
        modules["supervisor"].runtime = SimpleNamespace(usb_connected=usb_connected)
        modules["wifi"].radio = SimpleNamespace(ipv4_address="192.0.2.1" if wifi else None)
        modules["socketpool"].SocketPool = lambda radio: object()
        modules["mdns"].Server = lambda radio: SimpleNamespace(advertise_service=lambda **kwargs: None)
        modules["rtc"].RTC = lambda: SimpleNamespace(datetime=None)
        class Status:
            def tick(self, state, now):
                result["statuses"].append(state)
            def restore(self):
                result["restored"] = True
            def suspend(self):
                result["suspended"] = True
        modules["board_status"].BoardStatus = Status
        modules["network_clock"].NetworkClock = lambda *args: SimpleNamespace(poll=lambda now: None, close=lambda: None)
        modules["webserver"].WebControl = lambda *args, **kwargs: SimpleNamespace(poll=lambda: None)
        namespace = {"__name__": "__main__"}
        with patch.dict(sys.modules, modules):
            try:
                exec(compile((ROOT / "firmware/code.py").read_text(), "code.py", "exec"), namespace)
            except (Finished, Slept):
                pass
        result["globals"] = namespace
        return result

    def test_missing_location_with_saved_automatic_setting_does_not_sleep(self):
        result = self.run_board(epoch(2020, 1, 1), location=False, grace=0)
        self.assertIsNone(result['sleep'])
        self.assertEqual(result['globals']['schedule_status']['phase'], 'location required')
        self.assertIn(bytes([51] * 48), result['frames'])

    def test_polar_location_keeps_main_loop_and_controls_running(self):
        for automatic in (False, True):
            result = self.run_board(epoch(2026, 12, 1), coordinates=(69.65, 18.96), automatic=automatic, grace=0)
            self.assertIsNone(result["sleep"])
            self.assertIsNotNone(result["globals"]["web"])
            self.assertIn(bytes([51] * 48), result["frames"])

    def test_late_night_applies_dim_factor_to_real_pixel_output(self):
        _, setting = sun_events(epoch(2026, 10, 20), 37.7749, -122.4194)
        result = self.run_board(setting + 14400)
        self.assertIn(bytes([12] * 48), result["frames"])
        self.assertAlmostEqual(result["globals"]["effective_brightness"], .05)
        self.assertIn("online", result["statuses"])
        self.assertIsNone(result["sleep"])

    def test_saved_gradient_and_full_brightness_reach_real_grb_output(self):
        result = self.run_board(epoch(2026, 10, 20, 20), automatic=False, selection={
            "brightness": 1, "color_mode": "gradient",
            "gradient": [[0,255,0,0,50],[100,0,0,255,50]]})
        self.assertTrue(any(frame[:3] == bytes([0,255,0]) and frame[-3:] == bytes([0,0,255])
                            for frame in result["frames"]))
        self.assertEqual(result["globals"]["show"].settings["mode"], "solid")
        self.assertEqual(result["globals"]["effective_brightness"], 1)

    def test_breathing_uses_shared_gradient_color_and_fractional_hardware_levels(self):
        result = self.run_board(epoch(2026,10,20,20),automatic=False,selection={
            "mode":"breathing", "brightness":.1, "speed":.25, "color_mode":"gradient",
            "gradient":[[0,255,0,0,50],[100,0,0,255,50]]})
        frame=result["frames"][0]
        self.assertEqual(frame[::3],bytes(16))
        self.assertEqual(frame[2::3],bytes(16))
        self.assertGreater(len(set(frame[1::3])),1)
        self.assertAlmostEqual(sum(frame[1::3])/16,255*.56*.1,delta=1/32)

    def test_daytime_timer_wake_returns_to_sleep_with_leds_off(self):
        result = self.run_board(epoch(2026, 10, 20, 20), wake="timer")
        self.assertIsNotNone(result["sleep"])
        self.assertTrue(result["suspended"])
        self.assertFalse(result["restored"])
        self.assertTrue(all(frame == bytes(48) for frame in result["frames"]))
        timer, button = result["sleep"]
        self.assertLessEqual(timer.arguments["monotonic_time"], 7200)
        self.assertEqual(button.arguments["pin"], "BOOT")

    def test_boot_button_and_manual_setting_keep_daytime_controls_awake(self):
        for kwargs in ({"wake": "button"}, {"automatic": False}):
            result = self.run_board(epoch(2026, 10, 20, 20), grace=0, **kwargs)
            self.assertIsNone(result["sleep"])
            self.assertIn(bytes([51] * 48), result["frames"])
            self.assertTrue(result["restored"])

    def test_unknown_clock_stays_dark_then_sleeps_before_retry(self):
        result = self.run_board(epoch(2000, 1, 1), grace=.04, wifi=False)
        self.assertTrue(all(frame == bytes(48) for frame in result["frames"]))
        self.assertIsNotNone(result["sleep"])
        timer, _ = result["sleep"]
        self.assertAlmostEqual(timer.arguments["monotonic_time"], 600.04, places=2)

    def test_valid_rtc_keeps_nighttime_lights_running_without_wifi(self):
        _, setting = sun_events(epoch(2026, 10, 20), 37.7749, -122.4194)
        result = self.run_board(setting + 14400, wifi=False)
        self.assertIn(bytes([12] * 48), result["frames"])
        self.assertIn("offline", result["statuses"])
        self.assertIsNone(result["sleep"])

    def test_usb_host_keeps_daytime_disk_installation_accessible(self):
        result = self.run_board(epoch(2026, 10, 20, 20), wake="timer", usb_connected=True)
        self.assertIsNone(result["sleep"])
        self.assertTrue(all(frame == bytes(48) for frame in result["frames"]))
