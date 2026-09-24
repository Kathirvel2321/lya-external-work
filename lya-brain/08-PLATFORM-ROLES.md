# 08 — PLATFORM ROLES: how we decide, and what each platform is for

> **Status: PROPOSAL, 2026-09-24.** Free-tier numbers re-verified on that date against vendor
> pages; anything not re-verified is labelled **unverified**. Free tiers change without notice.

---

## 1. The basis on which we decide (score 1–5, never "how big is it")

| # | Criterion | The question that actually decides it |
|---|---|---|
| 1 | **Fit** | Does the data's *shape* match the platform's native shape? (blob→object store, text→git, rows→SQL) |
| 2 | **The number that bites** | Not the headline limit — the real wall (tokens/day, 5 MB/file, pause-after-idle) |
| 3 | **Latency class** | Hot path (<100 ms) or background (minutes)? Wrong class = wrong platform |
| 4 | **Data policy** | If private data leaves the device, who trains on it? Check **before** grounding a prompt with memory |
| 5 | **Failure mode** | When it dies: silent wrong answer, or honest degradation? |
| 6 | **Exit cost** | Can we leave in an afternoon with a script? Markdown yes, proprietary schema no |
| 7 | **Verifiable offline** | Can a test prove it works with no human watching? |
| 8 | **5-year cost** | $0 today, or $X/month forever? |

**Surviving rule:** *one thing has one home; if the home is a local file, back it up somewhere
the laptop's death cannot reach it.*

---

## 2. Role assignment

| Platform | Role | Carries | Verified fact (2026-09-24) |
|---|---|---|---|
| **Real device** | Hot brain L1–L6 + vault + registry + audit | everything private | single source of truth |
| **Groq** | Fast cloud brain + STT | chat, transcription | `gpt-oss-20b` free: 30 RPM / **1,000 RPD / 8K TPM / 200K TPD**; Whisper 2,000 RPD; **cached tokens do not count toward limits** |
| **OpenRouter** | Fallback pool + model shopping | outages, trials | already in `03-MODEL-STRATEGY.md`: 20 RPM / 50 req/day for free models; higher daily cap after credits |
| **Gemini** | Rare, explicit long-context only | one long doc, on request | free Flash measured **5 RPM / 20 RPD** (2026-09-02); 2.5 models return 404 for new keys |
| **Oracle Cloud** | L7 consolidation + sandbox + gateway | nightly jobs, untrusted code | 1,500 OCPU-h + 9,000 GB-h = **2 OCPU / 12 GB**; 200 GB block; 20 GB object; 10 TB egress — **home region only**; **idle ≥7 days can be reclaimed** → convert to PAYG inside free limits |
| **Cloudflare Worker + D1** | Phone bridge, auth gate, webhook | phone access | free tier exists; CPU-time limit **unverified** — not a compute host |
| **Cloudflare R2** | Encrypted blobs | backups, media, model files | 10 GB-month, 1M Class A, 10M Class B ops, **zero egress** |
| **GitHub private** | Code, skills, docs, contracts | versioned text | plaintext by design — **never secrets**; check LFS terms before storing blobs |
| **Obsidian** | Human-readable A–Z knowledge | notes, greppable via FTS5 | it *is* your disk; redundancy comes from git/R2, not Obsidian |
| **NotebookLM** | Research bench (manual) | 40 PDFs → you read the result | no write API; **never put secrets in it** |
| **Notion** | Human dashboard (**deferred**) | calendar-ish views | free = **5 MB per file**; structure not queryable |
| **ntfy** | Push delivery | reminders while LYA is closed | free; listed in `01`, not yet used |
| **JEV (TypeSafe)** | Typed decisions (**LATER**) | plan validation, duplicate detection | real, early access, **paid**: $0.042/MTok input, output free, 70–500 ms, no prose |
| **Supabase** | Optional mirror (**deferred**) | nothing on the hot path | 500 MB DB / 1 GB files / 5 GB egress; **pauses after 1 week idle** |
| **Turso** | Optional remote SQL | phone-side reads | free = **5 GB** (9 GB is the $4.99 Developer plan) |
| **Hugging Face** | Corpus / model artifacts | A–Z text, models | public by default |

**Corrected vs earlier drafts:** Cerebras has **no free tier** ($5 trial credit, expires in 30
days, requires a verified payment method) — remove it as a fallback. Gemini free is **20 req/day**
on Flash, not a workhorse. Turso free is 5 GB. **OpenRouter was already present** in
`03-MODEL-STRATEGY.md`; an earlier review of mine called it missing — that was my error.

## 3. How the platforms connect — one fabric, many adapters

### 3.1 MCP is now the standard pipe (spec `2026-07-28`)

The MCP primitives map almost one-to-one onto things this project already hand-rolled:

