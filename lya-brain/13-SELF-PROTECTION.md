# 13 — SELF-PROTECTION, BLAST RADIUS AND LONG-TERM SECURITY

> **Status: PROPOSAL, 2026-09-24.** Owner ask: *"LYA must not do something that can totally boom
> the LYA system"*, and *"many new techniques will come and go, many hackers will become more
> advanced — we have to stay up to date."*
> This file covers the two halves of that: **she must not destroy herself**, and **she must not age
> out of date.**

---

## 1. Least privilege: the cheapest large win

- **Never run elevated.** Measured today: the Windows account is **not** administrator. **This is a
  security feature — keep it.** An assistant running as admin converts every bug into a
  system-wide compromise.
- Deny-list by default, allow-list for apps, and **no arbitrary shell**: `skills/device.py:50`
  (`shell=True`) and the `os.system(f"taskkill /f /im {name}.exe")` pattern must be deleted, not
  "guarded" — an allow-list of exact app names cannot express arbitrary text (S‑3).
- Every tool gets `timeout_ms`, and non-idempotent tools get an idempotency key
  (`contracts/tool_descriptor.schema.json`).
- **No elevated installs from within LYA.** Installation steps are proposed to the owner, who runs
  them — the current `skills/autonomous.py` pattern of driving installs is the opposite of this
  rule.

---

## 2. She must not boom herself: self-preservation rules

| Rule | Why |
|---|---|
| She may **never** modify her own security-critical files (vault, policy, registry, audit writer) | a self-modifying security core has no security core |
| She may **never** delete, overwrite, or "clean up" her own recovery material or backups | recovery is the last line; automate it out and nothing is left |
| She may **never** disable, truncate or bypass the audit log | the log is evidence; a gap is indistinguishable from an attack |
| Policy changes require an **owner-approved ADR**, never a runtime change | D‑2 and D‑7 in one place |
| Everything she changes is **versioned and revertible** (atomic write + previous version kept) | so a bad change is a rollback, not a loss |
| **Resource guards**: max RAM/disk/CPU, max tokens/minute, max job duration, max file count | see §3 |
| **Crash-loop breaker**: after N failures in M minutes, stop and report | otherwise a bug becomes a disk-filling loop |
| **Safe mode**: on an integrity-check failure, boot read-only with automation disabled and say so loudly | fail *closed and visible*, never silently degraded |
| **Emergency stop** that works even if the UI is dead — file-based kill switch + watchdog | `skills/autonomous.py` already expects a `KILL_SWITCH` path; wire it into `main.py` (W‑14) |

**The principle:** every one of these rules limits what LYA can do *to herself*. That is what makes
"she can't boom the system" a property rather than a hope.

---

## 3. Blast radius: what a bug can cost (OWASP #6, *Unbounded Consumption* — 10th → 6th in 2026)

This jumped four places because agents genuinely burn resources. Guards:

| Resource | Guard |
|---|---|
| API quota / money | per-provider token bucket, a **reserve** never spent, hard per-task cap, and a "stop when the budget is gone" path that degrades honestly |
| Disk | per-directory size cap, retention purge, refuse to write when free space < N GB |
| RAM | the CPU-only constraint (`09-LOCAL-STACK-CPU.md`) already forbids co-resident heavy models; enforce it with a free-RAM check |
| CPU/heat | throttle background jobs when on battery or above a temperature threshold |
| Files | no unbounded recursion, no "clean up my disk" style commands without an explicit plan approval |

**Rule of thumb:** any action whose worst case is "worse than doing nothing" requires a plan
approval. Deleting, moving, resizing, installing, uploading: never silent, never automatic.

## 4. Recovery: assume breach, engineer for it

You cannot promise "no breach". You *can* promise "we detect it, contain it, and come back". That is
the only durable posture, and it is also the answer to your "no security breach or bug" concern:
bugs are certain, so the design goal becomes **recoverable**, not **perfect**.

**3‑2‑1 adapted to LYA:**

