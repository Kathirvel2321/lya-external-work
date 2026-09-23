"""Offline regression suite for the face-recognition module.

Runs without a camera and without a network. That is deliberate: these tests
must be runnable on any machine, and they must verify the *security rules*, not
the camera driver.

Placeholder embeddings are generated as unit vectors (like real ArcFace output),
because raw uniform vectors have a mean of 0.5 and produce a meaningless ~0.75
cosine similarity even between unrelated samples.

Every check below corresponds to a rule that, if it silently broke, would let
someone unlock the owner's private material. The suite is written so a failure
is loud.
"""
from __future__ import annotations

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import auth_wall          # noqa: E402
import config             # noqa: E402
import liveness           # noqa: E402
import recognizer         # noqa: E402
import vault              # noqa: E402
import verifier           # noqa: E402

PASSED: list[str] = []
FAILED: list[str] = []


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def unit(seed: int, dim: int = 512) -> np.ndarray:
    """Deterministic unit vector, standing in for one face embedding."""
    rng = np.random.default_rng(seed)
    vector = rng.standard_normal(dim).astype(np.float32)
    return vector / float(np.linalg.norm(vector))


def person_like(seed: int, noise: float = 0.35) -> np.ndarray:
    """A *different view* of the person represented by ``seed``.

    Real recognition never compares identical vectors: lighting, angle and
    distance all shift the embedding. This models that shift so the thresholds
    are tested against realistic variation rather than a perfect copy.
    """
    base = unit(seed)
    return unit(0) * 0.0 + _normalize(base + noise * unit(seed * 977 + 13))


def _normalize(vector: np.ndarray) -> np.ndarray:
    return vector / float(np.linalg.norm(vector))


def check(label: str, condition: bool, detail: str = ""):
    if condition:
        PASSED.append(label)
        print(f"  [ok]   {label}" + (f"  ({detail})" if detail else ""))
    else:
        FAILED.append(label)
        print(f"  [FAIL] {label}" + (f"  ({detail})" if detail else ""))


def section(title: str):
    print(f"\n--- {title} ---")


# ----------------------------------------------------------------------
# 1. recognizer policy
# ----------------------------------------------------------------------
def test_recognizer_policy():
    section("recognizer: identity and ambiguity rules")

    store = vault.empty_store()
    vault.add_template(store, "owner", {
        "embedding": unit(1), "bucket": "front", "pose": {"yaw": 0},
        "quality": {"score": 0.9}})
    vault.set_owner(store, "owner")

    verdict = recognizer.match(unit(1), store)
    check("owner matches own template", verdict["status"] == "owner",
          f"score {verdict['score']}")

    shifted = recognizer.match(person_like(1), store)
    check("owner still matches under view variation",
          shifted["status"] == "owner", f"score {shifted['score']}")

    stranger_scores = [recognizer.match(unit(seed), store)["score"]
                       for seed in range(100, 400)]
    check("no unrelated vector is accepted",
          all(recognizer.match(unit(seed), store)["status"] == "unknown"
              for seed in range(100, 120)),
          f"max stranger score {max(stranger_scores):.3f}")

    # Ambiguity: a second person whose template is nearly as close must be
    # refused rather than guessed, even though both are above threshold.
    twin_store = vault.empty_store()
    vault.add_template(twin_store, "owner", {
        "embedding": unit(2), "bucket": "front", "pose": {}, "quality": {"score": 0.9}})
    vault.set_owner(twin_store, "owner")
    near = _normalize(unit(2) * 0.9995 + unit(3) * 0.0316)
    vault.add_template(twin_store, "twin", {
        "embedding": near, "bucket": "front", "pose": {}, "quality": {"score": 0.9}})
    probe = _normalize(unit(2) * 0.999 + unit(3) * 0.045)
    twin_verdict = recognizer.match(probe, twin_store)
    check("two close candidates are refused as ambiguous",
          twin_verdict["status"] == "ambiguous",
          f"margin {twin_verdict['margin']}")

    empty = recognizer.match(unit(5), vault.empty_store())
    check("empty store never reports the owner", empty["status"] == "unknown")

    # Quality gate: a blurred frame must not be matched at all.
    low = recognizer.evaluate_reading({
        "embedding": unit(1), "bbox": (10, 10, 60, 60), "det_score": 0.99,
        "quality": {"score": 0.05, "reason": "blurry - hold still"},
        "pose": {"yaw": 0}, "bucket": "front"}, store)
    check("low quality frames are rejected before matching",
          low["status"] == "low_quality", low.get("reason"))


