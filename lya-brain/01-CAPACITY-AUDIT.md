# 01 — CAPACITY AUDIT

> Every platform you named, its **real** free capacity, its **trap**, and what it is
> genuinely good for. Figures verified **2026-09-23** against the sources linked below.
> Free tiers change — treat this as a starting point, not a contract.

---

## Summary table — free capacity at a glance

| Platform | Free capacity | Hard limit you will actually hit | Verdict |
|---|---|---|---|
| **Your laptop** | Disk-limited (typically 200 GB–1 TB SSD) | Single point of failure; laptop off = gone | **Primary hot store** |
| **Oracle Cloud** | 2 OCPU / 12 GB ARM, 200 GB block, 20 GB object, 2× 20 GB databases, 10 TB/mo egress | Idle-reclaim; ARM capacity often unavailable | **Best free cloud home** |
| **Supabase / Postgres** | 500 MB DB + 1 GB files + 5 GB egress | **Pauses after 1 week idle**; 2 projects max | **Sync mirror, not source of truth** |
| **Notion** | Unlimited pages/blocks, unlimited file count | **5 MB per file**; structure is not queryable | **Human-readable dashboard** |
| **Obsidian** | Unlimited (plain Markdown on your disk) | It is your laptop's disk — no independent copy | **The editable layer** |
| **Notebook LM** | Free tier, generous for a single user | Not an API; no programmatic write path | **Research/reading, not storage** |
| **GitHub** | Unlimited public, ~1 GB soft private (free) | Not private by default; not for secrets | **Code + docs only** |
| **Render** | Free web service | **Spins down after ~15 min idle → ~30 s cold start** | Pair with an uptime pinger |
| **Cloudflare R2** | 10 GB storage, zero egress fees | 1M Class-A ops/mo | **Best free object storage** |
| **Hugging Face** | Free datasets/models, public by default | Public unless you pay for private | **Skill library corpus** |

**Combined free ceiling, if you use them all correctly: ~750 GB+** — far beyond what a
personal assistant needs. **Capacity is solved. Coordination is not.**

---

## 1. The laptop

**Capacity:** whatever your SSD has. Let me get the real number rather than guess:

```powershell
Get-PSDrive C | Select-Object Used,Free
Get-CimInstance Win32_ComputerSystem | Select-Object TotalPhysicalMemory
Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors
```

**Real limits:**
- Disk is not the constraint — *availability* is. Laptop closed = LYA offline.
- Windows user account boundaries: your DPAPI-encrypted vault (`security/vault.py`) is
  bound to this Windows account and is **unreadable on any other machine**. This is a
  feature (a stolen `.lya` file is useless) and a constraint (you cannot restore it on a
  new laptop without a deliberate recovery path — currently there is none).

**Best role:** hot cache, live memory, biometrics, device control, the vault.
**Never:** the only copy of anything you would grieve losing.

---

## 2. Oracle Cloud Always Free — your best free compute

This is the one platform on your list that gives genuine *always-on* capacity.

**What you actually get** ([Oracle Always Free Resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)):

| Resource | Free amount | Notes |
|---|---|---|
| ARM (Ampere A1) compute | **2 OCPU + 12 GB RAM** | One VM, or split. Flexible shape |
| AMD micro VMs | 2 × 1/8 OCPU, 1 GB each | Too small for much |
| Block volume (boot disks) | **200 GB total** | Min 47 GB per boot volume |
| Object Storage | **20 GB** combined (Standard/IA/Archive) | + 50,000 API requests/mo |
| Outbound transfer | **10 TB/month** | Effectively unlimited for personal use |
| Autonomous DB | **2 databases × 20 GB** | Real Oracle DB with REST access |
| NoSQL DB | 3 tables × 25 GB | 133M reads + 133M writes/mo |
| MySQL HeatWave | 1 node, 50 GB (+50 GB backup) | |
| Logging | 10 GB/month | |

**The trap — read this twice.** Oracle's docs state that **ARM-based Always Free
instances are disabled and deleted after 30 days** if your tenancy exceeds the Always
Free allowance (more than 2 OCPUs / 12 GB total). Note the discrepancy: the marketing page
says "4 OCPUs and 24 GB", the *Always Free eligibility rules* cap you at **2 OCPUs /
12 GB**. Make sure you fall in the lower band or your instance can vanish. See
[Oracle Cloud Infrastructure Free Tier](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm).

