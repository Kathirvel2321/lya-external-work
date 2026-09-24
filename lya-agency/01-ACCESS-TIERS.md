# 01 — ACCESS TIERS: what she may do, and who approves it

> The six tiers below are the *agency* counterpart to `security/policy.py`'s authority tiers.
> Reach is described here; authority stays in the policy/registry layer (`contracts/tool_descriptor.schema.json`).

---

## The six tiers

| Tier | Name | Examples | Needs | Reversible? | Blast radius |
|---|---|---|---|---|---|
| **A0** | **Observe** | screenshot, read screen text, watch a folder, take a temperature reading | nothing | n/a | none (memory only) |
| **A1** | **Read** | open a file, list a folder, read event logs, query a device | TRUSTED session | n/a | none |
| **A2** | **Act locally (safe)** | write a note, render a video into `out/`, create a report, organise a folder you named | OWNER + plan | usually | low |
| **A3** | **Drive the UI** | click/type in another app that has no API | OWNER + plan + **visible progress** | sometimes | medium — misclicks are real |
| **A4** | **Publish / communicate** | upload to YouTube/Instagram, send an email, post a message | OWNER + plan + **explicit per-target approval** | partly | **high — it left your control permanently** |
| **A5** | **Spend / authorise** | buy, pay, subscribe, sign, accept terms | ⛔ **never automated** — owner performs the final step | no | **irreversible** |

**Two rules that define the whole ladder:**
1. **A4 and A5 are never bundled.** "Generate the video and upload it" is one approval for the
   *edit*, and a separate approval for the *publish* — because the second one can embarrass you and
   the first cannot.
2. **A3 is a fallback, not a foundation.** If an app has an API, use it. UI automation breaks on
   every layout change and leaves no reliable success signal.

---

## The "Upgrade test" — five questions before any new capability ships

A capability may exist only if all five are answered in writing:

1. **Does it need elevation?** If yes → it does not ship. (The account is not admin, and that stays.)
2. **Can it be undone?** If no → it needs a plan approval *and* an idempotency key, so a retry cannot
   double-act.
3. **Does it touch money, identity, or another person's account?** If yes → the owner performs the
   final step; LYA prepares.
4. **Does anything leave the device?** If yes → egress shield (`12` §4): allow-listed host, classified
   payload, secret scan, ledger entry.
5. **Is there a test that proves it stays inside its tier?** If no → the capability is `🟡 unverified`
   and must not be routed.

Rule 5 is the one that keeps the registry honest: **a capability without a test is a liability with
a nice name.**

---

## Coverage: how far "one task" actually gets

A realistic multi-app task decomposes into tiers, and the tier distribution is what determines
feasibility — not the buzzword:

| Task | Tier path | Coverage today |
|---|---|---|
| **"Diagnose my slow laptop"** | A1 (logs, metrics) + A0 (screen) | **95%** — only the final judgement about *who* is unprovable |
| **"Make a video and upload it"** | A2 (render) + A4 (publish) | **90%** — the 10% is platform setup: OAuth consent, API audit, app review |
| **"Post it to Instagram too"** | A4 | **80%** — needs a professional account + permissions; 50 posts/24 h cap |
| **"Buy me a ticket"** | A3 (fill) + **A5** (pay) | **70% automated, 30% permanently yours** — and the 30% is the important part |
| **"Take over any device like Upgrade"** | would require SYSTEM/driver | **0% — refused by design** |

That 70/30 split on the ticket is not a limitation to overcome later. It is the correct design, and
`04-BUY-A-TICKET.md` explains why (3-D Secure, CAPTCHA, PCI, ToS, and the US BOTS Act).

---

## The walls that never move

UAC secure desktop · DRM content · anti-cheat games · bank/checkout OTP · another person's account
without their own consent · kernel/driver access · running elevated. See `00-REALITY-CHECK.md` for
the measured table. **If a proposed feature needs one of these walls removed, the feature is wrong,
not the wall.**

---

## Change log

### 2026-09-24 — Access tiers defined
**Goal:** give "full access" a measurable scale instead of a yes/no, so capabilities can be
approved or refused consistently.
**Changed:** this file created — six agency tiers (A0–A5), the five-question Upgrade test, a coverage
table for the owner's four real requests, and the list of walls that are not negotiable.
**Verified by:** mapping each tier onto capabilities measured on this machine (non-admin account,
Windows 11 Home build 26200, ffmpeg 8.1.2 present, no usable GPU) and onto the policy tiers already
in `security/policy.py`.
**Left undone / follow-up:** the registry entries in `05-CAPABILITY-REGISTRY.md` need a test each
before any of them may be marked ✅.
**Notes:** the tiers exist so that *approval* is granular. One blanket "full access" switch is exactly
how an assistant becomes indistinguishable from malware.