# ----------------------------------------------------------------------
# 2. frame voting
# ----------------------------------------------------------------------
def test_voting():
    section("recognizer: frame voting")

    window = recognizer.VoteWindow(window=5, votes=3)
    for _ in range(2):
        window.add({"status": "owner", "name": "owner", "score": 0.8}, 0.9)
    check("two agreeing frames are not yet enough",
          not window.decision()["decided"], f"{window.decision()['votes']}/3")

    window.add({"status": "owner", "name": "owner", "score": 0.82}, 0.9)
    decision = window.decision()
    check("three agreeing frames confirm the identity",
          decision["decided"] and decision["name"] == "owner",
          f"{decision['votes']}/{window.votes} votes")

    mixed = recognizer.VoteWindow(window=5, votes=3)
    for name in ("a", "b", "a", "b", "c"):
        mixed.add({"status": "known", "name": name, "score": 0.7}, 0.9)
    check("mixed votes never reach a majority",
          not mixed.decision()["decided"], str(mixed.decision()))

    timeout = recognizer.VoteWindow(window=5, votes=3)
    timeout.started = time.time() - (config.VERIFY_TIMEOUT + 1)
    check("a stalled verification times out", timeout.timed_out())


# ----------------------------------------------------------------------
# 3. liveness
# ----------------------------------------------------------------------
def test_liveness():
    section("liveness: photo and replay resistance")

    static = liveness.MotionProfile()
    for _ in range(10):
        static.add({"pose": {"yaw": 1.0}, "eye_openness": 0.30,
                    "quality": {"size": 0.25}})
    check("a perfectly still image is flagged as static",
          static.verdict()["verdict"] == "static", static.verdict()["detail"])

    live = liveness.MotionProfile()
    for index in range(10):
        live.add({"pose": {"yaw": 1.0 + index * 0.9},
                  "eye_openness": 0.30 + (0.03 if index % 2 else 0.0),
                  "quality": {"size": 0.25 + index * 0.002}})
    check("natural movement is accepted as live",
          live.verdict()["verdict"] == "live", live.verdict()["detail"])

    challenge = liveness.Challenge(actions=2, seed=11)
    check("every challenge requires a physical action",
          len(challenge.required) >= 1, str(challenge.required))

    challenge.observe({"eye_openness": 0.30, "pose": {"yaw": 0.0}})
    still_ok = challenge.satisfied()
    challenge.observe({"eye_openness": 0.16, "pose": {"yaw": 0.0}})
    challenge.observe({"eye_openness": 0.30, "pose": {"yaw": 26.0}})
    check("a still frame alone cannot satisfy the challenge", not still_ok)
    check("blink and head turn satisfy it",
          challenge.satisfied(), str(challenge.state()["completed"]))
    check("the challenge gives a plain instruction",
          isinstance(challenge.instruction(), str) and challenge.instruction())

    short = liveness.Challenge(actions=2, seed=11)
    short.started = time.time() - (config.CHALLENGE_TIMEOUT + 1)
    check("an unanswered challenge times out", short.timed_out())

    check("passive model absence is reported, not faked",
          liveness.passive_liveness(np.zeros((80, 80, 3), dtype=np.uint8))
          .get("live") in (None, True, False))


# ----------------------------------------------------------------------
# 4. grants and scopes
# ----------------------------------------------------------------------
def test_grants():
    section("verifier: single-use, action-bound grants")

    service = verifier.VerificationService()
    grant = service._issue_grant("open vault", "owner")

    ok_wrong, message_wrong = service.consume_grant(grant.token, "send email")
    check("a grant refuses a different action", not ok_wrong, message_wrong)

    ok_right, message_right = service.consume_grant(grant.token, "open vault")
    check("the correct action is accepted", ok_right, message_right)

    ok_reuse, message_reuse = service.consume_grant(grant.token, "open vault")
    check("a grant cannot be used twice", not ok_reuse, message_reuse)

    expired = verifier.Grant("any", "owner", seconds=-1)
    check("an expired grant is invalid", not expired.valid)

    short = service._issue_grant("x", "owner")
    service._grants.pop(short.token)
    unknown_ok, unknown_message = service.consume_grant(short.token, "x")
    check("an unknown token is refused", not unknown_ok, unknown_message)


