import importlib.util
import json
from pathlib import Path
import sys
import unittest
import urllib.error
from unittest.mock import patch

# device.py runs on Python 3.11+; firmware tests also work with the Mac's Python 3.9.
if sys.version_info >= (3, 11):
    spec = importlib.util.spec_from_file_location("device", Path(__file__).resolve().parents[1] / "scripts/device.py")
    device = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(device)


@unittest.skipIf(sys.version_info < (3, 11), "OTA host tool requires Python 3.11+")
class OTATests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.private = patch.object(device, "PRIVATE", Path(self.temp.name))
        self.private.start()
        self.addCleanup(self.private.stop)

    def fake_request(self, files, fail=None, board=None):
        failures = [fail] if fail else []
        def request(path, method="GET", data=None):
            if path == "/cp/version.json":
                return json.dumps({"board_id": board or device.BOARD_ID, "version": "test"}).encode()
            if path == "/cp/diskinfo.json":
                return b'[{"root":"/","writable":true}]'
            name = path.removeprefix("/fs/")
            if name.endswith("/") and method == "PUT":
                return b""
            if method == "PUT":
                files[name] = data
                if failures and name == failures[0]:
                    failures.pop()
                    raise OSError("simulated interrupted upload")
                return b""
            if method == "DELETE":
                files.pop(name, None)
                return b""
            if name not in files:
                raise urllib.error.HTTPError(path, 404, "Not Found", {}, None)
            return files[name]
        return request

    def test_success_uploads_and_verifies_all_files_before_reset(self):
        files = {name: b"old " + name.encode() for name in device.deployment_files()}
        updater = device.Updater("http://192.0.2.200:8080", "test-password")
        with patch.object(updater, "request", self.fake_request(files)), patch.object(device, "Repl") as repl:
            updater.update()
            repl.return_value.restart.assert_called_once()
        self.assertEqual(files, device.deployment_files())
        self.assertEqual(len(list(Path(self.temp.name).rglob("manifest.json"))), 1)

    def test_hostname_is_resolved_before_stopping_mdns_application(self):
        with patch.object(device.socket, "gethostbyname", return_value="192.0.2.200") as resolve:
            updater = device.Updater("http://halloween.local:8080", "test-password")
        resolve.assert_called_once_with("halloween.local")
        self.assertEqual(updater.base, "http://192.0.2.200:8080")
        files = {}
        with patch.object(updater, "request", self.fake_request(files)), patch.object(device, "Repl") as repl:
            updater.update()
        self.assertEqual(repl.call_args.args[0], "http://192.0.2.200:8080")

    def test_interrupted_upload_restores_original_files(self):
        files = {name: b"previous " + name.encode() for name in device.deployment_files()}
        before = dict(files)
        updater = device.Updater("http://192.0.2.200:8080", "test-password")
        with patch.object(updater, "request", self.fake_request(files, fail="show.py")), patch.object(device, "Repl") as repl:
            with self.assertRaises(OSError):
                updater.update()
            repl.return_value.restart.assert_called_once()
        self.assertEqual(files, before)

    def test_wrong_board_is_rejected_before_repl(self):
        updater = device.Updater("http://192.0.2.200:8080", "test-password")
        with patch.object(updater, "request", self.fake_request({}, board="other")), patch.object(device, "Repl") as repl:
            with self.assertRaisesRegex(RuntimeError, "different board"):
                updater.update()
            repl.assert_not_called()

    def test_rollback_removes_new_files_from_a_first_deployment(self):
        files = {"config.py": b"previous config", "code.py": b"previous code"}
        before = dict(files)
        updater = device.Updater("http://192.0.2.200:8080", "test-password")
        with patch.object(updater, "request", self.fake_request(files, fail="www/app.js")), patch.object(device, "Repl"):
            with self.assertRaises(OSError):
                updater.update()
        self.assertEqual(files, before)
