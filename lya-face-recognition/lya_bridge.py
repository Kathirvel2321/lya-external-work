"""Bridge to LYA — how the assistant asks this module a question.

This folder does not modify anything inside LYA. Instead it exposes a small,
explicit surface that LYA can call, so the two stay independent and either one
can be updated without breaking the other.

The contract, deliberately narrow:

    from lya_face_recognition.service import service        # or the path shim
    svc = service()
    svc.start("watch")                       # background, cheap
    grant = svc.verify_now("secure")         # blocking, returns a report
    if grant["status"] == "verified":
        token = grant["grant_token"]         # single-use, per-action
        ...

Bridging rules that matter for security:

* This module **never** grants permission by itself. It returns facts plus a
  single-use grant token. LYA's own policy layer still decides what a verified
  owner may do, exactly as it does for phone approval today.
* A grant is bound to one action string. ``consume_grant(token, action)``
  refuses a token issued for a different action, so a "presence" grant can never
  be replayed as "open the vault".
* Nothing here imports or monkey-patches LYA code.

How LYA should wire it (in its own time, when the owner asks): add this folder
to ``sys.path`` and call the functions below from the task worker thread, then
poll with ``result()``. Do not call ``verify_now`` on the Tk event loop.
"""
from __future__ import annotations

import threading

import config
import service as service_module
import verifier


def available() -> dict:
    """Cheap readiness probe LYA can call at startup."""
    ok, detail = config.models_available()
    import vault

    try:
        store = vault.summary()
    except Exception as exc:                            # pragma: no cover - defensive
        store = {"exists": True, "error": str(exc), "people": []}
    return {
        "module": "lya_face_recognition",
        "ready": bool(ok and store.get("people")),
        "model": detail,
        "enrolled": [p["name"] for p in store.get("people", [])],
        "owner": store.get("owner"),
        "camera_index": config.CAMERA_INDEX,
    }


def start_watching(mode: str = config.MODE_WATCH) -> dict:
    """Begin cheap background presence watching."""
    svc = service_module.service()
    svc.start(mode)
    return {"ok": True, "mode": svc.mode, "running": svc.is_running()}


def stop() -> dict:
    svc = service_module.service()
    svc.stop()
    return {"ok": True, "running": svc.is_running()}


def who_is_here(timeout: float = 12.0) -> dict:
    """Answer 'who is in front of the camera' without granting anything.

    Non-private: this is the everyday personalisation path. It returns a name
    and role for information only.
    """
    svc = service_module.service()
    result = svc.verify_now(scope=verifier.SCOPE_PRESENCE)
    return {"person": result.get("person"), "role": result.get("role"),
            "status": result["status"], "reason": result.get("reason")}


def request_secure_approval(action: str, timeout: float = 15.0) -> dict:
    """Ask for a live, liveness-checked owner approval for one named action.

    Runs on a worker thread because it opens the camera and waits for a blink or
    head turn. Returns a single-use token to pass to ``consume(token, action)``.
    """
    svc = service_module.service()
    result = svc.verify_now(scope=verifier.SCOPE_SECURE)
    if result["status"] != "verified":
        return {"approved": False, "reason": result.get("reason"),
                "detail": result.get("detail")}

    # Re-bind the grant to the caller's specific action string so it cannot be
    # reused for anything else.
    token = result.get("grant_token")
    if token:
        issued = svc.verifier._grants.get(token)
        if issued is not None:
            issued.action = action
    return {"approved": True, "person": result.get("person"),
            "token": token, "action": action,
            "seconds_valid": (result.get("grant") or {}).get("seconds_left")}


def consume(token: str, action: str) -> dict:
    """Redeem an approval token for exactly one action."""
    svc = service_module.service()
    ok, message = svc.verifier.consume_grant(token, action)
    return {"ok": ok, "message": message}


def ask_about_scene(question: str, wait: float = 40.0) -> dict:
    """Queue a scene question and wait briefly for the answer.

    Calls LYA should make from its worker thread, not the UI loop.
    """
    svc = service_module.service()
    if not svc.is_running():
        svc.start(config.MODE_WATCH)
    queued = svc.ask_scene(question)
    request_id = queued["id"]

    waited = 0.0
    step = 0.25
    while waited < wait:
        result = svc.result(request_id)
        if result.get("ok") is not None and "answer" in result:
            return result
        if not result.get("pending") and result.get("reason") == "unknown request id":
            break
        threading.Event().wait(step)
        waited += step
    return {"answered": False, "id": request_id,
            "reason": "timed out waiting for the scene answer"}


def grade_action(action: str, result: dict) -> str:
    """Map a verification report to the decision LYA's policy layer expects.

    Kept explicit so the mapping is auditable: an unrecognised status is always
    treated as a denial, never as an approval.
    """
    if not isinstance(result, dict):
        return "deny"
    status = result.get("status")
    if status == "verified" and action:
        return "allow"
    return "deny"