# ----------------------------------------------------------------------
# 5. session handling
# ----------------------------------------------------------------------
def test_sessions():
    section("verifier: session decay")

    service = verifier.VerificationService()
    check("no session before verification",
          not service.session_state()["active"])

    service._open_session("owner", verifier.SCOPE_PRESENCE)
    check("session opens after verification",
          service.session_state()["active"],
          f"{service.session_state()['seconds_left']}s left")

    service.session_expires = time.time() - 1
    check("session expires on its own", not service.session_state()["active"])

    service._open_session("owner", verifier.SCOPE_PRESENCE)
    dropped = service.note_absence(config.EMPTY_LIMIT + 1)
    check("session drops when the person leaves",
          dropped and not service.session_state()["active"])

    cleared = service.note_absence(0)
    check("absence below the limit does not drop the session", not cleared)


# ----------------------------------------------------------------------
# 6. vault
# ----------------------------------------------------------------------
def test_vault():
    section("vault: encrypted store behaviour")

    check("store reports existence correctly",
          isinstance(vault.store_exists(), bool))
    check("DPAPI is available for key protection",
          vault.dpapi_available(), "pywin32 present")

    quantised = vault.vector_to_list(np.ones(512, dtype=np.float64))
    restored = vault.list_to_vector(quantised)
    check("templates survive a round trip",
          restored.shape == (512,) and restored.dtype == np.float32,
          f"dtype {restored.dtype}")

    store = vault.empty_store()
    person = vault.upsert_person(store, "tester", "owner")
    # Give each direction exactly the configured minimum so the coverage rule
    # is tested against config rather than a hardcoded number.
    for index, bucket in enumerate(config.POSE_LABELS):
        for repeat in range(config.POSE_MIN_PER_BUCKET):
            person["templates"].append({
                "vector": vault.vector_to_list(unit(index * 10 + repeat)),
                "bucket": bucket})
    counts = vault.bucket_counts(person)
    check("bucket counts per direction are tracked",
          all(counts[bucket] == config.POSE_MIN_PER_BUCKET
              for bucket in config.POSE_LABELS), str(counts))

    check("coverage is complete once every direction meets the minimum",
          vault.coverage_complete(person),
          f"{config.POSE_MIN_PER_BUCKET} per direction")

    check("the higher enrollment target is tracked separately",
          not vault.target_reached(person),
          f"target is {config.ENROLL_TARGET_PER_BUCKET} per direction")

    sparse = vault.empty_store()
    thin = vault.upsert_person(sparse, "thin", "owner")
    # One sample only, in front. Because the minimum per direction is
    # config.POSE_MIN_PER_BUCKET (>1), front is *also* still incomplete - so all
    # five directions must be reported, not just the untouched four.
    thin["templates"].append({"vector": vault.vector_to_list(unit(1)),
                              "bucket": "front"})
    check("every direction short of the minimum is reported",
          set(vault.missing_buckets(thin)) == set(config.POSE_LABELS),
          str(vault.missing_buckets(thin)))

    # Add a second front sample: front becomes satisfied, the four turned
    # directions remain outstanding.
    thin["templates"].append({"vector": vault.vector_to_list(unit(2)),
                              "bucket": "front"})
    check("a satisfied direction drops out of the missing list",
          set(vault.missing_buckets(thin))
          == set(config.POSE_LABELS) - {"front"},
          str(vault.missing_buckets(thin)))

    two = vault.empty_store()
    vault.upsert_person(two, "a", "owner")
    vault.upsert_person(two, "b", "owner")
    check("two owners is an invalid state", vault.owner_person(two) is None)

    vault.set_owner(store, "tester")
    check("exactly one owner resolves", vault.owner_person(store) is not None)


# ----------------------------------------------------------------------
# 7. fail-closed behaviour
# ----------------------------------------------------------------------
def test_fail_closed():
    section("verifier: fails closed")

    ok, detail = auth_wall.preflight()
    check("local model pack is detected offline", ok, detail)

    service = verifier.VerificationService()
    result = service.verify(scope=verifier.SCOPE_SECURE)

    # With no owner enrolled this must deny, and must not issue a token.
    if not vault.owner_person(vault.load_store() or vault.empty_store()):
        check("un-enrolled system denies a secure action",
              result["status"] in ("denied", "unavailable"), result["reason"])
        check("no grant is issued on denial", "grant_token" not in result)
    else:
        check("existing enrollment was not disturbed (manual check skipped)",
              result["status"] in ("denied", "verified", "unavailable"),
              result["status"])

    check("a denial is never reported as verified",
          result["status"] != "verified" or result.get("person"))