Second trap: **capacity is frequently unavailable.** "Out of capacity" for Ampere A1 is a
common, well-documented experience, and it varies by region and by day
([Oracle Always Free limits, 2026](https://space-node.net/blog/oracle-cloud-always-free-limits-2026)).
Do not build a plan that *requires* an Oracle VM to exist. Build one that *uses* it when it does.

**Your open question, now answerable:** `LYAPROJECTBRAIN.md` §6.1 lists
"Whether an Oracle VM exists; its shape, region, CPU/RAM" as unresolved. That is still
unresolved on your side — but the *allowed* shape is now known: aim for
**VM.Standard.A1.Flex, 2 OCPU / 12 GB, ~47 GB boot volume, Ubuntu.**

**Best role:** the always-on brain. Runs the API, the sync worker, scheduled tasks,
reminder delivery while the laptop sleeps.

---

## 3. Supabase / Postgres — good, but it sleeps

Free tier ([Supabase Pricing](https://supabase.io/pricing), [2026 breakdown](https://uibakery.io/blog/supabase-pricing)):

| Resource | Free | Trap |
|---|---|---|
| Database size | **500 MB** | Shared CPU, ~500 MB RAM |
| File storage | 1 GB | |
| Database egress | **5 GB/month** | |
| Active projects | **2 max** | |
| Backups | **None** | No point-in-time recovery |
| Inactivity | **Paused after 1 week idle** | Your mirror goes stale silently |

**Why it still matters:** you already have working code for it — `brain/sync.py` and
`cloud/lya_cloud.py`. 500 MB of *encrypted text* is genuinely years of personal memory
(the existing `memories` table stores ciphertext, which is compact).

**Best role:** the **backup mirror**, never the source of truth. If it pauses, nothing
breaks — you just lose replication until someone pokes it.

**Caveat from your own audit:** `LYA_RESEARCH.md` finding **S-10** — `brain/sync.py` has
an inconsistent storage contract and calls `pull_future_cloud()` every 30 s even when
sync was never configured. Fix that before leaning on Supabase harder.

---

## 4. Notion — a dashboard, not a database

Free plan ([Notion pricing](https://www.notion.com/pricing), [file limits](https://www.notion.com/help/images-files-and-media)):

- Unlimited pages and blocks for personal use
- **5 MB maximum per uploaded file** on Free (5 GB on paid)
- Up to 10 guests
- 7-day page history

**The trap:** Notion *looks* structured (databases, relations, filters — genuinely nice).
But its API is rate-limited, its rich-text properties cap at 2,000 characters per object,
and it is not designed to be written to thousands of times a day by a bot. Using Notion as
LYA's live memory will produce slow, lossy writes.

**Best role:** the **human-readable window** into LYA. You open Notion on your phone and
*see* your memory, projects, calendar notes — pretty, browsable, shareable. LYA's code
writes to it rarely (a daily summary), never on the hot path.

---

## 5. Obsidian — the editable layer (and a hidden risk)

Obsidian itself is free and stores plain Markdown files in a folder **on your disk**.
"Unlimited" is honest, because the limit is your SSD.

**The good:** plain text is the most durable format that exists. No vendor can lock you
out. You can grep it, diff it, version it, print it.

**The trap — and this one is important:** Obsidian's storage **is your laptop's storage**.
People assume "I have it in Obsidian" means "it is safe". It does not. It is the same
disk. Without the vault folder also synced somewhere independent, Obsidian adds
*convenience*, not *redundancy*.

Second consideration: Obsidian vaults are **plaintext by default**. Never put the
password store or the admin identity file in an Obsidian vault.

**Best role:** the **notes and knowledge layer** — the things you want to read and edit
by hand. Synced to GitHub (private) or R2 for actual redundancy.

---

## 6. Notebook LM — great tool, wrong job

Free, and genuinely excellent at "read these 40 PDFs and tell me what matters", with
source-grounded answers and citations. That is a real asset for building a skill library.

**Why it is not storage:** there is no supported programmatic write API for LYA to use.
It is a **manual research tool** — you feed it, you read the output, you hand the result
to LYA by other means.

**Best role:** the **research bench**. Use it to digest material, then store the *result*
in Obsidian/HF, not in Notebook LM.

---

## 7. Additional platforms you did not list — worth knowing

| Platform | Free offer | Why you would add it |
|---|---|---|
| **Cloudflare R2** | 10 GB storage, **zero egress fees**, 1M ops/mo | Best free object storage. No egress bill, ever |
| **GitHub** | Unlimited repos, ~1 GB private soft cap | Versioned backup for Obsidian vault + code |
| **Hugging Face** | Free public datasets & models | Natural home for the A-to-Z skill corpus |
| **Cloudflare D1** | 5 GB SQLite, 5M reads/day | Real SQL, no cold start, generous — better fit than Supabase for small structured data |
| **Cloudflare Workers** | 100k requests/day | Always-on API with **no cold start** — beats Render's 15-min spin-down |
| **Turso** | 9 GB SQLite, 1B row reads/mo | SQLite over HTTP; ideal for a fast personal brain |
| **Groq** | Free LLM API, ~1,000 requests/day | The fast brain — see `03-MODEL-STRATEGY.md` |
| **Cerebras** | Free tier, ~1M tokens/day | Very high throughput for batch work |
| **Google AI Studio** | Free Gemini, 1M-token context | Long documents, multimodal |
| **NVIDIA NIM** | Free endpoints, ~1,000 req/day | Another free provider for fallback |
| **ntfy** | Free push notifications | Reminder delivery to your phone, self-hostable |

**The two I would actually add to your plan:** **Cloudflare R2** (replaces paid object
storage entirely, and unlike Supabase it does not pause) and **Turso or Cloudflare D1**
(a genuinely fast always-on SQL layer with no cold start — the thing Render cannot give you).

---

## 8. The uncomfortable truth about "unlimited"

Nothing on this list is unlimited, and **you do not need it to be.** Run the arithmetic:

| Data type | Realistic size after 5 years |
|---|---|
| Personal facts + admin profile | < 5 MB |
| Encrypted password store (500 entries) | < 1 MB |
| Calendar events (10/day × 5 years) | ~15 MB |
| Chat/session history (bounded, discarded) | ~0 (by design) |
| Knowledge notes (Obsidian) | 50–200 MB |
| Skill library (text) | 50–500 MB |
| Biometrics (face embeddings, voiceprints) | < 50 MB |
| Screenshots / media (optional) | 5–20 GB |

**Everything except media fits in well under 1 GB.** The 500 MB Supabase limit is only a
problem if you start dumping media into it — which you should not do.

**So the design goal is not "more space". It is:**
1. The right data in the right place.
2. Clear rules for which copy wins.
3. Fast reads of the small, hot data.

That is `02-DATA-ROUTING.md`.