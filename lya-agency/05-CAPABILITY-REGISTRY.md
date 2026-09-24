# 05 — CAPABILITY REGISTRY: the new entries

> These plug into the registry defined in `../lya-brain/10-CONTRACTS.md` and
> `../lya-brain/contracts/tool_descriptor.schema.json`. Format:
> `name, matcher, tier, fast, timeout_ms, idempotent, egress, test`.
>
> **Rule (unchanged):** no capability without a registered matcher, a tier, and a test.

---

## A. Diagnostics (read-only — build these first)

| Capability | Tier | fast | Notes | idempotent |
|---|---|---|---|---|
| `device_health` | PUBLIC | ✅ | CPU/RAM/disk/temperature summary | ✅ |
| `disk_health` | PUBLIC | ✅ | volume space, reliability counters (counters need elevation — degrade gracefully) | ✅ |
| `timeline_events` | OWNER | ✅ | System/Application critical+error events, with times | ✅ |
| `startup_audit` | OWNER | ✅ | startup entries + scheduled tasks + non-MS services | ✅ |
| `persistence_scan` | OWNER | ✅ | autoruns, WMI event subscriptions, unusual paths | ✅ |
| `protection_state` | OWNER | ✅ | Defender status **including exclusion paths** | ✅ |
| `connection_audit` | OWNER | ✅ | established connections **with owning process** | ✅ |
| `account_audit` | OWNER | ✅ | local users, admin group, recent/failed logons | ✅ |
| `evidence_snapshot` | OWNER | ❌ | write one encrypted archive **before** any repair | ❌ (timestamped) |

**Hard rules for this group:** read-only unless writing the snapshot; **never elevated**; never
deletes, quarantines or "optimises"; every finding carries a confidence level; **never attributes**
an attacker.

---

## B. Video pipeline

| Capability | Tier | fast | Notes | idempotent |
|---|---|---|---|---|
| `generate_script` | OWNER | ❌ | cloud model; grounded, no private facts | ✅ |
| `generate_assets` | OWNER | ❌ | images/clips; **verify the service's terms and cost per call** | ✅ |
| `render_video` | OWNER | ❌ | **ffmpeg locally** (installed, 8.1.2) | ✅ (output path per key) |
| `video_metadata` | OWNER | ✅ | title/description/tags/thumbnail | ✅ |
| `publish_youtube` | OWNER + plan + per-target approval | ❌ | OAuth + resumable `videos.insert`; **report `private` honestly when not audited** | ❌ → needs key |
| `publish_instagram` | OWNER + plan + per-target approval | ❌ | container → publish; professional account; 50/24 h | ❌ → needs key |
| `notify_push` | PUBLIC | ✅ | ntfy, short message + deep link | ✅ |

**Hard rules:** never automate the platform's **website** where an API exists; never re-render on a
retry; never claim "published" when the platform returned `private`; report per-platform status.

---

## C. Watching and preparing (no money)

| Capability | Tier | fast | Notes | idempotent |
|---|---|---|---|---|
| `watch_page` | OWNER | ✅ | polite polling with a floor interval + backoff; **no CAPTCHA bypass, ever** | ✅ |
| `open_platform` | TRUSTED | ✅ | allow-listed app or URL only — never `shell=True` (`S-3`) | ✅ |
| `prefill_form` | OWNER + plan | ❌ | fill up to, but **not including**, payment | ✅ |
| `record_receipt` | OWNER | ✅ | store the confirmation and file it | ✅ |
| `remind_deadline` | OWNER | ✅ | reuse the existing reminder path | ✅ |
| `ui_drive` | OWNER + plan + visible progress | ❌ | **fallback only**, when no API exists; every action screenshotted to the audit log | ❌ |

**Hard rules:** no purchase, no payment, no 3‑D Secure, no card data — ever (`04-BUY-A-TICKET.md`).

---

## D. What must NEVER become a capability

| Never | Why |
|---|---|
| Complete a card payment / 3DS step | SCA exists to require a human; PCI scope; ToS (`04`) |
| Store a PAN or CVV inside LYA | makes the vault a cardholder-data environment |
| Hold third-party account passwords in a prompt | `12` §4 — the model never sees credentials |
| Perform account recovery on your behalf | the exact capability an attacker wants |
| Run elevated, install a driver, or automate UAC | `01` — the walls we keep |
| Automate the anti-cheat / DRM path | `LYA_VISION.md` already refuses it |
| Defeat a CAPTCHA or anti-bot control | ToS + the US BOTS Act class of behaviour |
| Delete, wipe or "clean" without a preserved snapshot | `03` — evidence first |
| Publish anything publicly without a per-target approval | A4 gate |

---

## Change log

### 2026-09-24 — Agency capabilities registered
**Goal:** turn the four owner requests into registry entries that can be tiered, tested and gated.
**Changed:** this file created — 22 proposed capabilities across diagnostics, video, and
watch/prepare, each with a tier and idempotency, plus a nine-row "never" list.
**Verified by:** each entry mapped to `contracts/tool_descriptor.schema.json` and to the tier model
in `01-ACCESS-TIERS.md`; local capability check (ffmpeg 8.1.2 present, non-admin account, no GPU).
**Left undone / follow-up:** every entry needs a real test name before it may be marked ✅; none of
these are implemented in the running assistant.
**Notes:** the diagnostics group (A) is deliberately first — read-only, no third-party platform, no
paperwork, and immediately useful.
