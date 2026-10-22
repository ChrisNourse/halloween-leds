# /// script
# requires-python = ">=3.11"
# dependencies = ["websocket-client>=1.8,<2", "pyserial>=3.5,<4"]
# ///
"""Install over USB, inspect hardware, and update application files over Wi-Fi."""
import argparse
import base64
import datetime
import getpass
import json
import os
from pathlib import Path
import socket
import sys
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = Path.home() / "Library/Application Support/haloween_leds" if sys.platform == "darwin" else Path.home() / ".config/haloween_leds"
BOARD_ID = "adafruit_feather_esp32s2"
FILES = ("config.py", "show.py", "protocol.py", "webserver.py", "board_status.py", "schedule.py", "network_clock.py", "boot.py", "code.py")


def deployment_files():
    payloads = {name: (ROOT / "firmware" / name).read_bytes() for name in FILES if name != "code.py"}
    for name in ("index.html", "style.css", "app.js"):
        payloads["www/" + name] = (ROOT / "web" / name).read_bytes()
    payloads["code.py"] = (ROOT / "firmware/code.py").read_bytes()
    return payloads


def backup_dir():
    path = PRIVATE / "backups" / datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    path.mkdir(parents=True, mode=0o700)
    return path


def private_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "wb") as stream:
        stream.write(data)


def install(volume, settings):
    volume = Path(volume).resolve()
    boot = volume / "boot_out.txt"
    if not boot.exists() or BOARD_ID not in boot.read_text():
        raise RuntimeError("Expected the Adafruit Feather ESP32-S2 CIRCUITPY drive; install its CircuitPython runtime first.")
    payloads = deployment_files()
    if settings:
        data = Path(settings).read_bytes()
        parsed = tomllib.loads(data.decode())
        for key in ("CIRCUITPY_WIFI_SSID", "CIRCUITPY_WIFI_PASSWORD", "CIRCUITPY_WEB_API_PASSWORD"):
            if not parsed.get(key):
                raise RuntimeError("Missing setting: " + key)
        payloads["settings.toml"] = data
    backup = backup_dir()
    for name in payloads:
        target = volume / name
        if target.exists():
            private_write(backup / name, target.read_bytes())
    # code.py last: other files are in place before the new entry point runs.
    ordered = [name for name in payloads if name != "code.py"] + ["code.py"]
    for name in ordered:
        target = volume / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payloads[name])
        if target.read_bytes() != payloads[name]:
            raise RuntimeError("USB verification failed: " + name)
    if hasattr(os, "sync"):
        os.sync()
    marker = volume / "USB_INSTALL"
    if marker.exists():
        marker.unlink()
    print("Installed and verified %d files. Backup: %s" % (len(payloads), backup))
    print("Press RESET or reconnect USB so boot.py enables the separate USB data port and Wi-Fi OTA.")


def expose_usb_drive(port=None):
    import serial
    import serial.tools.list_ports
    if not port:
        ports = sorted(p.device for p in serial.tools.list_ports.comports() if p.vid == 0x239A)
        if not ports:
            raise RuntimeError("No Adafruit USB port found. Connect the board with a data cable.")
        port = ports[0]
    with serial.Serial(port, 115200, timeout=.1) as console:
        def send(text):
            for offset in range(0, len(text), 8):
                console.write(text[offset:offset + 8].encode())
                time.sleep(.02)
        def until(marker):
            data = b""
            deadline = time.monotonic() + 6
            while marker not in data and time.monotonic() < deadline:
                data += console.read(1024)
            if marker not in data:
                raise RuntimeError("No USB console response. Use --port with the console interface, usually the first port.")
            return data.decode(errors="replace")
        def run(command):
            send(command + "; print('HW_USB_OK')\r\n")
            output = until(b"\r\nHW_USB_OK\r\n")
            if "Traceback" in output:
                raise RuntimeError(output)
            return output
        send("\x03\x03\r\n")
        until(b">>> ")
        identity = run("import board; print(board.board_id)")
        if BOARD_ID not in identity:
            raise RuntimeError("Refusing to change a different board")
        run("import supervisor; supervisor.runtime.autoreload=False")
        run("import storage; storage.remount('/',readonly=False)")
        run("open('/USB_INSTALL','w').close()")
        send("import microcontroller; microcontroller.reset()\r\n")
    print("USB installation mode requested. Wait for CIRCUITPY, then run the install command.")


class Repl:
    def __init__(self, base, authorization):
        import websocket
        parsed = urllib.parse.urlsplit(base)
        self.socket = websocket.create_connection(
            "ws://" + parsed.netloc + "/cp/serial/", timeout=8,
            origin=base, header=["Authorization: " + authorization], skip_utf8_validation=True)
        self.send("\x03\x03\r\n")
        self.until(">>> ")
        self.sequence = 0

    def send(self, data):
        # The device serial input ring is tiny; small frames keep REPL input reliable.
        for offset in range(0, len(data), 8):
            self.socket.send(data[offset:offset + 8])
            time.sleep(0.02)

    def until(self, marker):
        received = ""
        deadline = time.monotonic() + 12
        while marker not in received:
            if time.monotonic() > deadline:
                raise RuntimeError("Timed out waiting for device REPL")
            _, chunk = self.socket.recv_data()
            if not chunk:
                raise RuntimeError("Device REPL closed unexpectedly")
            received += chunk.decode("utf-8", errors="replace") if isinstance(chunk, bytes) else chunk
            if marker != ">>> " and "Traceback" in received and received.rfind(">>> ") > received.find("Traceback"):
                raise RuntimeError("Device REPL command failed: " + received)
        return received

    def run(self, command):
        self.sequence += 1
        token = "HW_DONE_%d" % self.sequence
        # A complete output line distinguishes execution from input echo and stale prompts.
        self.send(command + "; print('" + token + "')\r\n")
        result = self.until("\r\n" + token + "\r\n")
        if "Traceback" in result or "Error:" in result:
            raise RuntimeError("Device REPL command failed: " + result)
        return result

    def restart(self):
        self.send("import microcontroller; microcontroller.reset()\r\n")

    def close(self):
        self.socket.close()


