"""Low-output onboard NeoPixel heartbeat; external show brightness is independent."""
import math


def status_color(state, now):
    if state == "starting":
        return (6, 2, 0)
    if state == "error":
        return (8, 0, 0)
    if state == "offline":
        level = .15 + .85 * (.5 + .5 * math.sin(now * 2))
        return (int(6 * level), int(2 * level), 0)
    phase = now % 2
    beat = max(0, 1 - abs(phase - .15) / .15) + .6 * max(0, 1 - abs(phase - .45) / .12)
    level = int(7 * beat)
    return (0, 0, level) if state == "blackout" else (0, level, 0)


class BoardStatus:
    def __init__(self):
        import board
        import digitalio
        import neopixel_write
        import supervisor
        self.supervisor = supervisor
        self.write = neopixel_write.neopixel_write
        supervisor.runtime.rgb_status_brightness = 0
        self.power = digitalio.DigitalInOut(board.NEOPIXEL_POWER)
        self.power.switch_to_output(value=True)
        self.pin = digitalio.DigitalInOut(board.NEOPIXEL)
        self.pin.switch_to_output(value=False)
        self.buffer = bytearray(3)
        self.previous = -1
        self.tick("starting", 0)

    def tick(self, state, now):
        if now - self.previous < .04:
            return
        self.previous = now
        red, green, blue = status_color(state, now)
        self.buffer[0], self.buffer[1], self.buffer[2] = green, red, blue
        self.write(self.pin, self.buffer)

    def restore(self):
        self.write(self.pin, bytearray(3))
        self.pin.deinit()
        # Leave the power output enabled for CircuitPython's native REPL/OTA indicator.
        self.supervisor.runtime.rgb_status_brightness = 8

    def suspend(self):
        self.write(self.pin, bytearray(3))
        self.pin.deinit()
        self.power.value = False
        self.power.deinit()
        self.supervisor.runtime.rgb_status_brightness = 0
