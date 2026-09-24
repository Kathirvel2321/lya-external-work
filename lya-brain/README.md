# LYA BRAIN & STORAGE — the plan

> **Status: PLAN ONLY. Nothing here is deployed, and no platform was signed up for.**
> Every number in this folder is sourced and dated. Re-verify before you rely on it —
> free tiers change without notice.

This folder is the design workspace for **where LYA keeps data** and **which model thinks
for her**. It is deliberately separate from the working app in the repo root
(`brain/`, `security/`, `main.py`). Nothing in here is imported by the running code yet.

---

## Why this folder exists

The owner's request, in plain terms:

1. Find out **how much capacity each platform actually gives** — laptop, Oracle free tier,
   Obsidian, Notion, a notebook LLM.
2. Decide **which platform stores which kind of data** — temporary, permanent,
   structured, high-value secrets, admin/personal, calendar.
3. Find **free models** that give *correct* answers, not confident wrong ones.
4. Make the whole thing **fast** — "like a cheetah, not a snail".
5. Plan it, then build it.

This folder answers 1–4. Building starts only after the owner reviews the plan.

---

## Read in this order

| # | File | What it answers |
|---|---|---|
| **0** | [`00-VAULT-RECOVERY.md`](00-VAULT-RECOVERY.md) | ⚠️ **THE LANDMINE.** Your vault key dies with your Windows install. Fix this first |
| 1 | [`01-CAPACITY-AUDIT.md`](01-CAPACITY-AUDIT.md) | Real free-tier numbers for every platform, with sources and the trap in each |
| 2 | [`02-DATA-ROUTING.md`](02-DATA-ROUTING.md) | Which platform holds which data — now cut to **three stores**, not five |
| 3 | [`03-MODEL-STRATEGY.md`](03-MODEL-STRATEGY.md) | Which brain thinks, when, for free — and what "JEV / Laya / UltraJEV" actually are |
| 4 | [`04-SPEED-BUDGET.md`](04-SPEED-BUDGET.md) | The latency targets and the one bottleneck that actually matters |
| 5 | [`05-BUILD-PLAN.md`](05-BUILD-PLAN.md) | Build order — **~5 hours** to safe + backed up + fast, down from ~23 |
| 6 | [`06-SKILL-LIBRARY.md`](06-SKILL-LIBRARY.md) | How to reach "A-to-Z skills" without drowning in 3.6 MB of dead corpora |
| **7** | [`07-NEURAL-SCHEMA.md`](07-NEURAL-SCHEMA.md) | **How she thinks** — eight layers (L0–L7), the ten-step loop, the abstention contract |
| **8** | [`08-PLATFORM-ROLES.md`](08-PLATFORM-ROLES.md) | The 8-criterion decision basis, what each platform is for, and how they connect (MCP `2026-07-28`) |
| **9** | [`09-LOCAL-STACK-CPU.md`](09-LOCAL-STACK-CPU.md) | The measured laptop, and what actually runs on a CPU-only machine |
| **10** | [`10-CONTRACTS.md`](10-CONTRACTS.md) | The handoff pack: contracts, ADR register, evals, definition-of-done |
| **11** | [`11-THREAT-MODEL.md`](11-THREAT-MODEL.md) | **Security.** What we defend, what we cannot, and 15 weaknesses with file:line evidence |
| **12** | [`12-ZERO-DISCLOSURE.md`](12-ZERO-DISCLOSURE.md) | **Compromise ≠ disclosure** — compartment keys, egress shield, injection shield, 20 red tests |
| **13** | [`13-SELF-PROTECTION.md`](13-SELF-PROTECTION.md) | She must not boom herself — least privilege, resource guards, recovery, staying current |
| — | [`contracts/`](contracts/) · [`ADR/`](ADR/) · [`evals/golden.jsonl`](evals/golden.jsonl) | Machine-readable schemas, decision records, and the accuracy gate |
| — | [`recovery/vault_recovery.py`](recovery/vault_recovery.py) | **Working code**, cryptographically verified. Run `export` today |
| — | [`../lya-agency/`](../lya-agency/) | **Sister folder — what she can actually do:** access tiers, video→upload pipeline, laptop diagnosis, and why payment stays yours |
| — | [`../lya-platform/`](../lya-platform/) | **Sister folder — where she works:** isolate risky work into a workshop so failures never land on your data |

---

## v2 — revised after owner review

The first version over-built. Three corrections, all accepted:

**1. Vault recovery is now step zero, not an "open item".**
`security/vault.py` wraps the master key with Windows DPAPI. Microsoft documents that such
data can *"only be done on the computer where the data was encrypted"*, and the domain
backup-key escape hatch does not exist on a personal laptop. So **reinstalling Windows
permanently destroys every password and memory you ever saved** — and the cloud backup I
proposed would faithfully replicate *unreadable ciphertext*. Fixed, with working code:
`00-VAULT-RECOVERY.md`.

