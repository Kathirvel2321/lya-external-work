# 07 — THE LYA NEURAL SCHEMA (how she thinks)

> **Status: PROPOSAL, 2026-09-24. Nothing here is wired into `main.py`.**
> This file answers the owner's question: *"how do we decide the neural schema that acts like a
> human brain and gives correct output for the query — how does she think?"*
>
> This is a **spec**. The real implementation happens on the owner's other device.
> Every claim about current code was verified on 2026-09-24 by reading it (see §10).

---

## 1. The one rule everything follows

**Correctness is a property of the loop, not of the model.**

A generic LLM answer appears because the system has *no other place to get an answer from*.
LYA gets correct answers by making the model the **last** resort, and by permitting it to
abstain. Concretely: **before any model is called, four cheaper things must have failed** —
registry match, cache hit, grounded recall, and rule evaluation.

---

## 2. The eight layers

| # | Layer (human analogue) | Holds | Home | Lifetime | Budget |
|---|---|---|---|---|---|
| **L0** | Senses | mic frames, camera, screen, typed text | RAM ring buffer | seconds | < 200 ms wake |
| **L1** | **Working memory** | assembled state for this turn: pinned facts + recalled items + plan | RAM, cacheable prefix | one turn | < 50 ms assemble |
| **L2** | **Episodic** | what happened, in order — turns, actions, outcomes | encrypted local | discard by default; `pin` keeps | < 5 ms write |
| **L3** | **Semantic** | facts, entities + **typed edges with validity intervals**, preferences, profile | encrypted local SQLite | permanent | **< 20 ms read** |
| **L4** | **Procedural** | skills/tools: matcher, tier, timeout, idempotency, test | `skills/` + **one registry** | versioned | **< 100 ms** |
| **L5** | **Self-model** | how the owner likes answers, what failed before, calibration records | encrypted local | permanent | < 10 ms |
| **L6** | **Verification** | ground → check → label; abstention | rules first, model last | per answer | < 50 ms |
| **L7** | **Consolidation** ("sleep") | episodes → facts, dedupe, decay, reindex, export | **always-on box**, never the laptop | nightly | offline |

**Design constraint (measured 2026-09-24):** the laptop has **7.71 GB RAM usable**, an
**Intel i3-1315U (6C/8T)**, no NPU, Intel UHD graphics. Therefore **L1–L6 must fit in well under
400 MB** of Python-process RAM, and L7 must not run here. See `09-LOCAL-STACK-CPU.md`.

---

## 3. The thinking loop

```
1  PERCEIVE    normalize input (local; ms)
2  ROUTE       registry match ──► else static-embedding classifier ──► else model
               └── the majority of queries must exit here (L4, < 100 ms, zero model call)
3  RECALL      FTS5 BM25  +  vectors  +  graph expansion  →  5–20 items
               └── EVERY item carries provenance (store, row, timestamp)
4  CHECK       is the answer already fully determined by what we recalled?
               yes ──► answer now, no model.   no ──► continue
5  PLAN        multi-step only: steps + tool + tier + timeout  →  plan_hash
6  APPROVE     ONE owner approval for the PLAN (not per step)
7  ACT         tool call + timeout + idempotency key + audit row
8  VERIFY      result vs intent  →  retry | escalate | ABSTAIN
9  ANSWER      label the confidence + name the source
10 CONSOLIDATE write episode (L2), update facts (L3), update self-model (L5), emit metrics
```

**Step 4 is what removes generic answers.** If recall already contains the fact, the model has
nothing to add except risk. `"What's my brother's name?"` must be answered from L3 — or with
*"I don't have that saved."* Never from model memory.

## 4. The four thinking operations, and when a model is allowed

| Operation | Deterministic implementation (default) | Model allowed when |
|---|---|---|
| **Route** | registry matcher → else static-embedding nearest-prototype | the rule table has grown painful and mis-routes are *measured* |
| **Recall** | FTS5 + RRF fusion + 1–2 hop graph expansion | only for query *expansion* (synonyms), never for choosing facts |
| **Plan** | templates for known multi-step goals; the model fills slots | genuinely novel goals — and the plan is validated (see L6) |
| **Verify** | schema / format / path / registry checks; result diff | judged answers where no mechanical test exists |

