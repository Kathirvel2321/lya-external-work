# 14 — GENIUS TRICKS: what the cleverest builders do, applied to LYA
> Written 2026-09-26. Status: PROPOSAL. Constraints: Intel i3-1315U, 7.71 GB RAM, no NPU,
> non-admin Windows 11 Home, ₹0 budget. Every trick below must survive THOSE constraints.

The owner's ask: *"Be like a mathematician and a magician — not magic, but the way geniuses
make something enormous out of almost nothing. What can we do, and how?"*

A magician's secret is not power. It is **misdirection and preparation**: the audience sees
one impossible-looking effect because everything behind it was arranged in advance. A
mathematician's secret is not harder computation — it is **changing the problem** so the hard
part becomes easy (think of how Gauss added 1–100 in seconds by pairing terms instead of
adding them).

That is exactly what LYA can do. Nothing below needs money. Each trick changes the problem
instead of brute-forcing it.

---

## Trick 1 — The magician's rule: never call the expensive thing ( Routing)
**Audience sees:** an instant answer. **Behind the curtain:** 90% of queries never touched a model.

- Your `bench_latency.py` already proved the punchline: the blind-index SQL on a warm DB is
  **sub-millisecond**, while vault/decryption-heavy open/close is ~180 ms. The "magic"
  is: keep the index hot, keep the vault cold, decrypt only the 5 rows that matched.
- **Fastest query = the one you never send.** A permanent cache keyed on
  (intent-hash + argument-hash) beats any model. Cache is free, RAM-sized, and expired by
  the L7 nightly job.
- Rule for the build: *every capability must declare `fast: true/false`*. `fast` ones are
  banned from touching network or model. That is how "24 of 29 skills < 100 ms" becomes
  structural, not aspiration.

## Trick 2 — The Gauss trick: change the representation (the blind index)
**Problem:** memory is encrypted, so search means decrypt-everything (O(n), the snail).
**Gauss move:** you cannot search ciphertext, but you *can* search a **blind index** of
HMAC'd tokens — the index holds zero readable content, so it can live unencrypted next to
the vault, and the search is an `IN (…)` over token hashes instead of a full decrypt scan.

- This is the mathematical identity: `search(encrypted) = search(HMAC(token), row_ids)`.
- 10,000 rows → 10,000 decryptions becomes → ~5 decryptions. That is the whole speed budget,
  already coded in `bench_latency.py`. The remaining fix is connection reuse (see Trick 6).
- Bonus trick within the trick: the index is **revocable** — wipe one key and the index is
  meaningless noise. Cheap to store, safe to lose.

## Trick 3 — The tailor trick: quantization (wear the model that fits your body)
Your laptop cannot run a big model — so **do not run it; borrow it, and when you must run
locally, run it 4-bit**.

