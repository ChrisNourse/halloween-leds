"""Sunset-to-sunrise schedule using NOAA's approximate solar equations."""
import math
import time

DIM_STEPS = ((0, 1.0), (7200, .5), (14400, .25))


def dim_factor(seconds):
    seconds = max(0, seconds)
    for i in range(1, len(DIM_STEPS)):
        start, first = DIM_STEPS[i - 1]
        end, last = DIM_STEPS[i]
        if seconds < end:
            return first + (last - first) * (seconds - start) / (end - start)
    return DIM_STEPS[-1][1]


def sun_events(day_start, latitude, longitude):
    """Return UTC sunrise/sunset epochs for a Gregorian date, including date rollover."""
    date = getattr(time, "gmtime", time.localtime)(day_start)
    leap = date.tm_year % 4 == 0 and (date.tm_year % 100 != 0 or date.tm_year % 400 == 0)
    gamma = 2 * math.pi / (366 if leap else 365) * (date.tm_yday - 1)
    equation = 229.18 * (.000075 + .001868 * math.cos(gamma) - .032077 * math.sin(gamma)
                         - .014615 * math.cos(2 * gamma) - .040849 * math.sin(2 * gamma))
    declination = (.006918 - .399912 * math.cos(gamma) + .070257 * math.sin(gamma)
                   - .006758 * math.cos(2 * gamma) + .000907 * math.sin(2 * gamma)
                   - .002697 * math.cos(3 * gamma) + .00148 * math.sin(3 * gamma))
    lat = math.radians(latitude)
    cosine = (math.cos(math.radians(90.833)) / (math.cos(lat) * math.cos(declination))
              - math.tan(lat) * math.tan(declination))
    if not -1 <= cosine <= 1:
        raise ValueError("No sunrise/sunset at this latitude on this date")
    angle = math.degrees(math.acos(cosine))
    noon = 720 - 4 * longitude - equation
    return (day_start + (noon - 4 * angle) * 60,
            day_start + (noon + 4 * angle) * 60)


class SolarSchedule:
    def __init__(self, latitude, longitude):
        self.latitude = latitude
        self.longitude = longitude
        self.day = None
        self.events = []

    def evaluate(self, epoch, automatic=True, force_awake=False):
        if not automatic:
            return {"phase": "manual", "factor": 1.0, "next_transition": None,
                    "next_sunset": None, "next_sunrise": None, "can_sleep": False}
        if self.latitude is None or self.longitude is None:
            return {"phase": "location required" if automatic else "manual",
                    "factor": 1.0, "next_transition": None,
                    "next_sunset": None, "next_sunrise": None, "can_sleep": False}
        if epoch is None:
            manual = not automatic or force_awake
            return {"phase": "manual" if manual else "waiting for clock",
                    "factor": 1.0 if manual else 0.0, "next_transition": None,
                    "next_sunset": None, "next_sunrise": None, "can_sleep": False}
        day = int(epoch // 86400) * 86400
        if day != self.day:
            events = []
            for offset in (-2, -1, 0, 1, 2):
                try:
                    rise, setting = sun_events(day + offset * 86400, self.latitude, self.longitude)
                except ValueError:
                    events = []
                    break
                events.extend(((rise, "sunrise"), (setting, "sunset")))
            self.events = sorted(events)
            self.day = day
        if not self.events:
            # Polar seasons have no daily cycle; keep controls available and retry next day.
            return {"phase": "solar unavailable", "factor": 1.0, "next_transition": None,
                    "next_sunset": None, "next_sunrise": None, "can_sleep": False}
        previous = max(event for event in self.events if event[0] <= epoch)
        upcoming = min(event for event in self.events if event[0] > epoch)
        sunrise = min(t for t, kind in self.events if kind == "sunrise" and t > epoch)
        sunset = min(t for t, kind in self.events if kind == "sunset" and t > epoch)
        night = previous[1] == "sunset"
        manual = not automatic or (force_awake and not night)
        return {"phase": "manual wake" if force_awake and automatic and not night else ("manual" if not automatic else ("night" if night else "day")),
                "factor": 1.0 if manual else (dim_factor(epoch - previous[0]) if night else 0.0),
                "next_transition": upcoming[0], "next_event": upcoming[1],
                "next_sunset": sunset, "next_sunrise": sunrise,
                "can_sleep": automatic and not night and not force_awake}
