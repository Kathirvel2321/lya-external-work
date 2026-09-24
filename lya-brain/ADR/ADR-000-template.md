# ADR-000 — TEMPLATE (copy this for every decision)

> One decision per file. **Never edit an accepted ADR** — write a new one that supersedes it.
> Status values: `PROPOSED` → `ACCEPTED` → `SUPERSEDED BY ADR-0NN` (or `REJECTED`).
> Only the owner moves a decision to `ACCEPTED`.

---

# ADR-0NN — <short decision title>

- **Status:** PROPOSED
- **Date:** YYYY-MM-DD
- **Owner decision required:** yes / no
- **Supersedes:** — / ADR-0NN
- **Related:** file references, findings (e.g. S-10), other ADRs

## Context

What is true today, measured. Include the command or file:line that proves it. No estimates
without the word "estimate".

## Decision

One sentence, in the active voice: *"We will …"*

## Why

The reasoning, including the alternative that was rejected and **why it lost**. If a platform or
model was considered and rejected, name it.

## Consequences

- **Good:** what becomes possible.
- **Bad:** what we accept — including the cost, the new failure mode, and what we can no longer do.
- **Reversible?** yes / no, and what reverting would cost.

## How we will know it worked

A command, a test name, or a number. Per the project's §0.1 rule: *never write ✅ without naming
the command you ran.*

## Open questions

Anything unresolved. Do not guess — list it.

## Change log

| Date | Change |
|---|---|
| YYYY-MM-DD | Created (PROPOSED) |
