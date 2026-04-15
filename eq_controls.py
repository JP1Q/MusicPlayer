from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass
class KnobControl:
    name: str
    label: str
    center: tuple[int, int]
    radius: int = 20
    value: float = 0.5
    angle_min: float = -135.0
    angle_max: float = 135.0

    def contains_point(self, point: tuple[int, int]) -> bool:
        return math.hypot(point[0] - self.center[0], point[1] - self.center[1]) <= self.radius

    def set_from_pointer(self, point: tuple[int, int]) -> bool:
        previous_value = self.value
        ang = math.degrees(math.atan2(point[1] - self.center[1], point[0] - self.center[0]))
        ang = max(self.angle_min, min(self.angle_max, ang))
        value = (ang - self.angle_min) / (self.angle_max - self.angle_min)
        self.value = max(0.0, min(1.0, float(value)))
        return abs(self.value - previous_value) > 1e-9

    def render_angle(self) -> float:
        return self.angle_max - (self.value * (self.angle_max - self.angle_min))

    def line_indicator_end(self, padding: int = 4) -> tuple[float, float]:
        angle = -math.pi * 0.75 + (self.value * math.pi * 1.5)
        end_x = self.center[0] + math.sin(angle) * (self.radius - padding)
        end_y = self.center[1] - math.cos(angle) * (self.radius - padding)
        return end_x, end_y

    def percent(self) -> int:
        return int(self.value * 100)


class EqualizerControls:
    def __init__(self, knobs: list[KnobControl]):
        self.knobs = knobs
        self._knobs_by_name = {knob.name: knob for knob in knobs}
        self.active_drag_name: str | None = None

    def knob(self, name: str) -> KnobControl:
        return self._knobs_by_name[name]

    def begin_drag(self, point: tuple[int, int]) -> bool:
        for knob in self.knobs:
            if knob.contains_point(point):
                self.active_drag_name = knob.name
                return True
        return False

    def end_drag(self) -> None:
        self.active_drag_name = None

    def drag_to(self, point: tuple[int, int]) -> str | None:
        if not self.active_drag_name:
            return None
        knob = self._knobs_by_name[self.active_drag_name]
        changed = knob.set_from_pointer(point)
        if changed:
            return knob.name
        return None
