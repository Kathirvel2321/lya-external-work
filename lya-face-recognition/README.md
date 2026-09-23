# lya-face-recognition

A camera controller and face-recognition service for LYA. It lives in its own
folder and **does not modify anything inside the LYA project**.

It answers three questions:

1. **Who is in front of the laptop?** — correctly, from any direction, and only
   for a live person (a photo of you does not work).
2. **What is in front of the laptop?** — "do you see a pen on my desk?"
3. **What does this cost?** — measured, not claimed.

Everything is local and free. No subscription, no API key required, no model
downloaded behind your back.

---

## Status: what is verified vs. what is not

**Verified on this machine (real runs, real numbers):**

- The camera opens, reads 640x480 frames, and releases cleanly.
- InsightFace `buffalo_l` is already on disk and loads **offline** — no
  download happens, and the code refuses to start if the files are missing.
- The offline test suite: **65 checks, 0 failures** (`python cli.py test`).
- Idle cost: **20 seconds of watching an empty room = 0 motion triggers,
  0 detector passes, 0 verification runs.** The camera opened and closed itself
  4 times. (Before a fix described below, that same test did 3 wasted
  verifications in 12 seconds.)
- Motion check costs **~74 microseconds** when nothing moves.
- Detector-only pass: **~0.6 s**. Full face read with embedding: **~0.6 s**.

**Not yet verified — you must do this part:**

- **No face has been enrolled.** Nobody is registered, so end-to-end unlock
  with your real face has *not* been proven. Run `python cli.py enroll <name>`.
- The passive anti-spoof model is **not installed**, so printed-photo rejection
  currently relies on the movement check plus the active blink/head-turn
  challenge. Adding a local ONNX model strengthens it — see `models/README.md`.
- The scene question ("is there a pen") is wired and reports its provider, but
  **has not been run against a real photo of your desk** in this session.
- No independent security review. This is a solid prototype, not an audited
  product. Do not treat it as suitable for police or investigative use.

---

## Quick start

```powershell
cd C:\Users\ipvis\Documents\Brain\lya\lya-face-recognition
$env:PYTHONUTF8=1
C:\Python314\python.exe -B cli.py doctor
```

Then:

```powershell
C:\Python314\python.exe -B cli.py enroll ipvis        # guided, all directions
C:\Python314\python.exe -B cli.py templates           # check angle coverage
C:\Python314\python.exe -B cli.py verify              # quick "who is there"
C:\Python314\python.exe -B cli.py verify-secure       # owner + blink/turn
C:\Python314\python.exe -B cli.py stream              # live camera + AI view
C:\Python314\python.exe -B cli.py watch               # background always-ready
C:\Python314\python.exe -B cli.py see "is there a pen on my desk"
C:\Python314\python.exe -B cli.py test                # offline suite
```

`enroll ipvis` is the one you need to run for the "hey LYA, recognise me" part
to work.

---

## How the three requirements are met

### 1. "A photo of me must not work"

Matching alone is never enough. A decision needs **identity + liveness**:

| Signal | What it stops | Cost |
| --- | --- | --- |
| ArcFace match + runner-up margin | a similar-looking person | ~0.6 s |
| Frame voting (3 of 5 frames must agree) | one lucky blurred frame | free |
| Natural-movement check | a printed photo taped to the lid | free |
| **Active challenge: blink / head turn** | a photo, and a looping video | free |
| Passive anti-spoof ONNX (optional) | screen replay, paper reflection | ~0.1 s |

The active challenge is the important one: it is **randomly chosen each time**
and a photo cannot comply. This is enforced for private actions and is what
makes `verify-secure` different from `verify`.

Additional rules, all tested in the suite:

- **Ambiguity is refused.** If a second person's template is nearly as close as
  the winner, access is denied instead of guessed.
- **Fails closed.** Missing model, empty enrollment or unreadable store all
  *deny*. There is no fallback to "allow".
- **Grants are single-use and action-bound.** A token issued for "open the
  vault" cannot be replayed for "send email".
- **Sessions decay** (120 s) and drop the moment you leave the frame.

### 2. "Recognise me from every direction"

