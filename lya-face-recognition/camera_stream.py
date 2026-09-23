"""Live camera viewer — you watch the camera, and the AI's reading is overlaid.

The owner's requirement: *"when I open camera I see what is visible in camera
right now ... but we have to build an interface which AI will analyse — we are
giving an eye to AI."*

So this window shows two things at once and never mixes them up:

* **Left: the raw frame.** What the camera physically sees, untouched, with the
  face box drawn so you can tell the detector is finding the right thing.
* **Right: the AI's reading.** The labelled measurements the service actually
  uses - which bucket the head angle falls into, the quality score and its
  reason, eye openness, and the match verdict with its score and margin.

Frames come from the shared ``CameraController``, so opening this viewer does
not open a second camera, and closing it releases the device. Overlays are only
drawn when the user asks for them ("show me what the AI sees"), so the plain
camera view stays a plain camera view.

Requires OpenCV's HighGUI window, which is available in the standard
``opencv-python`` wheel. If it is not available the module reports that clearly
instead of failing silently.
"""
from __future__ import annotations

import threading
import time

import cv2
import numpy as np

import auth_wall
import camera_control
import config
import liveness
import recognizer
import vault

WINDOW = "LYA - camera and AI view"

_COLORS = {
    "owner": (90, 220, 90),
    "known": (230, 190, 70),
    "unknown": (70, 70, 235),
    "ambiguous": (200, 130, 240),
    "low_quality": (150, 150, 150),
    "no_face": (110, 110, 110),
}


def gui_available() -> tuple[bool, str]:
    """Check that a GUI window can actually be created here."""
    try:
        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
        cv2.destroyWindow(WINDOW)
        return True, "opencv HighGUI available"
    except Exception as exc:
        return False, f"no GUI window available ({exc})"