**2. Oracle is demoted from "always-on brain" to "optional experiment".**
The v1 doc said *don't depend on an Oracle VM*, then made it the always-on host. It can be
deleted for being idle. Cloudflare Workers is the honest always-on answer — no cold start,
no reclamation. See `02-DATA-ROUTING.md`.

**3. The architecture was startup-shaped for a single user. Cut.**
Five storage tiers → three stores. Reconciliation engine → deleted (it solved multi-device
conflicts you do not have). Effort: **~23 h → ~5 h** before the first new skill.

---

## v3 — added 2026-09-24 (architecture of the real build)

`01`–`06` answer *"where does data live and which model thinks"*. They do not answer *"how does
she think, and how do the platforms connect"* — the owner asked for both. **Files `07`–`10`
answer those, and they are the spec for the build that runs on the other device.**

Three things worth stating plainly:

**1. This folder is a spec repo, not a codebase.** The real implementation runs elsewhere, so
what must be correct *here* is the **agreement**: `07` (the layered brain + thinking loop),
`08` (platform roles + connection fabric), `09` (the measured CPU-only stack), `10` (contracts,
ADRs, evals). Nothing here is imported by the app. No real data ever enters this folder.

**2. `08-PLATFORM-ROLES.md` corrects four numbers from earlier drafts.**
Cerebras has **no free tier** (30-day $5 trial, payment method required). Gemini's free Flash is
**5 RPM / 20 requests per day**, measured — not a workhorse. Turso's free tier is **5 GB** (9 GB
is the $4.99 plan). OpenRouter was already listed in `03-MODEL-STRATEGY.md`; an earlier review
called it missing, which was wrong.

**3. `09-LOCAL-STACK-CPU.md` changes one earlier claim.** Measured on the owner's laptop:
**7.71 GB RAM, Intel i3-1315U, no NPU**. So `03`'s M-5 ("keep Ollama as the offline guarantee")
is **currently false on this machine** — `ollama list` returns `Error: could not locate ollama
app`. Either repair it or stop claiming an offline tier.

---

## v4 — added 2026-09-24 (security)

Files `11`–`13` answer the owner's security request. **Read `11` first, and read §0 of it twice.**

The honest position, because it matters more than any feature:

- **"Unhackable" does not exist** and must never be claimed. `LYA_VISION.md` already refuses that
  claim — keep that refusal.
- The achievable goal is **compromise ≠ disclosure**: an attacker may own the laptop and still be
  unable to read the top-tier secrets, because the key that opens them **is not on the laptop**
  (`12` §1–§2).
- The other half is **recoverability**: assume breach, detect it, contain it, restore, and turn the
  incident into a new row in `evals/redteam.jsonl` (`13` §4).
- **The owner's AI-attacker concern is well founded.** OWASP's 2026 list — for the first time ranked
  on real incident data (7,714 incidents) — keeps prompt injection at #1 for a third year, and
  *Excessive Agency* rose from 6th to 3rd precisely as agents began **acting** rather than reading.
  Documented MCP tool-poisoning attacks exist; `12` §5 is the response.

**Two findings that should be fixed before the vault holds anything real:**

1. **W‑2 — the vault's own second factor leaves the device.** `security/auth_wall.py:88-102` uploads
   audio containing your **spoken security word** to Groq Whisper for transcription.
2. **W‑1 — one key opens everything.** `security/vault.py:31` builds a single Fernet key for
   secrets, memory, biometrics and logs, so there is exactly one blast radius (`12` §1).

**And one item that needs an elevated shell:** whether **BitLocker** is on. The query returned
`Access denied`, and it is the largest single unknown in the whole threat model.

---

## The three honest findings up front

**Finding 1 — the real risk is not capacity, it is recovery.**
You have ~750 GB of free space available. You also have a vault that becomes permanently
unreadable if Windows is reinstalled. **Space was never the problem.**

**Finding 2 — "free + perfect results" is not a thing, but "free + verified" is.**
Free tiers are rate-limited and occasionally wrong. The fix is not a better free model;
it is a **verification layer** — LYA checks the answer and says "I'm not sure" instead of
inventing one.

**Finding 3 — the fastest thing you can do costs nothing.**
`brain/memory.py` decrypts every row of the database on every query. That is the biggest
cause of "snail" behaviour, and it is a ~2 hour fix with no new platform and no spend.
See `04-SPEED-BUDGET.md`.

---

## The build order — three steps, not five phases

```
Step 0  ⚠️  Vault recovery     ← script built and crypto-verified. You run `export`
Step 1      Backup off-laptop  ← encrypted blob → R2 + notes → private GitHub
Step 2      Speed              ← the memory blind index (~2 h)
Step 3      Skills             ← now the fun part, on a stable foundation
```

**No schema engine, no reconciliation, no five tiers.** Three steps to a system that is
safe, backed up and fast — then skills land immediately.

---

## Ground rules for this folder

- Nothing here is wired into `main.py` without an explicit owner decision.
- No real credentials, tokens or personal data live in this folder. Ever.
- Numbers are cited. If a number has no source, it is labelled **estimate**.
- A platform is only "chosen" when it appears in the decision table in
  `02-DATA-ROUTING.md` with a dated rationale.