| MCP primitive | What it replaces in LYA |
|---|---|
| **Stateless core** — no handshake, no session id | our own session handling; any request can land on any instance behind a plain load balancer |
| **`Mcp-Method` / `Mcp-Name` headers** | **authorize *before* the tool runs** → `security/policy.py`'s default-deny, enforced at the protocol layer |
| **Cacheable list results** (cache hints, deterministic order) | tool catalogs cache; **upstream prompt caches stay stable** → faster *and* fewer billed tokens |
| **Multi Round-Trip Requests** (sampling/elicitation) | **the phone-approval flow** — ask the owner mid-tool |
| **Tasks extension** | **the durable job store** |
| **Extensions framework + 12-month deprecation policy** | safe to build on; no surprise breakage |

Sources: the `2026-07-28` specification post on `blog.modelcontextprotocol.io` (checked
2026-09-24), and MCP's own ecosystem page listing OpenRouter's **Jev/TypeSafe** tutorial —
i.e. the two 2026 systems in this plan already meet at MCP.

### 3.2 The adapter contract (one interface, every platform)

```
Adapter(
  read(query)        -> records
  write(record)      -> receipt
  search(query, k)   -> ranked refs
  auth()             -> handle
  rate_budget()      -> {requests_left, tokens_left, reset_at}
  health()           -> {ok, latency_ms, degraded}
  reconcile(local)   -> diffs
  egress_class()     -> public | derived | private_never
)
```

Swapping Notion / Supabase / Turso becomes an adapter change, never a brain change. **No
platform is imported directly by L3/L4 code.**

### 3.3 The egress ledger — what makes free cloud models safe to use

Every byte that leaves the device is logged: `{at, provider, class, purpose, tokens}`.
`egress_class() == private_never` is refused **by the transport layer, not by convention**.

Tier‑2 grounding (`03-MODEL-STRATEGY.md`) is precisely the moment private data leaves the
device — so it requires an **explicit, recorded per-provider data-policy check**. The plan
currently examines capacity and rate limits but never data policy; that is the gap.

### 3.4 Degradation ladder (offline-first)

```
rules/registry → local static-embedding router → cached answer
   → Groq → OpenRouter pool → Gemini (rare) → ABSTAIN HONESTLY
```

A cloud outage must leave LYA **slow but correct**, never silent. Today it is neither:
`brain/mind.py:129` collapses *every* provider failure into one prose string, and the handler at
`mind.py:163-164` is **unreachable** because `_chat()` never raises.

## 4. Capacity — the honest arithmetic

Personal facts <5 MB · 500 passwords <1 MB · calendar ~15 MB/5 yr · notes 50–200 MB · skills text
50–500 MB · biometrics <50 MB. **Everything except media fits in under 1 GB**, against a free
ceiling of ~750 GB. Capacity was never the problem.

**Automation does not need space; it needs durability and audit.** A resumable job store plus an
append-only audit log, kept 5 years, is **tens of megabytes**. Do not plan capacity for
automation — plan resumability and audit instead.

Media is the only real growth, and it is already leaking: `shots/` and `debug/` hold
**unencrypted** PNG/WAV files today (367 KB + 1.9 MB, measured 2026-09-24) — apply the retention
purge (**S-8**).

---

## 5. Decisions this file proposes

| # | Decision | Proposal |
|---|---|---|
| P-1 | Fast cloud brain | Groq `gpt-oss-20b`, cache-first |
| P-2 | Fallback pool | OpenRouter `:free` router — one API, many providers |
| P-3 | Long context | Gemini, **manual and explicit**, never inside a loop |
| P-4 | Always-on host | Oracle **PAYG** (stays $0 inside free limits, immune to idle reclaim) |
| P-5 | Blob store | R2 — encrypted blobs only |
| P-6 | Phone path | Worker + D1 as the auth gate; no DB credentials on the phone |
| P-7 | Push | ntfy for off-device delivery |
| P-8 | Interop | MCP `2026-07-28` for tools/resources; adapter contract locally |
| P-9 | Secrets | **never** on a third-party platform — vault + portable recovery key only |
| P-10 | Egress | default-deny transport + egress ledger + per-provider data-policy check |

---

## Change log

### 2026-09-24 — Platform roles + connection fabric proposed
**Goal:** decide which platform stores what, and how they connect, for a build that executes on
another device.
**Changed:** this file created — an 8-criterion scoring basis, a role matrix, the adapter
contract, the egress ledger, the degradation ladder, and 10 proposed decisions (P-1…P-10).
**Verified by:** vendor pages fetched and read on 2026-09-24 — Oracle Always Free resources,
Cloudflare R2 pricing, Supabase pricing, Notion pricing + file-limit help page, Groq rate limits,
Turso pricing, Cerebras rate limits, Google Gemini rate limits, the MCP `2026-07-28`
specification post, TypeSafe's Jev announcement.
**Left undone / follow-up:**
- Cloudflare Workers/D1 free CPU-time limit — **unverified**, must be checked before P-6.
- GitHub free private/LFS limits — **unverified** this session.
- Per-provider data-policy check for anything that will receive grounded memory (P-10) — not
  yet performed for any provider.
**Notes:** three corrections to earlier drafts — Cerebras has no free tier; Gemini free Flash is
20 req/day; Turso free is 5 GB. And **OpenRouter was already in `03-MODEL-STRATEGY.md`**; an
earlier review of mine wrongly called it missing.


