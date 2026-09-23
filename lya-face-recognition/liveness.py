"""Liveness — the layer that makes "a photo of me" fail.

Face matching answers "whose face is this". Liveness answers "is there a real
person here right now". Both are required, and neither one alone is a decision:
``verifier.py`` combines them and only then may report success.

Three independent checks, ordered from free to expensive:

1. **Consistency** (free, always on). A printed photo held to the camera
   produces the *same* embedding and the *same* micro-movement pattern frame
   after frame. A live face has natural jitter in pose and eye openness. This
   check needs no model and catches the crudest replay.
2. **Passive anti-spoof** (local ONNX, if a model is placed in ``models/``).
   A MiniFASNet-class model separates real skin from a screen or paper
   reflection using Fourier/illumination cues. Loaded strictly from disk, never
   downloaded.
3. **Active challenge** (mandatory for secure actions, no model needed). The
   owner is asked to blink or turn their head. A still photo cannot comply, and
   a looping video fails because the required action is chosen at random.

Signals are returned individually. A caller can therefore say "face matched but
no blink was seen" instead of a flat "denied", and no check silently pretends
to have run when it did not.
"""
from __future__ import annotations

import glob
import os
import random
import threading
import time

import numpy as np

import auth_wall
import config

_model_session = None
_model_path = ""
_model_state = "not loaded"
_model_lock = threading.Lock()

_KNOWN_PATTERNS = ("fas_minifasnet.onnx", "face_landmark.onnx", "*minifasnet*.onnx")


# ----------------------------------------------------------------------
# passive anti-spoof model (optional, local only)
# ----------------------------------------------------------------------
def _find_model() -> str | None:
    """Find an approved liveness model on disk. Never downloads anything."""
    for pattern in _KNOWN_PATTERNS:
        matches = sorted(glob.glob(os.path.join(config.MODEL_DIR, pattern)))
        for match in matches:
            if os.path.isfile(match) and os.path.getsize(match) > 1024:
                return match
    return None


def passive_status() -> dict:
    """Report availability without loading the model (cheap, UI-safe)."""
    path = _find_model()
    if path is None:
        return {"available": False, "path": "", "state": "no local liveness model"}
    return {"available": True, "path": os.path.basename(path), "state": _model_state}


def _load_model():
    """Load the anti-spoof ONNX once, in a plain CPU session."""
    global _model_session, _model_path, _model_state
    if _model_session is not None:
        return _model_session
    with _model_lock:
        if _model_session is not None:
            return _model_session
        path = _find_model()
        if path is None:
            _model_state = "no local liveness model; passive check skipped"
            return None
        try:
            import onnxruntime as ort

            options = ort.SessionOptions()
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            session = ort.InferenceSession(
                path, sess_options=options, providers=["CPUExecutionProvider"]
            )
            _model_session = session
            _model_path = path
            _model_state = f"loaded {os.path.basename(path)}"
            return session
        except Exception as exc:                        # pragma: no cover - defensive
            _model_state = f"model failed to load: {exc}"
            return None


def _model_input_size(session) -> tuple[int, int]:
    shape = session.get_inputs()[0].shape
    height = shape[2] if len(shape) > 2 and isinstance(shape[2], int) else 80
    width = shape[3] if len(shape) > 3 and isinstance(shape[3], int) else 80
    return int(height), int(width)


