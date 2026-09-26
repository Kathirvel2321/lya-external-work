# 02 — TURN-TAKING: how LYA learns to pause, wait, and not talk over you

> The skill that makes the Jarvis reel feel alive is not intelligence — it is **timing**.
> Jarvis asks *"shall I tell you now or after 5 minutes?"* because he **modelled your state
> and waited for a signal**. This doc specs that skill, master-style, in the lightest way
> possible: a state machine, not a neural net.

---

## 1. The master principle — how the best systems do it

Voice assistants that feel human (Alexa's haptic hints, Duplex's pauses, good call-centre
bots) all share one insight:

**Conversation is not a chat stream. It is a shared protocol with states.**

A human speaker constantly emits and reads tiny signals:
- silence after a question → *I'm waiting for you*
- "umm…", a breath, a half-started word → *I'm about to speak — hold*
- a long hesitation → *offer an out* ("shall I tell later?")

Duplex (Google) literally inserts *"umm"* and lengthens vowels so the *other* party can
take their turn. The lesson for LYA: **the pause is a feature you design, not a latency you hide.**

---

## 2. The state machine — the whole skill in one table

LYA's conversational channel is a small FSM (~200 lines of Python, no dependencies):

```
            ┌────────── SPEAKING ──────────┐
            │  (says briefing / answer)    │
            ▼                              │
  LISTENING ──── owner starts ────▶ BARGE-IN
      │  (mic open, patient)          │ owner overlaps LYA's speech
      │                               ▼
      │                          YIELDING  (stop, save partial, listen)
      │
      ├── asks a question ──▶ WAITING_FOR_REPLY
      │                          │
      │            ┌─────────────┼──────────────┐
      │       reply < 3 s    3–30 s, silence   > 30 s silence
      │            ▼             ▼              ▼
      │        RESUME       GENTLE_NUDGE   DEFER
      │      (continue)   "still there?    (write deferred
      │                     now or later?"  to L2, retry later)
      ▼
  IDLE (long silence) → proactive triggers may fire (briefing, notify)
```

### The states, precisely

| State | Rule | Exit condition |
|---|---|---|
| **LISTENING** | mic open; emit nothing | any owner audio/keystroke |
| **SPEAKING** | deliver; display captions if muted | done → LISTENING |
| **BARGE-IN** | owner overlaps → **stop within 200 ms**, keep the unsaid part in L1 | owner stops → LISTENING |
| **WAITING_FOR_REPLY** | after a question, *watch*, don't speak | see the 3-way branch below |
| **YIELDING** | never interrupts back; resumes only when owner yields | — |
| **DEFER** | stores the deferral **as a fact**: "deferred at 06:02, retry 06:07" | retry fires |

### The WAITING_FOR_REPLY branch — the reel's exact behaviour

```
ask "shall I tell you now or after 5 minutes?"
  ├─ reply in < 3 s          → treat as answer, act
  ├─ silence 3–30 s          → one gentle nudge, max once
  └─ silence > 30 s          → defer: write "deferred" to L2,
                               retry in 5 min — silently
```

**Why the 3 s threshold:** human turn-gaps are typically ~200 ms, but *waking up* gaps are
seconds long. Two thresholds (instant vs. sleepy) is what makes the wake-up ask feel
empathetic instead of robotic.

---

## 3. How to *teach* LYA this — three layers, cheapest first

### Layer 1 — Rules (do this first, it covers ~80%)

Deterministic thresholds, zero model calls, < 100 ms:

- after LYA asks a question → WAITING state opens, timer starts
- any audio/typing → answer path
- silence thresholds per the table
- **never nudge more than once** — a second nudge is how bots annoy humans
- **never speak during owner speech** — the barge-in yield is absolute (D-2 spirit)

### Layer 2 — Learned calibration (L5 self-model)

Store what worked, per context — this is the "getting smarter over years" part:

```
L5 row: { context: "wake-up 06:00", 
          what_worked: "wait 5 min then screen push", 
          nudge_accepted: 0.2, defer_accepted: 0.8 }
```

After each interaction LYA records: did the nudge land, was the deferral honoured, did the
owner say "why did you wait so long?". Over months, LYA's *default wait time per context*
becomes personalised — that is the reel's "he understands me", built from statistics, not
sentience.

### Layer 3 — Model phrasing (the only place a model appears)

The FSM decides **when**; the model only shapes **how it sounds**. Give it a tiny prompt:

> "You just noticed the owner did not answer for 20 s after you asked whether to speak now.
> Produce ONE short line offering to wait. Warm, ≤ 12 words. Do not repeat the question."

This keeps even the phrasing cheap and fast, and abstention still applies — no phrase
available from rules + model? Stay silent. **Silence is a valid turn.**

---

## 4. The lightweight stack (summary)

| Component | Tech | Size |
|---|---|---|
| FSM | Python stdlib (asyncio timers) | ~200 lines |
| Signal detection | last-input timestamp / VAD level (local) | stdlib / tiny |
| Nudge phrasing | small model call, 1 line out, rules-first | existing providers |
| Memory of outcomes | L5 rows | existing store |
| Popup/push | ntfy + HTML overlay | see `01` |

**No new platform. No cloud. No GPU.** The entire "human-feeling timing" skill is a
state machine + a statistics table.

---

## 5. Red tests (fail-closed)

```
RT-01  owner speaks over LYA          → LYA stops ≤ 200 ms, never talks back over
RT-02  silence 40 s after a question  → exactly one deferral written, zero nudges after
RT-03  "later" said at 06:00          → retry fires at 06:05 ± 5 s, not before
RT-04  briefing while fullscreen app  → popup suppressed, queued
RT-05  deferral never written to L2   → retry never fires (provenance required to act)
RT-06  mic failure                    → LISTENING impossible → falls back to push-only,
                                        never pretends it heard something
```

---

## 6. What this skill is NOT

- **Not emotion detection.** LYA models *signals and outcomes*, not feelings.
- **Not fake personality.** The warmth comes from patience (thresholds) and memory
  (deferrals honoured), not from a persona prompt.
- **Not always-on listening.** Mic opens on wake-word or scheduled wake; no continuous
  recording — the same privacy posture as the rest of the security model.
```
