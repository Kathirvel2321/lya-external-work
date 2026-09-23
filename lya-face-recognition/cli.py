"""Command-line interface for the face-recognition service.

    python cli.py doctor          - check camera, models, store, providers
    python cli.py status          - service/report snapshot
    python cli.py enroll ipvis    - guided multi-direction enrollment
    python cli.py enroll-test     - the same capture, saving labelled debug frames
    python cli.py verify          - presence verification (fast)
    python cli.py verify-secure   - secure verification (owner + liveness challenge)
    python cli.py watch           - run the background watch service until Ctrl+C
    python cli.py stream          - open the live camera + AI view window
    python cli.py see "is there a pen on my desk"  - ask about the scene
    python cli.py templates       - show who is enrolled and angle coverage
    python cli.py forget ipvis    - remove a person
    python cli.py wipe            - destroy templates and the key
    python cli.py test            - run the offline test suite

Everything prints plain text and exits with a status code, so it is scriptable
and easy to check without a GUI. No command downloads anything.
"""
from __future__ import annotations

import json
import sys
import time

import config


def _print(title: str):
    print(f"\n=== {title} ===")


def _json(value) -> str:
    return json.dumps(value, indent=2, default=str)


# ----------------------------------------------------------------------
# doctor
# ----------------------------------------------------------------------
def cmd_doctor() -> int:
    _print("model pack (offline check)")
    ok, detail = config.models_available()
    print(f"  available: {ok}")
    print(f"  detail   : {detail}")

    _print("camera")
    import camera_control

    cam = camera_control.camera()
    opened = cam.open()
    print(f"  opened  : {opened}")
    if opened:
        frame = cam.read()
        if frame is not None:
            print(f"  frame   : {frame.bgr.shape[1]}x{frame.bgr.shape[0]}")
            import cv2
            import numpy as np

            print(f"  brightness: {float(np.mean(frame.gray)):.1f}")
            print(f"  sharpness : {camera_control.blur_score(frame.gray):.1f}")
        cam.close()
        print(f"  released: {not cam.is_open}")
    else:
        print(f"  error   : {cam.last_error}")

    _print("encrypted store")
    import vault

    try:
        print(_json(vault.summary()))
    except Exception as exc:
        print(f"  error: {exc}")

    _print("liveness")
    import liveness

    print(_json(liveness.liveness_available()))

    _print("scene provider")
    import scene_eye

    print(_json(scene_eye.provider_status()))

    _print("face engine")
    import auth_wall

    warm_ok, warm_detail = auth_wall.warm_up()
    print(f"  loaded: {warm_ok} ({warm_detail})")

    _print("summary")
    if not ok:
        print("  face recognition is NOT usable: the local model pack is missing.")
        print("  see models/README.md - this project never downloads models.")
    elif not vault.store_exists():
        print("  ready. nobody is enrolled yet - run: python cli.py enroll <name>")
    else:
        print("  ready. see 'python cli.py templates' for enrollment coverage.")
    return 0


# ----------------------------------------------------------------------
# enrollment
# ----------------------------------------------------------------------
def _run_enrollment(name: str, dataset: bool, per_bucket: int) -> int:
    import enroll

    dataset_path = config.DATASET_DIR if dataset else None
    session = enroll.EnrollmentSession(name, role="owner", per_bucket=per_bucket,
                                       dataset_path=dataset_path)
    if not session.start():
        print(f"  cannot start enrollment: {session.last_message}")
        return 1

    print(f"\nGuided enrollment for '{name}'.")
    print("Follow the prompt. Every direction is captured so side profiles match too.")
    print("Press Ctrl+C to abort (nothing partial is kept).\n")

    last_prompt = ""
    try:
        while not session.finished:
            progress = session.step()
            if progress["prompt"] != last_prompt:
                last_prompt = progress["prompt"]
                print(f"\n  >> {last_prompt}")
            coverage = progress["coverage"]
            summary = "  ".join(
                f"{bucket}:{data['have']}/{data['need']}"
                for bucket, data in coverage.items())
            print(f"\r  {summary}   {progress['message'][:52]:<52}", end="")
            time.sleep(0.02)
    except KeyboardInterrupt:
        print("\n\n  aborted - no partial enrollment was saved for this run.")
        session.stop()
        return 1
    finally:
        session.stop()

    progress = session.progress()
    print(f"\n\n  {progress['message']}")
    print(f"  captured {progress['captured']} samples, "
          f"rejected {progress['rejected']} low-quality frames")
    print("  coverage:")
    for bucket, data in progress["coverage"].items():
        mark = "ok " if data["done"] else "..."
        print(f"    [{mark}] {bucket:<14} {data['have']}/{data['need']}")
    if dataset:
        print(f"  debug frames: {dataset_path}\\{name}\\<direction>\\")
    print("\n  next: python cli.py verify")
    return 0


