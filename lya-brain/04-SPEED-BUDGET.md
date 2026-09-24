# 04 — SPEED BUDGET: making it a cheetah

> "Like a cheetah, not a snail." Speed is not just a nice property here — it is what makes
> LYA feel like an assistant instead of a form submission.

---

## The targets

These are the numbers to hold LYA to. They are **budgets**, not aspirations — each one has
a defined owner and a way to measure it.

| Interaction | Target | Ceiling | Owner |
|---|---|---|---|
| Wake word → orb appears | < 200 ms | 500 ms | `ui/orb.py` |
| Simple command → done ("open notepad") | **< 100 ms** | 300 ms | `main.py` routing |
| Memory read ("what's my wifi password") | **< 20 ms** | 100 ms | `brain/memory.py` |
| Memory write ("remember that…") | **< 50 ms** | 200 ms | `brain/memory.py` |
| Reminder list | < 20 ms | 100 ms | `skills/reminder.py` |
| Chat, Tier 1 (Groq) | 0.3–1.5 s | 3 s | `brain/mind.py` |
| Chat, Tier 3 (local Ollama) | 2–10 s | 30 s | `brain/mind.py` |
| Idle CPU (orb visible) | **< 1%** | 3% | `ui/orb.py` |
| Idle CPU (sleeping) | ~0% | 0.5% | `ui/orb.py` |
| Cold start → first answer | < 2 s | 5 s | `main.py` |

---

## The cheetah principle: separate the fast path from the slow path

**Almost everything LYA does should never touch a network or a model.** The single biggest
performance win available is architectural, and it is free:

```
FAST PATH (target < 100 ms, no network, no model):
    open/close app · volume · reminders · folder browse · memory read/write
    · theme change · "what's on my calendar" · sleep/wake

SLOW PATH (network, model, or both — must never block the UI):
    open-ended conversation · research · long analysis · council
```

The orb must stay responsive while a slow path runs. Your project already does this
correctly — one `queue.Queue(maxsize=8)` and a single worker, with UI marshalling via
`_post()` (`ui/orb.py`). **Keep that design. Do not let slow work leak onto the main thread.**

---

## The real bottleneck, found in your own code

This is the most valuable finding in this folder, so I want to be precise about it.

**`brain/memory.py` line 34–50 — `recall()` does this:**

```python
def recall(key=None, kind=None, limit=10):
    # ... SELECT * ...
    for kind_, k_enc, v_enc, imp, hits, created in c.execute(q, args):
        k, v = vault.decrypt_text(k_enc), vault.decrypt_text(v_enc)   # ← decrypt EVERY row
        if key and key.lower() not in k.lower() and key.lower() not in v.lower():
            continue
        rows.append(...)
```

**Every query decrypts every row in the database** — even rows it will discard. It must,
because the data is encrypted, so SQL `WHERE` cannot match on it.

Your own `LYA_RESEARCH.md` §7 flags this: *"Memory `recall` — **O(n) decrypt-scan**"*.

**Why this will become the snail:** Fernet decryption is deliberate, slow AES + HMAC work.
At 100 memories it is invisible. At 10,000 memories it is seconds *per query*, and it gets
worse forever, on the hot path of every single conversation.

**The fix — a searchable index that is not itself secret:**

```
Add a side table:  memory_index(id, token_hash, id_ref)

At write time:
    for each word in the plaintext fact:
        store  hmac_sha256(word.lower(), device_key)   ← deterministic, searchable
        linked to the row id

At query time:
    hash the query words the same way
    → SQL WHERE token_hash IN (...)   ← no decryption at all
    → decrypt ONLY the matched rows (usually 1–5)
```

This is a **blind index**. The database still contains no readable plaintext — the hashes
are keyed by a device-local secret, so they cannot be brute-forced without the key. Query
cost drops from *"decrypt everything"* to *"decrypt the few matches"*.

**Expected result:** memory queries stay **under 20 ms whether you have 100 memories or
100,000.** No new platform. No subscription. One table and two functions.

> **Scope note (v2).** This is a **~2 hour performance fix**, not an infrastructure project.
> It does not need a migration framework, a schema registry, or a rollback plan — it is one
> extra table plus a rebuild-on-open. Treat it as a speed change, and keep it small.
>
> Trade-off to be honest about: a blind index leaks **word frequency** — an attacker with
> the raw file learns that some word appears 400 times, even without knowing the word.
> For a personal assistant that is an acceptable trade. It must be a **recorded decision**,
> not a silent one.

---

## Second bottleneck: `brain/knowledge.py` rewrites the whole DB per message

`knowledge.py` `_conn()` / `_close()` decrypts the **entire database file** into a temp
file, works on it, then re-encrypts and rewrites the **whole file** — on *every* ingest.

Two problems:
1. It is O(total database size) per message, not O(1).
2. It creates a **plaintext temp file on disk** (`DB + ".working"`) during the operation.

`security/database.py` already solves this properly — in-memory SQLite, atomic
`os.replace`, no plaintext temp file. **`knowledge.py` should use it instead of its
hand-rolled `_conn`/`_close`.** This is both a speed fix and a security fix.

(Also note `LYAPROJECTBRAIN.md` §2 records `knowledge.py` as ⚙️ **NOT WIRED IN**. So this
is a fix-before-use item, not a live outage.)

---

## Third: the network calls you did not ask for

`brain/sync.py` `pull_future_cloud()` is called by the reminder watcher every 30 seconds.
Your audit finding **S-10** flags it: an outbound network request on a fixed cadence even
when sync was never configured.

For a "cheetah": **no network traffic on a timer that the user did not ask for.** Make
sync **explicitly enabled** and **event-driven** (on write, or on demand), not polled.

---

## Measuring it — a benchmark you can run

Speed claims need evidence, or they are marketing. Add a benchmark that reports real
numbers, following the honesty rule already in `LYAPROJECTBRAIN.md` §0.1 (*"never write ✅
without naming the command you ran"*):

```
bench_latency.py    (proposed — does not exist yet)

  reports, on THIS machine:
    - memory.recall()  with 100 / 1,000 / 10,000 seeded facts
    - memory.remember() round-trip
    - cold start to first rule-based command
    - idle CPU over 60 s (orb visible + sleeping)
    - wake-word detection latency (voice mode only)
```

**Run it before and after each change.** The project's own rule is *"never claim something
works — run it, paste the output."* Apply that to speed too.

---

## Budget summary — what to fix, ranked by impact per hour of work

| Rank | Fix | Effort | Speed gain | Risk |
|---|---|---|---|---|
| **1** | Blind index in `brain/memory.py` | ~2 h | **O(n) → O(1)** on the hot path | Low, needs a decision on word-frequency leak |
| **2** | Make sync opt-in + event-driven | ~1 h | Removes unnecessary network; restores offline purity | Low |
| **3** | Move `knowledge.py` onto `security/database.py` | ~1 h | Removes full-DB rewrite per message + plaintext temp file | Low |
| **4** | Tier-0 rule path for common commands | ~2 h | Commands return in ms instead of seconds | Low |
| **5** | Cache the system prompt + memory block | ~1 h | Saves a memory scan per chat turn | Low |
| **6** | Pre-warm Groq connection on wake | ~1 h | Shaves TLS handshake from first reply | Low |

**Fix #1 alone changes LYA from "gets slower every day" to "stays fast forever."** If you
only do one thing in this document, do that one.

**Fixes #1–#3 are the only ones that matter right now** (~4 h total, all local, no new
accounts). #4–#6 are polish — do them when a real interaction feels slow, not pre-emptively.