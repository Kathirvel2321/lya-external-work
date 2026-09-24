# 01 — OPTIONS MATRIX: what your machine can actually do

> Availability verified against vendor documentation on **2026-09-24** for **Windows 11 Home
> Single Language**. RAM costs are estimates for this laptop (7.71 GB usable) and are labelled as
> such.

---

## The isolation ladder (strongest boundary at the top)

| Rank | Option | Boundary strength | Why |
|---|---|---|---|
| 1 | **Separate physical machine** (your VivoBook) | strongest practical | no shared anything except the network |
| 1 | **Cloud VM** (Oracle ARM, 2 OCPU/12 GB) | strongest practical | different machine, different network, in a datacenter |
| 3 | **Local full VM** (VMware/VirtualBox) | strong | separate kernel + separate virtual disk; the host hypervisor is the wall |
| 4 | **WSL2** (Ubuntu) | medium | its own Linux kernel in a light VM, **but shared filesystem/interop by default** |
| 5 | **Container** (Docker on WSL2) | weak | shares the kernel; packaging tool, not a security boundary |
| 6 | **Separate Windows user account** | very weak | protects against **accidents**, not against an attacker |
| 7 | **Dual boot bare-metal Linux** | **none at runtime** | one OS runs at a time; also risks your only laptop's bootloader |

**The rule that falls out of it:** isolate where the *consequence* is worst, using the strongest
boundary you have. Your worst consequences are generated code, scrapers, and untrusted content — so
they belong at ranks 1–3, not rank 5 or 6.

---

## Availability on *your* machine

| Option | Available on Win11 Home? | RAM cost (estimate) | Setup effort | Verdict |
|---|---|---|---|---|
| **Windows Sandbox** | ❌ **no** — Microsoft: *"not supported on Windows Home edition"*; needs Pro/Enterprise/Pro Education/Education | n/a | — | ✗ unavailable |
| **Hyper-V Manager** | ❌ no (Hyper-V role needs Pro/Enterprise) | n/a | — | ✗ unavailable |
| **WSL2 (Ubuntu)** | ✅ **yes** — `wsl --install`, needs admin once + a reboot; uses Virtual Machine Platform, not full Hyper-V | ~0.5–2 GB | **low** (one evening) | ✅ **start here** |
| **VMware Workstation Pro** | ✅ yes — **free for personal *and* commercial use** since 2024‑11‑11 (no support entitlement) | 1.5–2 GB for a headless Linux guest; **4 GB+ for a Windows guest — not viable on 7.71 GB** | medium | ✅ for a Linux guest; ⚠️ Windows guest out of RAM budget |
| **VirtualBox** | ✅ yes | similar to VMware | medium | ✅ acceptable alternative |
| **Docker Desktop** | ✅ yes (WSL2 backend) | ~1–2 GB | low | 🟡 for *packaging*, not isolation |
| **VivoBook as test rig** | ✅ it exists | 0 on the main laptop | none | ✅ **best use of that machine** |
| **Oracle Always Free VM** | ✅ independent of Windows | 0 (it is elsewhere) | medium | ✅ **the recommended workshop** |
| **Bare-metal dual-boot Linux** | ✅ possible | 0 | **high risk** | ⛔ not at the testing stage |

**Two facts already true on your machine:** `HypervisorPresent = True` (virtualization is enabled in
firmware, so WSL2/VMware will work), and **WSL is not installed yet** (verified).

---

## What each option actually protects against

Mapped to the adversaries in `../lya-brain/11-THREAT-MODEL.md` §2:

| Option | A0 accident | A1 commodity malware | A2 stolen laptop | A3 local attacker | A4 remote via LYA | A5 AI-armed |
|---|---|---|---|---|---|---|
| Cloud VM (workshop) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (bounded) |
| VivoBook as test rig | ✅ | ✅ | 🟡 | ✅ | ✅ | ✅ |
| Local full VM | ✅ | ✅ | 🟡 | 🟡 | ✅ | ✅ |
| WSL2 | ✅ | 🟡 | ❌ | ❌ | 🟡 | 🟡 |
| Container | ✅ | ❌ | ❌ | ❌ | 🟡 | 🟡 |
| Separate user account | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

**Read the WSL2 row carefully.** It is excellent for *"I do not want a broken experiment to wreck my
Windows install"*, and useless for *"someone is already on my Windows machine"*. Use it for speed,
not for safety.

---

## The recommended combination ($0)

| Role | Where | Why |
|---|---|---|
| **Real workshop — risky work, generated code, scrapers, network tools** | **Oracle ARM VM (PAYG, stays $0)** | strongest boundary, zero laptop pressure, off when you close the lid |
| **Fast local scratch — quick scripts, tests, rendering** | **WSL2 on the laptop**, no `/mnt/c` mount, capped at 2 GB | speed of local file access without exposing your profile |
| **Sacrificial experiments you would not run anywhere else** | **VivoBook**, short sessions, wiped after | it is the machine whose loss costs least |
| **Crown jewels, identity, memory, audit** | **MSI laptop, Zone A, unchanged** | already the smallest, most boring surface you have |

---

## Change log

### 2026-09-24 — Options matrix compiled
**Goal:** establish which isolation options the owner's actual hardware and Windows edition permit.
**Changed:** this file created — a seven-rank isolation ladder, an availability matrix verified for
Windows 11 Home, an adversary-coverage table, and the recommended $0 combination.
**Verified by:** Microsoft Learn Windows Sandbox page (updated 2026‑03‑29 — Home unsupported),
Microsoft Learn WSL install page (`wsl --install`, Win10 2004+/Win11), VMware blog (free since
2024‑11‑11). Local: `Win32_OperatingSystem` → Windows 11 Home Single Language build 26200;
`HypervisorPresent = True`; `wsl --status` → **not installed**; no VirtualBox/VMware/Docker Desktop
binaries present; 7.71 GB RAM; 210.6 GB free.
**Left undone / follow-up:** RAM costs are **estimates** and must be replaced with measurements from
`bench_latency.py`/Task Manager once a sandbox exists. The VivoBook's specs are unmeasured.
**Notes:** the biggest surprise for most people is that Windows Sandbox — the obvious choice — is
unavailable on Home, while VMware Workstation is free. Verify current licensing before commercial use.
