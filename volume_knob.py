from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class VolumeKnobController:
    center: tuple[int, int]
    radius: int
    value: float = 0.5
    min_angle: float = -135.0
    max_angle: float = 135.0
    hit_padding: int = 6
    is_dragging: bool = False

    def _clamp_value(self, value: float) -> float:
        return float(max(0.0, min(1.0, value)))

    def _clamp_angle(self, angle: float) -> float:
        return float(max(self.min_angle, min(self.max_angle, angle)))

    def _angle_from_position(self, mouse_pos: tuple[int, int]) -> float:
        mx, my = mouse_pos
        cx, cy = self.center
        # Screen Y grows downward, invert Y-delta so "up" maps to larger angle/value.
        return math.degrees(math.atan2(cy - my, mx - cx))

    def _value_from_position(self, mouse_pos: tuple[int, int]) -> float:
        angle = self._clamp_angle(self._angle_from_position(mouse_pos))
        value = (angle - self.min_angle) / (self.max_angle - self.min_angle)
        return self._clamp_value(value)

    def contains(self, mouse_pos: tuple[int, int]) -> bool:
        mx, my = mouse_pos
        cx, cy = self.center
        return math.hypot(mx - cx, my - cy) <= (self.radius + self.hit_padding)

    def start_drag(self, mouse_pos: tuple[int, int]) -> bool:
        if not self.contains(mouse_pos):
            return False
        self.is_dragging = True
        self.value = self._value_from_position(mouse_pos)
        return True

    def stop_drag(self) -> None:
        self.is_dragging = False

    def drag(self, mouse_pos: tuple[int, int]) -> bool:
        if not self.is_dragging:
            return False
        self.value = self._value_from_position(mouse_pos)
        return True

    def sprite_rotation_degrees(self) -> float:
        return self.max_angle - (self.value * (self.max_angle - self.min_angle))