This is an enrollment problem, not a model problem. `enroll.py` walks you
through directions in order — front, slight turns, near-profile both sides, and
a second stability round — and stores samples **per direction bucket**.

- Every sample passes a quality gate, and the reason for rejection is shown
  ("hold still", "too dark", "come closer").
- One direction cannot be filled twice by sitting still; each bucket has its
  own count and target.
- `cli.py templates` shows you the coverage grid, so you can see a weak angle
  and fix it rather than guessing why a side-on look fails.

### 3. "No pressure on the laptop, camera not on 24 hours"

The camera is **released**, not just idle, and the watch loop has three levels:

| Situation | What runs | Measured cost |
| --- | --- | --- |
| Empty room | motion check only | **74 µs/frame** |
| Something moved | detector-only preselect | ~0.6 s, then closes if no face |
| A face is found | one bounded verification burst | ~0.6 s/frame, ≤10 s total |

Guard rails that make the promise real:

- Embeddings are computed **only** inside a verification burst, never while
  waiting.
- If the camera stays open for `WATCH_MAX_OPEN_SECONDS` (45 s) without
  producing a result, the loop **closes it anyway** — the light cannot stay on
  because of a bug.
- After `EMPTY_LIMIT` (12) empty checks the device is released entirely.
- `stop_hard()` releases the camera immediately, even mid-burst.
- `pause()` suspends all capture while keeping state.

---

## Two real bugs this project found and fixed

Worth recording, because they are the difference between "works on paper" and
"works on your laptop". Both were found by measuring, not guessing.

### 1. The idle watch loop was waking itself up for no reason

The first motion test compared **consecutive frames**. On this camera, a static
desk scene produced frame-to-frame differences between 1.5 and 14.7 (median
~4.9) purely because auto-exposure keeps hunting. Result: an empty room was
flagged as "motion" in ~35% of frames, which woke face detection and ran
**3 pointless verifications in 12 seconds**.

The fix compares against a **~1 second old reference frame** instead. Slow
exposure drift affects both frames similarly so it cancels out, while a person
moving does not. Measured: **0 false triggers in 80 frames** of an empty room,
and a person still triggers reliably.

### 2. The live view lagged because it was spinning, not because it was slow

You reported the preview felt laggy when moving. Measurement showed the cause
was not the model at all:

- While "streaming", `read()` returned the **same cached frame** whenever it was
  under 150 ms old — instantly, with no delay.
- The display loop therefore called it in a tight loop and ran
  **3,790,000 iterations in 4 seconds**, pinning a CPU core at 100%. The laptop
  was fighting itself, so the picture fell behind.
- Worse, when a face *was* present, analysis cost ~0.6 s **inline in the display
  loop**, freezing the preview for over half a second at a time.

Two fixes:

1. `wait_for_new_frame()` blocks until a genuinely new frame exists, and the
   loop is capped at `STREAM_MAX_FPS` (30). Measured: **30 fps of real frames**
   instead of ~1,000,000 useless iterations.
2. Analysis moved to a background `AsyncAnalyzer` thread that keeps only the
   freshest pending frame, so the preview never waits for the model. Measured:
   **30.7 fps with analysis running in parallel**, 0 stale frames dropped.

A third, smaller fix: the overlay used to clear its verdict on any not-yet-
analysed frame, making the panel flicker between "matched" and "not evaluated".
It now keeps the last known verdict.

> If the preview still feels less than perfectly smooth, the honest reason would
> be the CPU itself, since analysis runs alongside the preview.
> `FACE_STREAM_MAX_FPS` and `FACE_STREAM_ANALYSIS` tune that trade-off; the
> measured numbers above are the starting point.

Worth recording, because it is the difference between "works on paper" and
"works on your laptop".

The first motion test compared **consecutive frames**. On this camera, a static
desk scene produced frame-to-frame differences between 1.5 and 14.7 (median
~4.9) purely because auto-exposure keeps hunting. Result: an empty room was
flagged as "motion" in ~35% of frames, which woke face detection and ran
**3 pointless verifications in 12 seconds** — exactly the load you said to
avoid.