| Copy | Where | Contains |
|---|---|---|
| 1 | local, encrypted | live stores |
| 2 | off-device (R2), ciphertext only | backups — separate credentials from anything LYA can read |
| 3 | offline | the recovery key on paper + passphrase in your head |

**Rules that make the backup real:**
- **Never** back up T0 wrapping material with T0 ciphertext.
- **Never** back up T2 biometrics at all (a leaked face cannot be re-issued — `ADR-004`).
- **Restore drills are mandatory**: a copy you have never restored from is not a backup. Quarterly,
  documented, with the test suite run afterwards.
- Recovery must **not depend on LYA running**: a standalone script must be able to open a backup on
  a bare machine. `recovery/vault_recovery.py` already satisfies this for the key.

**Incident response playbook (write it on one page, keep it offline):**

1. **Detect** — chain break, honeytoken read, anomaly (mass decrypt, unusual egress, auth spike).
2. **Contain** — kill switch; revoke provider tokens; take LYA offline (network is optional).
3. **Preserve evidence** — copy the audit chain, digests, and `.lya` files *before* touching
   anything. Assume the attacker is still present.
4. **Rotate** — every credential in T0, then the root KEK.
5. **Restore** — from a pre-incident backup, verify integrity, re-run all tests.
6. **Learn** — the incident becomes a **new row in `evals/redteam.jsonl`**, and a new ADR if a
   design assumption was wrong.

Step 6 is the whole mechanism. Without it, you re-learn the same lesson from the next attacker.

---

## 5. Staying current in a 5-year project (crypto agility + cadence)

The threat landscape moves, and so do the standards. The defense is a **schedule**, not vigilance:

| Cadence | Action |
|---|---|
| **Monthly** | dependency + CVE review; `pip freeze` compared to the SBOM; nothing upgrades silently |
| **Quarterly** | restore drill; red-test run (`evals/redteam.jsonl`); re-check BitLocker/TPM state; read the OWASP GenAI project's updates |
| **Twice a year** | review this threat model against the current OWASP LLM/Agentic Top 10 and CSA **AICM**; revise rankings |
| **Annually** | key rotation; review PQC migration status; review whether any compartment should be split or merged |
| **On every change** | red-test gate; a security regression must fail a test |

**Crypto agility — the specific long-term requirement.** Long-lived secrets (passwords you will hold
for years) are exposed to "harvest now, decrypt later": ciphertext captured today is expected to be
decryptable once quantum hardware matures. NIST's post-quantum standards (FIPS 203/204/205) are
finalized; adoption across libraries is uneven. So:

- **Do now:** ensure every ciphertext carries an **algorithm/version header** so data can be
  re-encrypted without loss (the recovery file already does this — generalise it), and document the
  rotation procedure.
- **Do next:** when `cryptography` (or another vetted library) exposes stable hybrid PQC KEMs,
  migrate the *key wrapping* first (small, low-risk, high value), then the bulk encryption.
- **Do not:** hand-roll post-quantum crypto, and do not let a blog post drive this. Library support
  or it waits.

**Standards to watch (free, and they update):** OWASP GenAI Security Project (LLM + Agentic Top 10),
CSA **AICM v1.1** control catalog, CSA **MAESTRO** for agentic threat modelling, the MCP
specification changelog (it carries a **12-month deprecation policy**, so upgrades can be planned),
and Microsoft/Google threat-intelligence blogs for real-world agent attacks.

## 6. A specific recommendation: quarantine the offensive toolkit

The repository currently ships **offensive security modules** on disk:

| File | Size | What it is |
|---|---|---|
| `skills/hacker.py` | 10.0 KB | recon / netscan / wifi / portscan / hash / password helpers |
| `skills/kali.py` | 10.7 KB | Kali-style tooling wrapper |
| `skills/learnhack.py` | 16.5 KB | 700+ technique corpus + loader |
| `skills/autonomous.py` | 7.3 KB | install/walkthrough driver using `subprocess` + `webbrowser` |

**Recommendation: move them out of the import path (e.g. `legacy/offensive/`), or delete them.**
Reasons, in order:

1. **They add zero defensive value.** None of them protects you; all of them can act on a machine.
2. **They are a capability store for anyone who compromises the machine.** Malware that reaches LYA
   inherits a reconnaissance toolkit. That is the opposite of reducing blast radius (G2).
3. **They create legal exposure for you.** An assistant that performs or automates intrusion against
   third parties makes *you* the suspect, regardless of intent. `LYA_VISION.md` §"Learning and
   security clarification" already refuses the police/investigative framing for exactly this reason.
4. **D‑15 already keeps them unrouted** — they are dead weight with live risk. The risk is that
   "one careless wiring change" (the project's own phrase from `LYA_RESEARCH.md` S‑3) makes them
   reachable.
5. **Keep what is genuinely defensive:** `skills/security_brain.py` (knowledge), the policy/
   escalation code, and the anti-spoofing stack. Knowledge ≠ capability; the distinction is already
   drawn in `06-SKILL-LIBRARY.md`.

If the corpus is wanted for study, keep the **text** in the knowledge vault (Obsidian, `S-security/`)
where it is inert — and never inside the import path of a running assistant.

**Also stop the self-installing pattern.** `skills/autonomous.py` driving package installs from
inside the assistant contradicts §1's least-privilege rule. Installs are proposed to the owner, who
runs them.

---

## 7. Security ADRs to raise

Register these as `ADR/SEC-0NN-*.md` (template: `ADR/ADR-000-template.md`). All start `PROPOSED`.

| # | Decision |
|---|---|
| SEC-001 | **Compartmental key hierarchy (T0–T3)** — one key never opens two tiers |
| SEC-002 | **Off-device factor required for T0** (phone secret or hardware key), with two offline escrows |
| SEC-003 | **Argon2id** for passphrase KDF (replacing/alongside PBKDF2 600k) once availability is verified |
| SEC-004 | **The spoken security word never leaves the device** — local phrase check; fixes W‑2 |
| SEC-005 | **Egress default-deny** + allow-list + secret scan + ledger |
| SEC-006 | **Tool-description pinning** and a tool/package allow-list (MCP poisoning defense) |
| SEC-007 | **Two-channel rule**: untrusted content can never be an instruction |
| SEC-008 | **Hash-chained, append-only audit** + off-device digest |
| SEC-009 | **Self-integrity manifest + safe mode**; LYA may never edit her own security core |
| SEC-010 | **Resource guards + crash-loop breaker** (OWASP #6 Unbounded Consumption) |
| SEC-011 | **Offensive toolkit quarantine** (§6) |
| SEC-012 | **Crypto agility**: versioned ciphertext headers + documented rotation + PQC migration path |

---

## 8. Change log

### 2026-09-24 — Self-protection and long-term security specified
**Goal:** make "she must not boom the system" and "we must stay current" into engineering rules.
**Changed:** this file created — least-privilege rules, nine self-preservation rules, resource/
blast-radius guards, the 3‑2‑1 recovery model, a six-step incident-response playbook, a maintenance
cadence with crypto-agility requirements, the offensive-toolkit quarantine recommendation, and
ADR register SEC‑001…SEC‑012.
**Verified by:** local measurement 2026-09-24 — the Windows account is **not** administrator
(`WindowsPrincipal.IsInRole(Administrator)` → `False`), which §1 treats as a control to preserve;
file inventory of the offensive modules and their sizes; `skills/device.py:50` (`shell=True`);
`skills/autonomous.py` import line (`subprocess`, `webbrowser`). Standards cited: OWASP LLM Top 10
2026, OWASP Agentic Top 10 2026, CSA AICM v1.1 / MAESTRO, NIST FIPS 203/204/205.
**Left undone / follow-up:**
- Elevation needed to verify BitLocker/TPM (currently `Access denied`).
- The offensive-toolkit decision is the owner's — this file recommends, it does not execute.
- The incident-response page does not exist yet; write it and keep an offline copy.
**Notes:** an honest long-term posture is *assume breach, detect, contain, restore, and add a test*.
Every incident must leave a new row in `evals/redteam.jsonl`; otherwise the same failure returns
wearing a different hat.


