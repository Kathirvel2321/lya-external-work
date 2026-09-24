# 02 — ARCHITECTURE: three zones and one narrow bridge

> The design goal is not "more security features". It is: **when something goes wrong, nothing
> important is in the same place as the failure.**

---

## The zones

```
        ┌─────────────────────────── ZONE A — "HOME" ───────────────────────────┐
        │  the MSI laptop · Windows 11 Home · the ONLY place private data lives  │
        │                                                                        │
        │  vault (T0)   memory (T1)   biometrics (T2)   policy   audit   orb     │
        │  ── read-only diagnostics ── identity ── approvals ── notifications ─  │
        │                                                                        │
        │  RULES: no generated code · no untrusted content · no scrapers ·        │
        │         no publishing · no installs without you                        │
        └───────────────────────────────┬────────────────────────────────────────┘
                                        │
                     THE BRIDGE (audited; artefacts out, secrets never in)
                                        │
        ┌───────────────────────────────┴──── ZONE B — "WORKSHOP" ───────────────┐
        │  Oracle ARM VM (2 OCPU/12 GB)  ·  WSL2 for fast local scratch          │
        │  ·  VivoBook as the sacrificial rig                                   │
        │                                                                        │
        │  generated code · scrapers · network tools · ffmpeg renders ·          │
        │  browser automation · API clients · untrusted document processing      │
        │                                                                        │
        │  RULES: NO keys · NO biometrics · NO personal files · assume it WILL    │
        │         be compromised one day · rebuildable in <15 minutes            │
        └───────────────────────────────┬────────────────────────────────────────┘
                                        │
        ┌───────────────────────────────┴──── ZONE C — "FOREVER" ────────────────┐
        │  same Oracle box (or a Cloudflare Worker) — runs while the laptop is    │
        │  closed                                                                │
        │                                                                        │
        │  scheduler · nightly backup · consolidation (L7) · ntfy notifications   │
        │  RULES: ciphertext only · never a key · never a model with private      │
        │         data unless that adapter is cleared                            │
        └────────────────────────────────────────────────────────────────────────┘
```

---

## What lives where (the rule that prevents 90 % of accidents)

| Thing | Zone A (laptop) | Zone B (workshop) | Zone C (forever) |
|---|---|---|---|
| Vault keys / `.lya_key` | ✅ only here | ⛔ **never** | ⛔ never |
| Passwords, tokens, security word | ✅ | ⛔ | ⛔ |
| Memory DB / personal facts | ✅ | 🟡 a *copy* for an approved task only — never the live store | 🟡 ciphertext backup only |
| Biometrics | ✅ | ⛔ **never** | ⛔ |
| Phone token / escalation grants | ✅ | ⛔ | ⛔ |
| Generated code before review | — | ✅ runs here | ⛔ |
| Scrapers, network scans, recon-ish tools | ⛔ | ✅ | ⛔ |
| Video renders, ffmpeg jobs | 🟡 short ones only | ✅ preferred | ✅ nightly batch |
| Browser automation | ⛔ | ✅ with its **own** profile, never yours | ⛔ |
| Scheduler, backups, notifications | 🟡 | 🟡 | ✅ |
| Audit log | ✅ authoritative | 🟡 local log, shipped to A | 🟡 |

**The one-line test for any new feature:** *"If this thing turns hostile, what does it touch?"*
If the answer includes the vault, biometrics, or your files — it belongs in B, and it may reach them
**only** through the bridge.

## The bridge — what may cross, and in which direction

| Direction | May cross | Must never cross |
|---|---|---|
| **A → B** | a task description, a data slice **you** chose, public URLs, per-task scoped API tokens | vault files, `.lya_key`, biometrics, phone token, your browser profile, cookies, saved passwords |
| **B → A** | finished artefacts (rendered video, generated HTML/CSV, reports, logs) into a **quarantine folder** | anything auto-executed, auto-merged, unread shell scripts, binaries |

**Bridge rules:**
1. **One-way for artefacts.** B writes to `quarantine/`; A imports only after you look.
2. **No shared mount of your home directory.** Ever. A dedicated exchange folder only.
3. **No execution on import.** An artefact is data until you approve it.
4. **Scan on import** (`../lya-brain/12-ZERO-DISCLOSURE.md` §4): secret scan for anything coming
   *in*, classification for anything going *out*.
5. **Credentials are per-task and expiring.** If B needs an API, it gets a scoped token that dies
   with the task — never your long-lived keys.

---

## What a compromise in each zone costs you

| Zone compromised | Consequence | Recovery |
|---|---|---|
| **B (workshop)** — the expected case | nothing important was there | destroy the VM, rebuild from image, rerun the task — **minutes** |
| **C (forever)** | ciphertext + job metadata | rotate the provider tokens it held; restore from Zone A |
| **A (home)** | your actual life | `11`–`13` apply: compartments + off-device factor + audit + restore drill |

**This table is the whole point of the plan.** Today, every failure lands in row A. After this
change, almost every failure lands in row B — and row B is designed to be thrown away.

---

## What is deliberately NOT in this design

| Not doing | Why |
|---|---|
| A "LYA OS" distribution of our own | maintaining a distro is a full-time job and adds nothing over a stock VM |
| Kernel/driver-level access | `../lya-agency/00-REALITY-CHECK.md` — refuses the possession model |
| Containers as the security boundary | shares the kernel; used for packaging only |
| Dual-boot on the only laptop | no runtime isolation, and it risks the bootloader |
| Moving the vault into the workshop | the one thing that must never be true |
| Running LYA elevated anywhere | `../lya-brain/13-SELF-PROTECTION.md` §1 |

---

## Change log

### 2026-09-24 — Zone architecture specified
**Goal:** define where LYA's work happens so failures stop landing on the owner's personal data.
**Changed:** this file created — three zones, a per-asset placement table, five bridge rules, a
compromise-consequence table, and a "not doing" list.
**Verified by:** consistency with `../lya-brain/12-ZERO-DISCLOSURE.md` (at-rest rules),
`../lya-brain/13-SELF-PROTECTION.md` (blast radius, resource guards) and
`../lya-agency/01-ACCESS-TIERS.md` (which tiers may act). Zone C maps to the Oracle role already
recorded in `../lya-brain/08-PLATFORM-ROLES.md` §2.
**Left undone / follow-up:** the bridge does not exist yet — the quarantine folder, the scoped-token
mechanism and the import scan must be built before any automated B→A flow is allowed.
**Notes:** the strongest single rule is "**no shared mount of your home directory**". A sandbox with
your `C:\Users` mounted is not a sandbox — it is a second door into the same room.

