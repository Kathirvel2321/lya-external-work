"""Lazy, strictly offline loader for the local InsightFace ``buffalo_l`` pack.

* The service must never silently download a model. The library's default is to
  fetch the pack on first use, so ``INSIGHTFACE_HOME`` is set and the files are
  verified *before* the library is imported; otherwise we raise instead.
* CPU only. This laptop has Intel UHD integrated graphics, so a CUDA attempt
  only produces warnings and no speed-up.
* Only the modules we need: ``detection`` (RetinaFace det_10g), ``recognition``
  (ArcFace w600k_r50) and ``landmark_2d_106`` (eye/mouth points for blinks).
  ``genderage`` and the 3-D model are skipped, saving ~150 MB of weights.

Beyond loading, this module holds the *measurement* helpers: face quality,
pose estimation, eye openness and embedding caching. Keeping them here means
one place owns "what a face reading is", and ``recognizer.py`` owns only the
matching policy.
"""
from __future__ import annotations

import os
import threading

import numpy as np

import config

os.environ.setdefault("INSIGHTFACE_HOME", config.INSIGHTFACE_HOME)

_engine = None
_lock = threading.Lock()
_warm_state = {"ok": None, "detail": "not tried"}


class ModelUnavailable(RuntimeError):
    """Raised when the local model pack is absent, so the caller must deny."""


# ----------------------------------------------------------------------
# engine
# ----------------------------------------------------------------------
def preflight() -> tuple[bool, str]:
    return config.models_available()


def get_engine():
    """Return a prepared ``FaceAnalysis`` instance, loading it at most once."""
    global _engine
    if _engine is not None:
        return _engine
    with _lock:
        if _engine is not None:
            return _engine

        ok, detail = preflight()
        if not ok:
            raise ModelUnavailable(
                f"{detail}. Refusing to download a model automatically; place "
                "the buffalo_l pack locally (see models/README.md)."
            )

        from insightface.app import FaceAnalysis       # imported only after the check

        app = FaceAnalysis(
            name=config.MODEL_PACK,
            allowed_modules=["detection", "recognition", "landmark_2d_106"],
            providers=["CPUExecutionProvider"],
        )
        app.prepare(ctx_id=-1, det_size=(640, 640))
        _engine = app
        return _engine


def warm_up() -> tuple[bool, str]:
    """Force models into RAM *and* run one dummy inference, then report timing.

    Measured on this machine: the very first detector call costs ~12 s because
    ONNX Runtime compiles the graph and allocates arenas, while steady-state
    calls cost ~0.5 s. Paying that cost lazily inside a user's verification
    burst would look like a frozen camera, so it is paid here, at startup,
    on the idle warmer instead - never on a request path.
    """
    import time

    import numpy as np

    try:
        engine = get_engine()
        started = time.time()
        dummy = np.zeros((480, 640, 3), dtype=np.uint8)
        engine.det_model.detect(dummy, input_size=(640, 640))
        first_call = time.time() - started

        steady = time.time()
        engine.det_model.detect(dummy, input_size=(640, 640))
        second_call = time.time() - steady

        _warm_state.update(
            ok=True,
            detail=f"engine ready (first inference {first_call:.1f}s, "
                   f"steady {second_call:.2f}s)",
        )
        _warm_state["first_call_seconds"] = round(first_call, 2)
        _warm_state["steady_call_seconds"] = round(second_call, 3)
    except ModelUnavailable as exc:
        _warm_state.update(ok=False, detail=str(exc))
    except Exception as exc:                            # pragma: no cover - defensive
        _warm_state.update(ok=False, detail=f"engine failed to load: {exc}")
    return bool(_warm_state["ok"]), str(_warm_state["detail"])


def warm_state() -> tuple[bool | None, str]:
    return _warm_state["ok"], _warm_state["detail"]


def timing() -> dict:
    """Measured warm-up numbers, for the diagnostics report."""
    return {key: value for key, value in _warm_state.items() if key not in ("ok",)}


