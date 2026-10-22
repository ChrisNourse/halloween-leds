import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "firmware"))
from show import Show, MODES, PixelOutput, gradient_color
from protocol import Lines, Outbox, dispatch


class ShowTests(unittest.TestCase):
    def test_every_pattern_produces_16_valid_rgb_pixels(self):
        for mode in MODES:
            show = Show(mode=mode)
            for t in (0, .1, 2, 30, 96, 200):
                frame = show.frame(t)
                self.assertEqual(len(frame), 16)
                self.assertTrue(all(len(rgb) == 3 and all(type(c) in (int,float) and 0 <= c <= 255 for c in rgb) for rgb in frame))

    def test_selected_pattern_never_rotates_and_legacy_show_migrates(self):
        for mode in MODES:
            show = Show(mode=mode)
            for t in (0, 96, 86400):
                show.frame(t)
                self.assertEqual(show.active()[0], mode)
        show.update({"mode": "show"})
        self.assertEqual(show.settings["mode"], "embers")

    def test_every_pattern_uses_independent_solid_color_or_spatial_gradient(self):
        for mode in MODES:
            show = Show(mode=mode)
            show.update({"color": [0, 0, 255]})
            self.assertTrue(all(rgb[:2] == (0, 0) for rgb in show.frame(0)))
            show.update({"color_mode": "gradient", "gradient": [[0, 255, 0, 0, 50], [50, 0, 255, 0, 50], [100, 0, 0, 255, 50]]})
            frame = show.frame(1, 3)
            if mode == "breathing":
                self.assertEqual(frame, [frame[0]] * 3)
                continue
            self.assertGreater(frame[0][0], 0)
            self.assertGreater(frame[1][1], 0)
            self.assertGreater(frame[2][2], 0)
            self.assertEqual(show.settings["mode"], mode)

    def test_breathing_gradient_moves_shared_color_forward_and_back(self):
        show = Show(mode="breathing")
        show.update({"color_mode":"gradient", "gradient":[[0,255,0,0,50],[50,0,255,0,25],[100,0,0,255,50]]})
        for timestamp, primary in ((0,0), (math.pi / .8,1), (math.pi / .4,2), (2 * math.pi / .4,0)):
            frame = show.frame(timestamp)
            self.assertEqual(frame, [frame[0]] * 16)
            self.assertGreater(frame[0][primary], 100)
            self.assertTrue(all(value < .001 for channel,value in enumerate(frame[0]) if channel != primary))
        self.assertEqual(show.settings["mode"], "breathing")

    def test_low_speed_breathing_keeps_fractional_levels_until_wire_output(self):
        show = Show(mode="breathing")
        show.update({"speed":.25})
        values = [show.frame(step * .008)[0][0] for step in range(40)]
        self.assertEqual(len(set(values)), 40)
        self.assertTrue(any(value != int(value) for value in values))
        output = PixelOutput(16)
        levels=[]
        for value in values:
            wire=output.encode([(value,0,0)]*16,.0375,smooth=True)
            levels.append(sum(wire[1::3]) / 16)
        self.assertGreater(len(set(levels)), 4)

    def test_fractional_output_is_bounded_and_averages_to_target(self):
        output = PixelOutput(16)
        for level in (.02,.1,.5,1.25,12.75,254.9,255):
            total=0
            for _ in range(16):
                wire=output.encode([(level,level,level)]*16,1,smooth=True)
                self.assertTrue(all(int(level) <= value <= min(255,int(level)+1) for value in wire))
                self.assertEqual(wire[::3],wire[1::3])
                total+=sum(wire[::3])
            self.assertLessEqual(abs(total/256-level),1/32 + 1e-6)
        self.assertEqual(output.encode([(255,255,255)]*16,0,smooth=True),bytes(48))
        self.assertEqual(output.encode([(0,0,0)]*16,1,smooth=True),bytes(48))

    def test_gradient_stop_positions_and_fade_midpoint(self):
        stops = [[0, 0, 0, 0, 25], [80, 200, 100, 50, 50], [100, 255, 255, 255, 50]]
        self.assertEqual(gradient_color(stops, 20), (100, 50, 25))
        self.assertEqual(gradient_color(stops, 80), (200, 100, 50))
        self.assertEqual(gradient_color(stops, 100), (255, 255, 255))

    def test_full_brightness_and_maximum_gradient_fit_nvm_and_protocol(self):
        show = Show()
        stops = [[i * 20, 255, 255, 255, 50] for i in range(6)]
        show.update({"brightness": 1, "gradient": stops, "color_mode": "gradient"})
        self.assertEqual(show.settings["brightness"], 1)
        self.assertLessEqual(len(json.dumps(show.settings).encode()), 500)
        self.assertLessEqual(len(json.dumps({"command": "set", "settings": show.settings}).encode()), 1024)

    def test_speed_advances_without_jumping_phase(self):
        show = Show()
        show.frame(0)
        show.frame(5)
        show.update({"speed": 2})
        show.frame(6)
        self.assertEqual(show.elapsed, 7)

    def test_blackout_preserves_pattern_and_restores(self):
        show = Show(mode="solid")
        show.update({"blackout": True})
        self.assertEqual(show.frame(0), [(0, 0, 0)] * 16)
        show.update({"blackout": False})
        self.assertEqual(show.frame(1)[0], (255, 65, 0))

    def test_invalid_updates_are_atomic(self):
        invalid = ({"brightness": 1.01}, {"speed": float("nan")}, {"brightness": True},
                   {"color": [0, 256, 0]}, {"color": [0, 0, False]}, {"blackout": 1},
                   {"mode": "invalid"}, {"speed": 0}, {"unknown": 1}, None,
                   {"mode": "solid", "brightness": 2}, {"automatic": 1},
                   {"color_mode": "bad"}, {"gradient": []},
                   {"gradient": [[0, 255, 0, 0, 50], [0, 0, 0, 255, 50]]},
                   {"gradient": [[0, 255, 0, 0, 0], [100, 0, 0, 255, 50]]},
                   {"gradient": [[0, 255, 0, 0, 50], [99, 0, 0, 255, 50]]})
        for values in invalid:
            show = Show()
            before = dict(show.settings)
            with self.assertRaises((ValueError, TypeError)):
                show.update(values)
            self.assertEqual(show.settings, before)

    def test_command_ack_and_save(self):
        show = Show()
        saved = []
        response = dispatch(b'{"id": 8, "command":"set", "settings":{"brightness":0}}', show)
        self.assertTrue(response["ok"])
        self.assertEqual(response["id"], 8)
        self.assertEqual(show.settings["brightness"], 0)
        dispatch(b'{"command":"save"}', show, lambda s: saved.append(dict(s)))
        self.assertEqual(saved, [show.settings])

    def test_selection_autosaves_and_failed_save_reports_error(self):
        show = Show()
        saved = []
        response = dispatch(b'{"command":"set","settings":{"mode":"chase","color":[0,255,0]}}', show, lambda s: saved.append(dict(s)))
        self.assertTrue(response["ok"])
        restored = Show()
        restored.update(json.loads(json.dumps(saved[-1])))
        self.assertEqual(restored.settings, show.settings)
        def fail(settings):
            raise OSError("flash write failed")
        response = dispatch(b'{"command":"set","settings":{"mode":"solid"}}', show, fail)
        self.assertFalse(response["ok"])
        self.assertEqual(show.settings["mode"], "chase")

    def test_live_color_applies_without_flash_writes_until_committed(self):
        show=Show(mode="solid")
        saved=[]
        save=lambda settings:saved.append(json.loads(json.dumps(settings)))
        response=dispatch(b'{"command":"set","persist":false,"settings":{"color":[0,255,0]}}',show,save)
        self.assertTrue(response["ok"])
        self.assertEqual(show.frame(0)[0],(0,255,0))
        self.assertEqual(saved,[])
        response=dispatch(b'{"command":"set","persist":true,"settings":{"color":[0,255,0]}}',show,save)
        self.assertTrue(response["ok"])
        self.assertEqual(len(saved),1)
        self.assertEqual(saved[0]["color"],[0,255,0])
        before=dict(show.settings)
        response=dispatch(b'{"command":"set","persist":0,"settings":{"color":[255,0,0]}}',show,save)
        self.assertFalse(response["ok"])
        self.assertEqual(show.settings,before)

    def test_live_gradient_preview_and_final_commit_preserve_other_settings(self):
        show=Show(mode="breathing")
        show.update({"color_mode":"gradient","speed":.55})
        saved=[]
        stops=[[0,0,255,0,50],[100,0,0,255,50]]
        message={"command":"set","settings":{"gradient":stops},"persist":False}
        self.assertTrue(dispatch(json.dumps(message).encode(),show,lambda s:saved.append(dict(s)))["ok"])
        self.assertEqual(saved,[])
        self.assertEqual(show.settings["gradient"],stops)
        message["persist"]=True
        self.assertTrue(dispatch(json.dumps(message).encode(),show,lambda s:saved.append(dict(s)))["ok"])
        self.assertEqual(len(saved),1)
        self.assertEqual(show.settings["mode"],"breathing")
        self.assertEqual(show.settings["speed"],.55)

    def test_bad_command_does_not_break_next_command(self):
        show = Show()
        for raw in (b"garbage", b"[]", b"null", b'"string"', b'{"command":"set"}', b'\xff'):
            self.assertFalse(dispatch(raw, show)["ok"])
        self.assertTrue(dispatch(b'{"command":"hello"}', show)["ok"])

    def test_line_parser_handles_split_and_oversized_commands(self):
        lines = Lines()
        self.assertEqual(lines.feed(b'{"command":'), [])
        self.assertEqual(lines.feed(b'"hello"}\n'), [b'{"command":"hello"}'])
        self.assertEqual(lines.feed(b"x" * 4000), [])
        self.assertLessEqual(len(lines.buffer), 1024)
        self.assertEqual(lines.feed(b'\n{"command":"state"}\n'), [None, b'{"command":"state"}'])

    def test_partial_usb_writes_preserve_complete_ordered_messages(self):
        box = Outbox()
        messages = [{"id": 1, "ok": True}, {"id": 2, "settings": {"brightness": .15}}]
        for message in messages:
            self.assertTrue(box.send(message))
        class SlowSerial:
            data = bytearray()
            def write(self, data):
                self.data.extend(data[:7])
                return min(7, len(data))
        serial = SlowSerial()
        while box.buffer:
            box.flush(serial)
        self.assertEqual([json.loads(line) for line in serial.data.splitlines()], messages)
        self.assertFalse(box.send({"too_big": "x" * 5000}))


if __name__ == "__main__":
    unittest.main()
