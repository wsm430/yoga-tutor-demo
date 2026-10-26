"""
haptic_feedback.py

Convert pose deviations into haptic motor commands.

Physical motor layout confirmed on the current wrist band:
  M0 = wrist bottom
  M1 = wrist left side
  M2 = wrist top
  M3 = wrist right side

The firmware protocol still uses raw motor indexes. This module is where
semantic directions such as UP/DOWN/LEFT/RIGHT are mapped to those indexes.
"""

from typing import Dict, List, Tuple


class HapticMapper:
    """Pose deviation -> haptic motor command."""

    # Physical layout on the current band.
    DOWN = 0
    LEFT = 1
    UP = 2
    RIGHT = 3

    # Backward-compatible names used by the existing pose logic.
    INNER = LEFT
    OUTER = RIGHT

    MOTOR_COUNT = 4

    DIRECTION_NAMES = {
        DOWN: "down",
        LEFT: "left",
        UP: "up",
        RIGHT: "right",
    }

    @staticmethod
    def translate(result: dict) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
        """
        Parse PoseComparator.compare() results.

        Returns:
            (left_motors, right_motors), where each item is (motor_index, pwm).
        """
        left: Dict[int, int] = {}
        right: Dict[int, int] = {}

        for joint, dev in result.get("deviations", {}).items():
            if dev["is_correct"]:
                continue

            arm, motor_idx = HapticMapper._resolve(joint, dev["difference"])
            intensity = HapticMapper._intensity(dev)
            target = left if arm == "left" else right

            if motor_idx is not None and 0 <= motor_idx < HapticMapper.MOTOR_COUNT:
                if motor_idx not in target or intensity > target[motor_idx]:
                    target[motor_idx] = intensity

        return list(left.items()), list(right.items())

    @staticmethod
    def to_command(
        left_motors: List[Tuple[int, int]],
        right_motors: List[Tuple[int, int]],
    ) -> str:
        """
        Format commands for the ESP32 firmware.

        Example:
            L:0,255;2,128 R:3,180\n
            L:N R:N
        """
        left_str = HapticMapper._fmt_motors(left_motors)
        right_str = HapticMapper._fmt_motors(right_motors)
        return f"L:{left_str} R:{right_str}\n"

    @staticmethod
    def to_command_bytes(
        left_motors: List[Tuple[int, int]],
        right_motors: List[Tuple[int, int]],
    ) -> bytes:
        return HapticMapper.to_command(left_motors, right_motors).encode("utf-8")

    @staticmethod
    def _resolve(joint: str, diff: float) -> Tuple[str, int]:
        """
        Decide which arm and direction should vibrate.

        diff > 0 means the user's angle is larger than the reference angle.
        diff < 0 means the user's angle is smaller than the reference angle.
        """
        arm = "left" if joint.startswith("left") else "right"
        jtype = joint.split("_", 1)[1]  # elbow / shoulder / knee / hip

        mapping = {
            "elbow": HapticMapper.INNER if diff > 0 else HapticMapper.OUTER,
            "shoulder": HapticMapper.DOWN if diff > 0 else HapticMapper.UP,
            "knee": HapticMapper.INNER if diff > 0 else HapticMapper.OUTER,
            "hip": HapticMapper.DOWN if diff > 0 else HapticMapper.UP,
        }

        return arm, mapping.get(jtype)

    @staticmethod
    def primary_left_wrist_guidance(result: dict):
        """Select one highest-priority correction for the single left band."""
        candidates = []
        for joint, dev in result.get("deviations", {}).items():
            if dev.get("is_correct", True):
                continue
            threshold = max(float(dev.get("threshold", 1)), 1.0)
            ratio = float(dev.get("abs_difference", 0)) / threshold
            candidates.append((ratio, joint, dev))

        if not candidates:
            return None

        _, joint, dev = max(candidates, key=lambda item: item[0])
        _, motor_idx = HapticMapper._resolve(joint, float(dev["difference"]))
        return {
            "joint": joint,
            "motor": motor_idx,
            "direction": HapticMapper.DIRECTION_NAMES[motor_idx],
            "intensity": HapticMapper._intensity(dev),
            "difference": float(dev["difference"]),
        }

    @staticmethod
    def _intensity(dev: dict) -> int:
        threshold = max(float(dev.get("threshold", 1)), 1.0)
        ratio = float(dev.get("abs_difference", abs(dev.get("difference", 0)))) / threshold

        if ratio >= 2.0:
            return 255
        if ratio >= 1.5:
            return 200
        if ratio >= 1.0:
            return 150
        return 100

    @staticmethod
    def _fmt_motors(motors: List[Tuple[int, int]]) -> str:
        if not motors:
            return "N"

        valid = {
            int(m): max(0, min(255, int(p)))
            for m, p in motors
            if 0 <= int(m) < HapticMapper.MOTOR_COUNT
        }
        return ";".join(f"{m},{valid[m]}" for m in sorted(valid)) or "N"
