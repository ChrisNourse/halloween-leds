from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class BootTests(unittest.TestCase):
    def boot(self, install):
        source = (Path(__file__).resolve().parents[1] / "firmware/boot.py").read_text()
        modules = {name: ModuleType(name) for name in ("usb_cdc", "usb_hid", "usb_midi", "storage", "os", "supervisor")}
        modules["supervisor"].runtime = SimpleNamespace(rgb_status_brightness=63)
        for name in ("usb_hid", "usb_midi"):
            modules[name].disable = Mock()
        modules["usb_cdc"].enable = Mock()
        modules["storage"].disable_usb_drive = Mock()
        modules["os"].stat = Mock(return_value=()) if install else Mock(side_effect=OSError)
        with patch.dict(sys.modules, modules):
            exec(compile(source, "boot.py", "exec"), {})
        return modules

    def test_normal_mode_reserves_endpoints_for_two_serial_ports_and_ota(self):
        modules = self.boot(False)
        modules["storage"].disable_usb_drive.assert_called_once()
        modules["usb_cdc"].enable.assert_called_once_with(console=True, data=True)

    def test_usb_install_mode_keeps_disk_and_console_within_endpoint_budget(self):
        modules = self.boot(True)
        modules["storage"].disable_usb_drive.assert_not_called()
        modules["usb_cdc"].enable.assert_called_once_with(console=True, data=False)
