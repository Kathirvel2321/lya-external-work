# 05 — BUILD PLAN (v2, cut to ~5 hours)

> Phased, smallest-first. Each phase produces something **verifiable** before the next
> begins — following the project's own decision **D-16: one feature at a time:
> text → verify → next.**

> **v2 note.** v1 totaled ~23 hours of infrastructure before one new skill. That was the
> startup-backend shape you correctly called out. This version is **~5 hours to a safe,
> backed-up, fast system** — then skills start landing immediately.

---

## Phase -1 — ⚠️ Vault recovery (NEW, and it comes first)

**Why before everything, including Phase 0:** your vault key is wrapped by Windows DPAPI.
Microsoft documents that such data can *"only be done on the computer where the data was
encrypted"*, and the domain backup-key escape hatch does not exist on a personal laptop. So
a Windows reinstall means **every password and memory you ever saved is permanently gone**.

**This is a landmine, not an open item.** Full detail: `00-VAULT-RECOVERY.md`.

```powershell
# after installing cryptography + pywin32 (this was done while building the fix)
python recovery/vault_recovery.py export      # writes a passphrase-protected key
python recovery/vault_recovery.py verify <file>   # proves it actually restores your vault
```

**Exit condition:** `verify` prints **PASS**, and the passphrase + fingerprint are written
on paper, kept away from the file. **Do not put a single real password in the vault before
this passes.**

**Status: the script is built and its crypto is proven** (see the change log in
`00-VAULT-RECOVERY.md`). What remains is *you* running `export` and storing the paper.

---

## Phase 0 — Clear the remaining blockers

B-1 (`cryptography`) and B-2 (`pywin32`) were **installed while building the recovery fix**.
What is left:

```powershell
# B-3: make python reachable (each new shell)
$env:Path += ";C:\Users\ipvis\AppData\Local\Programs\Python\Python311;C:\Users\ipvis\AppData\Local\Programs\Python\Python311\Scripts"

# B-4: record what we now depend on
python -m pip freeze > requirements.txt

# B-5: prove it
python -B test_foundations.py     # target: 14/14 OK

# N-5: actually look at the orb
python main.py build
```

**Exit condition:** `test_foundations.py` reports 14/14, and the orb is visible on screen.

---

## Phase 1 — Stop the data-loss risk (1 hour)

**One job:** get a copy of the encrypted stores somewhere the laptop dying does not reach.
No schema engine, no reconciliation — see `02-DATA-ROUTING.md` v2 for why those were cut.

| Step | What |
|---|---|
| 1.1 | Create the R2 bucket; store credentials as env vars (never in a file in the repo) |
| 1.2 | `tools/backup.py` — uploads `security/*.lya` + `brain/*.lya` as encrypted blobs |
| 1.3 | `tools/backup.py --verify` — re-downloads and confirms the blobs decrypt |
| 1.4 | Private GitHub repo for the Markdown notes + `skills/` |

**Exit condition:** delete a `.lya` file locally, restore it from the backup, and confirm
`test_foundations.py` still passes. **A backup you have never restored from is not a backup.**

---

## Phase 2 — Speed foundation (2 hours, no new accounts)

**Goal:** LYA stops getting slower as memory grows. This is `04-SPEED-BUDGET.md` item #1.

| Step | File | What |
|---|---|---|
| 2.1 | `brain/memory.py` | Add blind-index table + `_index_tokens()` / `_query_tokens()` |
| 2.2 | `brain/memory.py` | Rewrite `recall()` to query the index, decrypt only matches |
| 2.3 | — | Backfill the index for existing rows on first open (one-time) |
| 2.4 | new `bench_latency.py` | Seed 100 / 1,000 / 10,000 facts; report query times |
| 2.5 | `test_foundations.py` | Add: recall correctness unchanged; index rebuild is idempotent |

**Verify:** `python bench_latency.py` → query time roughly **flat** across 100 → 10,000 rows.
That flatness *is* the proof. A graph that climbs is a failure.

**Decision needed (1 min):** confirm the word-frequency leak is acceptable — see
`04-SPEED-BUDGET.md`.

**Also in this phase (cheap wins from v1 Phase 2):**

| Step | File | What |
|---|---|---|
| 2.6 | `brain/sync.py` | Make cloud sync explicitly opt-in (`LYA_SYNC=on`) |
| 2.7 | `brain/sync.py` | Replace the 30 s poll with push-on-write |
| 2.8 | `brain/knowledge.py` | Move `_conn`/`_close` onto `security/database.py` |
| 2.9 | `brain/mind.py` | Distinguish "provider failed" from "no brain configured" |

**Verify:** with no sync configured, confirm **zero** outbound requests during a 5-minute
idle run.

---

## Phase 3 — Skills (start here for the fun part)

By this point LYA is **safe, backed up and fast** — about 5 hours of work. Now skills land
fast, because the foundation is not moving under them.

See `06-SKILL-LIBRARY.md`. The seven to build first, all `fast: True` (no model call):

1. Device status (battery/disk/CPU)
2. Notes create/append/search
3. Knowledge FTS search across the Markdown library
4. Task list
5. "What can you do" from the live registry
6. Export memories to Markdown
7. Timer / countdown

**Verify each one with a real command before moving on** — the project's own rule (§0.1).

---

## What I am deliberately NOT planning

Consistent with `LYAPROJECTBRAIN.md` §4 NEVER-WITHOUT-A-DECISION, and with your critique:

| Item | Why not |
|---|---|
| ⛔ Reconciliation engine | Solves a multi-device conflict you do not have |
| ⛔ Five storage tiers | Three stores. The taxonomy changed no code |
| ⛔ Oracle as always-on brain | Can be deleted for being idle. Optional tinkering only |
| ⛔ Notion / Supabase integration now | Deferred until a real need appears. Fix S-10 first if used |
| ⛔ Skill auto-activation | Needs isolation + rollback (D-8) |
| ⛔ Cloud copies of passwords/biometrics | Closed — never |
| ⌛ Self-rewriting code | **LYA proposes upgrades; you approve; changes are versioned and revertible.** Never unsupervised self-modification |

On that last row — your query said LYA "should want to be upgraded and act smart with
upcoming technology". The safe version of that ambition is *propose-and-approve*, matching
existing decision D-7 (appearance changes go through validated settings, never code rewrites).
Supervised self-improvement is fine. Unsupervised is the one capability whose failure is
silent and irreversible.

---

## Effort estimate (v2)

| Phase | Effort | Blocks on |
|---|---|---|
| **-1 — Vault recovery** | ~1 h | Nothing. **Script already built + tested** |
| 0 — Remaining blockers | ~15 min | Recovery (to avoid putting secrets in first) |
| **1 — Backup** | ~1 h | Recovery |
| **2 — Speed** | ~2 h | Phase 0 |
| 3 — Skills | ongoing | Phase 2 |

**Total before the first new skill: ~5 hours**, down from ~23.

**Phases -1 → 2 are the highest value by a wide margin, and they cost nothing but time.**
If you want to start building, that is the sequence — and the recovery step is already done
for you, waiting only on you running `export` and writing the paper.