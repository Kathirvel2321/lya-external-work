# 11 — THREAT MODEL (what we defend, and what we cannot)

> **Status: PROPOSAL, 2026-09-24.** Owner request: *"not just simple security — no one can hack
> it, and if they do, they still cannot reach my passwords or important files."*
> This file answers that honestly; `12-ZERO-DISCLOSURE.md` and `13-SELF-PROTECTION.md` specify
> the controls.

---

## 0. The honest claim (read this before anything else)

**"Unhackable" does not exist.** Anyone who promises it is either mistaken or selling something.
`LYA_VISION.md` already refuses that claim — that refusal is correct and must never be removed for
marketing.

**But the goal underneath your question is achievable, and it is strong:**

> **COMPROMISE ≠ DISCLOSURE.** An attacker who fully owns the laptop must still be unable to read
> your top-tier secrets, because the key that opens them is not on the laptop.

Three guarantee classes, each *testable* (tests in `12-ZERO-DISCLOSURE.md` §7):

| # | Guarantee | Meaning |
|---|---|---|
| **G1** | **Confidentiality of the top tier** | files + machine ≠ readable. Needs a factor held off-device. |
| **G2** | **Contained blast radius** | one compromised subsystem does not unlock the others (compartments) |
| **G3** | **Tamper-evidence + recovery** | we can prove *that* we were attacked, and return to a known-good state |

**What we explicitly do NOT guarantee** — saying this out loud is part of the design:

1. **An attacker with admin and an interactive session while you unlock.** A compromised OS can
   capture your passphrase as you type it. Hardware-backed factors shrink this; nothing removes
   it. The honest boundary: *data at rest and historical disclosure are protected; the live moment
   of use is not.*
2. **Physical coercion** — rubber-hose, or a court order compelling your passphrase.
3. **Zero-days** in Windows, Python, `cryptography`, or the CPU itself.
4. **Supply-chain compromise** upstream of us (mitigate, do not eliminate).
5. **Owner error** — passphrase kept beside the recovery file, a reused password.
6. **A resourced state-level adversary** with physical access and unlimited time.

Naming these is not defeatism. A threat model that claims to defend everything defends nothing,
because it cannot tell you where to spend effort.

## 1. Assets, ranked by damage if disclosed

| Asset | Today's home | Damage | Current protection | Gap |
|---|---|---|---|---|
| **Master key** | `security/.lya_key` (DPAPI-wrapped) | **total** — opens everything | DPAPI → Windows account | **one key for all tiers**; dies on reinstall (`00-VAULT-RECOVERY.md`) |
| Passwords / API keys / tokens | `security/*.lya` | severe, external accounts | Fernet AES‑256 under that one key | shares the key with everything else |
| Memory DB | `brain/lya_brain.db.lya` | severe, personal life | same key | same key |
| **Biometrics** | `vision/*.lya`, `admin` columns | **permanent** — a face cannot be re-issued | same key | must be compartmented (`ADR-004`) |
| Recovery key + passphrase | paper + your head | **total, forever** | PBKDF2 600k | add Argon2id + off-device factor |
| Audit log | `skills/lya_actions.log.lya` | reveals *how* you are attacked | encrypted | **not tamper-evident** (no hash chain) |
| **Offensive toolkit on disk** | `skills/hacker.py` (10.0 KB), `kali.py` (10.7 KB), `learnhack.py` (16.5 KB), `autonomous.py` (7.3 KB) | makes *you* the suspect; hands malware a ready-made capability store | unrouted (D‑15) | **quarantine — see `13-SELF-PROTECTION.md` §6** |
| **Unencrypted media** | `shots/*.png` (367 KB), `debug/*.wav` (1.9 MB) | screenshots/audio leak on theft | **none** — measured 2026‑09‑24 | purge + stop writing plaintext (S‑8) |
| The whole disk | Windows volume | everything above, *if the disk is unencrypted* | **BitLocker UNVERIFIED** — query needs elevation, returned `Access denied` | **verify first; largest single gap** |

**BitLocker matters more than most of this file.** If the volume is unencrypted, a stolen laptop
leaks `shots/`, `debug/`, browser data and every temp file — and the vault protects only its own
files.

---

## 2. Adversaries (who we actually defend against)

