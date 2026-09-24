# 03 — MODEL STRATEGY: which brain thinks, when, for free

> Your question: *"Can we use models like Laya, JEV, or UltraJEV for free and still get
> perfect results instead of incorrect ones?"*

---

## First: the honest answer about those three names

I checked. Here is what actually exists:

| Name | What it actually is | Free? | Fit for LYA |
|---|---|---|---|
| **JEV** | ✅ **Real.** TypeSafe's "System One" model — a *decision* model, not a chatbot. You send it a state (JSON/text) + typed questions (choice / score / yes-no) and it returns **probabilities with calibrated confidence**. Text-only. ([Jev AI](https://jev-ai.pro/), [background](https://www.heise.de/en/news/AI-model-Jev-to-make-machines-decide-faster-11457071.html)) | ⚠️ Free playground after sign-in; **API is paid** (credits from $10, no subscription). 5 free runs. | ⭐ **Excellent fit — but not as the chat brain.** |
| **"Laya"** | ❌ No such model found. I could not locate any model by this name — free or paid. | — | Likely a mishearing of *LYA* (your own project) or of **Llama**. |
| **"UltraJEV"** | ❌ No such model found. Not in TypeSafe's published line. | — | Probably a misremembering. The real current model is **Jev 1.13.0** (`jev-latest`). |

**I would rather tell you this than invent a capability.** Two of the three names do not
correspond to any model I can find. If you have a link or a screenshot for either, send it
and I will re-check — it may be very new or very niche, in which case my search simply
missed it.

---

## Now the genuinely valuable part: JEV is a great idea for LYA

This is worth dwelling on, because JEV solves a problem you have right now.

