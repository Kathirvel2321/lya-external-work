# Integrating with LYA

This document is for wiring the face service into LYA **later, when you ask**.
Nothing inside the LYA project has been modified, and nothing here changes LYA's
behaviour on its own.

## The one rule

**This module returns facts, never permission.**

It tells LYA "the owner is present and passed a liveness check" and hands back a
single-use token. LYA's own policy layer still decides what a verified owner may
do — exactly as it already does for phone approval. Recognition never silently
grants a capability.

## What LYA should call

Everything is in `lya_bridge.py`, which exists precisely so LYA does not need to
know about the eight internal modules.

```python
import sys
sys.path.insert(0, r"C:\Users\ipvis\Documents\Brain\lya\lya-face-recognition")

import lya_bridge

# 1. At startup: is the service usable?
info = lya_bridge.available()
#   {"ready": bool, "model": "...", "enrolled": ["ipvis"], "owner": "ipvis"}

# 2. Start cheap background watching (one thread, camera released when idle)
lya_bridge.start_watching("watch")

# 3. Everyday, non-private: who is here?
who = lya_bridge.who_is_here()
#   {"person": "ipvis", "role": "owner", "status": "verified", "reason": "..."}

# 4. Private action: ask for a live, liveness-checked approval
approval = lya_bridge.request_secure_approval("open vault")
if approval["approved"]:
    token = approval["token"]
    # ... do the sensitive work ...
    ok = lya_bridge.consume(token, "open vault")   # single-use, this action only

# 5. The AI's eye
answer = lya_bridge.ask_about_scene("is there a pen on my desk")

# 6. Shut down
lya_bridge.stop()
```

## Threading — important

`request_secure_approval` and `ask_about_scene` **open the camera and block**
while they wait for a person or a model. Never call them on the Tk event loop;
that is why LYA already has a task worker. Call them from that worker and poll
with `svc.result(request_id)` if you prefer not to block at all.

The service already follows the same pattern LYA uses: one background thread
does perceptual work, results are polled, the UI never waits.

## Camera sharing

Only one program can hold camera 0 on Windows. Two consequences:

- Do **not** open a second `cv2.VideoCapture(0)` anywhere in LYA. Use
  `lya_bridge` instead; its controller owns the device and hands out frames.
- If you need the camera for something else and the service is watching, call
  `lya_bridge.stop()` first, then start it again afterwards.

## Suggested policy mapping

This matches the role structure already in `LYA_VISION.md`:

| LYA concept | How to get it here |
| --- | --- |
| "approximate laptop recognition for personalisation" | `who_is_here()`, treat a failure as *guest*, never as owner |
| "stronger verification for confidential actions" | `request_secure_approval(action)` — requires a live owner + challenge |
| "highest sensitivity: admin only, fresh verification" | same call; grants expire, so a stale one cannot be reused |
| "unknown person = basic queries only" | `status != "verified"` → guest path |

Two rules worth keeping:

1. **Never** treat `who_is_here()` alone as authority for a private action. It
   is the fast personalisation path and does not require a challenge.
2. On any `deny`, `unavailable` or `ambiguous` status, fall through to LYA's
   existing guest behaviour. Do not retry in a loop — the burst already ran for
   up to `VERIFY_TIMEOUT` (10 s).

## Current gaps before a real integration

Be aware of these before promising behaviour:

- **Nobody is enrolled yet**, so `available()["ready"]` is False until you run
  `cli.py enroll <name>`.
- The voice/phone side of LYA's auth wall is unchanged; this module covers the
  **laptop camera** only. Combining it with the existing phone approval is a
  policy decision for you, not something this module does automatically.
- Grants are held in memory. If LYA restarts between approval and use, the token
  is gone — which is the safe direction, but it means approval must not be
  separated from the action by a restart.
- No independent security review has been done. Treat this as a strong
  prototype, not an audited lock.

## If you want a different shape

The surface is narrow on purpose. If you would rather have:

- an HTTP endpoint instead of direct calls, or
- a different grant lifetime or scope naming,

those are small changes in `lya_bridge.py` / `config.py`. Say which and it can
be adjusted without touching LYA.