def cmd_enroll(name: str) -> int:
    return _run_enrollment(name, dataset=False, per_bucket=config.ENROLL_TARGET_PER_BUCKET)


def cmd_enroll_test(name: str) -> int:
    print("Test mode: labelled debug frames will be written to dataset/.")
    print("These are the ONLY images this project ever writes to disk.\n")
    return _run_enrollment(name, dataset=True, per_bucket=config.ENROLL_TARGET_PER_BUCKET)


# ----------------------------------------------------------------------
# verification
# ----------------------------------------------------------------------
def _report(result: dict):
    print(f"  status : {result['status']}")
    print(f"  person : {result.get('person')}")
    print(f"  reason : {result.get('reason')}")
    if result.get("detail"):
        print(f"  detail : {result['detail']}")
    print(f"  frames : {result.get('frames')}  elapsed: {result.get('elapsed')}s")
    if result.get("votes"):
        print(f"  votes  : {result['votes']}")
    if result.get("challenge"):
        challenge = result["challenge"]
        print(f"  challenge: completed={challenge.get('completed')} "
              f"remaining={challenge.get('remaining')}")
    if result.get("grant_token"):
        print(f"  grant  : {result['grant_token']} (single-use, "
              f"{result['grant'].get('seconds_left')}s)")
    signals = result.get("signals") or {}
    for key, value in signals.items():
        print(f"  signal {key}: {_json(value)}")


def cmd_verify(secure: bool) -> int:
    import verifier

    scope = verifier.SCOPE_SECURE if secure else verifier.SCOPE_PRESENCE
    _print(f"{scope} verification")
    if secure:
        print("  A live challenge will be required (blink / head turn).")
    service = verifier.VerificationService()
    result = service.verify(scope=scope)
    _report(result)
    return 0 if result["status"] == "verified" else 2


# ----------------------------------------------------------------------
# service / watch
# ----------------------------------------------------------------------
def cmd_watch(seconds: float | None) -> int:
    import service as service_module

    svc = service_module.service()
    _print("watch service")
    print("  The camera wakes on movement, verifies, then releases itself.")
    print("  Press Ctrl+C to stop.\n")
    svc.start(config.MODE_WATCH)
    started = time.time()
    try:
        while True:
            time.sleep(1.0)
            status = svc.status()
            session = status["session"]
            print(f"\r  mode={status['mode']:<7} "
                  f"camera={'open ' if status['camera']['open'] else 'closed'} "
                  f"opens={status['stats']['camera_opens']:<3} "
                  f"closes={status['stats']['camera_closes']:<3} "
                  f"detector={status['stats']['detector_passes']:<4} "
                  f"verify={status['stats']['verify_runs']:<3} "
                  f"session={session['person'] or '-':<10}"
                  f" {round(session['seconds_left'])}s", end="")
            if seconds and time.time() - started > seconds:
                break
    except KeyboardInterrupt:
        print("\n")
    finally:
        svc.stop()
    _print("diagnostics after run")
    print(_json(svc.diagnostics()))
    return 0


def cmd_stream(seconds: float, show_ai: bool) -> int:
    import camera_stream

    _print("live camera view")
    ok, detail = camera_stream.gui_available()
    print(f"  gui: {ok} ({detail})")
    if not ok:
        return 1
    print("  Keys inside the window: 'a' toggles the AI panel, Q/Esc closes.")
    result = camera_stream.run_live(view_seconds=seconds, show_ai=show_ai)
    print(_json(result))
    return 0 if result.get("ok") else 1


