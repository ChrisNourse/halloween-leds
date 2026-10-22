import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "firmware"))
from webserver import WebControl


class WebTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        Path(self.temp.name, "index.html").write_text("<h1>Halloween lights</h1>")
        self.commands = []
        self.address = "192.0.2.1"
        self.web = WebControl(socket, self.command, lambda: {"device": "halloween-leds"}, root=self.temp.name, port=0,
                              hosts=lambda: ("halloween.local", self.address))
        self.web.port = self.web.server.getsockname()[1]
        self.addCleanup(self.web.server.close)
        self.addCleanup(self.web.close_client)

    def command(self, body):
        self.commands.append(json.loads(body))
        return {"ok": True}

    def exchange(self, request):
        port = self.web.server.getsockname()[1]
        with socket.create_connection(("127.0.0.1", port)) as client:
            client.settimeout(.001)
            client.sendall(request)
            received = b""
            for _ in range(200):
                self.web.poll()
                try:
                    chunk = client.recv(4096)
                    if not chunk:
                        return received
                    received += chunk
                except socket.timeout:
                    pass
            self.fail("HTTP server did not finish its response")

    def test_serves_real_page_and_state(self):
        response = self.exchange(b"GET / HTTP/1.1\r\nHost: halloween.local\r\n\r\n")
        self.assertIn(b"200 OK", response)
        self.assertIn(b"<h1>Halloween lights</h1>", response)
        response = self.exchange(b"GET /api/state HTTP/1.1\r\nHost: halloween.local\r\n\r\n")
        self.assertEqual(json.loads(response.split(b"\r\n\r\n")[1])["device"], "halloween-leds")

    def test_commands_are_delivered_once(self):
        body = b'{"command":"set","settings":{"blackout":true}}'
        request = b"POST /api/command HTTP/1.1\r\nHost: halloween.local\r\nOrigin: http://halloween.local\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body
        self.assertIn(b"200 OK", self.exchange(request))
        self.assertEqual(self.commands, [json.loads(body)])

    def test_rejects_cross_origin_and_directory_traversal(self):
        self.assertIn(b"403 Forbidden", self.exchange(b"POST /api/command HTTP/1.1\r\nHost: halloween.local\r\nOrigin: http://elsewhere.invalid\r\n\r\n"))
        self.assertEqual(self.commands, [])
        self.assertIn(b"404 Not Found", self.exchange(b"GET /../settings.toml HTTP/1.1\r\nHost: halloween.local\r\n\r\n"))

    def test_rejects_rebinding_hosts_before_reading_or_changing_state(self):
        for host in ("attacker.example", "halloween.local.attacker.example", "", "192.0.2.99", "halloween.local:8080"):
            for method, path in (("GET", "/api/state"), ("POST", "/api/command")):
                request = ("%s %s HTTP/1.1\r\nHost: %s\r\nOrigin: http://%s\r\nContent-Length: 2\r\n\r\n{}" %
                           (method, path, host, host)).encode()
                self.assertIn(b"403 Forbidden", self.exchange(request))
        self.assertEqual(self.commands, [])

    def test_accepts_current_ip_and_hostname_with_optional_server_port(self):
        for host in ("halloween.local", "HALLOWEEN.LOCAL", self.address):
            for suffix in ("", ":" + str(self.web.port)):
                authority = host + suffix
                request = ("POST /api/command HTTP/1.1\r\nHost: %s\r\nOrigin: http://%s\r\nContent-Length: 2\r\n\r\n{}" %
                           (authority, authority)).encode()
                self.assertIn(b"200 OK", self.exchange(request))
        self.address = "192.0.2.2"
        self.assertIn(b"200 OK", self.exchange(b"GET /api/state HTTP/1.1\r\nHost: 192.0.2.2\r\n\r\n"))
        self.assertIn(b"403 Forbidden", self.exchange(b"GET /api/state HTTP/1.1\r\nHost: 192.0.2.1\r\n\r\n"))

    def test_bounds_request_body_and_header_memory(self):
        self.assertIn(b"413 Payload Too Large", self.exchange(b"POST /api/command HTTP/1.1\r\nContent-Length: 99999\r\n\r\n"))
        self.assertIn(b"413 Payload Too Large", self.exchange(b"X" * 4500))
