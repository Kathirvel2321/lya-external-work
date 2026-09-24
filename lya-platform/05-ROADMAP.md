# 05 — ROADMAP: four stages, each with an exit test

> Rule from the project's own decision **D‑16** (*one feature at a time: text → verify → next*).
> A stage is finished only when its **exit test** has been run and its output recorded.

---

## Stage 0 — Decisions only (10 minutes, today)

**Do:** nothing technical. Write down three things and stick to them:

1. **The zone rule:** the vault, biometrics and phone token never enter Zone B.
2. **The bridge rule:** artefacts come back into a `quarantine/` folder and are never auto-executed.
3. **The one-at-a-time rule:** Zone A runs no heavy work while you are using the laptop.

**Exit test:** the three rules exist in writing in this folder. *(You can accept this document as
that record by saying so.)*

---

## Stage 1 — Local sandbox on the MSI (one evening)

**Do:** install WSL2, then apply the isolation settings from `03-SANDBOX-SPEC.md` §2 — interop off,
no `/mnt/c` usage, 2 GB / 2 CPU caps, one exchange folder. Install python, git, ffmpeg, playwright.

**Exit test (all three):**
1. `ls /mnt/c/Users` from inside the sandbox **fails**.
2. A test render or a Playwright run completes **while the laptop stays responsive**.
3. Task Manager shows the sandbox's memory **capped** at the configured limit.

**Cost:** ~1 hour, one admin prompt, one reboot. **Note:** installing WSL requires elevation once —
that is the *only* elevated step in this roadmap.

---

## Stage 2 — The real workshop (one evening)

**Do:** create the **Oracle Always Free ARM VM** (2 OCPU / 12 GB), convert the account to
**Pay-As-You-Go** so it is immune to idle reclamation (`../lya-brain/08-PLATFORM-ROLES.md` §2),
then: SSH-key-only login, no password auth, no inbound ports except SSH, a snapshot taken
immediately, and `ntfy` for notifications.

**Exit test:**
1. `ssh` from the laptop works with a key and fails with a password.
2. The VM survives a **reboot** and comes back with the services running.
3. A render or scrape runs on it while **both laptops are idle**.

**Why this is the centrepiece:** it is the only part of the plan that removes work from your
machines entirely, and it costs nothing.

---

## Stage 3 — Move the risky work across (a few evenings)

**Do:** migrate capability by capability, in this order (safest first):

| Order | Move | To |
|---|---|---|
| 1 | generated code execution, scrapers, network tools | Zone B |
| 2 | browser automation (its own profile) | Zone B |
| 3 | renders and batch jobs | Zone B/C |
| 4 | publishing (A4 tier) | Zone B/C |
| 5 | keep diagnostics (A1, read-only) | **Zone A** — it belongs there |
| never | vault, biometrics, approvals, identity | **Zone A only** |

Then build the **bridge**: quarantine folder, import scan, per-task scoped tokens.

**Exit test:** one complete real task (e.g. render → upload) runs end-to-end with **zero secrets** in
Zone B and every artefact passing through quarantine.

---

## Stage 4 — Prove it, then keep it true (ongoing)

**Do:** record real numbers, then put the maintenance on a calendar.

| Cadence | Action | Recorded where |
|---|---|---|
| Once | `bench_latency.py` on both the laptop and the VM | the numbers, not an adjective |
| Once | thermal reading during a real render on each machine | measured, per `04` §4 |
| Monthly | rebuild the sandbox from the recipe; re-run the boundary test | a line in the change log |
| Quarterly | restore drill + `evals/redteam.jsonl` run | `../lya-brain/12` §7 |
| On incident | new red-test row | `../lya-brain/13` §4 step 6 |

**Exit test:** you can destroy the sandbox and be working again in **under 15 minutes**, and you have
done it once for real.

---

## What NOT to do yet

| Don't | Why |
|---|---|
| Dual-boot Linux on the only laptop | no runtime isolation; bootloader risk |
| Reinstall the VivoBook with a server OS | it is fanless — the wrong machine for that job |
| Run LYA elevated "to make it work" | gives up the best control you have |
| Put the vault in the workshop "just for testing" | it only takes once |
| Build all four stages in one weekend | D‑16 exists because that is how projects die |

---

## Effort, honestly

| Stage | Time | Blocked by |
|---|---|---|
| 0 — decisions | 10 min | nothing |
| 1 — WSL2 sandbox | ~1 h | one admin prompt + reboot |
| 2 — Oracle VM | ~1 evening | account already exists (owner reports one) |
| 3 — migration + bridge | a few evenings | stages 1–2 |
| 4 — measurement + drills | ongoing | stage 3 |

---

## Change log

### 2026-09-24 — Isolation roadmap written
**Goal:** make the isolation plan executable in stages with verifiable exits.
**Changed:** this file created — four stages with explicit exit tests, a capability-migration order,
a maintenance cadence, a "not yet" list, and honest effort estimates.
**Verified by:** stage 1 prerequisites confirmed on this machine (`HypervisorPresent = True`, WSL not
installed, 210.6 GB free); stage 2 requirements taken from the already-verified Oracle Always Free
figures in `../lya-brain/08-PLATFORM-ROLES.md`. No stage has been executed yet.
**Left undone / follow-up:** every exit test above is unrun. Stage 1 is the only one that can start
tonight, and it needs one elevation prompt and one reboot.
**Notes:** if only one stage ever happens, make it **Stage 2** — the cloud VM gives the largest
reduction in both risk and laptop load for the least ongoing effort.
