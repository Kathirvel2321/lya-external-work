# 03 — DIAGNOSE MY LAPTOP (and the honest truth about "was I attacked?")

> Your question: *"my laptop feels so corrupted — find out why it was attacked, what is the root of
> the problem, which device broke or is damaged."*
> This is the **most valuable and lowest-risk** capability in this folder. It is also the one where
> honesty matters most, because one part of the question is answerable and one part usually is not.

---

## What is answerable, and what is not — say this to yourself first

| Question | Answerable? | Why |
|---|---|---|
| What is making it slow right now? | ✅ **yes** | measurable: CPU, RAM, disk queue, thermal |
| Is a device (SSD/RAM/battery) failing? | ✅ **usually yes** | SMART/reliability counters + error logs |
| What broke, and when did it start? | ✅ **yes** | event logs give a timeline |
| Is something still active / persistent? | ✅ **yes** | autoruns, tasks, services, connections |
| Was this a **compromise** or ordinary decay/breakage? | 🟡 **indicators, not proof** | logs can be incomplete or tampered with |
| **Who** attacked me? | ❌ **almost never** | requires ISP records, upstream logs, or law enforcement. Anyone who claims otherwise is guessing |

**The rule:** `03` produces **findings with confidence levels**, never accusations. "Evidence of
unauthorised persistence, high confidence" is a finding. "The attacker was X" is not something LYA
can honestly say.

---

## Capture before you clean (the rule that is always broken)

Cleaning a machine destroys the evidence that would explain it. So:

1. **Read-only first.** Every command below is diagnostic; none changes state.
2. **Snapshot the evidence** into one encrypted archive *before* any repair: event logs, autoruns,
   service list, connections, Defender status, disk counters, browser extension list.
3. **Then** clean, and record what you changed. A "fix" without a recorded cause is how the same
   problem returns next month.

---

## The diagnostic battery (grouped, Windows)

**A. Resource reality — why it *feels* slow**
- Top CPU/RAM/disk processes, over time (not one instant): `Get-Process | Sort CPU -Desc | Select -First 15`
- Disk queue and response time — the usual cause of "it feels corrupted": `Get-Counter '\PhysicalDisk(_Total)\Avg. Disk sec/Read','\PhysicalDisk(_Total)\% Disk Time'`
- Thermal throttling: WMI thermal zone counters; a hot, dust-filled laptop behaves exactly like a
  "corrupted" one.
- Startup impact: `Get-CimInstance Win32_StartupCommand`, plus Task Manager's Startup tab.

**B. Storage health — is the SSD dying?**
- Free space and volume errors: `Get-Volume`, `Get-PhysicalDisk`
- SMART-style reliability counters (usually admin): `Get-PhysicalDisk | Get-StorageReliabilityCounter`
- Read-only surface scan: `chkdsk C: /scan` (no write, no repair)
- **Why it matters:** a failing drive produces corrupted files, random freezes and boot problems —
  the exact symptom set people describe as "hacked".

**C. System integrity — what actually broke**
- Critical/error timeline: `Get-WinEvent -FilterHashtable @{LogName='System';Level=1,2} -MaxEvents 100`
- Application crashes: `LogName='Application'`
- Reliability view (crashes + updates + driver failures on one timeline): `Get-CimInstance Win32_ReliabilityRecords`
- Integrity of system files (admin): `sfc /scannow`, `DISM /Online /Cleanup-Image /ScanHealth`
- Pending updates / failed updates / reboot required.

**D. Persistence — is something still there?**
- Startup entries, scheduled tasks, non-Microsoft services:
  `Get-ScheduledTask`, `Get-CimInstance Win32_Service`
- WMI event subscriptions (a classic fileless persistence trick) — check for consumers/filters that
  should not exist.
- Unsigned or recently-added binaries in `Temp`, `AppData`, `Startup`.

**E. Network — who is talking to what**
- Established connections **with owning process**: `Get-NetTCPConnection -State Established |
  Select LocalPort,RemoteAddress,OwningProcess`
- Unusual listeners on your machine; proxy settings; hosts-file edits; DNS cache anomalies.

**F. Protection state — was the guard turned off?**
- `Get-MpComputerStatus` (real-time on? tamper protection? signature age?)
- **`Get-MpPreference` — check exclusions.** Attackers and *some "optimisers"* add exclusion paths.
  An unexplained exclusion is a **high-confidence finding**.
- `Get-MpThreatDetection` — what Defender already caught and what it did.

