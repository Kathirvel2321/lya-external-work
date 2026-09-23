"""The verification gate — where identity, liveness and policy meet.

This is the only module allowed to answer "may LYA proceed with a private
action". Everything else reports observations; this file makes decisions, so
all the fail-closed rules live in one readable place.

Rules that are enforced here, in order:

1. **Model missing -> deny.** If the local ArcFace pack is unavailable, no
   verification is possible. It never falls back to "allow".
2. **Nobody enrolled -> deny.** An empty store means unknown, not owner.
3. **Identity must be the owner for private actions.** A known friend passes
   ``presence`` but can never satisfy ``secure``.
4. **Identity must be unambiguous.** ``recognizer`` already refuses a match
   when two people score within the margin; that refusal is honoured here.
5. **Liveness must pass, not abstain.** For a secure action the active
   challenge is mandatory. A photo cannot blink on request, so this is the
   check that actually stops the printed-photo attack.
6. **A grant is per-action and single-use.** Grants name the action they were
   issued for and expire. Holding a grant for "open the vault" must never
   authorise "send email as me".
7. **Sessions decay.** A verification is valid for ``SESSION_TTL``, and drops
   immediately if the watch loop reports the person left, or if the frame turns
   into a static image (photo swapped in front of the lens).

The result object always lists which signals ran, which passed and which were
unavailable. Ambiguity is never hidden behind a single boolean.
"""
from __future__ import annotations

import secrets
import threading
import time

import auth_wall
import camera_control
import config
import liveness
import recognizer
import vault

SCOPE_PRESENCE = "presence"      # who is here (lightweight, non-private)
SCOPE_SECURE = "secure"          # private action: owner + liveness required


class Grant:
    """A single-use permission ticket for one named action."""

    def __init__(self, action: str, person: str, seconds: float):
        self.token = secrets.token_urlsafe(18)
        self.action = action
        self.person = person
        self.issued = time.time()
        self.expires = self.issued + seconds
        self.used = False

    @property
    def valid(self) -> bool:
        return not self.used and time.time() < self.expires

    def consume(self) -> bool:
        """Take the grant. Returns False if it was already used or expired."""
        if not self.valid:
            return False
        self.used = True
        return True

    def as_dict(self) -> dict:
        return {"action": self.action, "person": self.person,
                "seconds_left": round(max(0.0, self.expires - time.time()), 1),
                "valid": self.valid}