class Updater:
    def __init__(self, base, password):
        parsed = urllib.parse.urlsplit(base)
        if parsed.scheme != "http" or not parsed.hostname or parsed.username or parsed.path not in ("", "/"):
            raise ValueError("Use the device base address, e.g. http://192.0.2.123:8080")
        # The application advertises mDNS and stops during OTA. Resolve once
        # while it is running so later file requests do not wait on that name.
        address = socket.gethostbyname(parsed.hostname)
        self.base = "http://" + address + (":" + str(parsed.port) if parsed.port else "")
        self.auth = "Basic " + base64.b64encode((":" + password).encode()).decode()

    def request(self, path, method="GET", data=None):
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Authorization": self.auth, "Accept": "application/json"})
        # Never redirect credentials to a different host, or use system HTTP proxies for device traffic.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(req, timeout=15) as response:
            return response.read()

    def update(self):
        version = json.loads(self.request("/cp/version.json"))
        if version.get("board_id") != BOARD_ID:
            raise RuntimeError("Refusing to update a different board: " + str(version.get("board_id")))
        print("Found", version.get("board_name"), "running CircuitPython", version.get("version"), flush=True)
        payloads = deployment_files()
        # Back up every previous file before interrupting the running application.
        backup = backup_dir()
        originals = {}
        for name in payloads:
            try:
                originals[name] = self.request("/fs/" + name)
                private_write(backup / name, originals[name])
            except urllib.error.HTTPError as error:
                if error.code != 404:
                    raise
                originals[name] = None
        private_write(backup / "manifest.json", json.dumps({n: v is not None for n, v in originals.items()}).encode())
        print("Backup:", backup, flush=True)
        repl = Repl(self.base, self.auth)
        changed = []
        try:
            repl.run("import supervisor; supervisor.runtime.autoreload = False")
            # Normal remount preserves USB concurrent-write protection. Never disable it.
            repl.run("import storage; storage.remount('/', readonly=False)")
            disk = json.loads(self.request("/cp/diskinfo.json"))
            disks = disk if isinstance(disk, list) else [disk]
            if not any(d.get("root") == "/" and d.get("writable") for d in disks):
                raise RuntimeError("USB owns CIRCUITPY. Eject the drive or disconnect USB data, then retry OTA.")
            self.request("/fs/www/", "PUT")
            for name in payloads:
                changed.append(name)
                self.request("/fs/" + name, "PUT", payloads[name])
                if self.request("/fs/" + name) != payloads[name]:
                    raise RuntimeError("OTA readback verification failed: " + name)
                print("Verified", name, flush=True)
        except Exception:
            if changed:
                print("Update failed; restoring previous files.", file=sys.stderr)
                try:
                    for name in changed:
                        old = originals[name]
                        if old is None:
                            try:
                                self.request("/fs/" + name, "DELETE")
                            except urllib.error.HTTPError as error:
                                if error.code != 404:
                                    raise
                        else:
                            self.request("/fs/" + name, "PUT", old)
                            if self.request("/fs/" + name) != old:
                                raise RuntimeError("Rollback verification failed: " + name)
                    repl.restart()
                    print("Previous application restored.", file=sys.stderr)
                except Exception as rollback_error:
                    print("Recovery needed; application left stopped. Backup: %s. %s" % (backup, rollback_error), file=sys.stderr)
            else:
                repl.restart()
            raise
        else:
            repl.restart()
            print("OTA application update verified; reset requested. Runtime updates still require USB.")
        finally:
            repl.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect")
    mount = sub.add_parser("usb-drive", help="Expose CIRCUITPY for a USB install; pauses the show")
    mount.add_argument("--port", help="CircuitPython USB console port")
    usb = sub.add_parser("install")
    usb.add_argument("--volume", default="/Volumes/CIRCUITPY")
    usb.add_argument("--settings", help="Private settings.toml to install, preserving all other board files")
    ota = sub.add_parser("ota")
    ota.add_argument("--url", help="Board's web workflow address, including :8080")
    args = parser.parse_args()
    if args.command == "inspect":
        import serial.tools.list_ports
        for port in serial.tools.list_ports.comports():
            print(port.device, port.description, "interface:", port.interface)
        return
    if args.command == "install":
        install(args.volume, args.settings)
        return
    if args.command == "usb-drive":
        expose_usb_drive(args.port)
        return
    saved_path = PRIVATE / "ota.json"
    saved = json.loads(saved_path.read_text()) if saved_path.exists() else {}
    base = args.url or saved.get("base_url")
    if not base:
        parser.error("OTA needs --url http://BOARD_IP:8080 on its first run")
    password = saved.get("password") or getpass.getpass("Device OTA password: ")
    Updater(base, password).update()
    private_write(saved_path, (json.dumps({"base_url": base, "password": password, "board_id": BOARD_ID}, indent=2) + "\n").encode())


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError) as error:
        raise SystemExit(str(error))