**Rule:** a model may be introduced for an operation only after the deterministic version has
been **measured to fail**, and that failure is recorded. This is what stops LYA becoming a
prompt wrapper.

---

## 5. Provenance — mandatory, not optional

Every item entering L1 carries `{store, ref, written_at, confidence}`. An item **without**
provenance is not used for a factual claim. This is what makes §6 possible at all.

---

## 6. The abstention contract — what "correct output" means here

LYA speaks in exactly three registers, and never blurs them:

| Register | Wording | Source | Meaning |
|---|---|---|---|
| **Saved** | *"Here's what's saved: …"* | a store (L2/L3) | reliable, cited |
| **Belief** | *"I believe …"* | model-generated | plausible, unverified |
| **Refusal** | *"I'm not sure — I don't have that saved."* | no grounding | honest, **correct** |

A free model that abstains is **safer and more useful** than a paid model that invents your
mother's birthday. The third register is what makes the other two trustworthy.

---

## 7. Write rules — what may become memory

- Ordinary conversation → **L2 only**, bounded, discarded. Never auto-promoted to L3.
- `remember <fact>` → L3, explicit, never auto-deleted (decision **D-10**).
- `learn <topic>` → a *draft*, labelled unverified, expires (current: 10 min).
- Model output → **never** becomes a fact without owner confirmation. No exceptions.
- Every consequential write carries an **idempotency key**, so a retried automation step cannot
  duplicate it.

---

## 8. Consolidation (L7) — the "sleep" cycle

Runs on the always-on box, never the laptop, only when the laptop is idle:

1. compress stale episodes into facts, with `valid_from` / `valid_to`;
2. dedupe facts — a natural **typed decision** for JEV (*duplicate? yes/no + confidence*);
3. decay unused items' *ranking* — **never delete explicit memories** (D-10);
4. rebuild FTS + vector indexes;
5. export a readable Markdown snapshot (the escape hatch — `06-SKILL-LIBRARY.md` item #6);
6. emit one metrics line: facts, episodes compacted, index size, failures.

## 9. How to prove the schema works

Offline tests (synthetic data, no camera, no network) — these travel to the real device:

| Test | Asserts |
|---|---|
| `test_route_never_calls_model` | a known command resolves with the model unreachable |
| `test_answer_is_grounded_or_abstains` | a fact question with nothing stored returns the **refusal** register, not an invention |
| `test_provenance_required` | an item without provenance cannot be cited as *Saved* |
| `test_recall_is_flat` | recall latency flat from 100 → 10,000 rows (`bench_latency.py`) |
| `test_write_is_idempotent` | the same job step applied twice writes once |
| `test_validity_interval` | a superseded fact is not returned as current |

---

## 10. What this schema is NOT

- **Not** a claim that LYA thinks like a human. It is a layered state machine with a language
  model attached at the edges.
- **Not** a reason to add subsystems. Every layer above is *a table plus rules*: L1 is RAM,
  L2/L3/L5 are encrypted SQLite, L4 is the registry, L6 is a function, L7 is a scheduled job.
- **Not** permission for a model to act. **D-2 stands: model output is never authority.**

---

## Change log

### 2026-09-24 — Schema proposed (spec only)
**Goal:** answer "how do we decide the neural schema that acts like a brain and gives correct
output".
**Changed:** this file created. Eight layers (L0–L7), a ten-step thinking loop, four thinking
operations with an explicit "model only after measured failure" rule, a provenance requirement,
and a three-register abstention contract.
**Verified by:** reading the current code, on this machine, 2026-09-24:
`brain/mind.py` (provider order, memory injection, error handling), `main.py` (routing,
`using my memory` → `verified=True`), `brain/memory.py`, `brain/knowledge.py`,
`skills/reminder.py`.
**Left undone / follow-up:** the layer tables, `contracts/*.schema.json`, and the six tests in
§9 must be implemented on the real device. Nothing here is wired.
**Notes:** a correction to `04-SPEED-BUDGET.md` — the O(n) decrypt-scan is **not** on every
chat turn. Ordinary chat calls `mind.reply(verified=False)` (`main.py:234`), which skips
`_memory_block()`. The scan fires on `using my memory` (`main.py:182`), `show memories`, and any
`recall`/`touch` caller. Still the right fix, but it is a *memory-read* cost, not a *chat* cost.


