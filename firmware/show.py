"""Hardware-independent show engine; frame output is RGB, brightness applied later."""
import math

MODES = ("embers", "cauldron", "ghost", "chase", "breathing", "solid")


def scaled(rgb, value, precise=False):
    values = tuple(max(0, min(255, c * value)) for c in rgb)
    return values if precise else tuple(int(c) for c in values)


def gradient_color(stops, position, precise=False):
    """Sample RGB stops; each stop's fifth value is its fade midpoint."""
    for left, right in zip(stops, stops[1:]):
        if position <= right[0]:
            fraction = max(0, (position - left[0]) / (right[0] - left[0]))
            midpoint = left[4] / 100
            mix = .5 * fraction / midpoint if fraction <= midpoint else .5 + .5 * (fraction - midpoint) / (1 - midpoint)
            rgb = tuple(left[c] + (right[c] - left[c]) * mix for c in (1, 2, 3))
            return rgb if precise else tuple(int(c) for c in rgb)
    return tuple(stops[-1][1:4])


class PixelOutput:
    """Quantize once at the wire; distribute fractional breathing levels in space/time."""
    def __init__(self, count):
        self.buffer = bytearray(count * 3)
        self.phase = 0

    def encode(self, frame, brightness, smooth=False):
        for i, rgb in enumerate(frame):
            # Coprime offsets visit all 16 thresholds, staggered across the chain.
            threshold = (((i * 13 + self.phase * 7) % 16) + .5) / 16
            for channel, source in enumerate((1, 0, 2)):
                level = max(0, min(255, rgb[source] * brightness))
                whole = int(level)
                self.buffer[i * 3 + channel] = whole + int(smooth and level - whole > threshold)
        self.phase = (self.phase + 1) % 16 if smooth else 0
        return self.buffer


class Show:
    def __init__(self, brightness=0.15, speed=1.0, mode="embers", limit=1.0):
        self.limit = limit
        self.settings = {"mode": "embers" if mode == "show" else mode, "brightness": brightness, "speed": speed,
                         "color": [255, 65, 0], "color_mode": "solid",
                         "gradient": [[0, 255, 65, 0, 50], [100, 125, 15, 240, 50]],
                         "blackout": False, "automatic": True}
        self.elapsed = 0.0
        self.previous = None

    def update(self, values):
        if not isinstance(values, dict) or not values:
            raise ValueError("settings must be a nonempty object")
        candidate = dict(self.settings)
        for key, value in values.items():
            if key == "mode":
                # Migrate saved settings from the former rotating show.
                if value == "show":
                    value = "embers"
                if value not in MODES:
                    raise ValueError("unknown pattern")
            elif key in ("brightness", "speed"):
                low, high = (0, self.limit) if key == "brightness" else (0.25, 3)
                if type(value) not in (int, float) or not low <= value <= high:
                    raise ValueError("%s must be between %s and %s" % (key, low, high))
            elif key in ("blackout", "automatic"):
                if type(value) is not bool:
                    raise ValueError(key + " must be true or false")
            elif key == "color":
                if (not isinstance(value, (list, tuple)) or len(value) != 3
                        or any(type(v) is not int or not 0 <= v <= 255 for v in value)):
                    raise ValueError("color must contain three integers from 0 to 255")
                value = list(value)
            elif key == "color_mode":
                if value not in ("solid", "gradient"):
                    raise ValueError("color mode must be solid or gradient")
            elif key == "gradient":
                if not isinstance(value, (list, tuple)) or not 2 <= len(value) <= 6:
                    raise ValueError("gradient needs two to six stops")
                previous = -1
                for stop in value:
                    if (not isinstance(stop, (list, tuple)) or len(stop) != 5
                            or any(type(v) is not int for v in stop)
                            or not previous < stop[0] <= 100
                            or not all(0 <= v <= 255 for v in stop[1:4])
                            or not 1 <= stop[4] <= 99):
                        raise ValueError("invalid gradient stop or fade midpoint")
                    previous = stop[0]
                if value[0][0] != 0 or value[-1][0] != 100:
                    raise ValueError("gradient endpoints must be 0 and 100")
                value = [list(stop) for stop in value]
            else:
                raise ValueError("unknown setting: " + str(key))
            candidate[key] = value
        if candidate["mode"] != self.settings["mode"]:
            self.elapsed = 0.0
        self.settings = candidate

    def active(self):
        return self.settings["mode"], self.elapsed, 0

    def frame(self, now, count=16):
        if self.previous is not None:
            self.elapsed += max(0, now - self.previous) * self.settings["speed"]
        self.previous = now
        mode, t, _ = self.active()
        if self.settings["blackout"]:
            return [(0, 0, 0)] * count
        if mode == "breathing":
            # One shared color walks forward and back through the gradient.
            position = 50 * (1 - math.cos(t * .4))
            base = (gradient_color(self.settings["gradient"], position, precise=True)
                    if self.settings["color_mode"] == "gradient" else self.settings["color"])
            value = .12 + .88 * (.5 + .5 * math.sin(t * 1.6))
            return [scaled(base, value, precise=True)] * count
        result = []
        for i in range(count):
            base = (gradient_color(self.settings["gradient"], i * 100 / max(1, count - 1))
                    if self.settings["color_mode"] == "gradient" else self.settings["color"])
            if mode == "embers":
                value = 0.45 + 0.25 * math.sin(t * 6 + i * 2.3) + 0.2 * math.sin(t * 11 + i * 4.1)
            elif mode == "cauldron":
                value = 0.12 + 0.88 * (0.5 + 0.5 * math.sin(t * 2.8 - i * 0.65)) ** 3
            elif mode == "ghost":
                head = (0.5 + 0.5 * math.sin(t * 0.8)) * (count - 1)
                value = max(0.025, 1 - abs(i - head) / 3)
            elif mode == "chase":
                head = int(t * 8) % count
                distance = (head - i) % count
                value = max(0.02, 1 - distance / 5)
            else:
                value = 1
            result.append(scaled(base, value))
        return result
