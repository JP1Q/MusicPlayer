import unittest

from volume_knob import VolumeKnobController


class VolumeKnobControllerTests(unittest.TestCase):
    def test_start_drag_updates_value_immediately(self):
        knob = VolumeKnobController(center=(100, 100), radius=20, value=0.5)

        started = knob.start_drag((100, 80))  # top

        self.assertTrue(started)
        self.assertTrue(knob.is_dragging)
        self.assertGreater(knob.value, 0.8)

    def test_start_drag_rejects_click_outside_hit_area(self):
        knob = VolumeKnobController(center=(100, 100), radius=20, hit_padding=6)

        started = knob.start_drag((140, 100))

        self.assertFalse(started)
        self.assertFalse(knob.is_dragging)

    def test_drag_changes_value_only_while_dragging(self):
        knob = VolumeKnobController(center=(100, 100), radius=20, value=0.5)

        self.assertFalse(knob.drag((120, 100)))
        self.assertEqual(knob.value, 0.5)

        knob.start_drag((120, 100))
        self.assertTrue(knob.drag((100, 120)))
        self.assertLess(knob.value, 0.5)

    def test_sprite_rotation_degrees_maps_value_to_rotation(self):
        knob = VolumeKnobController(center=(0, 0), radius=20, value=0.0)
        self.assertEqual(knob.sprite_rotation_degrees(), -135.0)
        knob.value = 1.0
        self.assertEqual(knob.sprite_rotation_degrees(), 135.0)


if __name__ == "__main__":
    unittest.main()
