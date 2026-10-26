"""Yoga Tutor web server (pose-selectable version).

The browser owns the laptop camera and posts JPEG frames to this process.
Python runs MediaPipe, waits for stillness, compares against the selected
standard pose, and drives the left wrist band (serial or BLE).

Run:
    python web_mvp_server.py --haptic ble
    python web_mvp_server.py --haptic serial --motors 1,3
Then open http://127.0.0.1:4173
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import re
import threading
import time
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

from config import STANDARD_IMAGES_DIR, STANDARD_POSES_DIR
from haptic_feedback import HapticMapper
from haptic_transport import create_haptic_transport


SRC_DIR = Path(__file__).resolve().parent
WEB_DIR = SRC_DIR / "webui"
DEFAULT_POSE = "Warrior II Pose"
MAX_FRAME_BYTES = 2_500_000
MAX_JSON_BYTES = 10_000
REQUIRED_LANDMARKS = (11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28)
JOINT_LABELS = {
    "left_elbow": "左肘",
    "right_elbow": "右肘",
    "left_knee": "左膝",
    "right_knee": "右膝",
    "left_shoulder": "左肩",
    "right_shoulder": "右肩",
    "left_hip": "左髋",
    "right_hip": "右髋",
}
POSE_LABELS = {
    "Bow Pose": "弓式",
    "Downward-Facing Dog Pose": "下犬式",
    "Half Forward Fold": "半前屈式",
    "Plank Pose": "平板支撑",
    "Seated Meditation Pose": "冥想坐姿",
    "Standing Hand-to-Big-Toe Pose": "站立手抓大脚趾式",
    "Tree Pose": "树式",
    "Triangle Pose": "三角式",
    "Upward-Facing Dog Pose": "上犬式",
    "Vrischikasana": "蝎子式",
    "Warrior I Pose": "战士一式",
    "Warrior II Pose": "战士二式",
    "Wheel Pose": "轮式",
}
MOTOR_LABELS = {0: "下侧 M0", 1: "左侧 M1", 2: "上侧 M2", 3: "右侧 M3"}


def correction_text(joint: str, difference: float) -> str:
    kind = joint.split("_", 1)[-1]
    if kind in {"elbow", "knee"}:
        return "进一步弯曲" if difference > 0 else "适当伸直"
    if kind == "shoulder":
        return "降低手臂" if difference > 0 else "抬高手臂"
    if kind == "hip":
        return "减小髋部夹角" if difference > 0 else "增大髋部夹角"
    return "调整姿势"


# ---------------------------------------------------------------- pose library

def _base_name(stem: str) -> str:
    """'Bow Pose1' -> 'Bow Pose', 'Vrischikasana4' -> 'Vrischikasana'."""
    return re.sub(r"\d+$", "", stem).strip()


def load_pose_library():
    """One entry per pose. Numbered duplicates are merged; the variant that
    has a reference image is preferred."""
    poses_dir = Path(STANDARD_POSES_DIR)
    images_dir = Path(STANDARD_IMAGES_DIR)
    groups = {}
    for path in sorted(poses_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            angles = data["average_pose"]["angles"]
        except Exception as exc:  # broken file: skip, keep server alive
            print(f"[Web] Skip {path.name}: {exc}")
            continue
        image = data.get("source_file")
        has_image = bool(image) and (images_dir / image).is_file()
        if not has_image and (images_dir / f"{path.stem}.jpg").is_file():
            image, has_image = f"{path.stem}.jpg", True
        groups.setdefault(_base_name(path.stem), []).append({
            "id": path.stem,
            "path": path,
            "image": image if has_image else None,
            "joint_count": len(angles),
        })

    library = {}
    for base, items in groups.items():
        items.sort(key=lambda item: (item["image"] is None, item["id"] != base, item["id"]))
        best = items[0]
        library[best["id"]] = {
            "id": best["id"],
            "name": base,
            "label": POSE_LABELS.get(base, base),
            "path": best["path"],
            "image": best["image"],
        }
    return library


# ---------------------------------------------------------------- session

class TutorSession:
    def __init__(self, haptic_mode="serial", working_motors=(0, 1, 2, 3),
                 pose_id=DEFAULT_POSE):
        try:
            import cv2
            import numpy as np
            from one_euro_filter import MultiPointFilter
            from pose_comparator import PoseComparator
            from pose_detection import PoseDetector
            from stillness_detector import StillnessDetector
        except ImportError as exc:
            raise RuntimeError(
                "Missing vision dependencies. Activate the Yoga Tutor Python "
                "environment and install requirements.txt."
            ) from exc

        self.cv2 = cv2
        self.np = np
        self._PoseComparator = PoseComparator
        self._MultiPointFilter = MultiPointFilter
        self.detector = PoseDetector(static_mode=False)
        self.filter = MultiPointFilter(num_points=33)
        self.stillness = StillnessDetector()
        self.library = load_pose_library()
        if not self.library:
            raise RuntimeError(f"No standard poses found in {STANDARD_POSES_DIR}")
        if pose_id not in self.library:
            pose_id = next(iter(self.library))
        self.pose_id = pose_id
        self.comparator = PoseComparator(str(self.library[pose_id]["path"]))

        self.haptic_mode = haptic_mode
        self.working_motors = tuple(sorted(set(working_motors)))
        self.haptic_enabled = haptic_mode != "none"
        self.haptic = create_haptic_transport(haptic_mode)
        self._haptic_lock = threading.Lock()
        self._haptic_active = False
        self._haptic_state = "disconnected" if haptic_mode != "none" else "off"
        self._last_motor = None
        self._lock = threading.Lock()
        self._closing = threading.Event()

        # Connect in the background so a missing band never blocks frames.
        if haptic_mode != "none":
            threading.Thread(target=self._haptic_keeper, daemon=True).start()

    # ----- haptic connection management

    def _haptic_keeper(self):
        while not self._closing.is_set():
            if not self.haptic.connected:
                self._haptic_state = "connecting"
                try:
                    with self._haptic_lock:
                        self.haptic.connect()
                except Exception as exc:
                    print(f"[Web] Haptic connect error: {exc}")
                self._haptic_state = "connected" if self.haptic.connected else "disconnected"
            else:
                self._haptic_state = "connected"
            self._closing.wait(2.0)

    def reconnect_haptic(self):
        if self.haptic_mode == "none":
            return self.status()
        # If the keeper is already scanning, just let it finish.
        if not self._haptic_lock.acquire(timeout=0.2):
            return self.status()
        try:
            self.haptic.disconnect()
        except Exception:
            pass
        finally:
            # Allow the controller to retry immediately.
            if hasattr(self.haptic, "_last_connect_attempt"):
                self.haptic._last_connect_attempt = 0.0
            self._haptic_lock.release()
        self._haptic_state = "connecting"
        return self.status()

    def _send_haptic(self, motors):
        """Never blocks on a reconnect: only sends when already connected."""
        if not self.haptic.connected:
            return False
        if not self._haptic_lock.acquire(timeout=0.05):
            return False
        try:
            if motors:
                ok = self.haptic.send_motor_command(motors, [])
            else:
                ok = self.haptic.send_stop()
        finally:
            self._haptic_lock.release()
        return bool(ok)

    def _stop_haptic(self):
        if self._haptic_active:
            self._send_haptic([])
        self._haptic_active = False
        self._last_motor = None

    def set_haptic_enabled(self, enabled: bool):
        self.haptic_enabled = bool(enabled) and self.haptic_mode != "none"
        if not self.haptic_enabled:
            with self._lock:
                self._stop_haptic()
        return self.status()

    def test_motor(self, motor: int, duration=0.6):
        if motor not in range(HapticMapper.MOTOR_COUNT):
            raise ValueError("motor must be 0-3")
        if not self.haptic.connected:
            return {"ok": False, "message": "腕带未连接"}

        def run():
            self._send_haptic([(motor, 220)])
            time.sleep(duration)
            self._send_haptic([])

        threading.Thread(target=run, daemon=True).start()
        return {"ok": True, "message": f"{MOTOR_LABELS[motor]} 振动 {duration:.1f} 秒"}

    # ----- pose selection

    def poses(self):
        return [
            {
                "id": item["id"],
                "name": item["name"],
                "label": item["label"],
                "image": f"/api/pose-image/{quote(item['id'])}" if item["image"] else None,
            }
            for item in sorted(self.library.values(), key=lambda p: p["label"])
        ]

    def select_pose(self, pose_id: str):
        if pose_id not in self.library:
            raise ValueError(f"Unknown pose: {pose_id}")
        comparator = self._PoseComparator(str(self.library[pose_id]["path"]))
        with self._lock:
            self.pose_id = pose_id
            self.comparator = comparator
            self.stillness.reset()
            self._stop_haptic()
        return self.status()

    def pose_image_path(self, pose_id: str):
        item = self.library.get(pose_id)
        if not item or not item["image"]:
            return None
        return Path(STANDARD_IMAGES_DIR) / item["image"]

    # ----- status / control

    def status(self):
        pose = self.library[self.pose_id]
        return {
            "ready": True,
            "pose": {"id": pose["id"], "name": pose["name"], "label": pose["label"]},
            "target_pose": pose["name"],
            "standard_angles": self.comparator.standard_angles,
            "haptic": self._haptic_info(),
            "haptic_connected": bool(self.haptic.connected),
            "transport": self.haptic_mode,
        }

    def _haptic_info(self):
        return {
            "transport": self.haptic_mode,
            "state": self._haptic_state if self.haptic_mode != "none" else "off",
            "connected": bool(self.haptic.connected),
            "enabled": self.haptic_enabled,
            "working_motors": list(self.working_motors),
            "active_motor": self._last_motor,
        }

    def reset(self):
        with self._lock:
            self.stillness.reset()
            self.filter = self._MultiPointFilter(num_points=33)
            self._stop_haptic()
        return self.status()

    def close(self):
        self._closing.set()
        with self._lock:
            self._stop_haptic()
        try:
            self.haptic.disconnect()
        except Exception:
            pass

    # ----- frame processing

    def process_jpeg(self, payload: bytes):
        image = self.cv2.imdecode(
            self.np.frombuffer(payload, dtype=self.np.uint8),
            self.cv2.IMREAD_COLOR,
        )
        if image is None:
            raise ValueError("Invalid JPEG frame")

        with self._lock:
            t0 = time.perf_counter()
            landmarks, _ = self.detector.detect(image)
            if not landmarks:
                self.stillness.reset()
                self._stop_haptic()
                response = self._base_response("no_pose", image, None)
                response["message"] = "没有检测到人，请站到镜头前"
                return self._finish(response, t0)

            filtered = self.filter.filter_landmarks(landmarks)
            missing = [
                index for index in REQUIRED_LANDMARKS
                if filtered[index]["visibility"] < 0.45
            ]
            if missing:
                self.stillness.reset()
                self._stop_haptic()
                response = self._base_response("partial", image, filtered)
                response["message"] = "请后退一些，确保肩、手腕、髋、膝和脚踝都在画面内"
                response["missing_landmarks"] = missing
                return self._finish(response, t0)

            angles = self.detector.calculate_all_angles(filtered)
            result = self.comparator.compare(angles)
            joints = self._joint_rows(result)
            ready = self.stillness.update(filtered)
            if not ready:
                self._stop_haptic()
                response = self._base_response("holding", image, filtered)
                response["hold_progress"] = round(self.stillness.progress, 3)
                response["joints"] = joints  # live preview, no haptics yet
                response["message"] = f"保持{self.library[self.pose_id]['label']}不动"
                return self._finish(response, t0)

            guidance = HapticMapper.primary_left_wrist_guidance(result)
            haptic_guidance = self._haptic_guidance(result)
            haptic_sent = False
            if haptic_guidance and self.haptic_enabled:
                motors = [(haptic_guidance["motor"], haptic_guidance["intensity"])]
                haptic_sent = self._send_haptic(motors)
                self._haptic_active = self._haptic_active or haptic_sent
                self._last_motor = haptic_guidance["motor"] if haptic_sent else None
            else:
                self._stop_haptic()

            if guidance:
                guidance["joint_label"] = JOINT_LABELS.get(guidance["joint"], guidance["joint"])
                guidance["correction"] = correction_text(guidance["joint"], guidance["difference"])
                guidance["motor_label"] = MOTOR_LABELS.get(guidance["motor"])
                guidance["motor_working"] = guidance["motor"] in self.working_motors
            if haptic_guidance:
                haptic_guidance["joint_label"] = JOINT_LABELS.get(
                    haptic_guidance["joint"], haptic_guidance["joint"])
                haptic_guidance["motor_label"] = MOTOR_LABELS.get(haptic_guidance["motor"])
                haptic_guidance["sent"] = haptic_sent

            response = self._base_response("evaluating", image, filtered)
            response.update({
                "hold_progress": 1.0,
                "score": round(float(result["score"]), 1),
                "guidance": guidance,
                "haptic_guidance": haptic_guidance,
                "joints": joints,
                "correct_count": sum(row["is_correct"] for row in joints),
                "message": (
                    "很好！姿势在容差范围内"
                    if guidance is None
                    else f"{guidance['joint_label']}：{guidance['correction']}"
                ),
            })
            return self._finish(response, t0)

    def _haptic_guidance(self, result):
        """Like primary_left_wrist_guidance, but only among motors that work."""
        candidates = []
        for joint, dev in result.get("deviations", {}).items():
            if dev.get("is_correct", True):
                continue
            _, motor = HapticMapper._resolve(joint, float(dev["difference"]))
            if motor not in self.working_motors:
                continue
            ratio = float(dev["abs_difference"]) / max(float(dev["threshold"]), 1.0)
            candidates.append((ratio, joint, dev, motor))
        if not candidates:
            return None
        _, joint, dev, motor = max(candidates, key=lambda item: item[0])
        return {
            "joint": joint,
            "motor": motor,
            "direction": HapticMapper.DIRECTION_NAMES[motor],
            "intensity": HapticMapper._intensity(dev),
        }

    def _finish(self, response, t0):
        response["process_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        response["haptic"] = self._haptic_info()
        return response

    @staticmethod
    def _joint_rows(result):
        rows = []
        for joint, item in result["deviations"].items():
            rows.append({
                "joint": joint,
                "label": JOINT_LABELS.get(joint, joint),
                "current": round(float(item["current"]), 1),
                "standard": round(float(item["standard"]), 1),
                "difference": round(float(item["difference"]), 1),
                "threshold": float(item["threshold"]),
                "is_correct": bool(item["is_correct"]),
                "hint": None if item["is_correct"] else correction_text(joint, item["difference"]),
            })
        return rows

    def _base_response(self, state, image, landmarks):
        height, width = image.shape[:2]
        points = [] if landmarks is None else [
            {
                "x": round(float(item["x"]) / width, 6),
                "y": round(float(item["y"]) / height, 6),
                "visibility": round(float(item["visibility"]), 3),
            }
            for item in landmarks
        ]
        pose = self.library[self.pose_id]
        return {
            "state": state,
            "pose_id": pose["id"],
            "target_pose": pose["name"],
            "hold_progress": 0.0,
            "landmarks": points,
            "haptic_connected": bool(self.haptic.connected),
            "transport": self.haptic_mode,
        }


# Old name kept so existing imports keep working.
WarriorIISession = TutorSession


# ---------------------------------------------------------------- HTTP

class YogaTutorServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, handler, session, web_dir):
        super().__init__(address, handler)
        self.session = session
        self.web_dir = web_dir


class YogaTutorHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(args[2].web_dir), **kwargs)

    def log_message(self, fmt, *args):
        # Frame posts are ~10/s; keep the console readable.
        if "/api/frame" in (self.path or ""):
            return
        super().log_message(fmt, *args)

    def do_GET(self):
        path = urlparse(self.path).path
        session = self.server.session
        if path == "/api/status":
            self._send_json(session.status())
            return
        if path == "/api/poses":
            self._send_json({"poses": session.poses(), "current": session.pose_id})
            return
        if path.startswith("/api/pose-image/"):
            self._send_file(session.pose_image_path(unquote(path[len("/api/pose-image/"):])))
            return
        if path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self):
        session = self.server.session
        path = urlparse(self.path).path
        try:
            if path == "/api/frame":
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_FRAME_BYTES:
                    self.send_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                    return
                self._send_json(session.process_jpeg(self.rfile.read(length)))
                return

            body = self._read_json()
            if path == "/api/reset":
                self._send_json(session.reset())
            elif path == "/api/pose":
                self._send_json(session.select_pose(str(body.get("id", ""))))
            elif path == "/api/haptic":
                self._send_json(session.set_haptic_enabled(body.get("enabled", True)))
            elif path == "/api/haptic/reconnect":
                self._send_json(session.reconnect_haptic())
            elif path == "/api/haptic/test":
                self._send_json(session.test_motor(int(body.get("motor", -1))))
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        if length > MAX_JSON_BYTES:
            raise ValueError("Request too large")
        data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        return data if isinstance(data, dict) else {}

    def _send_file(self, path):
        if path is None or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "image/jpeg")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, data, status=HTTPStatus.OK):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def parse_motors(text: str):
    motors = tuple(int(part) for part in text.split(",") if part.strip() != "")
    if not motors or any(m not in range(4) for m in motors):
        raise argparse.ArgumentTypeError("motors must be like 0,1,2,3")
    return motors


def parse_args():
    parser = argparse.ArgumentParser(description="Run the Yoga Tutor web app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=4173, type=int)
    parser.add_argument("--haptic", choices=("serial", "none", "ble"), default="serial")
    parser.add_argument(
        "--motors", type=parse_motors, default=(0, 1, 2, 3),
        help="Motors that physically work, e.g. 1,3. Haptics only use these.",
    )
    parser.add_argument("--pose", default=DEFAULT_POSE, help="Initial pose id")
    parser.add_argument("--web-dir", default=str(WEB_DIR), help="Front-end folder")
    return parser.parse_args()


def main():
    args = parse_args()
    web_dir = Path(args.web_dir)
    if not (web_dir / "index.html").is_file():
        raise SystemExit(f"index.html not found in {web_dir}")
    session = TutorSession(
        haptic_mode=args.haptic, working_motors=args.motors, pose_id=args.pose
    )
    server = YogaTutorServer((args.host, args.port), YogaTutorHandler, session, web_dir)
    print(f"Yoga Tutor: http://{args.host}:{args.port}")
    print(f"Pose: {session.pose_id} | Haptic: {args.haptic} | Motors: {args.motors}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        session.close()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