class VerificationService:
    """Owns the session state, the camera lifecycle and the grant book."""

    def __init__(self, camera=None):
        self.camera = camera or camera_control.camera()
        self._lock = threading.RLock()
        self._grants: dict[str, Grant] = {}

        self.session_person: str | None = None
        self.session_scope: str | None = None
        self.session_expires: float = 0.0
        self.last_result: dict = {"status": "idle", "detail": "not run yet"}
        self.attempts: list[dict] = []

    # ------------------------------------------------------------------
    # session
    # ------------------------------------------------------------------
    def session_state(self) -> dict:
        with self._lock:
            active = bool(self.session_person and time.time() < self.session_expires)
            if not active:
                return {"active": False, "person": None, "scope": None,
                        "seconds_left": 0.0}
            return {"active": True, "person": self.session_person,
                    "scope": self.session_scope,
                    "seconds_left": round(self.session_expires - time.time(), 1)}

    def clear_session(self, reason: str = ""):
        with self._lock:
            self.session_person = None
            self.session_scope = None
            self.session_expires = 0.0
            if reason:
                self.last_result = {"status": "session_cleared", "detail": reason}

    def _open_session(self, person: str, scope: str):
        with self._lock:
            self.session_person = person
            self.session_scope = scope
            self.session_expires = time.time() + config.SESSION_TTL

    # ------------------------------------------------------------------
    # grants
    # ------------------------------------------------------------------
    def _issue_grant(self, action: str, person: str) -> Grant:
        grant = Grant(action, person, seconds=min(config.SESSION_TTL, 90))
        with self._lock:
            self._grants[grant.token] = grant
            self._prune_grants()
        return grant

    def consume_grant(self, token: str, action: str) -> tuple[bool, str]:
        """Redeem a grant for the exact action it was issued for."""
        with self._lock:
            grant = self._grants.get(token)
            if grant is None:
                return False, "unknown or expired grant"
            if grant.action != action:
                return False, (f"this grant authorises '{grant.action}', "
                               f"not '{action}'")
            if not grant.consume():
                return False, "grant already used or expired"
            return True, f"grant accepted for '{action}' as {grant.person}"

    def _prune_grants(self):
        now = time.time()
        for token in [t for t, g in self._grants.items()
                      if g.used or now > g.expires]:
            self._grants.pop(token, None)

    # ------------------------------------------------------------------
    # the main verification burst
    # ------------------------------------------------------------------
    def verify(self, scope: str = SCOPE_PRESENCE, *, require_challenge: bool | None = None,
               frame_limit: int | None = None, open_camera: bool = True) -> dict:
        """Run a full verification burst and return a structured report.

        ``require_challenge`` defaults to True for ``secure`` and False for
        ``presence``, which keeps the everyday "hey LYA, who's there?" path
        fast while making private actions slow and deliberate.
        """
        started = time.time()
        cache = auth_wall.EmbeddingCache()
        votes = recognizer.VoteWindow()
        profile = liveness.MotionProfile()

        if require_challenge is None:
            require_challenge = (scope == SCOPE_SECURE)

        report = {
            "scope": scope,
            "started": started,
            "status": "denied",
            "person": None,
            "role": None,
            "reason": "",
            "detail": "",
            "signals": {},
            "frames": 0,
            "elapsed": 0.0,
            "challenge": None,
            "grant": None,
        }

        # ---- gate 1: is verification even possible? ----
        ok, model_detail = auth_wall.preflight()
        if not ok:
            report.update(status="unavailable",
                          reason="face model not available locally",
                          detail=model_detail)
            return self._finish(report, started)

        try:
            store = vault.load_store()
        except vault.VaultError as exc:
            report.update(status="unavailable", reason="encrypted store unreadable",
                          detail=str(exc))
            return self._finish(report, started)

        owner = vault.owner_person(store)
        if owner is None:
            report.update(status="denied", reason="no owner enrolled",
                          detail="enroll a face first; an unenrolled system "
                                 "never grants private access")
            return self._finish(report, started)

        # ---- gate 2: camera ----
        opened_here = False
        if open_camera and not self.camera.is_open:
            if not self.camera.open():
                report.update(status="unavailable", reason="camera unavailable",
                              detail=self.camera.last_error)
                return self._finish(report, started)
            opened_here = True

        self.camera.set_streaming(True)          # share frames with the UI
        self.camera.reset_motion_baseline()

        challenge = liveness.Challenge() if require_challenge else None
        if challenge is not None:
            report["challenge"] = challenge.state()

        limit = frame_limit or 40
        frames_seen = 0
        static_strikes = 0

        try:
            while frames_seen < limit:
                if votes.timed_out():
                    break
                frame = self.camera.read()
                if frame is None:
                    time.sleep(0.03)
                    continue
                frames_seen += 1

                reading = cache.get(frame.index)
                if reading is None:
                    reading = auth_wall.read_face(frame.bgr, frame.index)
                    cache.put(frame.index, reading)

                if not reading:
                    votes.skip("no face detected")
                    time.sleep(0.08 if self.camera.is_open else 0.02)
                    continue

                profile.add(reading)

                # Active challenge consumes the same reading, and its result is
                # what gates a secure action.
                if challenge is not None:
                    challenge.observe(reading)
                    report["challenge"] = challenge.state()
                    if challenge.satisfied():
                        break
                    if challenge.timed_out():
                        break

                verdict = recognizer.evaluate_reading(reading, store)
                if verdict["status"] in ("low_quality", "no_face"):
                    votes.skip(verdict.get("reason", "low quality frame"))
                    continue

                votes.add(verdict, verdict.get("quality", 0.0))

                # A static image is a hard fail, not just a weak signal.
                if profile.verdict()["verdict"] == "static":
                    static_strikes += 1
                else:
                    static_strikes = 0
                if static_strikes >= 4:
                    behaviour = profile.verdict()
                    report["signals"]["consistency"] = behaviour
                    report.update(status="denied",
                                  reason="liveness failed",
                                  detail=behaviour["detail"])
                    votes._entries.clear()
                    break

                decision = votes.decision()
                if decision["decided"] and challenge is None:
                    break
                if decision["decided"] and challenge is not None and challenge.satisfied():
                    break
                time.sleep(0.05)
        finally:
            if opened_here:
                self.camera.set_streaming(False)
                self.camera.close()

        # ---- gate 3: who? ----
        decision = votes.decision()
        report["frames"] = frames_seen
        report["votes"] = {"frames": votes.window, "skipped": votes.skipped[-6:]}

        if not decision["decided"]:
            report.update(status="denied", reason="identity not confirmed",
                          detail=self._explain_failure(decision, votes))
            return self._finish(report, started)

        # ---- gate 4: liveness evidence ----
        behaviour = profile.verdict()
        report["signals"]["consistency"] = behaviour
        if require_challenge:
            challenge_state = challenge.state() if challenge else {}
            report["signals"]["challenge"] = challenge_state
            if not challenge_state.get("satisfied"):
                report.update(status="denied", reason="liveness challenge not completed",
                              detail=(challenge_state.get("instruction")
                                      or "no response to the challenge"))
                return self._finish(report, started)

        # ---- gate 5: is this person allowed this scope? ----
        if scope == SCOPE_SECURE and decision["status"] != "owner":
            report.update(status="denied", reason="private action requires the owner",
                          detail=f"recognised as {decision['name']} "
                                 f"({decision['status']})")
            return self._finish(report, started)

        person = decision["name"]
        self._open_session(person, scope)
        report.update(status="verified", person=person, role=decision["status"],
                      reason="identity and liveness confirmed",
                      detail=f"{person} verified ({decision['votes']}/{votes.window} "
                             f"frames, mean similarity "
                             f"{decision.get('mean_score', 0.0):.2f})")

        if scope == SCOPE_SECURE:
            grant = self._issue_grant(action=f"secure:{person}", person=person)
            report["grant"] = grant.as_dict()
            report["grant_token"] = grant.token

        return self._finish(report, started)

    def _explain_failure(self, decision: dict, votes: recognizer.VoteWindow) -> str:
        if not votes._entries:
            skipped = votes.skipped[-1] if votes.skipped else "no usable frames"
            return f"no frame passed the quality gate ({skipped})"
        if decision["votes"]:
            return (f"only {decision['votes']} of {votes.window} frames agreed; "
                    f"needed {votes.votes}")
        return "faces were seen but did not match any enrolled person"

    def _finish(self, report: dict, started: float) -> dict:
        report["elapsed"] = round(time.time() - started, 2)
        with self._lock:
            self.last_result = report
            self.attempts.append({"time": report["started"], "scope": report["scope"],
                                  "status": report["status"],
                                  "person": report.get("person"),
                                  "reason": report.get("reason")})
            self.attempts = self.attempts[-25:]
        return report

    # ------------------------------------------------------------------
    # helpers used by the service loop and UI
    # ------------------------------------------------------------------
    def is_owner_present(self) -> bool:
        state = self.session_state()
        return state["active"] and state["person"] is not None

    def note_absence(self, empty_iterations: int) -> bool:
        """Called by the watch loop; drops the session when the person leaves."""
        if empty_iterations >= config.EMPTY_LIMIT and self.session_state()["active"]:
            self.clear_session("person left the camera view")
            return True
        return False

    def status(self) -> dict:
        ok, model_detail = auth_wall.preflight()
        try:
            store_summary = vault.summary()
        except Exception as exc:                        # pragma: no cover - defensive
            store_summary = {"exists": True, "error": str(exc), "people": []}
        warm_ok, warm_detail = auth_wall.warm_state()
        return {
            "camera": {"open": self.camera.is_open,
                       "index": self.camera.index,
                       "opens": self.camera.open_count,
                       "reads": self.camera.read_count,
                       "error": self.camera.last_error},
            "model": {"available": ok, "detail": model_detail,
                      "warmed": warm_ok, "warm_detail": warm_detail},
            "store": store_summary,
            "session": self.session_state(),
            "liveness": liveness.liveness_available(),
            "last_result": self.last_result,
        }
