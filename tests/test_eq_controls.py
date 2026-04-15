import unittest

from eq_controls import EqualizerControls, KnobControl


class EqControlsTests(unittest.TestCase):
    def test_knob_pointer_mapping_clamps_to_range(self):
        knob = KnobControl(name="volume", label="Vol", center=(100, 100), radius=20, value=0.5)
        knob.set_from_pointer((0, 99))
        self.assertAlmostEqual(knob.value, 0.0, places=4)

        knob.set_from_pointer((0, 101))
        self.assertAlmostEqual(knob.value, 1.0, places=4)

    def test_knob_render_angle_matches_value(self):
        knob = KnobControl(name="mid", label="Mid", center=(0, 0), value=0.0)
        self.assertAlmostEqual(knob.render_angle(), 135.0)
        knob.value = 1.0
        self.assertAlmostEqual(knob.render_angle(), -135.0)

    def test_equalizer_drag_flow_tracks_active_knob(self):
        controls = EqualizerControls(
            [
                KnobControl(name="volume", label="Vol", center=(50, 50), radius=20),
                KnobControl(name="low", label="Low", center=(100, 50), radius=20),
            ]
        )
        self.assertTrue(controls.begin_drag((50, 50)))
        self.assertEqual(controls.active_drag_name, "volume")
        changed = controls.drag_to((0, 49))
        self.assertEqual(changed, "volume")
        self.assertLess(controls.knob("volume").value, 0.1)
        controls.end_drag()
        self.assertIsNone(controls.drag_to((0, 49)))


if __name__ == "__main__":
    unittest.main()
