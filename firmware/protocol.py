"""Bounded newline-delimited JSON transport on the USB data interface."""
import json

MAX_LINE = 1024


class Outbox:
    def __init__(self):
        self.buffer = bytearray()

    def send(self, message):
        payload = (json.dumps(message) + "\n").encode("utf-8")
        if len(self.buffer) + len(payload) > 4096:
            return False
        self.buffer.extend(payload)
        return True

    def flush(self, serial):
        if self.buffer:
            try:
                written = serial.write(self.buffer) or 0
                self.buffer = self.buffer[written:]
            except OSError:
                pass


class Lines:
    def __init__(self):
        self.buffer = bytearray()
        self.discard = False

    def feed(self, data):
        lines = []
        for byte in data:
            if byte == 10:
                if self.discard:
                    lines.append(None)
                elif self.buffer:
                    lines.append(bytes(self.buffer))
                self.buffer = bytearray()
                self.discard = False
            elif not self.discard:
                if len(self.buffer) >= MAX_LINE:
                    self.buffer = bytearray()
                    self.discard = True
                else:
                    self.buffer.append(byte)
        return lines


def dispatch(raw, show, save=None):
    request_id = None
    try:
        if raw is None:
            raise ValueError("command too long")
        message = json.loads(raw)
        if not isinstance(message, dict):
            raise ValueError("command must be an object")
        request_id = message.get("id")
        command = message.get("command")
        if command == "set":
            persist = message.get("persist", True)
            if type(persist) is not bool:
                raise ValueError("persist must be true or false")
            previous = show.settings
            previous_elapsed = show.elapsed
            show.update(message.get("settings"))
            if persist and save is not None and any(key in message["settings"] for key in ("mode", "color", "color_mode", "gradient")):
                try:
                    save(show.settings)
                except (OSError, RuntimeError, ValueError):
                    show.settings = previous
                    show.elapsed = previous_elapsed
                    raise
        elif command == "save":
            if save is None:
                raise ValueError("saving unavailable")
            save(show.settings)
        elif command not in ("hello", "state"):
            raise ValueError("unknown command")
        return {"id": request_id, "ok": True, "device": "halloween-leds",
                "protocol": 1, "settings": show.settings, "limit": show.limit,
                "active": show.active()[0]}
    except (ValueError, TypeError, UnicodeError, OSError, RuntimeError) as error:
        return {"id": request_id, "ok": False, "error": str(error)}
