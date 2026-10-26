import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from esp32_controller import ESP32Controller  # noqa: E402
from haptic_feedback import HapticMapper  # noqa: E402
from web_mvp_server import correction_text  # noqa: E402


class FakeSerial:
    def __init__(self):
        self.is_open = True
        self.writes = []

    def write(self, payload):
        self.writes.append(payload)

    def flush(self):
        pass


class HapticMappingTests(unittest.TestCase):
    def test_confirmed_physical_motor_layout(self):
        self.assertEqual(HapticMapper.DOWN, 0)
        self.assertEqual(HapticMapper.LEFT, 1)
        self.assertEqual(HapticMapper.UP, 2)
        self.assertEqual(HapticMapper.RIGHT, 3)

    def test_shoulder_direction_matches_correction_text(self):
        self.assertEqual(HapticMapper._resolve("left_shoulder", 25), ("left", 0))
        self.assertEqual(HapticMapper._resolve("left_shoulder", -25), ("left", 2))
        self.assertEqual(correction_text("left_shoulder", 25), "降低手臂")
        self.assertEqual(correction_text("left_shoulder", -25), "抬高手臂")

    def test_single_band_uses_largest_normalized_deviation(self):
        result = {
            "deviations": {
                "left_elbow": {
                    "is_correct": False,
                    "difference": 18,
                    "abs_difference": 18,
                    "threshold": 15,
                },
                "right_knee": {
                    "is_correct": False,
                    "difference": -45,
                    "abs_difference": 45,
                    "threshold": 20,
                },
            }
        }
        guidance = HapticMapper.primary_left_wrist_guidance(result)
        self.assertEqual(guidance["joint"], "right_knee")
        self.assertEqual(guidance["motor"], HapticMapper.RIGHT)
        self.assertEqual(guidance["direction"], "right")
        self.assertEqual(guidance["intensity"], 255)


class SerialKeepaliveTests(unittest.TestCase):
    def test_identical_command_is_resent_before_firmware_timeout(self):
        controller = ESP32Controller(port="COM_TEST")
        controller.connected = True
        controller.ser = FakeSerial()

        with patch("esp32_controller.time.monotonic", side_effect=[10.0, 10.5, 10.8]):
            self.assertTrue(controller.send_motor_command([(2, 150)], []))
            self.assertTrue(controller.send_motor_command([(2, 150)], []))
            self.assertTrue(controller.send_motor_command([(2, 150)], []))

        self.assertEqual(
            controller.ser.writes,
            [b"L:2,150 R:N\n", b"L:2,150 R:N\n"],
        )


if __name__ == "__main__":
    unittest.main()
