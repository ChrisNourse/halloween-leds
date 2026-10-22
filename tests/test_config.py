import os
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch

CONFIG = Path(__file__).resolve().parents[1] / 'firmware/config.py'

class LocationConfigTests(unittest.TestCase):
    def read(self, values):
        with patch.dict(os.environ, values, clear=True):
            return runpy.run_path(str(CONFIG))

    def test_device_location_overrides_without_firmware_edits(self):
        result = self.read({'LATITUDE': '-33.8688', 'LONGITUDE': '151.2093', 'TIMEZONE': 'Australia/Sydney'})
        self.assertEqual((result['LATITUDE'], result['LONGITUDE']), (-33.8688, 151.2093))
        self.assertEqual(result['TIMEZONE'], 'Australia/Sydney')
        self.assertTrue(result['LOCATION_CONFIGURED'])

    def test_partial_blank_invalid_and_nonfinite_coordinates_have_no_city_fallback(self):
        for values in ({'LATITUDE':'','LONGITUDE':''}, {'LATITUDE':'0'}, {'LATITUDE':'91','LONGITUDE':'0'},
                       {'LATITUDE':'0','LONGITUDE':'-181'}, {'LATITUDE':'nan','LONGITUDE':'0'},
                       {'LATITUDE':'0','LONGITUDE':'inf'}, {'LATITUDE':'oops','LONGITUDE':'0'}):
            with self.subTest(values=values):
                self.assertFalse(self.read(values)['LOCATION_CONFIGURED'])
    def test_omitted_settings_default_to_san_francisco(self):
        result = self.read({})
        self.assertEqual((result['LATITUDE'], result['LONGITUDE']), (37.7749, -122.4194))
        self.assertEqual(result['TIMEZONE'], 'America/Los_Angeles')
        self.assertTrue(result['LOCATION_CONFIGURED'])

    def test_zero_coordinates_are_valid(self):
        self.assertTrue(self.read({'LATITUDE':'0','LONGITUDE':'0'})['LOCATION_CONFIGURED'])