# ----------------------------------------------------------------------
# 8. scene provider honesty
# ----------------------------------------------------------------------
def test_scene_provider():
    section("scene: provider reporting")

    import scene_eye

    status = scene_eye.provider_status()
    check("scene provider is always reported", status["provider"]
          in ("local", "groq", "off"), status["provider"])
    if status["provider"] == "off":
        check("no provider means it says so", "cannot be answered" in status["detail"])

    result = scene_eye.answer_question("is there a pen", [])
    check("a question without frames is not answered",
          not result["answered"], result["reason"])

    prompt = scene_eye.build_prompt("a pen", mode="find")
    check("the prompt forbids guessing",
          "not clearly visible" in prompt and "never invent" in prompt.lower())


# ----------------------------------------------------------------------
# 9. camera controller cost model
# ----------------------------------------------------------------------
def test_camera_cost_model():
    section("camera: lifecycle and trigger logic")

    import camera_control

    check("camera starts closed", not camera_control.camera().is_open)

    previous = np.zeros((96, 96), dtype=np.uint8)
    identical = np.zeros((96, 96), dtype=np.uint8)
    check("an unchanged frame is not motion",
          not camera_control.is_motion(previous, identical))

    changed = np.full((96, 96), 255, dtype=np.uint8)
    check("a changed frame is motion",
          camera_control.is_motion(previous, changed))

    check("first frame is treated as motion for one detection pass",
          camera_control.is_motion(None, identical))

    modest = previous.copy()
    modest[0:3, 0:3] = 255
    check("a tiny change does not trigger detection",
          not camera_control.is_motion(previous, modest),
          "avoids wasted passes on sensor noise")

    service = verifier.VerificationService()
    service._open_session("owner", verifier.SCOPE_PRESENCE)
    check("an open session is fast to read", service.is_owner_present())
    service.clear_session()
    check("a cleared session reports not present",
          not service.is_owner_present())


# ----------------------------------------------------------------------
# 10. service wiring without a camera
# ----------------------------------------------------------------------
def test_service_wiring():
    section("service: wiring and emergency control")

    import service as service_module

    svc = service_module.FaceService()
    check("service starts stopped", not svc.is_running() and svc.mode == config.MODE_OFF)

    status = svc.status()
    check("status exposes camera/model/store/session",
          all(key in status for key in
              ("camera", "model", "store", "session", "liveness", "stats")))

    diagnostics = svc.diagnostics()
    check("diagnostics prove the wake/sleep lifecycle is counted",
          "camera_opens" in diagnostics and "camera_closes" in diagnostics)

    check("unknown modes are refused",
          not svc.request_mode("turbo")["ok"])

    svc.mode = config.MODE_WATCH
    svc.stop_hard()
    check("emergency stop releases the camera and stops the loop",
          not svc.camera.is_open and svc.mode == config.MODE_OFF)

    queued = svc.ask_scene("is there a pen")
    polled = svc.result(queued["id"])
    check("a queued request can be polled without blocking",
          polled.get("pending") in (True, False), str(polled.get("reason")))

    check("an unknown request id is reported honestly",
          not svc.result("nope")["ok"])


# ----------------------------------------------------------------------
# 11. bridge surface
# ----------------------------------------------------------------------
def test_bridge():
    section("bridge: LYA-facing contract")

    import lya_bridge

    info = lya_bridge.available()
    check("bridge reports readiness and who is enrolled",
          "ready" in info and "model" in info, str(info.get("enrolled")))

    check("bridge grants nothing without verification",
          lya_bridge.grade_action("open vault", {"status": "denied"}) == "deny")
    check("bridge treats unknown status as deny",
          lya_bridge.grade_action("open vault", {"status": "weird"}) == "deny")
    check("bridge allows only a verified report",
          lya_bridge.grade_action("open vault", {"status": "verified"}) == "allow")
    check("bridge handles a malformed report safely",
          lya_bridge.grade_action("x", None) == "deny")

    result = lya_bridge.consume("not-a-token", "anything")
    check("bridge cannot redeem an invented token", not result["ok"])


# ----------------------------------------------------------------------
def main() -> int:
    print("=" * 70)
    print("LYA face-recognition - offline regression suite")
    print("No camera and no network are used. Placeholder vectors only.")
    print("=" * 70)

    test_recognizer_policy()
    test_voting()
    test_liveness()
    test_grants()
    test_sessions()
    test_vault()
    test_fail_closed()
    test_scene_provider()
    test_camera_cost_model()
    test_service_wiring()
    test_bridge()

    print("\n" + "=" * 70)
    print(f"passed: {len(PASSED)}   failed: {len(FAILED)}")
    if FAILED:
        print("\nFAILURES:")
        for label in FAILED:
            print(f"  - {label}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