# ----------------------------------------------------------------------
# scene
# ----------------------------------------------------------------------
def cmd_see(question: str, frames: int) -> int:
    import camera_control
    import scene_eye

    _print("scene question")
    status = scene_eye.provider_status()
    print(f"  provider: {status['provider']} - {status['detail']}")
    if status["provider"] == "off":
        print("  cannot answer. Options:")
        print("   - install a local vision model (Ollama + llava/moondream): free,")
        print("     nothing uploaded, best privacy")
        print("   - or configure a cloud key (GROQ_API_KEY or LYA's stored key)")
        return 3

    cam = camera_control.camera()
    if not cam.open():
        print(f"  camera unavailable: {cam.last_error}")
        return 1
    captured = []
    try:
        cam.set_streaming(True)
        time.sleep(0.35)
        for index in range(max(1, frames)):
            frame = cam.read()
            if frame is not None:
                captured.append(frame)
            if index + 1 < frames:
                time.sleep(0.35)
    finally:
        cam.set_streaming(False)
        cam.close()

    print(f"  captured {len(captured)} frame(s); camera released: {not cam.is_open}")
    result = scene_eye.answer_question(question, captured, mode="find" if question
                                       else "look")
    print()
    if result.get("answered"):
        print(f"  ANSWER: {result['answer']}")
        print(f"  privacy: {result['privacy']}")
    else:
        print(f"  no answer: {result.get('reason')}")
    print(f"  elapsed: {result.get('elapsed')}s")
    return 0 if result.get("answered") else 2


# ----------------------------------------------------------------------
# store management
# ----------------------------------------------------------------------
def cmd_templates() -> int:
    import vault

    _print("enrolled people")
    try:
        summary = vault.summary()
    except Exception as exc:
        print(f"  error: {exc}")
        return 1
    if not summary.get("exists"):
        print("  nothing enrolled yet")
        return 0
    print(f"  owner: {summary.get('owner')}")
    for person in summary["people"]:
        print(f"\n  {person['name']} ({person['role']}), {person['samples']} samples")
        for bucket, count in person["buckets"].items():
            need = config.ENROLL_TARGET_PER_BUCKET
            mark = "ok " if count >= need else "..."
            print(f"    [{mark}] {bucket:<14} {count}/{need}")
        if person["missing"]:
            print(f"    thin directions: {', '.join(person['missing'])}")
    return 0


def cmd_forget(name: str) -> int:
    import vault

    if vault.forget(name):
        print(f"  removed '{name}' and their templates")
        return 0
    print(f"  no person named '{name}'")
    return 1


def cmd_wipe() -> int:
    import vault

    existing = vault.summary().get("people", [])
    print(f"  this destroys {len(existing)} enrolled person(s) and the key.")
    answer = input("  type WIPE to confirm: ").strip()
    if answer != "WIPE":
        print("  cancelled")
        return 1
    vault.wipe()
    print("  templates and key destroyed")
    return 0


# ----------------------------------------------------------------------
# status / tests
# ----------------------------------------------------------------------
def cmd_status() -> int:
    import service as service_module

    svc = service_module.service()
    print(_json(svc.status()))
    return 0


def cmd_test() -> int:
    import tests.test_headless as suite

    return suite.main()


# ----------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 0
    command, rest = argv[0], argv[1:]

    if command == "doctor":
        return cmd_doctor()
    if command == "camera-check":
        import camera_check

        return camera_check.main()
    if command == "status":
        return cmd_status()
    if command == "enroll":
        return cmd_enroll(rest[0] if rest else input("name: ").strip())
    if command == "enroll-test":
        return cmd_enroll_test(rest[0] if rest else input("name: ").strip())
    if command == "verify":
        return cmd_verify(secure=False)
    if command == "verify-secure":
        return cmd_verify(secure=True)
    if command == "watch":
        seconds = float(rest[0]) if rest else None
        return cmd_watch(seconds)
    if command == "stream":
        seconds = float(rest[0]) if rest else 120.0
        return cmd_stream(seconds, show_ai=True)
    if command == "see":
        question = " ".join(rest) if rest else ""
        return cmd_see(question, frames=1)
    if command == "templates":
        return cmd_templates()
    if command == "forget":
        return cmd_forget(rest[0] if rest else input("name: ").strip())
    if command == "wipe":
        return cmd_wipe()
    if command == "test":
        return cmd_test()

    print(f"unknown command '{command}'\n")
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