def detect_only(frame_bgr: np.ndarray, det_size: int | None = None) -> list[tuple]:
    """Detector-only pass on a downscaled copy. No embedding is computed.

    This is the cheap path used while waiting for someone to appear: it answers
    "is there a face at all?" and returns only boxes. Coordinates are scaled
    back to the original frame size.

    Using a smaller detector input is what makes the waiting state cheap.
    Measured on this laptop: a 640x640 pass costs ~0.55 s, but the watch loop
    only needs "is a face present", and ``WATCH_DET_SIZE`` (320 by default)
    answers that at roughly a third of the cost. Accuracy for *matching* still
    uses the full 640 input in ``read_face`` - only the cheap preselection is
    reduced.
    """
    import cv2

    if det_size is None:
        det_size = config.WATCH_DET_SIZE

    engine = get_engine()
    h, w = frame_bgr.shape[:2]
    scale = min(1.0, float(det_size) / float(max(h, w)))
    small = (cv2.resize(frame_bgr, (max(1, int(w * scale)), max(1, int(h * scale))),
                        interpolation=cv2.INTER_AREA)
             if scale < 1.0 else frame_bgr)
    boxes, _ = engine.det_model.detect(small, input_size=(det_size, det_size))
    if boxes is None or len(boxes) == 0:
        return []
    out = []
    for box in boxes:
        b = np.asarray(box[:4], dtype=np.float32) / max(scale, 1e-6)
        out.append((float(b[0]), float(b[1]), float(b[2]), float(b[3]), float(box[4])))
    return out


# ----------------------------------------------------------------------
# measurements
# ----------------------------------------------------------------------
def face_quality(frame_bgr: np.ndarray, bbox) -> dict:
    """Objective quality of one detected face region.

    Cheap, explainable components - a decision must not be a black box:

    * ``sharpness``  Laplacian variance (motion blur / out of focus)
    * ``brightness`` mean luminance, penalised near 0 or 255
    * ``size``       face width as a fraction of frame width
    * ``contrast``   standard deviation of luminance

    Returns a score in 0..1 plus the parts, so the UI can say *why* a frame was
    rejected ("hold still", "too dark", "come closer") instead of just failing.
    """
    import cv2

    x1, y1, x2, y2 = [int(v) for v in bbox[:4]]
    h, w = frame_bgr.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    crop = frame_bgr[y1:y2, x1:x2]
    if crop.size == 0:
        return {"score": 0.0, "sharpness": 0.0, "brightness": 0.0,
                "size": 0.0, "contrast": 0.0, "reason": "empty crop"}

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(np.mean(gray))
    contrast = float(np.std(gray))
    size = float(x2 - x1) / float(max(1, w))

    sharp_s = min(1.0, sharpness / max(config.BLUR_MIN * 4.0, 1.0))
    bright_s = max(0.0, 1.0 - abs(brightness - 128.0) / 128.0)
    size_s = min(1.0, size / max(config.FACE_GOOD_RATIO, 1e-6))
    contrast_s = min(1.0, contrast / 48.0)

    score = 0.40 * sharp_s + 0.20 * bright_s + 0.25 * size_s + 0.15 * contrast_s

    reason = "ok"
    if sharpness < config.BLUR_MIN:
        reason = "blurry - hold still"
    elif brightness < 55:
        reason = "too dark - more light"
    elif brightness > 215:
        reason = "over-exposed"
    elif size < config.FACE_MIN_RATIO:
        reason = "too far - come closer"

    return {"score": round(float(score), 3), "sharpness": round(sharpness, 2),
            "brightness": round(brightness, 1), "size": round(size, 3),
            "contrast": round(contrast, 1), "reason": reason}


def _yaw_from_landmarks(face) -> float | None:
    """Rough yaw in degrees from the 106-point landmarks.

    Uses the nose tip against the midpoint of the eye outer corners: a turned
    head shifts the nose off that midpoint proportionally. This is an
    *estimate*, which is fine because it is only used to bucket enrollment
    samples by direction and to detect that a head actually turned - never to
    make an authentication decision on its own.

    Positive = facing the camera's right (subject's left).
    """
    lm = getattr(face, "landmark_2d_106", None)
    if lm is None:
        return None
    try:
        pts = np.asarray(lm, dtype=np.float32)
        if pts.shape[0] < 106:
            return None
        left_eye_outer = pts[52]      # subject's right eye, image-left
        right_eye_outer = pts[71]     # subject's left eye, image-right
        nose = pts[86]
        eye_mid = (left_eye_outer + right_eye_outer) / 2.0
        eye_dist = float(np.linalg.norm(right_eye_outer - left_eye_outer)) + 1e-6
        offset = float(nose[0] - eye_mid[0]) / eye_dist
        return float(np.clip(offset / 0.55, -1.0, 1.0)) * 45.0
    except Exception:
        return None


def _yaw_from_kps(face) -> float | None:
    """Fallback yaw from the 5-point detector keypoints."""
    kps = getattr(face, "kps", None)
    if kps is None:
        return None
    try:
        pts = np.asarray(kps, dtype=np.float32)
        left_eye, right_eye, nose = pts[0], pts[1], pts[2]
        eye_mid = (left_eye + right_eye) / 2.0
        eye_dist = float(np.linalg.norm(right_eye - left_eye)) + 1e-6
        offset = float(nose[0] - eye_mid[0]) / eye_dist
        return float(np.clip(offset / 0.55, -1.0, 1.0)) * 45.0
    except Exception:
        return None


