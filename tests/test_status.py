from pathlib import Path
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "firmware"))
from board_status import BoardStatus, status_color


class StatusTests(unittest.TestCase):
    def test_heartbeat_is_dim_animated_and_distinct_by_state(self):
        for state in ("online", "offline", "blackout"):
            colors = [status_color(state, i / 20) for i in range(80)]
            self.assertGreater(len(set(colors)), 1)
            self.assertTrue(all(0 <= c <= 8 for rgb in colors for c in rgb))
        self.assertEqual(status_color("online", .15), (0, 7, 0))
        self.assertEqual(status_color("blackout", .15), (0, 0, 7))
        self.assertEqual(status_color("offline", 0)[2], 0)

    def test_hardware_status_uses_circuitpython_10_runtime_brightness_property(self):
        modules = {name: ModuleType(name) for name in ("board", "digitalio", "neopixel_write", "supervisor")}
        modules["board"].NEOPIXEL_POWER = "power"
        modules["board"].NEOPIXEL = "pixel"
        modules["digitalio"].DigitalInOut = Mock(side_effect=lambda pin: Mock())
        modules["neopixel_write"].neopixel_write = Mock()
        modules["supervisor"].runtime = SimpleNamespace(rgb_status_brightness=63)
        with patch.dict(sys.modules, modules):
            led = BoardStatus()
            self.assertEqual(modules["supervisor"].runtime.rgb_status_brightness, 0)
            led.tick("online", .15)
            self.assertEqual(list(led.buffer), [7, 0, 0])
            led.restore()
            self.assertEqual(modules["supervisor"].runtime.rgb_status_brightness, 8)