def passive_liveness(face_bgr: np.ndarray) -> dict:
    """Classify one face crop as live or spoofed using the local model.

    Returns ``{"available", "live", "confidence", "detail"}``. When no model is
    present ``available`` is False and ``live`` is ``None`` - meaning "no
    opinion", which is different from "passed". Secure flows treat a missing
    model as "collect another signal", never as approval.
    """
    import cv2

    if not config.PASSIVE_ENABLED:
        return {"available": False, "live": None, "confidence": 0.0,
                "detail": "passive liveness disabled by configuration"}

    session = _load_model()
    if session is None:
        return {"available": False, "live": None, "confidence": 0.0,
                "detail": _model_state}

    try:
        height, width = _model_input_size(session)
        resized = cv2.resize(face_bgr, (width, height),
                             interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        tensor = rgb.transpose(2, 0, 1)[None, ...]

        input_meta = session.get_inputs()[0]
        feed = {input_meta.name: tensor}
        outputs = session.run(None, feed)
        logits = np.asarray(outputs[0]).ravel()
        if logits.size < 2:
            return {"available": True, "live": None, "confidence": 0.0,
                    "detail": "model output shape not understood"}
        shifted = logits - float(np.max(logits))
        probabilities = np.exp(shifted) / float(np.sum(np.exp(shifted)))
        live_probability = float(probabilities[-1])      # last index = live
        return {
            "available": True,
            "live": bool(live_probability >= config.PASSIVE_THRESHOLD),
            "confidence": round(live_probability, 3),
            "detail": f"{os.path.basename(_model_path)} live={live_probability:.2f} "
                      f"(threshold {config.PASSIVE_THRESHOLD})",
        }
    except Exception as exc:                            # pragma: no cover - defensive
        return {"available": True, "live": None, "confidence": 0.0,
                "detail": f"model inference failed: {exc}"}


# ----------------------------------------------------------------------
# 1. consistency / replay detection (no model)
# ----------------------------------------------------------------------
class MotionProfile:
    """Watches natural micro-movement across a handful of frames.

    A live face is never perfectly still: breathing, blinking and micro-tremor
    keep the pose estimate and eye openness drifting. A still photo is
    *unnaturally* stable, and a replayed video often repeats a fixed pattern.
    Neither is proof, so this only ever *fails* or *abstains* - it never
    grants access by itself.
    """

    def __init__(self, window: int = 10):
        self.window = window
        self.yaws: list[float] = []
        self.eyes: list[float] = []
        self.sizes: list[float] = []

    def add(self, reading: dict):
        yaw = (reading.get("pose") or {}).get("yaw")
        if yaw is not None:
            self.yaws.append(float(yaw))
        eye = reading.get("eye_openness")
        if eye is not None:
            self.eyes.append(float(eye))
        size = (reading.get("quality") or {}).get("size")
        if size is not None:
            self.sizes.append(float(size))
        for series in (self.yaws, self.eyes, self.sizes):
            if len(series) > self.window:
                series.pop(0)

    def verdict(self) -> dict:
        """Return ``{"verdict": "live"|"static"|"unknown", "detail": str}``."""
        if len(self.yaws) < 5:
            return {"verdict": "unknown", "detail": "not enough frames yet"}

        yaw_span = float(np.max(self.yaws) - np.min(self.yaws))
        eye_span = (float(np.max(self.eyes) - np.min(self.eyes))
                    if len(self.eyes) >= 5 else 0.0)
        size_span = (float(np.max(self.sizes) - np.min(self.sizes))
                     if len(self.sizes) >= 5 else 0.0)

        # A real person in front of a laptop virtually always moves a little.
        # A paper photo taped to the lid does not.
        if yaw_span < 0.35 and eye_span < 0.008 and size_span < 0.004:
            return {"verdict": "static",
                    "detail": "no natural movement detected across frames "
                              "(possible photo or still image)"}
        return {"verdict": "live",
                "detail": f"natural movement present (yaw span {yaw_span:.1f} deg, "
                          f"eye span {eye_span:.3f})"}


# ----------------------------------------------------------------------
# 3. active challenge
# ----------------------------------------------------------------------
class Challenge:
    """A randomly chosen physical action the person must perform.

    Randomisation matters: a recorded video of the owner blinking on loop
    cannot satisfy a head turn, and a printed photo can satisfy nothing. The
    action set is deliberately built from movements that are cheap for a person
    and hard to fake with a still image.
    """

    ACTIONS = ("blink", "turn_head")

    def __init__(self, actions: int = config.CHALLENGE_ACTIONS, seed=None):
        rng = random.Random(seed)
        count = max(1, min(actions, len(self.ACTIONS)))
        self.required = rng.sample(self.ACTIONS, count)
        self.completed: dict[str, float] = {}
        self.started = time.time()
        self.eye_baseline: float | None = None
        self.yaw_baseline: float | None = None
        self.peak_eye_drop = 0.0
        self.peak_turn = 0.0

    # ---------------- observation ----------------
    def observe(self, reading: dict) -> dict:
        """Feed one live face reading; returns the current challenge state."""
        if not reading:
            return self.state()
        eye = reading.get("eye_openness")
        yaw = (reading.get("pose") or {}).get("yaw")

        if "blink" in self.required and eye is not None:
            if self.eye_baseline is None:
                self.eye_baseline = float(eye)
            else:
                # Slowly track the open-eye value so gradual lighting changes
                # do not look like a blink, but a fast drop does.
                self.eye_baseline = max(self.eye_baseline * 0.95 + float(eye) * 0.05,
                                        float(eye) * 0.85)
                if self.eye_baseline > 1e-6:
                    drop = (self.eye_baseline - float(eye)) / self.eye_baseline
                    self.peak_eye_drop = max(self.peak_eye_drop, drop)
                    if drop >= config.BLINK_DROP_RATIO and "blink" not in self.completed:
                        self.completed["blink"] = time.time()

        if "turn_head" in self.required and yaw is not None:
            if self.yaw_baseline is None:
                self.yaw_baseline = float(yaw)
            turn = abs(float(yaw) - self.yaw_baseline)
            self.peak_turn = max(self.peak_turn, turn)
            if turn >= config.HEAD_TURN_YAW and "turn_head" not in self.completed:
                self.completed["turn_head"] = time.time()

        return self.state()

    # ---------------- reporting ----------------
    def elapsed(self) -> float:
        return time.time() - self.started

    def timed_out(self) -> bool:
        return self.elapsed() > config.CHALLENGE_TIMEOUT

    def satisfied(self) -> bool:
        return all(action in self.completed for action in self.required)

    def state(self) -> dict:
        return {
            "required": list(self.required),
            "completed": sorted(self.completed.keys()),
            "remaining": [a for a in self.required if a not in self.completed],
            "elapsed": round(self.elapsed(), 1),
            "timeout": config.CHALLENGE_TIMEOUT,
            "satisfied": self.satisfied(),
            "peak_eye_drop": round(self.peak_eye_drop, 3),
            "peak_turn_deg": round(self.peak_turn, 1),
            "instruction": self.instruction(),
        }

    def instruction(self) -> str:
        """Plain language prompt for the person in front of the camera."""
        remaining = [a for a in self.required if a not in self.completed]
        if not remaining:
            return "verified - thank you"
        phrases = []
        for action in remaining:
            if action == "blink":
                phrases.append("blink slowly twice")
            elif action == "turn_head":
                phrases.append("turn your head slightly to one side")
        return "please " + " and ".join(phrases)


def challenge_action_count() -> int:
    return max(1, min(config.CHALLENGE_ACTIONS, len(Challenge.ACTIONS)))


def liveness_available() -> dict:
    """What can be enforced on this machine right now."""
    return {
        "passive_model": passive_status(),
        "active_challenge": bool(config.ACTIVE_ENABLED),
        "consistency": True,
        "note": "a still photo can satisfy neither the active challenge nor "
                "the movement check; the passive model adds a third signal "
                "when a local ONNX model is present",
    }


def face_crop(frame_bgr: np.ndarray, bbox) -> np.ndarray | None:
    """Small helper so callers do not re-implement bbox clamping."""
    import cv2

    x1, y1, x2, y2 = [int(v) for v in bbox[:4]]
    height, width = frame_bgr.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(width, x2), min(height, y2)
    if x2 - x1 < 16 or y2 - y1 < 16:
        return None
    return frame_bgr[y1:y2, x1:x2]


def quick_self_test() -> dict:
    """Exercise the pure-python parts without a camera (used by the tests)."""
    profile = MotionProfile()
    static_reading = {"pose": {"yaw": 1.0}, "eye_openness": 0.30,
                      "quality": {"size": 0.25}}
    for _ in range(8):
        profile.add(dict(static_reading))
    static_verdict = profile.verdict()

    moving = MotionProfile()
    for index in range(8):
        moving.add({"pose": {"yaw": 1.0 + index * 1.5},
                    "eye_openness": 0.30 + (0.05 if index % 2 else 0.0),
                    "quality": {"size": 0.25 + index * 0.002}})
    moving_verdict = moving.verdict()

    challenge = Challenge(actions=2, seed=7)
    challenge.observe({"eye_openness": 0.30, "pose": {"yaw": 0.0}})
    challenge.observe({"eye_openness": 0.18, "pose": {"yaw": 0.0}})   # blink
    challenge.observe({"eye_openness": 0.30, "pose": {"yaw": 20.0}})  # head turn

    return {
        "static": static_verdict,
        "moving": moving_verdict,
        "challenge": challenge.state(),
        "engine": auth_wall.warm_state(),
    }
