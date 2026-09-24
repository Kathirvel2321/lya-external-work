# 02 — DATA ROUTING (v2, cut down)

> **v2 note.** Your critique was correct: v1 specified five storage tiers, a reconciliation
> engine, and a migration — the shape of a small startup's backend for a system that talks
> to exactly one person. This version keeps the one rule that actually prevents data loss
> and deletes the rest. **The recovery fix is now `00-VAULT-RECOVERY.md`, and it comes first.**

---

## The whole design, in one sentence

**One thing has one home. If that home is a local file, back it up somewhere that is not
this laptop.**

That is it. Everything below is only the specifics of "which file, and which backup".

---

## Three stores, not five

v1's T0–T5 was a taxonomy looking for a use case. There are really only three places data
lives, and you already have the code for two of them:

| # | Store | Holds | Already exists? |
|---|---|---|---|
| **1** | **Your laptop** — encrypted files in `security/` and `brain/` | everything private | ✅ yes |
| **2** | **A backup, off this laptop** — private GitHub repo, or R2 | copies of #1, and your Markdown notes | ❌ to build |
| **3** | **Your head / a piece of paper** | the vault recovery passphrase | ❌ **build this first** |

**Store 3 is not a joke and is not optional.** It is the single point of failure that
currently exists in your project, and `00-VAULT-RECOVERY.md` fixes it.

**Store 2 is one job:** get a copy of your data somewhere the laptop dying does not reach.
That is a `git push` and an encrypted blob upload. It does not need a schema engine.

---

## The routing table — still just a table

| Data | Lives in | Backed up to | Notes |
|---|---|---|---|
| Passwords, API keys, tokens | `security/*.lya` vault | **encrypted blob → R2** | ⚠️ Only after recovery is proven |
| Admin identity / profile | `brain/lya_brain.db.lya` | encrypted blob → R2 | |
| Memories, calendar, reminders | `brain/lya_brain.db.lya` | encrypted blob → R2 | |
| Face/voice biometrics | same encrypted DB | ❌ **never** | Cannot be re-issued if leaked |
| Notes & knowledge | Markdown folder | **private GitHub repo** | Plaintext by design — you read these |
| Skills (code) | `skills/` | private GitHub repo | Version history for free |
| Screenshots | `shots/` | usually nothing | Apply a retention purge instead (audit S-8) |
| Conversation history | RAM | ❌ never | Vision doc D-9 — temporary talk is not saved |

**Seven rows. One rule. Done.**

---

## What I deleted from v1, and why

| v1 item | Verdict | Reason |
|---|---|---|
| T0–T5 five-tier taxonomy | ❌ deleted | Three stores. The taxonomy did not change any code |
| Reconciliation engine (4-step protocol) | ❌ **replaced** | See below — this was the worst offender |
| Supabase as a sync mirror | ⌛ deferred | Your code exists (`brain/sync.py`) but has open bug S-10. Fix it before relying on it |
| Notion as a view layer | ⌛ deferred | Nice-to-have. Not needed to make LYA work |
| Oracle DB as a store | ❌ dropped | 20 GB Oracle SQL is overkill for < 1 GB of personal data |
| Blind-index migration as *infrastructure* | ✅ **kept, but demoted** | It is a *performance* fix, not an architecture. See `04-SPEED-BUDGET.md` |
| "Degraded mode" behaviour matrix | ❌ deleted | With one store, "degraded" means "read the local file". No matrix needed |

### Why the reconciliation engine was the worst part

v1 specified: *"authority always wins, preserve `.conflict-<date>`, never merge."*

That protocol exists to solve **concurrent writes from multiple devices**. But you have
**one laptop and one phone that talks to it.** There is no concurrent writer. I designed a
conflict-resolution scheme for a conflict that cannot occur.

**The honest replacement:**

```
Write: local file first. Then push the backup. If the push fails, the write still
       succeeded — say so, retry later. Never fail a user action because a backup failed.

Read:  local file. Always. There is no second source to consult.
```

If you later genuinely run LYA on two always-on machines, *then* add reconciliation — with
a real conflict to test against. Not before.

---

## Oracle — the contradiction, resolved

You caught this exactly, and you were right. v1 said:

> *"Do not build a plan that requires an Oracle VM to exist"* — and then assigned it the role
> of "always-on brain" in Phase 4.

**I cannot have it both ways, so here is the decision:**

### Oracle is ⛔ demoted from "always-on brain" to "optional experiment"

| |
|---|---|
| **What it is now** | A free VM you try, for tinkering — if capacity happens to be available |
| **What it is not** | Anything LYA depends on |
| **If it vanishes tomorrow** | Nothing breaks, because nothing hangs off it |

