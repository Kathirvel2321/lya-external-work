# ADR-001 — Memory shape: local-only hybrid with validity intervals

- **Status:** PROPOSED
- **Date:** 2026-09-24
- **Owner decision required:** yes
- **Supersedes:** —
- **Related:** `02-DATA-ROUTING.md`, `04-SPEED-BUDGET.md`, `07-NEURAL-SCHEMA.md` (L3),
  `contracts/memory_record.schema.json`, `contracts/entity_edge.schema.json`

## Context

Verified 2026-09-24 by reading the code:

- `brain/memory.py:43-49` — `recall()` selects rows and **decrypts every row** before filtering,
  because the data is encrypted and SQL `WHERE` cannot match ciphertext. This is O(n) per read.
- The trigger set is narrower than `04-SPEED-BUDGET.md` states: ordinary chat calls
  `mind.reply(verified=False)` (`main.py:234`), which skips `_memory_block()`. The scan fires on
  `using my memory` (`main.py:182`), `show memories`, and any `recall`/`touch` caller.
- `brain/knowledge.py:58,76` writes a **plaintext** `DB + ".working"` temp file per ingest, and
  rewrites the whole file — O(total DB) per message. (`knowledge.py` is not wired in, per
  `LYAPROJECTBRAIN.md` §2.)
- There is **no** validity interval anywhere: a superseded fact and a current fact are
  indistinguishable, so recall can answer with something no longer true.

## Decision

**We will store all owner memory locally, encrypted, in one SQLite file shape: a fact table with
provenance and validity intervals, a blind-index/FTS5 search surface, and a typed edge table —
and we will never send raw memory to a third-party platform.**

## Why

- Local-only is not a preference: the vault's ciphertext is useless anywhere else, and
  `02-DATA-ROUTING.md` already chose "encrypted blob → R2" over "cloud copy".
- The blind index removes the O(n) scan **without** moving data off the device.
- Validity intervals fix a correctness bug, not just a speed one — the abstention contract
  (`ADR-006`) is impossible to honour if superseded facts look current.
- Rejected alternative: a cloud vector database. For a corpus measured in **megabytes**, a remote
  vector DB adds latency, a monthly quota and a data-policy problem to solve a problem we do not
  have.
- Rejected alternative (for now): `sqlite-vec` as the vector engine — the pre-compiled extension
  has **reported loading problems on Windows**, so it is a *verify-then-depend* item (`ADR-005`).

## Consequences

- **Good:** memory reads stay flat as the corpus grows; recall can be cited; "was true in July"
  becomes answerable; the corpus never leaves the device.
- **Bad:** a blind index leaks **word frequency** to anyone holding the raw file. Accepted for a
  personal assistant, but it is a *recorded* trade, not a silent one.
- **Bad:** the index must be backfilled once and kept in sync on every write (one extra table).
- **Reversible?** Yes — the index is derivable; dropping it returns to today's behaviour.

## How we will know it worked

- `bench_latency.py`: `recall()` time **flat** across 100 → 1,000 → 10,000 seeded facts (the
  flatness *is* the proof; a climbing graph is a failure).
- `test_recall_is_flat`, `test_validity_interval`, `test_provenance_required` pass offline.
- `test_foundations.py` remains green (no behaviour change for existing rows).

## Open questions

- Blind index only, or blind index **plus** FTS5 on decrypted-at-rest cache? (Measure both.)
- Vector search: numpy brute force is expected to be sufficient below ~50k chunks — confirm by
  measurement before adding any dependency.
- Does `knowledge.py` get wired in, or archived? (`LYAPROJECTBRAIN.md` L-5 is still open.)

## Change log

| Date | Change |
|---|---|
| 2026-09-24 | Created (PROPOSED) |
