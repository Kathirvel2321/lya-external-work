# ADR-002 — Approval is bound to the plan, not to the step

- **Status:** PROPOSED
- **Date:** 2026-09-24
- **Owner decision required:** yes
- **Supersedes:** —
- **Related:** `07-NEURAL-SCHEMA.md` (L4/L6), `10-CONTRACTS.md`, `contracts/plan.schema.json`,
  `contracts/job.schema.json`, decisions **D-2** and **D-8**, `security/escalation.py`

## Context

Verified by reading the code:

- Every sensitive action currently escalates **individually** through
  `security/escalation.py` (nonce-bound, one-time grant, 5 failures → 600 s lockout) via
  `main.py`'s `permit(action, task)` (`main.py:100`).
- That design is **correct and it does not scale to automation**: a 12-step task would require 12
  phone approvals, which makes multi-step work unusable and pushes toward the dangerous shortcut
  of removing approval.
- `main.py:220-225` refuses activation outright ("Automatic code activation is disabled"), so no
  approval path exists for multi-step or generated work at all today.
- Decision **D-2** ("model output is never authority") must survive this change.

## Decision

**We will approve a plan once, bound to its `plan_hash`; execution proceeds without per-step
prompts, and any step that deviates from the approved hash — different tool, new target, wider
scope, higher tier — re-escalates to the owner.**

## Why

- It keeps the *existing* escalation primitive (nonce-bound, one-time, expiring) but changes what
  it authorises: **a described sequence**, not a bare action.
- The owner still sees exactly what will happen, before it happens — the vision document's
  requirement that LYA "identify the exact pending operation" is preserved and strengthened.
- Rejected alternative: auto-approve "low-risk" steps by rule. Rejected because the risk is
  frequently a property of the *combination* of steps, not of any single step (`delete temp file`
  + `empty recycle bin` + `resize partition` are individually mundane).
- Rejected alternative: per-step approval with a longer timeout. Rejected because it just moves
  the fatigue, and fatigue is what produces blind approval.

## Consequences

- **Good:** multi-step automation becomes usable while approval stays meaningful; the audit log
  gains a single, checkable artefact (the plan) per task.
- **Bad:** a *stale* plan hash is dangerous if the world changed between approval and execution —
  so every step must re-validate its preconditions (VERIFY, step 8) before acting.
- **Bad:** new surface — the hash must cover **targets and arguments**, not just tool names, or a
  subtle argument change slips through. This needs a test.
- **Reversible?** Yes — falling back to per-step approval is a config change, not a rewrite.

## How we will know it worked

- `test_plan_hash_binds_targets` — altering a target changes the hash and forces re-escalation.
- `test_deviation_reescalates` — a step outside the approved tool set cannot execute.
- `test_approval_is_single_use` — a consumed plan approval cannot be replayed (mirrors the
  existing grant semantics).
- A live end-to-end run of one real multi-step task **with one** approval, observed and recorded.

## Open questions

- Where does the plan approval live — reusing `escalation.py`, or the MCP Tasks/elicitation path
  (`08-PLATFORM-ROLES.md` §3.1)? Decide before implementing either.
- Does a plan approval expire on wall-clock time, on task completion, or on both?
- Should the owner be able to approve "this class of plan" for repeat jobs (e.g. the nightly
  backup), or must every instance be approved? (Nightly at 03:00 needs an answer.)

## Change log

| Date | Change |
|---|---|
| 2026-09-24 | Created (PROPOSED) |