- Weight quantization (16→8/4 bit) is precisely the trick that makes small machines viable:
  it cuts memory-bound data movement in half or more; FP16 Llama-3-70B → FP8 cut
  time-to-first-token under load from ~30,000 ms to ~4,800 ms on real hardware
  ([Red Hat quantization guide](https://developers.redhat.com/articles/2026/09/02/llm-quantization-guide-how-to-do-it--and-how-it-helps)).
- Honest hardware tiers: on ~8 GB RAM / integrated GPU, **3–4B models at 4-bit (GGUF Q4)**
  are the ceiling — good at *transformation* (summarize, rewrite, extract), shaky at factual
  recall ([Local LLMs in 2026](https://dev.to/ai_maya_063fc568e157562fd/local-llms-in-2026-what-actually-runs-well-on-a-laptop-now-hk1)).
- **LYA's application:** never ask a 4-bit local model for *facts* (that is what L3 stores are
  for — Trick 2). Ask it only for *shape*: rewriting, classifying intent, compressing an
  episode into candidate facts. Shape tasks at Q4 are excellent; truth tasks belong to
  provenance, not the model.
- 04-SPEED-BUDGET already notes small models confabulate more — this trick is how you live
  with that honestly: small model = grammarian, not witness.

## Trick 4 — The escape-artist trick: egress minimisation (never put the rabbit in the box)
The threat model (12) says compromise ≠ disclosure because the key isn't on the laptop.
The *mathematician's version* of that is: **minimise the surface that can leak at all.**

- Free models often train/retain on API data. Where possible choose providers with
  **Zero Data Retention** — OpenRouter, for instance, offers transparent retention agreements
  and ZDR options across providers
  ([Hacker News on router privacy](https://news.ycombinator.com/item?id=47909797)), and
  dedicated ZDR gateways exist ([abliteration.ai](https://abliteration.ai/)). Kagi's per-model
  privacy table is the template for what LYA should keep: a **retention policy per provider**
  ([Kagi LLMs & Privacy](https://help.kagi.com/kagi/ai/llms-privacy.html)).
- **LYA rule:** before any payload leaves the laptop it passes the egress shield — secrets,
  biometrics, personal identity are stripped or the request is refused. The
  *pre-emptive redaction* is the escape-artist move: the trick is performed on data that was
  never in the box.
- Practical: route *shape tasks* to any free model; route *anything touching T3/T2 facts* to
  local-only paths or ZDR providers. One routing flag per provider: `zdr: true/false/unknown`,
  default `unknown = treat as trains-on-data`.

## Trick 5 — The dancer's trick: precomputation (all the work happens before the show)
Nothing on stage is improvised. LYA's equivalents:

1. **L7 nightly consolidation** pre-computes everything slow: dedupe decisions, index
   rebuilds, Markdown snapshots. At 7 AM the index is warm, deduped, and the laptop only
   *reads* it.
2. **Pre-embedded intents.** Embedding your 29 skill matchers once (or just regex-matching
   them — cheaper still) means routing is a table lookup. No per-turn embedder call.
3. **Prefetched briefing.** The 6-AM "boss, here's the update" Jarwis moment is exactly a
   precomputed artifact: compiled at 5:55, delivered at 6:00, no model call on stage.
4. **Idempotency keys** (already in the plan): retries cannot duplicate work — the
   precomputation is safe to re-run, which is what makes nightly jobs fearless.

## Trick 6 — The friction accountant: measure what actually costs (connect(), not SQL)
`bench_latency.py` found the real villain is not search — it is **open/close + decrypt on
every connection (~180 ms)** while the warm query is ~0.00x ms. The magician's lesson: the
audience (you) was watching the wrong hand.

- Fix: **one long-lived read connection** per session; re-encrypt-on-write only; measure
  everything with `perf_counter` pairs like the bench does.
- Adopt the folder's own rule: **measure, don't inspect.** Every new trick in this file gets
  a number pasted next to it or it doesn't count.

## Trick 7 — The ensemble trick: small models voting (the council, on the cheap)
Geniuses don't get more right by being bigger; they get right by **cross-checking**. LYA's
verification layer is already this — extend it cheaply:

- Two free models, different families (e.g. a Groq-hosted model + an OpenRouter free model)
  answer only *verifiable* sub-questions; agreement → SAVED-adjacent confidence;
  disagreement → abstain. Cost: two free-tier calls. Accuracy: abstention is the win, not the
  answer.
- This is the ensemble/variance-reduction identity: the average of two biased estimators
  with uncorrelated errors is better than either. With free tiers, "unverifiable" defaults to
  REFUSAL — the honest register your docs already defined.

## Trick 8 — The illusionist's contract: it must *look* like it understands the situation
The Instagram-Jarvis moments you loved (the 6-AM call, "shall I tell you now or in 5
minutes?") are not intelligence tricks — they are **state + templates**:

- **State:** "you were asleep" is just `last_seen + idle_duration + time_of_day` from L2.
- **Templates with slots:** "You told me yesterday to call at 6" is a template whose slot is
  filled from L3 (the remembered instruction). The *magic feel* comes from provenance: the
  system quotes a real remembered fact with a timestamp.
- This is already specced (07: the ten-step loop; lya-presence: briefing + turn-taking). The
  trick to copy from the magicians: **lead with the evidence** (show the stored fact, the
  message counts) — grounded numbers are what make it feel mind-blowing instead of chatbot-y.
- iOS restriction reality check: on iPhone you cannot get true background agency; push via
  ntfy/apns-style notifications is the reachable version. Your docs are right; the reels gloss
  over it.

## Trick 9 — The investor's trick: compounding small wins (the ₹0 stack)
The mathematician sees exponentials everywhere. LYA's compounding assets, all free:

| Asset | Cost | Compounds because |
|---|---|---|
| Blind index | 0 | every fact added makes search *faster relative to scan* |
| Nightly L7 | 0 (VM/idle) | each night's compression makes every morning faster |
| Skill library in Git | 0 | every skill is greppable, testable, reusable forever |
| Eval sets (`golden.jsonl`, `must_not`) | 0 | every red test ever added protects all future answers |
| Provider retention table | 0 | every new provider is classified once, trusted forever after |

Nothing in this table decays. That is what "build once, benefit forever" looks like on ₹0.

## What NOT to do (the anti-tricks)
1. **Don't chase bigger local models.** 7.71 GB says no; the tier data says a Q4 3–4B model
   is the honest ceiling.
2. **Don't chase "unhackable" or "perfect free results".** Both are marketing tricks aimed at
   *you*. Your own docs already refuse them — keep refusing.
3. **Don't add another platform while three stores are unfinished.** More stage props, same
   show.
4. **Don't trust any number without a paste.** Including every number in this file.

## The one-line summary
> A magician prepares everything before the show and never calls the expensive thing on
> stage. A mathematician changes the problem instead of brute-forcing it.
> LYA = prepare nightly (L7), route cheaply (registry → cache → index → model-last),
> search ciphertexts via blind index, run small models at 4-bit for *shape* only,
> leak nothing by *redacting before egress*, and label every answer with where it came from.

---

### Verification status of this file
- ✅ `bench_latency.py` read in full; its findings (warm-query ms vs ~180 ms open/close,
  FTS5 check, remember() scaling) are quoted from the code itself.
- ✅ Quantization claims sourced: [Red Hat guide](https://developers.redhat.com/articles/2026/09/02/llm-quantization-guide-how-to-do-it--and-how-it-helps),
  [local-LLM tiers](https://dev.to/ai_maya_063fc568e157562fd/local-llms-in-2026-what-actually-runs-well-on-a-laptop-now-hk1).
- ✅ Privacy/ZDR claims sourced: [Kagi table](https://help.kagi.com/kagi/ai/llms-privacy.html),
  [OpenRouter ZDR discussion](https://news.ycombinator.com/item?id=47909797).
- ⚠️ Everything else is architecture inference from the existing lya-brain docs — labelled as
  design, not measurement.
- ⚠️ One new number this file *demands*: re-run `bench_latency.py` with a persistent
  connection to confirm the open/close cost fix. Until pasted, Trick 6 is unverified.
