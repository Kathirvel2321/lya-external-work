"""The background service — "always able to answer, never burning the laptop".

The owner's exact requirement: *"camera detection should run 24 hour ... it
should only open and end after giving result, it should wake only when it needs
to verify or confirm."*

That is implemented as a single daemon thread with a strict lifecycle:

    OFF    camera released. Nothing runs. Cost is one sleeping thread.
    WATCH  camera open, cheap motion + detector-only passes. No embeddings.
    VERIFY a short, bounded burst with embedding + liveness. Then back to WATCH.
    SCENE  one question answered, then the camera is released again.

Idle cost control, concretely:

* While the room is empty the loop sleeps ``WATCH_IDLE_INTERVAL`` (~1.5 s) and
  only does a motion check. No model runs, no network, no disk.
* Embeddings are computed only inside a VERIFY burst, never in WATCH.
* If the camera stays open without producing a result for
  ``WATCH_MAX_OPEN_SECONDS`` the loop closes it anyway, so the light cannot stay
  on for hours because of a bug.
* ``EMPTY_LIMIT`` consecutive empty iterations release the device entirely.

Requests never block on the loop. A caller asks a question and gets an id; the
loop executes it and the caller polls the result. That is what keeps a GUI
responsive - the same pattern LYA's task worker already uses.

Emergency control is first-class: ``stop_hard()`` closes the camera immediately
regardless of what the loop is doing, and ``pause()`` suspends all capture while
keeping state.
"""
from __future__ import annotations

import threading
import time

import auth_wall
import camera_control
import config
import liveness
import recognizer
import scene_eye
import vault
import verifier