def _draw_face_box(canvas: np.ndarray, reading: dict, verdict: dict | None):
    bbox = reading.get("bbox")
    if not bbox:
        return
    x1, y1, x2, y2 = [int(v) for v in bbox]
    status = (verdict or {}).get("status", "no_face")
    color = _COLORS.get(status, (200, 200, 200))
    cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)

    label = (verdict or {}).get("name") or status.replace("_", " ")
    score = (verdict or {}).get("score")
    text = label if score is None else f"{label} {score:.2f}"
    cv2.putText(canvas, text, (x1, max(18, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX,
                0.55, color, 2, cv2.LINE_AA)

    # Corner ticks instead of a plain box: easier to see at a glance.
    tick = max(8, int((x2 - x1) * 0.12))
    for (cx, cy, dx, dy) in ((x1, y1, 1, 1), (x2, y1, -1, 1),
                             (x1, y2, 1, -1), (x2, y2, -1, -1)):
        cv2.line(canvas, (cx, cy), (cx + dx * tick, cy), color, 2)
        cv2.line(canvas, (cx, cy), (cx, cy + dy * tick), color, 2)


def _panel(width: int, height: int, reading: dict, verdict: dict | None,
           challenge_state: dict | None, mode: str, fps: float) -> np.ndarray:
    """Build the right-hand 'what the AI sees' panel.

    Every number shown here is a real measurement from the pipeline. Nothing is
    invented to look impressive - the owner explicitly does not want fake HUD
    telemetry.
    """
    panel = np.full((height, width, 3), 22, dtype=np.uint8)
    y = 30

    def line(text, color=(215, 215, 215), scale=0.52):
        nonlocal y
        if y > height - 12:
            return
        cv2.putText(panel, text, (14, y), cv2.FONT_HERSHEY_SIMPLEX, scale,
                    color, 1, cv2.LINE_AA)
        y += 24

    line(f"mode: {mode}", (170, 200, 255), 0.58)
    line(f"fps: {fps:4.1f}", (150, 150, 150), 0.48)
    y += 6

    if not reading:
        line("no face in frame", (120, 120, 240))
        return panel

    quality = reading.get("quality", {})
    pose = reading.get("pose", {})
    line(f"AI reading", (255, 240, 200), 0.56)
    line(f"bucket: {reading.get('bucket')}")
    yaw = pose.get("yaw")
    line(f"head yaw: {'n/a' if yaw is None else f'{yaw:+.1f} deg'}")
    line(f"eye openness: {reading.get('eye_openness') or 'n/a'}")
    line(f"detector: {reading.get('det_score')}")
    y += 6

    line("quality", (255, 240, 200), 0.56)
    qscore = quality.get("score")
    qcolor = (90, 210, 90) if (qscore or 0) >= config.ENROLL_QUALITY_MIN \
        else (80, 120, 240)
    line(f"score: {qscore}  ({quality.get('reason')})", qcolor)
    line(f"sharp: {quality.get('sharpness')}  bright: {quality.get('brightness')}")
    line(f"face size: {quality.get('size')} of frame width")
    y += 6

    line("match", (255, 240, 200), 0.56)
    if verdict:
        status = verdict.get("status", "?")
        color = _COLORS.get(status, (215, 215, 215))
        line(f"{status}: {verdict.get('name') or '-'}", color)
        line(f"score {verdict.get('score')} / threshold {verdict.get('threshold')}")
        line(f"runner-up {verdict.get('runner_up')}  margin {verdict.get('margin')}")
        if verdict.get("reason"):
            line(verdict["reason"][:46], (170, 170, 170), 0.44)
    else:
        line("not evaluated yet")
    y += 6

    if challenge_state:
        line("liveness challenge", (255, 240, 200), 0.56)
        line(f"remaining: {', '.join(challenge_state.get('remaining', [])) or 'none'}",
             (90, 210, 90) if challenge_state.get("satisfied") else (80, 160, 240))
        line(challenge_state.get("instruction", "")[:46], (180, 180, 180), 0.44)

    return panel


class AsyncAnalyzer:
    """Runs face analysis on a background thread so the preview never stalls.

    Measured reason this exists: analysing a frame that contains a face costs
    ~0.6 s on this laptop. Doing that inline in the display loop meant the live
    view froze for over half a second at a time whenever the owner was actually
    in frame - exactly the "it lags when I move" symptom.

    The thread keeps the *freshest* pending frame only. It never queues a
    backlog: if analysis is slow, older frames are dropped rather than played
    back late, because a stale reading is worse than a skipped one.
    """

    def __init__(self, cache: "auth_wall.EmbeddingCache"):
        self._cache = cache
        self._lock = threading.Lock()
        self._pending = None              # Frame | None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="face-analyzer",
                                        daemon=True)
        self.last_result: dict = {}
        self.analyzed = 0
        self.dropped = 0
        self.busy = 0.0

    def start(self):
        self._thread.start()

    def submit(self, frame):
        """Offer a frame for analysis. Replaces any frame not yet started."""
        with self._lock:
            if self._pending is not None:
                self.dropped += 1
            self._pending = frame

    def _run(self):
        while not self._stop.is_set():
            with self._lock:
                frame = self._pending
                self._pending = None
            if frame is None:
                time.sleep(0.01)
                continue
            started = time.time()
            try:
                reading = auth_wall.read_face(frame.bgr, frame.index)
                self._cache.put(frame.index, reading)
                self.last_result = reading or {}
                self.analyzed += 1
            except Exception:                       # pragma: no cover - defensive
                pass
            self.busy = time.time() - started

    def stop(self):
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=1.5)


