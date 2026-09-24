# LYA PLATFORM — a separate place for her to work

> **Status: PROPOSAL, 2026-09-24.** Owner's plan: *"don't give full access on my current device at
> the testing stage — build LYA her own platform (a special Windows or Linux) for networking,
> coding, creating, storing and securing."*
>
> **Verdict: the plan is right, and it is the single best idea in this whole project so far.**
> It is also the cheapest one — **$0**.

---

## The one-sentence architecture

> **Your laptop holds the crown jewels and stays boring. The risky work happens in a workshop that
> contains nothing you would miss.**

```
ZONE A  "HOME"      the laptop you use — vault, identity, memory, policy, audit
                    minimal surface. No experiments. No untrusted content.
ZONE B  "WORKSHOP"  an isolated box — code, networking, automation, rendering, publishing
                    assume it WILL be infected one day. It holds no keys, no biometrics, no
                    personal files.
ZONE C  "FOREVER"   an always-on machine — scheduler, backups, consolidation, notifications
                    runs when your laptop is closed. Never touches secrets.

        A ──(narrow, audited bridge: artifacts out, secrets never in)── B ── C
```

---

## Why this answers your worry exactly

You said it yourself: at the testing stage, one bug, one bad generated script, one poisoned
web page, one Windows reinstall, and the machine holding your passwords and memories is a mess.
That instinct matches `11-THREAT-MODEL.md` §0 (**compromise ≠ disclosure**) and
`13-SELF-PROTECTION.md` §3 (**blast radius**). Isolation is how those stop being slogans:

| If this happens | On your laptop today | With the workshop |
|---|---|---|
| Generated code deletes the wrong thing | could reach your files | dies in a throwaway VM |
| A scraped page injects instructions | LYA's session is the target | the sandbox has nothing worth stealing |
| A test build corrupts a database | your real memory is at risk | rebuild the sandbox in minutes |
| A "harmless" tool is malware | your vault shares the blast radius | the vault was never mounted |

---

## Read in this order

| # | File | What it answers |
|---|---|---|
| **0** | [`00-VERDICT.md`](00-VERDICT.md) | Is the plan useful? Yes — plus the six things it will **not** do |
| **1** | [`01-OPTIONS-MATRIX.md`](01-OPTIONS-MATRIX.md) | Every isolation option, and which ones your **Windows 11 Home** edition actually allows |
| **2** | [`02-ARCHITECTURE.md`](02-ARCHITECTURE.md) | The three zones, the bridge, and what lives where |
| **3** | [`03-SANDBOX-SPEC.md`](03-SANDBOX-SPEC.md) | The concrete build: what is installed, what is forbidden, how it is rebuilt |
| **4** | [`04-HARDWARE-REALITY.md`](04-HARDWARE-REALITY.md) | Both laptops measured honestly — including why the fanless VivoBook must not be a server |
| **5** | [`05-ROADMAP.md`](05-ROADMAP.md) | Four stages, each with an exit test |

---

## What it costs

| Item | Cost | Notes |
|---|---|---|
| Oracle Always Free ARM VM (2 OCPU / 12 GB) | **$0** | the real workshop; convert to PAYG to avoid idle reclamation (`../lya-brain/08-PLATFORM-ROLES.md`) |
| WSL2 on the laptop | **$0** | one command, needs admin once + reboot; **not installed yet** |
| VMware Workstation Pro | **$0** | free for personal *and* commercial use since 2024‑11‑11 (no support included) |
| The fanless VivoBook | **$0** | already yours — as a *sacrificial test rig*, not a server |
| **Total** | **$0** | the only spend is a few evenings |

---

## What this does NOT fix (read `00` before deciding)

- It does **not** make LYA safe. It makes her failures **survivable** — a different and more
  honest goal.
- It does **not** remove the need for `ADR-SEC-001`/`002` (compartment keys + off-device factor).
  Isolation protects the *machine*; those protect the *data*.
- It does **not** remove the paperwork walls (`../lya-agency/02-VIDEO-PIPELINE.md`) — YouTube's
  audit and Instagram's permissions are account tasks, not sandbox tasks.