| # | Adversary | Likelihood | Our posture |
|---|---|---|---|
| **A0** | **Accident** — you, a crash, a bad update, a reinstall | **highest by far** | backup + restore drill + recovery key |
| A1 | Commodity malware / infostealer | high | disk encryption, no plaintext secrets, compartment keys |
| A2 | Thief with the powered-off laptop | medium | BitLocker + DPAPI + compartments |
| A3 | Local attacker **with your Windows account** | medium | **this is the project's stated threat model** (`README`); compartments are the answer |
| A4 | Remote attacker via LYA's own surfaces (`web_server.py`, cloud, MCP servers) | rising | token+nonce+HTTPS already; add header-based authz + tool pinning |
| **A5** | **AI-armed attacker** | **growing fast** | see below — changes *speed and scale*, not fundamentals |
| A6 | State actor / insider with physical access + time | low | **out of scope; say so** |

**On A5 — your instinct is right, and here is the data.** AI does not make an attacker smarter than
you; it *removes the skill floor and multiplies speed*. An AI-orchestrated cyber-espionage
campaign (reported late 2025, tracked as MITRE ATT&CK Campaign C0062) automated reconnaissance and
intrusion steps across ~30 targets. Enterprise agent counts are projected to grow from
**28.6 million (2025) to 2.2 billion (2030)** — a target surface growing faster than defenders can
staff.

**Consequence for LYA:** the answer is not "a better model". It is **fewer doors, verified pipes,
no ambient authority** — exactly what `12` and `13` specify.

---

## 3. Mapping to the 2026 standards (so we are not inventing a taxonomy)

OWASP published its **Top 10 for LLM Applications 2026** on 2026‑08‑03, ranked for the first time
using **real incident data** (7,714 reported AI security incidents, 6,639 classifiable) blended
with expert voting. The movements matter to us specifically:

| OWASP 2026 category | Movement | LYA instance | Control |
|---|---|---|---|
| **Prompt Injection** (#1, third year) | expanded to **cross-modal** (images/audio), **memory persistence**, agentic blast radius | a poisoned document, web page, or MCP tool description instructing LYA | `12` §5 |
| **Sensitive Information Disclosure** (#2) | held | memory/facts leaving the device in a grounded prompt | `12` §4 |
| **Excessive Agency** (#3) | **6th → 3rd** | LYA gaining multi-step tool authority | `12` §5, `13` §2 |
| **Unbounded Consumption** (#6) | **10th → 6th** | an automation loop burning RAM/disk/API quota or money | `13` §3 |
| **Hidden Context Exposure** | renamed/broadened from *System Prompt Leakage* | policy/config disclosure | `12` §4 |
| *(agentic)* OWASP Top 10 for Agentic Applications 2026 | new | agent-specific planning/tooling risk | `12` §5 |

Also worth using, and free: CSA's **AICM v1.1** (control catalog) and **MAESTRO** (agentic threat
modelling). OWASP itself warns about the **"defense effect"** — a low incident count can mean
"well defended", not "safe". Do not read absence of incidents as safety. **This document carries a
version and a date for exactly that reason: it expires.**

## 4. Trust boundaries

**Everything outside LYA's own signed code is untrusted input** — including model output, tool
results, MCP tool descriptions, web pages, documents, your own notes if they came from the web,
and the phone.

```
   [ YOU ]  ===== passphrase (never typed into LYA while online) =====>  [ PAPER ]
      |                                                                     ^
      v                                                                     |
+-------------------- LAPTOP (untrusted if compromised) ----------------------+--+
|  Windows OS  -- BitLocker? UNVERIFIED --                                    |  |
|      |                                                                      |  |
|      v                                                                      |  |
|  [ LYA PROCESS ] -- policy.py (default-deny) -- registry -- audit(chain)    |  |
|      |            \                                                         |  |
|      |             \-- [ VAULT ] -- per-compartment keys -- needs OFF-DEVICE factor (phone)
|      v                                                              |       |  |
|  [ MODEL OUTPUT ] == untrusted ==                                   |       |  |
|      |                                                              v       |  |
|      v                                                        [ PHONE SECRET ]  |
|  [ TOOL RESULT ]  == untrusted ==                                   |       |  |
+------|---------------|---------------------------------------------|----------+
       v               v                                             |
  [ CLOUD MODEL ] [ MCP / WEB / FILES ] == untrusted, hostile ==      |
       |               |                                             |
       +-----> EGRESS GATE (allow-list + classification + ledger) <---+
```

**Two rules fall out of it:**
1. **Untrusted text may never become an instruction.** Data stays in the data channel; only signed
   code and owner-typed commands enter the instruction channel.
2. **Nothing outside the process may hold a key.** Credentials are resolved inside the vault and
   never travel to a model, a log, an adapter, or a prompt.

---

## 5. Assumptions we depend on (if one breaks, this model is void)

- The Windows account is not already compromised at boot. *(A3 is handled by compartments, not by
  identity checks.)*
- **BitLocker (or equivalent) is ON.** *Unverified today — needs elevation.*
- `cryptography`'s primitives are sound and not backdoored.
- The passphrase is kept **off** the machine and reused nowhere.
- The phone factor is genuinely separate (not a file copied onto the laptop).
- LYA is **never run elevated**. Today the account is *not* admin — **keep it that way.**

## 6. Honest scorecard — what exists today (2026‑09‑24)

**Genuinely strong (keep; do not "improve" these):** default-deny policy (`security/policy.py:26` —
an unknown action denies); in-memory SQLite with atomic encrypted commit
(`security/database.py:36-46`); nonce-bound, one-time, expiring phone grants with fail-closed
lockout (`security/escalation.py`); build mode with no sensors or memory; guest prompts carrying no
saved facts.

**Weaknesses found, with evidence:**

| # | Weakness | Evidence | Severity |
|---|---|---|---|
| W‑1 | **One key opens everything** — secrets, memory, biometrics share the master key | `security/vault.py:31` (single `_F`) | **critical** |
| W‑2 | **The vault's own second factor leaves the device** — audio containing the spoken security word is uploaded to Groq Whisper | `security/auth_wall.py:88-102` | **critical** |
| W‑3 | Cloud key read from an environment variable | `auth_wall.py:98` | high (S‑2) |
| W‑4 | No rate limit or lockout inside the auth wall | `auth_wall.py:114` | high |
| W‑5 | Thresholds hardcoded and uncalibrated (face 0.45, voice 0.75) | `auth_wall.py:60,82` | high (D‑13) |
| W‑6 | Plaintext temp file + full-DB rewrite per ingest | `brain/knowledge.py:58,76` | high |
| W‑7 | `shell=True` / `os.system` interpolation still on disk | `skills/device.py:50` | high (S‑3) |
| W‑8 | No tamper-evident audit (no hash chain, no off-device digest) | design gap | high |
| W‑9 | Unencrypted media on disk | `shots/`, `debug/` (measured) | medium (S‑8) |
| W‑10 | No egress control — nothing stops secrets going outward | design gap | high |
| W‑11 | No tool-description pinning → **MCP tool poisoning** applies | TPA class | high |
| W‑12 | Duress path built but **unreachable** | `escalation.py:310` (`hasattr` guard) | medium |
| W‑13 | Offensive toolkit on disk | `skills/hacker.py`, `kali.py`, `learnhack.py` | medium–high |
| W‑14 | No self-integrity check; kill switch not wired into `main.py` | design gap | medium |
| W‑15 | No post-quantum plan for long-lived secrets | design gap | low now, rising |

Controls for every row are in `12-ZERO-DISCLOSURE.md` and `13-SELF-PROTECTION.md`.

---

## 7. Change log

### 2026-09-24 — Threat model created
**Goal:** answer the owner's request for security beyond "simple", without making a false claim.
**Changed:** this file created — honest guarantee classes (G1–G3), explicit non-guarantees, asset
ranking, six adversary classes including AI-armed, OWASP 2026 mapping, trust boundaries,
assumptions, and a 15-row weakness scorecard with file:line evidence.
**Verified by:** reading `security/policy.py`, `security/database.py`, `security/auth_wall.py`,
`security/vault.py`, `brain/memory.py`, `brain/knowledge.py`, `skills/device.py`; local queries
`Win32_OperatingSystem` (Windows 11 Home, build 26200, **user is not admin**) and TPM/BitLocker
(**both `Access denied`** — elevation required); a file inventory of `shots/` and `debug/`.
**Left undone / follow-up:**
- **Verify BitLocker** in an elevated shell — the largest unknown in this model.
- Confirm TPM 2.0 presence (also needs elevation).
- W‑1…W‑15 each need an ADR and a test before they may be called closed.
**Notes:** the owner's AI-attacker concern is well founded — prompt injection has led OWASP's list
three years running, and *Excessive Agency* moved 6th → 3rd precisely as agents began acting rather
than reading.