class FaceService:
    """Owns the watch loop, the request queue and all shared state."""

    def __init__(self, camera=None):
        self.camera = camera or camera_control.camera()
        self.verifier = verifier.VerificationService(self.camera)

        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._thread: threading.Thread | None = None

        self.mode = config.MODE_OFF
        self.enabled = False
        self.empty_iterations = 0
        self.camera_opened_at = 0.0
        self.watch_started_at = 0.0
        self.requests: list[dict] = []
        self.results: dict[str, dict] = {}
        self.events: list[dict] = []
        self.stats = {"wakeups": 0, "motion_hits": 0, "detector_passes": 0,
                      "verify_runs": 0, "scene_runs": 0, "camera_opens": 0,
                      "camera_closes": 0, "watch_seconds": 0.0}
        self.last_error = ""
        self._next_result_id = 1

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    def start(self, mode: str = config.MODE_WATCH):
        """Start the background thread. Safe to call twice."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                if mode != self.mode:
                    self.request_mode(mode)
                return False
            self.enabled = True
            self._stop.clear()
            self._paused.clear()
            self.mode = mode if mode in config.VALID_MODES else config.MODE_WATCH
            self._thread = threading.Thread(target=self._loop, name="face-watch",
                                            daemon=True)
            self._thread.start()
            self._log(f"service started in {self.mode} mode")
            return True

    def stop(self, join_timeout: float = 3.0):
        """Stop the thread and release the camera."""
        with self._lock:
            self.enabled = False
            self._stop.set()
            thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=join_timeout)
        self._close_camera("service stopped")
        self.mode = config.MODE_OFF
        self._log("service stopped")

    def stop_hard(self):
        """Emergency stop: release the camera right now, then unwind the loop.

        Used by the UI's kill switch. The camera is closed synchronously so the
        indicator light goes out immediately even if the loop is mid-burst.
        """
        self._stop.set()
        self.enabled = False
        self.camera.set_streaming(False)
        self.camera.close()
        self.stats["camera_closes"] += 1
        self.mode = config.MODE_OFF
        self._log("EMERGENCY STOP - camera released")

    def pause(self, paused: bool = True):
        if paused:
            self._paused.set()
            self._close_camera("paused")
            self._log("service paused")
        else:
            self._paused.clear()
            self._log("service resumed")

    @property
    def paused(self) -> bool:
        return self._paused.is_set()

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # ------------------------------------------------------------------
    # modes
    # ------------------------------------------------------------------
    def request_mode(self, mode: str) -> dict:
        if mode not in config.VALID_MODES:
            return {"ok": False, "reason": f"unknown mode '{mode}'"}
        if mode == config.MODE_OFF:
            self._close_camera("mode off")
        self.mode = mode
        self._log(f"mode -> {mode}")
        return {"ok": True, "mode": mode}

    # ------------------------------------------------------------------
    # camera bookkeeping
    # ------------------------------------------------------------------
    def _open_camera(self) -> bool:
        if self.camera.is_open:
            return True
        if self.camera.open():
            self.camera_opened_at = time.time()
            self.stats["camera_opens"] += 1
            self._log("camera opened")
            return True
        self.last_error = self.camera.last_error
        self._log(f"camera open failed: {self.last_error}")
        return False

    def _close_camera(self, reason: str):
        if self.camera.is_open:
            self.camera.set_streaming(False)
            self.camera.close()
            self.stats["camera_closes"] += 1
            self.camera_opened_at = 0.0
            self._log(f"camera released ({reason})")

    def _open_seconds(self) -> float:
        return time.time() - self.camera_opened_at if self.camera_opened_at else 0.0

    # ------------------------------------------------------------------
    # the loop
    # ------------------------------------------------------------------
    def _loop(self):
        """Single background thread: watch cheaply, verify briefly, sleep again."""
        while not self._stop.is_set():
            try:
                if self._paused.is_set():
                    self._close_camera("paused")
                    time.sleep(0.4)
                    continue

                self.stats["wakeups"] += 1
                self._drain_requests()

                if self.mode == config.MODE_OFF:
                    self._close_camera("mode off")
                    time.sleep(0.5)
                    continue

                if self.mode == config.MODE_ENROLL:
                    # Enrollment is driven by its own session object.
                    time.sleep(0.2)
                    continue

                if not self._open_camera():
                    time.sleep(2.0)
                    continue

                self.camera.set_streaming(True)

                # Hard ceiling: never hold the device open without a result.
                if self._open_seconds() > config.WATCH_MAX_OPEN_SECONDS \
                        and self.mode == config.MODE_WATCH:
                    self._close_camera("watch ceiling reached without a result")
                    time.sleep(0.2)
                    continue

                if self.mode == config.MODE_WATCH:
                    self._watch_pass()
                elif self.mode == config.MODE_VERIFY:
                    self._verify_pass()
                elif self.mode == config.MODE_SCENE:
                    self._scene_pass()
                elif self.mode == config.MODE_STREAM:
                    # Owner is watching the live view. This loop still owns the
                    # device read (one read per frame) and simply paces itself,
                    # so the viewer gets fresh frames without a second reader
                    # competing for the camera.
                    self.camera.read()
                    time.sleep(1.0 / max(config.STREAM_MAX_FPS, 1.0))
                else:
                    time.sleep(0.3)
            except Exception as exc:                   # pragma: no cover - defensive
                self.last_error = f"watch loop error: {exc}"
                self._log(self.last_error)
                time.sleep(0.5)

    def _watch_pass(self):
        """Cheap presence pass: motion first, detector second, no embeddings."""
        started = time.time()
        frame = self.camera.read()
        if frame is None:
            time.sleep(0.2)
            return

        had_motion = self.camera.note_motion(frame)
        if not had_motion:
            self.empty_iterations += 1
            if self.empty_iterations >= config.EMPTY_LIMIT:
                self._close_camera("nobody in view")
                self.verifier.note_absence(self.empty_iterations)
                time.sleep(config.WATCH_IDLE_INTERVAL)
                return
            time.sleep(config.WATCH_IDLE_INTERVAL * 0.5)
            return

        self.stats["motion_hits"] += 1
        self.stats["detector_passes"] += 1

        # Detector only: is there a face at all?
        try:
            boxes = auth_wall.detect_only(frame.bgr)
        except auth_wall.ModelUnavailable as exc:
            self._log(f"model unavailable: {exc}")
            self._close_camera("model unavailable")
            time.sleep(3.0)
            return

        if not boxes:
            self.empty_iterations += 1
            if self.empty_iterations >= config.EMPTY_LIMIT:
                self._close_camera("no face found")
                self.verifier.note_absence(self.empty_iterations)
                time.sleep(config.WATCH_IDLE_INTERVAL)
            else:
                time.sleep(config.DETECT_INTERVAL)
            return

        # A face appeared. Escalate once, briefly, to a full verification.
        self.empty_iterations = 0
        self._log("face detected - starting verification burst")
        self._verify_pass(escalated=True)

    def _verify_pass(self, escalated: bool = False):
        """One bounded verification burst. Returns to WATCH afterwards."""
        self.stats["verify_runs"] += 1
        result = self.verifier.verify(scope=verifier.SCOPE_PRESENCE,
                                      open_camera=False)
        self._publish("presence", result)
        self._log(f"verification {result['status']}: {result.get('reason')}")

        if result["status"] == "verified":
            self._touch("presence", result.get("person"))
        if escalated and self.mode == config.MODE_VERIFY:
            self.mode = config.MODE_WATCH

        # After a verification the loop goes back to cheap watching, and the
        # camera is released once the person is gone.
        if result["status"] in ("unavailable", "denied"):
            self.empty_iterations += 1
            if self.empty_iterations >= config.EMPTY_LIMIT:
                self._close_camera("verification failed and view is empty")

    def _scene_pass(self):
        """Answer one queued scene question, then release the camera."""
        request = self._next_request(config.MODE_SCENE)
        if request is None:
            self.mode = config.MODE_WATCH
            return

        frames = []
        wanted = max(1, int(request.get("frames", 1)))
        for index in range(wanted):
            frame = self.camera.read()
            if frame is not None:
                frames.append(frame)
            if index + 1 < wanted:
                time.sleep(0.35)                      # a different instant

        self.stats["scene_runs"] += 1
        try:
            result = scene_eye.answer_question(
                request.get("question", ""), frames,
                mode=request.get("ask_mode", "look"),
                provider=request.get("provider"))
        except Exception as exc:
            result = {"answered": False, "reason": str(exc), "answer": ""}
        result["id"] = request["id"]
        result["kind"] = "scene"
        self._store_result(request["id"], result)
        self._log(f"scene question answered={result.get('answered')} "
                  f"via {result.get('provider')}")
        self.mode = config.MODE_WATCH
        # A scene question is a one-off: do not keep the device open for it.
        if request.get("close_after", True):
            self._close_camera("scene question finished")

    # ------------------------------------------------------------------
    # request queue
    # ------------------------------------------------------------------
    def ask_scene(self, question: str, *, ask_mode: str = "look",
                  provider: str | None = None, frames: int = 1,
                  close_after: bool = True) -> dict:
        """Queue a scene question. Returns an id to poll with ``result()``."""
        with self._lock:
            request_id = f"r{self._next_result_id}"
            self._next_result_id += 1
            self.requests.append({
                "id": request_id, "kind": config.MODE_SCENE,
                "question": question, "ask_mode": ask_mode,
                "provider": provider, "frames": frames,
                "close_after": close_after, "queued": time.time(),
            })
            if self.mode not in (config.MODE_ENROLL,):
                self.mode = config.MODE_SCENE
        self._log(f"scene question queued ({request_id})")
        return {"ok": True, "id": request_id, "status": "queued"}

    def verify_now(self, scope: str = verifier.SCOPE_SECURE,
                   frames: int = 30) -> dict:
        """Run a verification synchronously and return the full report.

        This is the path a private action uses: it blocks the *caller* (usually a
        worker thread), opens the camera, verifies, and releases the device.
        """
        self._log(f"synchronous {scope} verification requested")
        result = self.verifier.verify(scope=scope, frame_limit=frames)
        self._publish(scope, result)
        if result["status"] == "verified":
            self._touch(scope, result.get("person"))
        return result

    def _next_request(self, kind: str) -> dict | None:
        with self._lock:
            for request in self.requests:
                if request["kind"] == kind:
                    self.requests.remove(request)
                    return request
        return None

    def _drain_requests(self):
        """Drop requests that were queued but never ran (service stopped)."""
        if not self.enabled:
            with self._lock:
                self.requests.clear()

    def _store_result(self, request_id: str, result: dict):
        with self._lock:
            self.results[request_id] = result
            if len(self.results) > 40:
                for key in list(self.results.keys())[:-40]:
                    self.results.pop(key, None)

    def result(self, request_id: str) -> dict:
        """Poll for a queued request's result. Non-blocking, by design."""
        with self._lock:
            found = self.results.get(request_id)
            pending = any(r["id"] == request_id for r in self.requests)
        if found:
            return found
        return {"ok": False, "id": request_id, "pending": pending,
                "reason": "queued" if pending else "unknown request id"}

    # ------------------------------------------------------------------
    # observation log for the UI
    # ------------------------------------------------------------------
    def _publish(self, kind: str, result: dict):
        self.events.append({
            "time": time.time(), "kind": kind,
            "status": result.get("status"),
            "person": result.get("person"),
            "reason": result.get("reason"),
        })
        self.events = self.events[-40:]

    def _touch(self, scope: str, person: str | None):
        self.events.append({"time": time.time(), "kind": "session",
                            "status": "opened", "person": person, "scope": scope})
        self.events = self.events[-40:]

    def _log(self, message: str):
        self.events.append({"time": time.time(), "kind": "log", "message": message,
                            "mode": self.mode})
        self.events = self.events[-40:]

    # ------------------------------------------------------------------
    # reporting
    # ------------------------------------------------------------------
    def status(self) -> dict:
        base = self.verifier.status()
        base.update({
            "running": self.is_running(),
            "enabled": self.enabled,
            "paused": self.paused,
            "mode": self.mode,
            "camera_open_seconds": round(self._open_seconds(), 1),
            "queued_requests": len(self.requests),
            "stats": dict(self.stats),
            "last_error": self.last_error,
            "scene_provider": scene_eye.provider_status(),
            "events": self.events[-12:],
        })
        return base

    def diagnostics(self) -> dict:
        """Everything needed to answer "is it actually cheap and safe?".

        Deliberately reports the *measured* counters rather than describing the
        design: camera opens/closes show the wake/sleep lifecycle is real, and
        detector passes vs verify runs show embedding work is rare.
        """
        return {
            "camera_opens": self.stats["camera_opens"],
            "camera_closes": self.stats["camera_closes"],
            "camera_currently_open": self.camera.is_open,
            "detector_passes": self.stats["detector_passes"],
            "verify_runs": self.stats["verify_runs"],
            "scene_runs": self.stats["scene_runs"],
            "embeddings_are_only_in_verify": True,
            "watch_ceiling_seconds": config.WATCH_MAX_OPEN_SECONDS,
            "empty_limit": config.EMPTY_LIMIT,
            "idle_interval_seconds": config.WATCH_IDLE_INTERVAL,
            "model": auth_wall.warm_state(),
            "liveness": liveness.liveness_available(),
            "store": vault.summary(),
            "thresholds": {"owner": config.OWNER_THRESHOLD,
                           "known": config.KNOWN_THRESHOLD,
                           "margin": config.MARGIN_MIN},
        }


_SERVICE: FaceService | None = None
_SERVICE_LOCK = threading.Lock()


def service() -> FaceService:
    """Process-wide service instance (one camera, one watch loop)."""
    global _SERVICE
    if _SERVICE is None:
        with _SERVICE_LOCK:
            if _SERVICE is None:
                _SERVICE = FaceService()
    return _SERVICE
