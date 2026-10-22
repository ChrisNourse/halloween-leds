import datetime
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "firmware"))
from schedule import SolarSchedule, dim_factor, sun_events
from network_clock import ntp_time, NetworkClock


def epoch(year, month, day, hour=0, minute=0):
    return datetime.datetime(year, month, day, hour, minute, tzinfo=datetime.timezone.utc).timestamp()


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.schedule = SolarSchedule(37.7749, -122.4194)
        self.day = epoch(2026, 10, 20)
        self.rise, self.setting = sun_events(self.day, 37.7749, -122.4194)

    def test_san_francisco_solar_times_have_correct_utc_date_rollover(self):
        # Reference: api.sunrise-sunset.org at these coordinates, fetched 2026-10-19.
        self.assertLess(abs(self.rise - (epoch(2026, 10, 20, 14, 21) + 55)), 120)
        self.assertLess(abs(self.setting - (epoch(2026, 10, 21, 1, 26) + 52)), 120)

    def test_sunset_starts_show_sunrise_stops_and_sleeps(self):
        before = self.schedule.evaluate(self.setting - 1)
        self.assertEqual(before["phase"], "day")
        self.assertEqual(before["factor"], 0)
        self.assertTrue(before["can_sleep"])
        night = self.schedule.evaluate(self.setting)
        self.assertEqual(night["phase"], "night")
        self.assertEqual(night["factor"], 1)
        self.assertFalse(night["can_sleep"])
        morning = self.schedule.evaluate(night["next_sunrise"])
        self.assertEqual(morning["factor"], 0)
        self.assertTrue(morning["can_sleep"])
        self.assertGreater(morning["next_sunset"], night["next_sunrise"])

    def test_mando_fade_is_continuous_at_two_and_four_hours(self):
        for elapsed, expected in ((0, 1), (3600, .75), (7200, .5), (10800, .375), (14400, .25), (20000, .25)):
            self.assertAlmostEqual(dim_factor(elapsed), expected)
        self.assertAlmostEqual(self.schedule.evaluate(self.setting + 14400)["factor"], .25)

    def test_unconfigured_location_keeps_manual_lighting_and_never_sleeps(self):
        for coords in ((None, None), (0, None), (None, 0)):
            for when in (None, epoch(2026, 10, 20)):
                result = SolarSchedule(*coords).evaluate(when, automatic=True)
                self.assertEqual(result['phase'], 'location required')
                self.assertEqual(result['factor'], 1)
                self.assertFalse(result['can_sleep'])
                self.assertIsNone(result['next_sunset'])

    def test_manual_override_and_unknown_clock(self):
        self.assertEqual(self.schedule.evaluate(None)["factor"], 0)
        self.assertFalse(self.schedule.evaluate(None)["can_sleep"])
        self.assertEqual(self.schedule.evaluate(None, automatic=False)["factor"], 1)
        daytime = self.setting - 3600
        manual = self.schedule.evaluate(daytime, automatic=False)
        self.assertEqual(manual["factor"], 1)
        self.assertFalse(manual["can_sleep"])
        wake = self.schedule.evaluate(daytime, force_awake=True)
        self.assertEqual(wake["phase"], "manual wake")
        self.assertEqual(wake["factor"], 1)
        self.assertFalse(wake["can_sleep"])

    def test_manual_mode_does_not_require_solar_events(self):
        with patch("schedule.sun_events", side_effect=AssertionError("manual mode must bypass solar calculations")):
            result = SolarSchedule(69.65, 18.96).evaluate(epoch(2026, 12, 1), automatic=False)
        self.assertEqual(result["phase"], "manual")
        self.assertEqual(result["factor"], 1)
        self.assertFalse(result["can_sleep"])

    def test_polar_seasons_keep_controls_available_and_retry_when_season_changes(self):
        for latitude in (69.65, -69.65, 90, -90):
            schedule = SolarSchedule(latitude, 18.96)
            for month in (6, 12):
                for awake in (False, True):
                    result = schedule.evaluate(epoch(2026, month, 21), force_awake=awake)
                    self.assertEqual(result["phase"], "solar unavailable")
                    self.assertEqual(result["factor"], 1)
                    self.assertFalse(result["can_sleep"])
                    self.assertIsNone(result["next_sunset"])
            if abs(latitude) < 90:
                result = schedule.evaluate(epoch(2027, 3, 21, 12))
                self.assertIn(result["phase"], ("day", "night"))
                self.assertIsNotNone(result["next_sunset"])

    def test_schedule_stays_dark_through_utc_midnight_and_dst_changes(self):
        for date in ((2026, 3, 8), (2026, 11, 1), (2028, 2, 29)):
            rise, setting = sun_events(epoch(*date), 37.7749, -122.4194)
            self.assertEqual(self.schedule.evaluate(rise + 60)["factor"], 0)
            self.assertEqual(self.schedule.evaluate(setting + 60)["phase"], "night")
            self.assertAlmostEqual(self.schedule.evaluate(setting + 3600)["factor"], .75)


