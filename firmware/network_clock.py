"""Small polled NTP client. The RTC stays in UTC, including through deep sleep."""
import os
import time


def ntp_time(packet, nonce):
    if len(packet) < 48 or packet[0] & 7 != 4 or packet[0] >> 6 == 3:
        raise ValueError("invalid NTP server response")
    if not 1 <= packet[1] <= 15 or packet[24:32] != nonce:
        raise ValueError("untrusted NTP response")
    seconds = int.from_bytes(packet[40:44], "big")
    epoch = seconds - 2208988800
    if not 2025 <= getattr(time, "gmtime", time.localtime)(epoch).tm_year <= 2035:
        raise ValueError("NTP time outside supported deployment range")
    return epoch


class NetworkClock:
    def __init__(self, pool, set_time, server="time.cloudflare.com"):
        self.pool = pool
        self.set_time = set_time
        self.server = server
        self.socket = None
        self.next_attempt = 0
        self.deadline = 0
        self.nonce = b""
        self.buffer = bytearray(48)
        self.last_error = None
        self.synced = False

    def close(self):
        if self.socket is not None:
            try:
                self.socket.close()
            except OSError:
                pass
            self.socket = None

    def poll(self, now):
        if self.socket is None:
            if now < self.next_attempt:
                return
            self.next_attempt = now + 60
            try:
                address = self.pool.getaddrinfo(self.server, 123, self.pool.AF_INET, self.pool.SOCK_DGRAM)[0][-1]
                self.socket = self.pool.socket(self.pool.AF_INET, self.pool.SOCK_DGRAM)
                self.socket.settimeout(0)
                packet = bytearray(48)
                packet[0] = 0x23
                self.nonce = os.urandom(8)
                packet[40:48] = self.nonce
                self.socket.sendto(packet, address)
                self.deadline = now + 4
            except OSError as error:
                self.last_error = str(error)
                self.close()
            return
        try:
            count, _ = self.socket.recvfrom_into(self.buffer)
            epoch = ntp_time(bytes(self.buffer[:count]), self.nonce)
            self.set_time(epoch)
            self.synced = True
            self.last_error = None
            self.next_attempt = now + 21600
            self.close()
        except ValueError as error:
            self.last_error = str(error)
        except OSError as error:
            if error.args and error.args[0] not in (11, 35, 110, 116):
                self.last_error = str(error)
                self.close()
        if self.socket is not None and now >= self.deadline:
            self.last_error = "NTP response timed out"
            self.close()
