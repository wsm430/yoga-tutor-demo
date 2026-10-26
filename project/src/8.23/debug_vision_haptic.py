r"""Print the haptic direction that camera-based pose comparison would send.

By default this script does not vibrate the band. It only prints the left-wrist
command that the vision pipeline would produce.

Run from the project root:
    python src\debug_vision_haptic.py

Optional:
    python src\debug_vision_haptic.py --pose "Plank Pose"
    python src\debug_vision_haptic.py --send
"""

import argparse
import os
import time

import cv2

from config import CAMERA_INDEX, CAMERA_WIDTH, CAMERA_HEIGHT, STANDARD_POSES_DIR
from esp32_controller import ESP32Controller
from haptic_feedback import HapticMapper
from one_euro_filter import MultiPointFilter
from pose_comparator import PoseComparator
from pose_detection import PoseDetector


MOTOR_NAMES = {
    HapticMapper.DOWN: "DOWN / M0",
    HapticMapper.LEFT: "LEFT / M1",
    HapticMapper.UP: "UP / M2",
    HapticMapper.RIGHT: "RIGHT / M3",
}


def find_pose_path(pose_name=None):
    pose_files = sorted(f for f in os.listdir(STANDARD_POSES_DIR) if f.endswith(".json"))
    if not pose_files:
        raise FileNotFoundError(f"No pose JSON files found in {STANDARD_POSES_DIR}")

    if pose_name:
        wanted = pose_name.lower()
        for filename in pose_files:
            name = filename[:-5]
            if name.lower() == wanted:
                return os.path.join(STANDARD_POSES_DIR, filename)
        raise FileNotFoundError(f"Pose not found: {pose_name}")

    print("\nAvailable poses:")
    for index, filename in enumerate(pose_files, 1):
        print(f"  {index}. {filename[:-5]}")

    raw = input(f"Select pose (1-{len(pose_files)}, default=1): ").strip() or "1"
    try:
        index = int(raw) - 1
    except ValueError:
        index = 0

    index = max(0, min(index, len(pose_files) - 1))
    return os.path.join(STANDARD_POSES_DIR, pose_files[index])


def describe_motors(motors):
    if not motors:
        return "STOP"
    parts = []
    for motor, pwm in motors:
        parts.append(f"{MOTOR_NAMES.get(motor, 'M' + str(motor))} pwm={pwm}")
    return ", ".join(parts)


def top_deviation(result):
    wrong = [
        (joint, data)
        for joint, data in result.get("deviations", {}).items()
        if not data.get("is_correct")
    ]
    if not wrong:
        return "all checked joints OK"

    joint, data = max(wrong, key=lambda item: item[1].get("abs_difference", 0))
    return (
        f"{joint}: current={data['current']:.0f}, "
        f"target={data['standard']:.0f}, diff={data['difference']:+.0f}"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pose", help="Pose name, for example: Plank Pose")
    parser.add_argument("--send", action="store_true", help="Also send printed left-wrist commands to hardware")
    args = parser.parse_args()

    pose_path = find_pose_path(args.pose)
    comparator = PoseComparator(pose_path)
    detector = PoseDetector(static_mode=False)
    landmark_filter = MultiPointFilter(num_points=33)

    haptic = ESP32Controller() if args.send else None
    if haptic and not haptic.connect():
        print("Could not connect to haptic band. Continuing in print-only mode.")
        haptic = None

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print("Could not open camera.")
        return 1

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)

    last_text = None
    last_print = 0.0

    print("\nVision haptic debug started.")
    print("This prints what the camera would send to the LEFT wrist.")
    print("Press q in the camera window to quit.\n")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            frame = cv2.flip(frame, 1)
            landmarks, annotated = detector.detect(frame)

            if landmarks:
                filtered = landmark_filter.filter_landmarks(landmarks)
                angles = detector.calculate_all_angles(filtered)
                result = comparator.compare(angles)
                left, right = HapticMapper.translate(result)

                text = f"LEFT WRIST: {describe_motors(left)} | {top_deviation(result)}"
                now = time.time()
                if text != last_text or now - last_print > 1.0:
                    print(text)
                    last_text = text
                    last_print = now

                if haptic:
                    haptic.send_motor_command(left, [])

                cv2.putText(annotated, describe_motors(left), (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            else:
                if haptic:
                    haptic.send_stop()
                cv2.putText(annotated, "No pose detected", (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)

            cv2.imshow("Vision Haptic Debug", annotated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        if haptic:
            haptic.send_stop()
            haptic.disconnect()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