def estimate_pose(face) -> dict:
    """Best-effort head pose for enrollment bucketing and the turn challenge."""
    yaw = _yaw_from_landmarks(face)
    if yaw is None:
        yaw = _yaw_from_kps(face)
    pitch = None
    try:
        kps = np.asarray(getattr(face, "kps", None), dtype=np.float32)
        if kps is not None and len(kps) >= 5:
            eye_mid = (kps[0] + kps[1]) / 2.0
            mouth = (kps[3] + kps[4]) / 2.0
            eye_dist = float(np.linalg.norm(kps[1] - kps[0])) + 1e-6
            pitch = float((mouth[1] - eye_mid[1]) / eye_dist)
    except Exception:
        pitch = None
    return {"yaw": None if yaw is None else round(float(yaw), 1),
            "pitch": None if pitch is None else round(float(pitch), 3)}


def pose_bucket(yaw: float | None) -> str:
    """Map a yaw estimate onto one of the configured direction buckets."""
    if yaw is None:
        return "front"
    for name, low, high in config.POSE_BUCKETS:
        if low <= yaw < high:
            return name
    return "left" if yaw < 0 else "right"


def eye_openness(face) -> float | None:
    """Eye-openness ratio from the 106 landmarks, or ``None`` if unavailable.

    Returns eye height / eye width averaged over both eyes. A blink makes this
    drop sharply *relative to the same person's own baseline*, which is why the
    blink check compares against a running baseline rather than a fixed number:
    that works across eye shapes and with glasses on.
    """
    lm = getattr(face, "landmark_2d_106", None)
    if lm is None:
        return None
    try:
        pts = np.asarray(lm, dtype=np.float32)
        if pts.shape[0] < 106:
            return None

        def eye_ratio(idx):
            axis_x = pts[list(idx), 0]
            axis_y = pts[list(idx), 1]
            width = float(np.max(axis_x) - np.min(axis_x)) + 1e-6
            height = float(np.max(axis_y) - np.min(axis_y)) + 1e-6
            return height / width

        # InsightFace 106 layout: 33..42 right eye, 43..52 left eye.
        return round((eye_ratio(range(33, 43)) + eye_ratio(range(43, 53))) / 2.0, 4)
    except Exception:
        return None


def similarity(a, b) -> float:
    """Cosine similarity between two embeddings (normed or not)."""
    a = np.asarray(a, dtype=np.float32).ravel()
    b = np.asarray(b, dtype=np.float32).ravel()
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= 1e-9:
        return 0.0
    return float(np.dot(a, b) / denom)


def largest_face(engine_result):
    """Pick the biggest, most confidently detected face from a result list."""
    if not engine_result:
        return None
    return max(engine_result,
               key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1])
               * float(getattr(f, "det_score", 1.0)))


def read_face(frame_bgr: np.ndarray, frame_index: int = 0) -> dict:
    """Full read: detect the largest face and compute everything needed once.

    Returns a plain dict so it can be logged, queued and tested without
    importing this module. ``embedding`` is the 512-d normed ArcFace vector;
    ``quality`` and ``pose`` are the measurements above.
    """
    engine = get_engine()
    faces = engine.get(frame_bgr[:, :, ::-1])           # BGR -> RGB
    best = largest_face(faces)
    if best is None:
        return {}
    det_score = float(getattr(best, "det_score", 1.0))
    bbox = tuple(float(v) for v in best.bbox)
    pose = estimate_pose(best)
    return {
        "frame_index": frame_index,
        "bbox": bbox,
        "det_score": round(det_score, 3),
        "embedding": np.asarray(best.normed_embedding, dtype=np.float32),
        "quality": face_quality(frame_bgr, bbox),
        "pose": pose,
        "bucket": pose_bucket(pose.get("yaw")),
        "eye_openness": eye_openness(best),
        "face_count": len(faces),
    }


class EmbeddingCache:
    """Keeps recent readings so the same frame is never analysed twice.

    The encode step is the most expensive part of a verification burst. The
    camera controller may hand the same frame to both the recognition loop and
    the stream overlay, and the challenge loop re-reads frames while waiting;
    this cache makes those repeats free.
    """

    def __init__(self, size: int = 12):
        self._size = size
        self._items: list[tuple[int, dict]] = []

    def get(self, frame_index: int) -> dict | None:
        for idx, value in self._items:
            if idx == frame_index:
                return value
        return None

    def put(self, frame_index: int, value: dict):
        self._items.append((frame_index, value))
        if len(self._items) > self._size:
            self._items.pop(0)

    def clear(self):
        self._items.clear()
