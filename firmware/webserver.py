"""Small bounded HTTP server polled between LED frames; one client at a time."""
import json
import time

ASSETS = {"/": ("index.html", "text/html; charset=utf-8"),
          "/index.html": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8")}


class WebControl:
    def __init__(self, pool, command, state, root="/www", port=80, hosts=None):
        self.command = command
        self.state = state
        self.root = root
        self.hosts = hosts or (lambda: ("halloween.local",))
        self.port = port
        self.server = pool.socket(pool.AF_INET, pool.SOCK_STREAM)
        self.server.settimeout(0)
        self.server.bind(("0.0.0.0", port))
        self.server.listen(2)
        self.client = None
        self.input = bytearray()
        self.output = b""
        self.scratch = bytearray(512)
        self.started = 0

    def close_client(self):
        if self.client is not None:
            try:
                self.client.close()
            except OSError:
                pass
        self.client = None
        self.input = bytearray()
        self.output = b""

    def reply(self, code, body, content_type="application/json"):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode("utf-8")
        headers = "HTTP/1.1 %s\r\nContent-Type: %s\r\nContent-Length: %d\r\nConnection: close\r\nCache-Control: no-store\r\n\r\n" % (code, content_type, len(body))
        self.output = headers.encode("utf-8") + body

    def handle(self):
        boundary = self.input.find(b"\r\n\r\n")
        if boundary < 0:
            return
        try:
            rows = bytes(self.input[:boundary]).decode("utf-8").split("\r\n")
            method, path, _ = rows[0].split(" ", 2)
            headers = {}
            for row in rows[1:]:
                key, value = row.split(":", 1)
                headers[key.lower()] = value.strip()
            size = int(headers.get("content-length", "0"))
            if not 0 <= size <= 1024:
                self.reply("413 Payload Too Large", {"error": "request too large"})
                return
            if len(self.input) - boundary - 4 < size:
                return
            host = headers.get("host", "").lower()
            allowed = tuple(str(name).lower() for name in self.hosts() if name)
            if host not in allowed and host not in tuple(name + ":" + str(self.port) for name in allowed):
                self.reply("403 Forbidden", {"error": "unrecognized host"})
                return
            if method == "GET" and path == "/api/state":
                self.reply("200 OK", self.state())
            elif method == "POST" and path == "/api/command":
                origin = headers.get("origin")
                if origin and origin != "http://" + headers.get("host", ""):
                    self.reply("403 Forbidden", {"error": "origin mismatch"})
                    return
                body = bytes(self.input[boundary + 4:boundary + 4 + size])
                self.reply("200 OK", self.command(body))
            elif method == "GET" and path in ASSETS:
                name, kind = ASSETS[path]
                with open(self.root + "/" + name, "rb") as stream:
                    self.reply("200 OK", stream.read(), kind)
            else:
                self.reply("404 Not Found", {"error": "not found"})
        except (ValueError, UnicodeError):
            self.reply("400 Bad Request", {"error": "invalid request"})

    def poll(self):
        if self.client is None:
            try:
                self.client, _ = self.server.accept()
                self.client.settimeout(0)
                self.started = time.monotonic()
            except OSError:
                return
        if time.monotonic() - self.started > 5:
            self.close_client()
            return
        try:
            if self.output:
                sent = self.client.send(self.output[:2048])
                self.output = self.output[sent:]
                if not self.output:
                    self.close_client()
            else:
                count = self.client.recv_into(self.scratch)
                if count == 0:
                    self.close_client()
                    return
                self.input.extend(self.scratch[:count])
                if len(self.input) > 4096:
                    self.reply("413 Payload Too Large", {"error": "request too large"})
                else:
                    self.handle()
        except OSError as error:
            if not error.args or error.args[0] not in (11, 35, 110, 116):
                self.close_client()
