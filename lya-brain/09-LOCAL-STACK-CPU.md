# 09 — LOCAL STACK ON A CPU-ONLY LAPTOP

> **Status: PROPOSAL, 2026-09-24.** Owner decision on 2026-09-24: the real device is an
> **ordinary Windows laptop — no NPU, CPU-only** — so the local stack is planned for CPU and the
> model is kept **off the hot path**.
>
> All hardware numbers below were **measured on this machine** on 2026-09-24.

---

## 1. Measured hardware (the constraint that shapes everything)

| Fact | Value | How measured |
|---|---|---|
| Machine | MSI notebook | `Win32_ComputerSystem` |
| CPU | **Intel Core i3-1315U** — 6 cores (2P + 4E), 8 threads | `Win32_Processor` |
| RAM | **7.71 GB usable** | `TotalPhysicalMemory` |
| GPU | Intel UHD Graphics (shared, no discrete) | `Win32_VideoController` |
| Disk | 242.8 GB used / **210.6 GB free** | `Get-PSDrive C` |
| Python | 3.11.9 | `python --version` |

**Consequences — state them plainly:**
1. **No local LLM on the hot path.** With ~7.7 GB total and Windows + Python + orb resident,
   a resident model competes for memory with everything else. The fast path must be **rules +
   SQLite + a static embedder**, which costs tens of MB, not gigabytes.
2. **A local LLM is a degradation mode, not a feature.** It exists so LYA is not mute when the
   network is down.
3. **Nothing heavy loads at startup.** Face/anti-spoof stacks (~100s of MB with ONNX models)
   load only when identity is actually needed and unload after.

---

## 2. The local tiers (what actually runs on this laptop)

| Tier | Job | Candidate | RAM | Expected on this CPU |
|---|---|---|---|---|
| **T0** | Routing, commands, policy | the **registry** — pure Python rules | ~0 | **< 5 ms** |
| **T1** | Recall (text) | **SQLite FTS5** (BM25) — built into Python, zero deps | ~0 | **< 20 ms** |
| **T2** | Semantic routing + semantic cache | **static embedding model** (Model2Vec-class, e.g. `potion-base-8M` / `potion-retrieval-32M`) — no transformer forward pass | ~30–60 MB | **sub-ms to few ms per query** |
| **T3** | Recall (vectors) | small ONNX embedder (`bge-small-en-v1.5` / `all-MiniLM-L6-v2`, int8) — **then** numpy brute force | ~60–100 MB | ~10–40 ms/query; matrix multiply is ms at <50k chunks |
| **T4** | Local STT fallback | **Vosk** small model (already wired via `LYA_VOSK_MODEL`) | ~50–80 MB | real-time-ish on 6 cores |
| **T5** | TTS | **pyttsx3** (SAPI) — already wired | ~0 | instant, offline |
| **T6** | Offline chat (last resort) | Ollama + a **≤1B Q4** model | **~0.8–1.5 GB** | ~8–20 tok/s (0.6B), ~5–12 tok/s (1B) |
| **T7** | Vision / face | InsightFace + anti-spoof, **lazy-loaded only** | 300 MB+ | ~100–300 ms per detection |

**Banned on this machine:** any 3B+ model, local Whisper (use Groq Whisper free — 2,000 RPD),
resident vector index of the whole corpus, and anything that loads at startup "because it might
be needed".

## 3. Model-loading policy — "off the hot path" made concrete

1. **Never load a model at startup.** No model is imported or warmed during boot.
2. **Lazy load on first real need**, with a free-RAM check before loading; if RAM is short, skip
   the local model and go straight to honest degradation.
3. **Unload after idle** (e.g. `keep_alive=5m` for Ollama, or an explicit unload call).
4. **Prewarm the cheap thing only:** the TLS connection to Groq — not a local model.
5. **One heavy resident at a time.** Local LLM **or** vision stack, never both.