The fix compares against a **~1 second old reference frame** instead. Slow
exposure drift affects both frames similarly so it cancels out, while a person
moving does not. Measured result: **0 false triggers in 80 frames** of an empty
room, and a person still triggers reliably. Both numbers are in
`camera_control.MotionGate`.

This is also why the diagnostics report *measured counters* rather than
describing the design — so you can check it yourself.

---

## The AI's eye (scene questions)

"Who is this" and "what is this" need different tools. Face embeddings cannot
see a pen; that needs a vision-language model. So scene questions are separate,
opt-in, and honest about privacy:

| Provider | Privacy | Cost | When |
| --- | --- | --- | --- |
| `local` (Ollama + llava/moondream) | nothing leaves the laptop | free | preferred, auto-detected |
| `groq` | frame is uploaded | free tier | used if LYA's key is present |
| `off` | nothing runs | free | default when nothing is configured |

On this machine `groq` is currently selected because LYA already has a key
stored. If you prefer zero uploads, install a local vision model:

```powershell
ollama pull moondream      # small, fast, works on CPU
```

Then `cli.py see "..."` will use it automatically and nothing is uploaded.

The prompt explicitly forbids guessing: if the object is not clearly visible,
the model is instructed to say so rather than infer it from context. A wrong
"yes, I see a pen" is worse than "I cannot see".

---

## The live camera + AI view

`cli.py stream` opens one window showing both things, never mixed up:

- **Left:** the raw frame with the detected face box — what the camera sees.
- **Right:** the AI's reading — direction bucket, yaw, eye openness, quality
  score *and the reason*, match status, score, runner-up and margin.

Every number is a real measurement from the pipeline. There is no invented HUD
telemetry. Press `a` to toggle the AI panel, `Q`/`Esc` to close.

---

## Security and privacy, stated plainly

- **Only vectors are stored, never images.** A 512-number vector cannot be
  turned back into a face. The optional `dataset/` capture (used only by
  `enroll-test`) is the single exception and is clearly labelled.
- **Templates are encrypted** (AES-256/Fernet) and the key is wrapped by
  **Windows DPAPI**, bound to your Windows account. Copying `private/` to
  another PC makes it useless, and the code says so instead of failing quietly.
- **Nothing is logged as raw biometric data.** Store contents are summarised as
  names, counts and coverage.
- **The store is off by default** until you explicitly enroll.

**Honest limits:**

- Any process running as your Windows user can also call DPAPI. This protects
  data at rest and against file theft, **not** against malware already inside
  your session.
- These thresholds are reasoned and unit-tested, but **not calibrated against
  real presentational attacks**. A determined attacker with a good video and
  the right timing may defeat the challenge. Do not use this as the only lock
  on genuinely sensitive material.
- This is not Apple's Face ID. There is no hardware-backed secure enclave.

---

## Files

| File | Responsibility |
| --- | --- |
| `config.py` | every tunable, plus the offline model check |
| `camera_control.py` | camera lifecycle, `Frame`, `MotionGate` |
| `auth_wall.py` | offline model loading, quality, pose, eye openness |
| `recognizer.py` | matching policy: thresholds, margin, frame voting |
| `liveness.py` | movement check, passive ONNX, active challenge |
| `vault.py` | encrypted, DPAPI-keyed template store |
| `verifier.py` | the gate: combines identity + liveness + session |
| `enroll.py` | guided multi-direction enrollment |
| `scene_eye.py` | "is there a pen" — provider selection and honest answers |
| `service.py` | background watch loop, request queue, emergency stop |
| `camera_stream.py` | live camera view with the AI overlay |
| `cli.py` | all commands |
| `lya_bridge.py` | the narrow surface LYA calls — see `INTEGRATION.md` |
| `tests/test_headless.py` | 65 offline checks, no camera, no network |

---

## Requirements

Already present on this machine, nothing new was installed:

- Python 3.14 (`C:\Python314\python.exe`)
- `opencv-python` 5.0, `numpy`, `insightface` 1.0.1, `onnxruntime`,
  `cryptography`, `pywin32`
- InsightFace `buffalo_l` at `~/.insightface/models/buffalo_l/` (already there)

`python` is not on PATH on this machine — use the full `C:\Python314\python.exe`
path as shown above, or add Python to PATH.
