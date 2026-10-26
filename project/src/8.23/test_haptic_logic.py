import unittest

from haptic_feedback import HapticMapper


class HapticMapperTests(unittest.TestCase):
    def test_stop_command(self):
        self.assertEqual(HapticMapper.to_command([], []), "L:N R:N\n")

    def test_all_four_motors_are_supported_and_sorted(self):
        command = HapticMapper.to_command([(3, 999), (0, -2)], [(2, 150)])
        self.assertEqual(command, "L:0,0;3,255 R:2,150\n")

    def test_physical_motor_layout(self):
        self.assertEqual(HapticMapper.DOWN, 0)
        self.assertEqual(HapticMapper.LEFT, 1)
        self.assertEqual(HapticMapper.UP, 2)
        self.assertEqual(HapticMapper.RIGHT, 3)
        self.assertEqual(HapticMapper.INNER, HapticMapper.LEFT)
        self.assertEqual(HapticMapper.OUTER, HapticMapper.RIGHT)

    def test_translate_uses_outer_motor(self):
        result = {"deviations": {
            "left_elbow": {
                "is_correct": False,
                "difference": -20,
                "abs_difference": 20,
                "threshold": 15,
            }
        }}
        left, right = HapticMapper.translate(result)
        self.assertEqual(left, [(HapticMapper.OUTER, 150)])
        self.assertEqual(right, [])


if __name__ == "__main__":
    unittest.main()
