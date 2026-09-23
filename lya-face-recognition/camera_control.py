"""Camera controller: lazy open, cheap trigger, explicit release.

Owner requirements this file implements:

* The camera must **not** run 24 hours. It wakes when needed, produces a
  result, and releases the device again.
* Idle cost must be near zero. When nobody is in front of the laptop the device
  is closed, not merely left open with a slow loop.
* Only one program can hold camera 0 on Windows, so nothing here may fight for
  the device. All callers share one ``CameraController`` instance.

Design:

* One hardware owner, one frame slot (``latest``), many consumers. No caller
  opens a second ``VideoCapture``.
* A watch loop (in ``service.py``) drives modes; this file only knows how to
  open, read, measure cheap motion, and close.
* Reading a frame fills ``Frame``, which pre-computes the grayscale and the
  96x96 thumbnail exactly once. Motion detection and quality metrics then cost
  microseconds and never touch the full-resolution image twice.
"""
from __future__ import annotations

import threading
import time

import cv2
import numpy as np

import config


class Frame:
    """One captured frame plus the cheap preprocessing done once per frame."""

    __slots__ = ("bgr", "gray", "small", "stamp", "index")

    def __init__(self, bgr: np.ndarray, index: int):
        self.bgr = bgr
        self.stamp = time.time()
        self.index = index
        self.gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        self.small = cv2.resize(
            self.gray, (config.MOTION_DOWNSCALE, config.MOTION_DOWNSCALE),
            interpolation=cv2.INTER_AREA,
        )

    def jpeg(self, quality: int = config.SCENE_JPEG_QUALITY) -> bytes | None:
        ok, buf = cv2.imencode(".jpg", self.bgr,
                               [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
        return buf.tobytes() if ok else None

    def crop(self, bbox) -> np.ndarray:
        x1, y1, x2, y2 = [int(v) for v in bbox[:4]]
        h, w = self.bgr.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        return self.bgr[y1:y2, x1:x2]


def change_ratio(previous: np.ndarray | None, current: np.ndarray,
                 pixel_delta: int = 18) -> float:
    """Fraction of thumbnail pixels that changed appreciably (0.0 without history)."""
    if previous is None or previous.shape != current.shape:
        return 0.0
    diff = cv2.absdiff(previous, current)
    return float(np.count_nonzero(diff > pixel_delta)) / float(diff.size)


def is_motion(previous: np.ndarray | None, current: np.ndarray) -> bool:
    """Very cheap 'did anything move' test, used to avoid wasted detection."""
    if previous is None:
        return True                        # first frame: allow one detection pass
    diff = cv2.absdiff(previous, current)
    mean_delta = float(np.mean(diff))
    ratio = change_ratio(previous, current)
    return mean_delta >= config.MOTION_THRESHOLD and ratio >= config.MOTION_PIXEL_RATIO


class MotionGate:
    """Motion detector that compares against a *slow* reference frame.

    Measured reality of this laptop camera on a static desk scene: the delta
    between *consecutive* frames wanders between 1.5 and 14.7 with a median of
    about 4.9, because auto-exposure keeps hunting. Empirical tests showed a
    naive threshold flagged 21 of 60 frames of an empty room as "motion",
    which would wake face detection and verification for no reason - exactly
    the load the owner asked to avoid.

    Comparing the current frame against a frame from ~1 second ago makes slow
    drift cancel out: both frames sit at a similar exposure, so their
    difference stays small. A person entering, sitting down or reaching for
    something moves relative to that reference, so the difference stays large.

    Two thresholds, both meaningful:

    * ``MOTION_REFERENCE_DELTA``  - moderate change vs. the reference.
    * ``MOTION_STRONG_DELTA``     - a person or a light: accepted immediately.

    This stays a cheap pixel comparison, not a model, so the idle cost remains
    microseconds per frame.
    """

    def __init__(self, required: int = config.MOTION_SUSTAIN,
                 window: int = config.MOTION_SUSTAIN_WINDOW):
        self.required = max(1, required)
        self.window = max(self.required, window)
        self._history: list[bool] = []
        self._reference: np.ndarray | None = None
        self._reference_at = 0.0
        self.last_delta = 0.0
        self.last_ratio = 0.0

    def update(self, current: np.ndarray, now: float | None = None) -> bool:
        now = time.time() if now is None else now

        # Establish or refresh the slow reference. Refreshing does not trigger:
        # it is the moment we re-baseline, not the moment something moved.
        if self._reference is None or \
                (now - self._reference_at) >= config.MOTION_REFERENCE_SECONDS:
            self._reference = current
            self._reference_at = now
            return False

        delta = float(np.mean(cv2.absdiff(self._reference, current)))
        ratio = change_ratio(self._reference, current)
        self.last_delta = delta
        self.last_ratio = ratio

        if delta >= config.MOTION_STRONG_DELTA:
            self._history.append(True)
            if len(self._history) > self.window:
                self._history.pop(0)
            return True

        raw = delta >= config.MOTION_REFERENCE_DELTA \
            and ratio >= config.MOTION_PIXEL_RATIO
        self._history.append(raw)
        if len(self._history) > self.window:
            self._history.pop(0)
        return sum(self._history) >= self.required

    def diagnostics(self) -> dict:
        return {"last_delta": round(self.last_delta, 2),
                "last_ratio": round(self.last_ratio, 4),
                "reference_delta_threshold": config.MOTION_REFERENCE_DELTA,
                "strong_delta_threshold": config.MOTION_STRONG_DELTA,
                "sustained_frames_required": self.required,
                "reference_age": round(time.time() - self._reference_at, 1)
                if self._reference_at else 0.0}

    def reset(self):
        self._history.clear()
        self._reference = None
        self._reference_at = 0.0
        self.last_delta = 0.0
        self.last_ratio = 0.0


class CameraController:
    """Owns the physical camera for this process."""
    def __init__(self, index: int = config.CAMERA_INDEX):
        self.index = index
        self._cap: cv2.VideoCapture | None = None
        self._lock = threading.RLock()
        self._latest: Frame | None = None
        self._previous_small: np.ndarray | None = None
        self._motion_gate = MotionGate()
        self._counter = 0
        self._streaming = False
        self.last_error = ""
        self.open_count = 0
        self.read_count = 0

    # ------------------------------------------------------------------
    # device lifecycle
    # ------------------------------------------------------------------
    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._cap is not None

    def open(self) -> bool:
        """Open the device if closed. Idempotent, so it is safe to call often."""
        with self._lock:
            if self._cap is not None:
                return True
            cap = None
            try:
                for backend in (getattr(cv2, "CAP_DSHOW", 700), cv2.CAP_ANY):
                    cap = cv2.VideoCapture(self.index, backend)
                    if cap.isOpened():
                        break
                    cap.release()
                    cap = None
                if cap is None:
                    self.last_error = f"camera {self.index} could not be opened"
                    return False

                cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)     # always the newest frame
                self._cap = cap
                self.open_count += 1
                self.last_error = ""
                for _ in range(max(0, config.CAMERA_WARMUP)):
                    cap.read()                          # let exposure settle
                return True
            except Exception as exc:                    # pragma: no cover - defensive
                self.last_error = f"camera open failed: {exc}"
                self._cap = None
                return False

    def close(self):
        """Release the device. After this the camera indicator light goes out."""
        with self._lock:
            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception:
                    pass
                self._cap = None
            self._latest = None
            self._previous_small = None
            self._streaming = False

    # ------------------------------------------------------------------
    # frame access
    # ------------------------------------------------------------------
    def read(self) -> Frame | None:
        """Grab one frame. Always returns the newest frame from the device."""
        with self._lock:
            if self._cap is None:
                return None
            try:
                ok, bgr = self._cap.read()
            except Exception as exc:                    # pragma: no cover - defensive
                self.last_error = f"camera read failed: {exc}"
                return None
            if not ok or bgr is None:
                return None
            self.read_count += 1
            self._counter += 1
            frame = Frame(bgr, self._counter)
            self._latest = frame
            return frame

    def wait_for_new_frame(self, timeout: float = 1.0,
                           make_current: bool = False) -> Frame | None:
        """Block until a frame newer than the caller's last one is available.

        ``make_current`` controls who owns the device read:

        * ``make_current=True``  - this call reads the device itself. Used by the
          live viewer, which is the only consumer while it is open.
        * ``make_current=False`` - this call only *waits* for the background
          watch loop to publish a new frame. Used when the service is watching,
          so there is still exactly one device read per frame.

        Why this exists: the previous streaming path returned the cached frame
        immediately whenever it was under 150 ms old. The live-view loop then
        called it in a tight loop and ran ~950,000 iterations per second,
        pinning a CPU core at 100% and making the image visibly laggy - the
        machine was competing with itself. Waiting for an actually-new frame is
        both far cheaper and smoother.
        """
        deadline = time.time() + max(0.0, timeout)
        seen = self._latest.index if self._latest is not None else -1
        while time.time() < deadline:
            if make_current:
                frame = self.read()
                if frame is not None and frame.index != seen:
                    return frame
            else:
                current = self._latest
                if current is not None and current.index != seen:
                    return current
            # A short sleep caps the polling rate. Without it the loop spins.
            time.sleep(1.0 / max(config.STREAM_MAX_FPS, 1.0))
        return self._latest

    @property
    def latest(self) -> Frame | None:
        return self._latest

    def set_streaming(self, enabled: bool):
        self._streaming = bool(enabled)

    def note_motion(self, frame: Frame) -> bool:
        """Motion test against a slow reference, so camera drift does not fire.

        Returns True only when something changed relative to about a second ago.
        """
        self._previous_small = frame.small
        return self._motion_gate.update(frame.small)

    def motion_diagnostics(self) -> dict:
        return self._motion_gate.diagnostics()

    def reset_motion_baseline(self):
        self._previous_small = None
        self._motion_gate.reset()


def blur_score(gray: np.ndarray) -> float:
    """Laplacian variance of a grayscale crop. Low = blurry/moving."""
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


_CAMERA = CameraController()


def camera() -> CameraController:
    """Process-wide camera (single hardware device, single owner)."""
    return _CAMERA