**Why:** Oracle's own docs state ARM instances are **disabled and deleted after 30 days** if
your tenancy exceeds the Always Free allowance
([Oracle Free Tier](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm)).
Combine that with the well-documented "out of capacity" problem
([2026 analysis](https://space-node.net/blog/oracle-cloud-always-free-limits-2026)) and you
have a platform that can delete your instance for reasons outside your control. **That is
not a foundation. That is a demo box.**

### If you want always-on, use the platform that actually stays up

| Option | Cold start | Reclaimed when idle? | Free |
|---|---|---|---|
| **Cloudflare Workers** | **none** | no | 100k requests/day |
| Render | ~30 s wake | spins down after ~15 min | yes |
| Oracle VM | none | ⚠️ **can be deleted** | yes, if available |

**Cloudflare Workers is the honest answer** for "always-on and free": edge-deployed, no
cold start, 100k requests/day, and no reclamation policy that can delete your work. It is
also where R2 lives, so backup and serve are in one place.

**But note the bigger point:** you do not need an always-on brain *yet*. The iPhone-first
decision (D-17) plus a laptop that is usually on covers most real usage. Always-on is a
problem you will have *after* LYA is actually useful — not before.

---

## The build order, corrected

v1 buried recovery inside a "Phase 3" and put storage architecture first. That ordering
was wrong. Corrected:

```
Step 0  ⚠️  Vault recovery              ← 00-VAULT-RECOVERY.md. Before everything.
Step 1      Stop the data loss risk      ← one backup job: encrypted blob → R2
Step 2      Speed: the memory blind index ← 04-SPEED-BUDGET.md, item #1
Step 3      ... then skills
```

**Three steps before architecture.** No schema engine, no reconciliation, no five tiers.
Storage architecture is what you build when Step 0–2 are done and you have hit a real
limit — not before you have one.

---

## Effort, honestly

| v1 estimate | v2 estimate | What changed |
|---|---|---|
| ~23 h before any new skill | **~5 h before any new skill** | Recovery (1 h) + backup (1 h) + speed fix (2 h) + tests (1 h) |

**Your instinct was correct:** ~23 hours of infrastructure for a single-user assistant is
how the project dies with "build" never finishing, and LYA never getting used. Five hours
reaches a system that is safe, backed up and fast — then skills start landing immediately.

---

## Decisions (three, not six)

| # | Decision | Proposal |
|---|---|---|
| R-1 | Backup destination | **Cloudflare R2** (10 GB, zero egress, does not pause) |
| R-2 | Notes backup | **Private GitHub repo** (free version history) |
| R-3 | Always-on hosting | **Cloudflare Workers** if/when needed. Oracle = optional tinkering only |

R-2 and R-6 from v1 ("cloud copies of passwords/biometrics") are **closed — never**. That
is not a decision to revisit, it is the one thing worth being absolute about.

---

## The password rule — stated plainly (kept from v1, it was right)

You asked whether one platform could "securely store high-value passwords". Here is the
honest engineering answer, and it is a deliberate *disagreement* with the framing:

**A third-party platform makes passwords less safe, not more.**

Notion, Supabase, Oracle and Obsidian all put your passwords behind a web account. That
account can be phished, and those providers' staff can technically reach stored data. Your
current design — Fernet AES-256 with the key wrapped by Windows DPAPI
(`security/vault.py`) — means the ciphertext is bound to *this Windows login* and is
useless anywhere else. That is **stronger** than any of the platforms on your list.

**But that strength is exactly what `00-VAULT-RECOVERY.md` has to fix**, because a vault
that cannot be recovered after a Windows reinstall is not "secure", it is *fragile*. The
answer is a passphrase-protected portable key — recovery without a cloud copy of the data.

**The correct redundancy for secrets is not "another platform". It is a recovery path:**
1. Primary: local `security/*.lya` vault (as today).
2. Recovery: the portable key from `recovery/vault_recovery.py`, with the passphrase on paper.
3. Rule: LYA never auto-uploads raw vault *contents*. Ever.

This is already encoded in your project: `LYAPROJECTBRAIN.md` §4 lists
"Password/vault disclosure — keep refused" under NEVER-WITHOUT-A-DECISION. **Keep it that way.**

---

## What this means concretely — "where does my calendar live?"

One answer, no merge, no mirror to reconcile:

```
"add a meeting with Ahmed on Friday 4pm"
        │
        ├─→ LOCAL: encrypted SQLite          ──── committed, reported saved
        │
        └─→ BACKUP: encrypted blob → R2      ──── best-effort; failure is non-fatal
                                                  and is retried, never hidden
```

Ask "what's on Friday?" → read the local file. One source, one answer, ~5 ms.

**The one rule that survives from v1:** *never claim something is saved when the write
failed.* A silent save failure is worse than a visible error.