**Observed reality (2026-09-24) — the offline guarantee does not exist yet:**
`ollama` is on PATH and `%USERPROFILE%\.ollama` exists, but `ollama list` returns
`Error: could not locate ollama app`. So `03-MODEL-STRATEGY.md` M-5 ("keep Ollama as offline
guarantee") and the `README` claim of an offline path are **currently false on this machine**.
Either repair the Ollama install or stop claiming an offline tier.

**Relevant code, verified by reading `brain/mind.py`:**

| Line | Fact | Consequence |
|---|---|---|
| 113–119 | provider order: Groq `openai/gpt-oss-20b` → OpenAI `gpt-4o-mini` → Ollama `qwen2.5:0.5b` (`LYA_LOCAL_MODEL`) | local model is ternary, good |
| 119 | `qwen2.5:0.5b` is a 2024 model | re-evaluate at install time for a current ≤1B Q4 (verify availability then — do not assume) |
| 33–61 | `SYSTEM` interpolates `{name}` **and** the whole `{memory}` block **and** mood | **breaks the cacheable prefix on every turn** → see §3.1 |
| 107 | `_memory_block()` → `memory.recall(limit=15)` → full decrypt-scan | O(n) on each grounded reply |
| 129 | one prose string for *every* provider failure | provider hiccup == no brain configured |
| 163–164 | `reply()`'s `except` is **unreachable** (`_chat()` never raises) | dead error handling |

### 3.1 The prompt-cache lever (a CPU-and-quota win, free)

Groq documents: **"Cached tokens do not count towards your rate limits."** But a cache hit
requires a **byte-stable prefix**. Today the system prompt is rebuilt with name + mood + memory
each turn, so nothing is cacheable — every turn pays full tokens against the 200K/day budget.

**Fix (spec):** split the prompt into
`[FIXED PREFIX: persona + rules + tool catalog] + [VARIABLE: facts + mood + user turn]`.
The fixed prefix must be byte-identical across turns. This is a latency win **and** a quota win
on a free tier, which is exactly the "cheetah, not turtle" lever this hardware needs.

---

## 4. Verification — `bench_latency.py` (spec; does not exist yet)

Run **on this machine** with synthetic data, then again on the real device; the delta is the
hardware answer.

| Measure | Method | Pass condition |
|---|---|---|
| `recall()` at 100 / 1,000 / 10,000 facts | seed then time 100 queries | flat, not climbing |
| `remember()` round-trip | 100 writes | < 50 ms each |
| FTS5 search across the Markdown corpus | build index, query | < 50 ms |
| static embedder per query | 1,000 queries | sub-ms to few ms |
| ONNX embedder per query | 100 queries | < 40 ms |
| cold start → first rule-based command | stopwatch, 10 runs | < 2 s |
| idle CPU 60 s (orb visible / sleeping) | process sampler | < 1% / ~0% |
| RSS of the resident process | sampler | < 400 MB without vision or local LLM |
| local LLM tokens/sec, if installed | generate 200 tokens | recorded, not asserted |

Report the actual numbers. Per the project's own §0.1 rule: **never write ✅ without naming the
command and pasting the output.**

---

## 5. Change log

### 2026-09-24 — CPU-only local stack specified
**Goal:** pin the local stack after the owner confirmed the real device is CPU-only with no NPU.
**Changed:** this file created — measured hardware, eight local tiers (T0–T7) with RAM and
latency expectations, an explicit model-loading policy, the prompt-cache fix, and the benchmark
spec.
**Verified by:** local measurement on 2026-09-24 —
`Win32_Processor` / `Win32_ComputerSystem` / `Get-PSDrive C` / `Win32_VideoController`;
`python --version` → 3.11.9; `ollama list` → `Error: could not locate ollama app`;
`python -B test_foundations.py` → 13/14 (`numpy` missing).
**Left undone / follow-up:**
- Ollama install repair (or remove the offline claim).
- `bench_latency.py` does not exist — write it before any speed claim.
- Candidate model names for T6 must be **re-verified at install time** on the real device.
- `numpy` is still missing here, so `test_face_template_decodes_saved_float32` fails (B-5).
**Notes:** measured RAM is **7.71 GB**, not 8 GB — the iGPU reserves some. Every RAM figure in
this file must be re-measured on the real device; if it has *less* memory than this laptop,
T6 moves from "last resort" to "not installed".