**JEV is not an LLM. It is a decision layer.** Instead of "write me a paragraph", you ask
"given this state, classify / score / yes-no this" — and it returns a *probability* and a
*confidence*, which a program can branch on directly with no prose parsing
([guide](https://a2aprotocol.ai/insights/jev-ai-model-2026-guide)).

**Why that matters for LYA specifically:** your project's entire safety model rests on
`security/policy.py` — a **default-deny** permission gate. That gate currently makes
*pure rule-based* decisions: known action → allowed tier; unknown action → deny.

A model like JEV could sit *beside* that gate and answer questions like:
- "Is this user request actually asking for a private action, phrased unusually?" → yes/no + confidence
- "Does this message contain a plausible duress signal?" → score
- "Which of these 22 skills best matches this request?" → choice + confidence
- "Is this remembered fact a duplicate of an existing one?" → yes/no + confidence

**And critically:** if confidence is low, the gate **still denies**. The model *advises*;
`policy.py` *decides*. That is exactly the architecture your project already committed to
(D-2: model output is never authority).

**But** — and this is the honest caveat — you do **not need JEV to start.** Your
`knowledge.py` classifier is currently plain regex + keyword rules, and it already works.
JEV is a *later optimisation* for when the rule lists get unwieldy. Its API is also paid
(though ~$0.042/M input tokens is close to free for personal volume).

**Recommendation: put JEV in `LATER`. Do not block on it.** Log it as a candidate for the
"intent routing" problem, and revisit when the rule table has grown painful.

---

## The free brain that actually works today

Forget exotic models. These are measured, currently-free, OpenAI-compatible endpoints:

| Provider | Free allowance (verified 2026-09-23) | Speed | Best for |
|---|---|---|---|
| **Groq** ⭐ | ~**1,000 req/day**, 8K TPM on free models; Whisper 2,000 req/day | **~320–500 tok/s** — fastest available | **Primary chat + voice.** Already wired in `brain/mind.py` |
| **Cerebras** | ~1M tokens/day | Very high throughput | Batch/summarisation |
| **Google AI Studio** | 20–1,500 req/day, **1M-token context** | Moderate | Long documents, images |
| **NVIDIA NIM** | ~1,000 req/day | Moderate | Fallback |
| **OpenRouter** | 20 RPM, 50 req/day free models | Varies | Model shopping, `openrouter/free` router |
| **Ollama (local)** | ∞ — your own CPU | Slow on CPU, instant if cached small model | **Offline guarantee** |

Groq's free-tier table ([GroqDocs rate limits](https://console.groq.com/docs/rate-limits))
lists free models including `openai/gpt-oss-20b`, `openai/gpt-oss-120b` and
`qwen/qwen3.8-27b` — each at 1,000 requests/day. **Whisper-large-v3 gets 2,000
requests/day free**, which is your speech-to-text budget.

> Note: Groq's limits are per-model and change. The 14,400 req/day figure circulating in
> older blog posts is **outdated** — the official docs now show ~1,000/day for the chat
> models. Always read [the live table](https://console.groq.com/docs/rate-limits).

Your `brain/mind.py` already chains **Groq → OpenAI → Ollama**. That chain is correct.
The problems are *what it does with the answer*, not which provider it calls.

---

## The routing design — a cheetah brain, not one big slow brain

**One model for everything is the snail.** Here is the tiered design:

```
                    ┌─────────────────────────────────────────┐
   user says ──────►│  TIER 0 — NO MODEL  (0 ms, always works) │
   "hey lya        │  Greetings, "open calculator", volume,   │
    open notepad"  │  reminders, folder browse, wake word.    │
                    │  Pure rules. Never calls an LLM.         │
                    └──────────────────┬──────────────────────┘
                                       │ needs language understanding
                    ┌──────────────────▼──────────────────────┐
   "what should    │  TIER 1 — FAST BRAIN (~0.3–1.5 s)        │
    I do about     │  Groq gpt-oss-20b / qwen3.8-27b.         │
    my project?"   │  Small, fast, free. Default for 90%.     │
                    └──────────────────┬──────────────────────┘
                                       │ genuinely hard / needs depth
                    ┌──────────────────▼──────────────────────┐
   "compare       │  TIER 2 — DEEP BRAIN (~2–8 s, async)     │
    these 3        │  Larger model or the existing council    │
    options"       │  (brain/council.py). Never blocks UI.    │
                    └──────────────────┬──────────────────────┘
                                       │ no network
                    ┌──────────────────▼──────────────────────┐
   offline        │  TIER 3 — LOCAL FALLBACK                 │
                    │  Ollama small model, or a cached answer.  │
                    └─────────────────────────────────────────┘
```

**The key insight:** most of LYA's work should never touch a model at all. Opening an app,
reading a memory, checking a reminder, browsing a folder — all of these are rule-driven
and should return in **milliseconds**. Only genuine language understanding pays the LLM tax.

---

## "Perfect results, not incorrect ones" — the verification layer

You asked for perfect. No free model is perfect. Here is what you *can* build, and it is
what actually matters:

**A three-stage check that turns "confident wrong" into "visibly uncertain":**

1. **Ground it — does the answer depend on a fact?**
   If yes, the model must be given the fact explicitly from `T2` (memory), never allowed
   to recall it from training. ("What is my brother's name?" → inject the stored fact, or
   say "I don't have that saved.")

2. **Check it — is the answer verifiable?**
   - Contains a date/number/time → validate the format before speaking it
   - Contains a file path or command → verify the target exists before acting
   - Contains a claimed capability → check against the real feature registry

3. **Label it — how sure are we?**
   LYA states uncertainty out loud. Three levels:
   - *"Here's what's saved: …"* (from a store — reliable)
   - *"I believe …"* (model-generated — plausible)
   - *"I'm not sure — I don't have that saved."* (no grounding — honest refusal)

**Stage 3 is the whole point.** A free model that says "I'm not sure" is *safer and more
useful* than a paid model that confidently invents your mother's birthday. This is also
exactly what your `LYA_VISION.md` already asks for — "provide evidence, alternatives,
tradeoffs and disagreement … instead of automatically agreeing with the owner."

---

## Model assignments — the decision table

| Task | Model tier | Provider | Why |
|---|---|---|---|
| Wake word detection | none | local (Vosk) | Zero latency, zero cost |
| Command routing (open/close/volume) | none | rules | Deterministic, instant |
| Ordinary conversation | Tier 1 | **Groq** `gpt-oss-20b` | Fastest free option |
| Memory-augmented answer | Tier 1 + T2 grounding | Groq | Must inject facts, not recall them |
| Long document analysis | Tier 2 | Gemini (1M context) | Free, huge window |
| Hard comparison / advice | Tier 2 | council (existing) | Advisory only |
| Speech-to-text | — | **Groq Whisper** | 2,000 req/day free |
| Text-to-speech | none | local `pyttsx3` | Offline, zero cost |
| Offline chat | Tier 3 | Ollama `qwen2.5:0.5b` | Already wired |
| Intent classification (later) | — | **JEV** (paid, cheap) | Deferred — see above |

---

## Open decisions

| # | Decision | Proposal |
|---|---|---|
| M-1 | Primary free brain | Groq (`gpt-oss-20b` fast path) — already half-wired |
| M-2 | Add Cerebras/Gemini as fallbacks? | Yes, as *fallback only* — avoid gateway sprawl (vision doc §6) |
| M-3 | Adopt JEV? | **Later.** Advisory intent-routing only, never authority |
| M-4 | Verification layer | **Build it — highest value item in this folder** |
| M-5 | Local model | Keep Ollama as offline guarantee; small quantised model |
| M-6 | Model for the *council* | Fix the stale IDs first (`LYAPROJECTBRAIN.md` gotcha 19) |

**One thing I want to flag:** `brain/mind.py` currently falls back to a hardcoded
"my brain is offline" string on any exception. That means a *provider hiccup* looks
identical to *no brain configured*. For a system that promises honesty about its own
state, those two need to read differently.