**G. Accounts and access**
- Local users and admin-group membership; recent logons; failed-logon bursts (4624/4625 events).
- **Why:** new admin accounts or failed-logon patterns are the clearest intrusion indicators.

## Turning findings into a root cause (this is the actual skill)

A pile of logs is not a diagnosis. The method:

1. **Establish the timeline.** When did it start? `Get-WinEvent` around that time; correlate with
   updates, new installs, driver changes, and your own activity.
2. **Check the boring causes first** — they win most of the time: **failing disk** (corruption and
   freezes), **full disk**, **thermal throttling / dust**, **RAM pressure** (7.71 GB here is easy to
   exhaust), **a bad update**, **a runaway app**, **antivirus scanning**, **backup/OneDrive sync**.
3. **Only then look for intrusion** — and use the indicators below.
4. **Rank every finding by confidence** and say what evidence would raise it.

**Why this order matters:** the most common cause of "my laptop feels corrupted, I think I was
hacked" is failing hardware or a full disk. Attributing it to an attacker on day one sends you to
reinstall Windows and lose data for no reason.

---

## Intrusion indicators (ranked by how much they actually mean)

| Indicator | Confidence | Notes |
|---|---|---|
| **Unexplained Defender exclusion path** | **high** | classic attacker move; also done by bad "optimisers" |
| **New local admin account** you did not create | **high** | check admin-group membership and creation times |
| New scheduled task / service pointing at `Temp` or `AppData` | **high** | unusual paths are unusual for a reason |
| WMI event subscription you did not create | **high** | fileless persistence |
| Unsigned binary in `Temp`/`AppData`/`Startup`, recently written | medium | `Get-AuthenticodeSignature` |
| Defender real-time protection **off**, or tamper protection off | medium | could also be a third-party AV conflict |
| Unusual established outbound connections, especially to odd ports | medium | needs process correlation; VPNs/updaters confuse this |
| Failed-logon bursts, or logons at hours you were asleep | medium | check 4624/4625 |
| Browser extension you do not recognise | medium | high impact if present |
| **Just "it is slow"** | **low** | almost always hardware, heat, disk, or a background task |

**Nothing on this list proves who.** Even a clear intrusion yields an indicator, not a name.

---

## The escalation ladder (what to do, in order)

```
1  DIAGNOSE (read-only, encrypted evidence snapshot)
2  CONTAIN   disconnect network; kill switch; do not "clean" yet
3  PRESERVE  copy logs, autoruns, .lya files, browser profile — before any repair
4  ROTATE    change passwords from a DIFFERENT device (not the suspect one)
5  REPAIR or REINSTALL if compromise is confirmed (persistence survives "cleanup")
6  RESTORE   from a pre-incident backup; re-run tests; verify integrity manifest
7  RECORD    new row in evals/redteam.jsonl + a note in the project brain
```

**Step 4 is the one people skip.** If the machine is compromised, changing passwords *on it* hands
the attacker the new passwords.

---

## What LYA must never do while diagnosing

- Never delete, quarantine, "optimise" or repair **before** the evidence snapshot exists.
- Never run elevated, never install a driver, never disable Defender or UAC "to get a cleaner result".
- Never upload logs, screenshots or the snapshot to a cloud model without `12` §4 clearance —
  diagnostic data is exactly the kind of file that contains your personal information.
- Never claim a cause without naming the evidence, and never state an attribution at all.
- Never act on a finding automatically: **propose, with confidence, and let the owner decide.**

---

## Change log

### 2026-09-24 — Laptop diagnosis capability specified
**Goal:** answer "why is my laptop slow/corrupted, was I attacked, what broke" honestly.
**Changed:** this file created — the answerable/unanswerable table, the capture-before-cleaning rule,
a seven-group read-only diagnostic battery, the root-cause method, a confidence-ranked indicator
table, and a seven-step escalation ladder.
**Verified by:** the diagnostic commands were chosen to run on this machine (Windows 11 Home build
26200, **non-admin** — so admin-only items such as `sfc`, `DISM`, `chkdsk /scan` and reliability
counters are explicitly flagged as needing elevation).
**Left undone / follow-up:** no command in this file has been executed yet — each must be run, its
output recorded, and its noise floor understood before it can be trusted in the assistant.
**Notes:** this is the highest-value capability in the folder: it is read-only, it needs no third-party
platform, and it answers a question the owner actually asks. **Start here.**