class ClockTests(unittest.TestCase):
    def packet(self, nonce):
        packet = bytearray(48)
        packet[0], packet[1] = 0x24, 2
        packet[24:32] = nonce
        packet[40:44] = struct.pack("!I", int(epoch(2026, 10, 20)) + 2208988800)
        return packet

    def test_ntp_uses_server_transmit_time_and_matches_the_request(self):
        nonce = b"12345678"
        self.assertEqual(ntp_time(self.packet(nonce), nonce), epoch(2026, 10, 20))
        for packet, expected in ((self.packet(b"87654321"), nonce), (b"short", nonce)):
            with self.assertRaises(ValueError):
                ntp_time(packet, expected)
        invalid = self.packet(nonce)
        invalid[1] = 0
        with self.assertRaises(ValueError):
            ntp_time(invalid, nonce)

    def test_ntp_waits_without_blocking_and_closes_after_timeout(self):
        class Socket:
            closed = False
            def settimeout(self, value):
                self.timeout = value
            def sendto(self, packet, address):
                self.packet = packet
            def recvfrom_into(self, buffer):
                raise OSError(11)
            def close(self):
                self.closed = True
        class Pool:
            AF_INET, SOCK_DGRAM = 2, 2
            client = Socket()
            def socket(self, *args):
                return self.client
            def getaddrinfo(self, *args):
                return [(None, None, None, None, ("192.0.2.1", 123))]
        pool = Pool()
        clock = NetworkClock(pool, lambda value: self.fail("clock must not be set without a valid response"))
        clock.poll(0)
        self.assertEqual(pool.client.timeout, 0)
        clock.poll(1)
        self.assertIsNotNone(clock.socket)
        clock.poll(5)
        self.assertIsNone(clock.socket)
        self.assertTrue(pool.client.closed)
        self.assertFalse(clock.synced)

    def test_ntp_success_updates_rtc_and_waits_six_hours_before_refresh(self):
        received = []
        fixture = self
        class Socket:
            closed = False
            def settimeout(self, value):
                pass
            def sendto(self, packet, address):
                self.nonce = bytes(packet[40:48])
            def recvfrom_into(self, buffer):
                buffer[:] = fixture.packet(self.nonce)
                return 48, ("192.0.2.1", 123)
            def close(self):
                self.closed = True
        class Pool:
            AF_INET, SOCK_DGRAM = 2, 2
            client = Socket()
            def socket(self, *args):
                return self.client
            def getaddrinfo(self, *args):
                return [(None, None, None, None, ("192.0.2.1", 123))]
        pool = Pool()
        clock = NetworkClock(pool, received.append)
        clock.poll(0)
        clock.poll(1)
        self.assertEqual(received, [epoch(2026, 10, 20)])
        self.assertTrue(clock.synced)
        self.assertTrue(pool.client.closed)
        self.assertEqual(clock.next_attempt, 21601)
