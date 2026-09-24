# 10 — CONTRACTS, ADRs AND EVALS (the handoff pack)

> **Status: PROPOSAL, 2026-09-24.** This repo is the **architecture/decision copy**. The real
> build runs on another device. Therefore the deliverable here is **not code — it is the set of
> contracts and decisions that device must satisfy**, plus the tests that prove it did.

---

## 1. Why contracts here, and not code

Code written here cannot be verified here (different hardware, different data, no enrollment —
see `LYA_VISION.md` §"Structured admin enrollment is deferred"). What *can* be verified here is
**agreement**: the exact shape of a memory record, a plan, a job.

Rules for this folder:
- No real data, secrets, tokens or biometrics. **Ever.** (existing ground rule — keep it)
- Nothing here is imported by the running app.
- A platform is "chosen" only when it appears in `08-PLATFORM-ROLES.md` §5 with a dated rationale.
- Every claim carries a date and a command that proved it.

---

## 2. The contract set

| File | Purpose | Key fields | Read by |
|---|---|---|---|
| `contracts/memory_record.schema.json` | one fact in L3 | `id, kind, key, value, importance, provenance{}, valid_from, valid_to` | memory writer, recall |
| `contracts/episode.schema.json` | one thing that happened (L2) | `id, at, session, actor, kind, summary, refs[]` | consolidation, audit |
| `contracts/entity_edge.schema.json` | a typed relationship (L3 graph) | `subject, predicate, object, valid_from, valid_to, source` | recall expansion |
| `contracts/plan.schema.json` | a multi-step goal | `id, goal, steps[], plan_hash, created` | approval, executor |
| `contracts/job.schema.json` | durable execution state | `id, plan_id, step, status, attempts, idempotency_key, approvals[]` | scheduler, resume |
| `contracts/tool_descriptor.schema.json` | one capability (L4) | `name, matcher, tier, fast, timeout, idempotent, test` | registry, policy, "what can you do" |
| `contracts/adapter.schema.json` | one platform integration | `name, methods[], rate_budget, egress_class` | transport layer |
| `evals/golden.jsonl` | accuracy gate | `id, input, expect, must_not, kind` | CI, every change |

**Rule:** if two devices disagree about a field name, the contract wins. No platform is imported
directly by L3/L4 code — everything goes through an adapter.

## 3. ADR register — one file per decision, numbered, immutable

Write each as `ADR/ADR-0NN-<slug>.md`. **Never edit an accepted ADR** — supersede it with a new
one. Status starts as `PROPOSED`; only the owner moves it to `ACCEPTED`.

| ADR | Decision | Status | Why it matters |
|---|---|---|---|
| 001 | **Memory shape**: local-only hybrid — FTS5 + vectors + typed edges with validity intervals | PROPOSED | fixes the O(n) scan and stops superseded facts poisoning recall |
| 002 | **Approval = plan hash.** One approval per *plan*; any step deviating re-escalates | PROPOSED | makes multi-step automation usable without weakening D-2 |
| 003 | **Secrets never leave the device**; recovery key on paper, passphrase separate | PROPOSED | closes the DPAPI landmine without a cloud copy of the data |
| 004 | **Biometrics live only in `vision/*.lya`**; drop `admin.face_encoding` / `voice_path` | PROPOSED | resolves the routing-table contradiction (`02-DATA-ROUTING.md`) |
| 005 | **Vector engine: numpy brute force first**; sqlite-vec only after proving it loads | PROPOSED | a reported Windows loading failure must not block the plan |
| 006 | **Three abstention registers** (saved / belief / refusal) are mandatory in output | PROPOSED | this is what "correct output" means operationally |
| 007 | **MCP `2026-07-28`** is the interop boundary; local adapter contract underneath | PROPOSED | header-based authz matches `policy.py`; Tasks = job store |
| 008 | **Egress default-deny** + ledger + per-provider data-policy check before grounding | PROPOSED | the plan currently has no data-policy gate at all |
| 009 | **Local stack is CPU-only, model off the hot path** | PROPOSED | measured: 7.71 GB RAM, i3-1315U, no NPU |
| 010 | **Retention purge** for `shots/` and `debug/`; no plaintext media on disk | PROPOSED | unencrypted PNG/WAV are on disk today (S-8) |
| 011 | **Durable job store + idempotency keys** (the automation spine) | PROPOSED | without it, "big task automation" is not possible |

---

## 4. Evals — `evals/golden.jsonl`

Four kinds of case, and the **`must_not`** field is the important one:

| kind | Tests |
|---|---|
| `grounded` | a stored fact is answered from the store, with provenance |
| `command` | a known command resolves **without** a model call |
| `abstain` | nothing stored → the *refusal* register, **not** an invention |
| `refuse` | a disabled capability (password disclosure, skill activation) stays disabled |

`must_not` states the failure explicitly (e.g. `must_not: "invent a birthday"`), so a regression
is a red test rather than a bad answer on a bad day.

---

## 5. Definition of done — what the real device must show

- [ ] `test_foundations.py` → **14/14** on that machine (paste output)
- [ ] `recovery/vault_recovery.py export` run; passphrase on paper, away from the file
- [ ] `verify` → **PASS against the real vault** (6 stores exist as of 2026-09-24)
- [ ] Backup to R2 **and a restore drill** (delete a `.lya` copy, restore, re-run tests)
- [ ] `bench_latency.py` numbers recorded, before and after
- [ ] `evals/golden.jsonl` green, including every `must_not`
- [ ] Registry exists; **every** command has a tier and a test
- [ ] Egress ledger refuses `private_never` — proved by a test, not by inspection
- [ ] No plaintext media (`shots/`, `debug/` purged)
- [ ] ADRs 001–011 either accepted or explicitly rejected — **none silently ignored**

---

## 6. Change log

### 2026-09-24 — Handoff pack defined
**Goal:** give the real-device implementation an unambiguous target by defining contracts,
decisions and evals here instead of code.
**Changed:** this file created; `contracts/*.schema.json`, `evals/golden.jsonl` and
`ADR/ADR-000-template.md` added; ADR register 001–011 raised as PROPOSED.
**Verified by:** consistency check against the existing folder — every schema field traces to
`07-NEURAL-SCHEMA.md` (layers) or `08-PLATFORM-ROLES.md` (adapters/egress). No code was changed
and nothing here is imported by the app.
**Left undone / follow-up:** owner sign-off on ADRs 001–011; the schemas must be re-checked
against the real implementation once it exists (a contract nobody honours is a wish).
**Notes:** the "spec repo" framing is deliberate. The project's ground rule for this folder — no
real credentials, tokens or personal data, ever — is what makes that framing work.