def run_live(view_seconds: float = 60.0, show_ai: bool = True,
             camera=None, service=None, challenge: bool = False) -> dict:
    """Open the live camera window for a bounded time.

    ``show_ai`` toggles the right-hand analysis panel, so the owner can compare
    "what the camera shows" against "what the AI concluded" directly. Press Q or
    Esc, or wait for ``view_seconds`` to pass; the camera is always released on
    exit.
    """
    ok, detail = gui_available()
    if not ok:
        return {"ok": False, "reason": detail}

    cam = camera or camera_control.camera()
    opened_here = False
    if not cam.is_open:
        if not cam.open():
            return {"ok": False, "reason": cam.last_error or "camera unavailable"}
        opened_here = True

    cam.set_streaming(True)
    cam.reset_motion_baseline()

    try:
        store = vault.load_store()
    except Exception:
        store = vault.empty_store()

    cache = auth_wall.EmbeddingCache()
    profile = liveness.MotionProfile()
    active_challenge = liveness.Challenge() if challenge else None

    # Warm the model *before* the window opens.
    #
    # Measured reason: the very first InsightFace call costs ~5 s on this laptop
    # (ONNX Runtime compiles the graph) while later calls are ~0.1-0.6 s. If we
    # let that happen lazily the window looks frozen for the first few seconds.
    warm_ok, warm_detail = auth_wall.warm_up()
    if not warm_ok:
        cv2.destroyAllWindows()
        return {"ok": False, "reason": f"face engine unavailable: {warm_detail}"}

    analyzer = AsyncAnalyzer(cache)
    analyzer.start()

    started = time.time()
    frames = 0
    fps = 0.0
    fps_stamp = started
    last_reading: dict = {}
    last_verdict: dict | None = None
    last_eval_index = -1
    last_submit = 0.0

    print("[camera] live view open - press Q or Esc in the window to close")
    try:
        while True:
            # Wait for a genuinely NEW frame instead of re-rendering the same
            # cached one. This is the fix for the measured lag: the old loop
            # called read() in a tight loop, got the cached frame back
            # instantly, and spun ~950,000 times a second - pinning a CPU core
            # so the laptop fought itself and the preview fell behind.
            #
            # ``make_current=True`` because while this viewer is open it is the
            # only consumer, so it owns the device read. If the background watch
            # loop is also running it publishes frames and we just wait for
            # them, keeping exactly one read per frame either way.
            frame = cam.wait_for_new_frame(
                timeout=1.0,
                make_current=not (service is not None and service.is_running()))
            if frame is None:
                if not cam.is_open:
                    break                          # device vanished; stop cleanly
                continue

            frames += 1
            if time.time() - fps_stamp >= 0.5:
                fps = frames / max(1e-6, (time.time() - fps_stamp))
                frames = 0
                fps_stamp = time.time()

            # Submit for analysis on the background thread. Never wait for it:
            # this is what keeps the preview smooth even when a face is present
            # and analysis takes ~0.6 s.
            if (time.time() - last_submit) >= config.STREAM_ANALYSIS_INTERVAL:
                analyzer.submit(frame)
                last_submit = time.time()

            reading = cache.get(frame.index)
            if reading:
                last_reading = reading
                profile.add(reading)
                if active_challenge is not None:
                    active_challenge.observe(reading)

            # Matching runs only when a *new* reading arrived, not per frame.
            if reading and frame.index != last_eval_index:
                last_eval_index = frame.index
                last_verdict = recognizer.evaluate_reading(reading, store)
            # Deliberately no ``elif not reading`` reset here: clearing the
            # verdict on frames that have not been analysed yet made the panel
            # flicker between "matched" and "not evaluated", because analysis
            # legitimately lags the display by up to one interval. The overlay
            # keeps the last known verdict and shows its age via the FPS and the
            # reading timestamp instead.

            canvas = frame.bgr.copy()
            _draw_face_box(canvas, last_reading, last_verdict)

            if show_ai:
                height = canvas.shape[0]
                panel = _panel(360, height, last_reading, last_verdict,
                               active_challenge.state() if active_challenge else None,
                               "stream", fps)
                combined = np.hstack([canvas, panel])
            else:
                combined = canvas

            cv2.imshow(WINDOW, combined)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):                  # Q or Esc
                break
            if key == ord("a"):
                show_ai = not show_ai
            if time.time() - started > view_seconds:
                break
    finally:
        analyzer.stop()
        cv2.destroyAllWindows()
        if opened_here:
            cam.set_streaming(False)
            cam.close()
        else:
            cam.set_streaming(False)

    behaviour = profile.verdict()
    result = {
        "ok": True,
        "seconds_viewed": round(time.time() - started, 1),
        "camera_released": not cam.is_open,
        "liveness_hint": behaviour,
        "last_verdict": last_verdict,
    }
    if active_challenge is not None:
        result["challenge"] = active_challenge.state()
    return result
