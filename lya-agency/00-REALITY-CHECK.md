# 00 — REALITY CHECK: the three tests

> Verified against vendor documentation on **2026-09-24**. Quotas and policies change; re-check
> before building.

---

## The scorecard, up front

| Test | Can she do it? | Where it breaks | Verdict |
|---|---|---|---|
| **1. Video → YouTube → Instagram, one by one** | **Mostly yes, with real walls** | YouTube: uploads are forced **private until your Google Cloud project passes an API audit**; Instagram: needs a **professional** account + app permissions and caps at **50 posts/24 h** | **Buildable** — but as API work, not browser clicking |
| **2. Diagnose a slow/corrupted laptop, find attacks** | **Yes on "what", weak on "who"** | "What is slow / what is broken / is something still active" is answerable from evidence. **"Who attacked me" is usually unprovable** without ISP records or law enforcement | **Buildable now** — high value, low risk |
| **3. Buy a ticket and complete payment** | **No — by design, and by law** | 3-D Secure OTP, CAPTCHA/anti-bot, PCI scope for card data, site ToS and the US **BOTS Act** | **Refuse the payment step.** She may *prepare everything*, you *authorise* |
| **"Full access like Venom / Upgrade"** | **No, and we should not build it** | Needs admin/kernel-level control, no consent layer, no audit — the opposite of `11`–`13` | **Refused as a design goal** |

---

## Why the answer is "delegated agency", not "possession"

**Venom / Upgrade, translated into engineering terms,** would mean: LYA runs as a kernel driver or
at SYSTEM level, has write access to every process, can disable protections, and acts without asking.

That is *possible* — it is what rootkits and some anti-cheat/EDR agents do. Three reasons we refuse:

1. **It destroys the security model built in `11`–`13`.** Every guarantee there assumes LYA is
   *inside* a boundary she cannot cross. Full possession deletes the boundary.
2. **It makes every bug a catastrophe.** At user level, a bug in LYA can annoy you. With kernel/SYSTEM
   access, the same bug can brick Windows, exfiltrate the vault, or make LYA malware's favourite host.
3. **It is legally indefensible.** An assistant with system-level reach that acts on third-party
   platforms is indistinguishable from malware, and *you* own the consequences.

**What we build instead:** LYA acts with *your* ordinary user rights (which today is **not admin** —
a feature, `13-SELF-PROTECTION.md` §1), through documented interfaces where they exist, and through
the same UI you use where they do not. She gets **capability**, not **possession**.

---

## The three access models — pick one, deliberately

| Model | Meaning | Blast radius | Our choice |
|---|---|---|---|
| **Possession** (Venom/Upgrade) | runs as SYSTEM/driver, no consent layer, acts freely | total, silent | ⛔ **refused** |
| **Permissioned access** (Android/iOS style) | typed capabilities, granted per app, revocable, visible | bounded, auditable | ✅ **this is LYA** |
| **Remote-control brute force** | LYA blindly clicks your screen with no app-level awareness | medium, brittle, breaks on any layout change | 🟡 allowed only as a **fallback** for apps with no API, never for money or auth |

**The rule that follows:** prefer **API → platform-native integration → UI automation**, in that
order. UI automation is the last resort, because it is the most fragile and the least visible.

## What Windows actually allows (measured reality, not myth)

| Capability | Available to a normal user process? | Notes |
|---|---|---|
| Read/write your files | ✅ yes | scoped to the user profile — already how `skills/files.py` works |
| Keyboard + mouse control | ✅ yes | `pyautogui`/SendInput; blind and layout-dependent |
| Read the UI of other apps | 🟡 mostly | UI Automation gives control names, buttons, text — **if** the app exposes them |
| Screenshots / screen reading | ✅ yes | plus OCR to make them meaningful |
| Launch any installed app | ✅ yes | allow-list by exact name (`S-3` fix), never `shell=True` |
| Clipboard | ✅ yes | a real leak channel — treat as egress, not as a convenience |
| Web automation | ✅ yes | Playwright-class driving your own browser session |
| Network calls | ✅ yes | subject to the egress shield (`12` §4) |
| Read another process's memory | ❌ no | needs admin + debug privileges |
| Install drivers / change system settings | ❌ no | UAC secure desktop — **a wall we keep** |
| Interact with the UAC prompt itself | ❌ **no** | by design; this is why "Upgrade" is fiction |
| Read DRM content (Netflix etc.) | ❌ no | deliberately protected |
| Automate anti-cheat-protected games | ❌ no | plus it violates publisher rules (`LYA_VISION.md` already refuses this) |
| Automate a bank/checkout OTP step | ❌ no | the OTP is *meant* to require you |

**The pattern:** everything that protects *you* from malware also protects you from LYA — and that is
why you can safely leave her running. If we broke those walls for convenience, we would be building
the thing `11-THREAT-MODEL.md` exists to prevent.

---

## The distinction that matters most: reach ≠ authority

LYA will have two independent layers, and they must never be merged:

```
REACH      (what she can technically touch)   →  files, screen, apps, network, camera
AUTHORITY  (what she is permitted to act on)  →  policy.py tiers + plan approval + budget
```

`security/policy.py` already models authority correctly (default-deny, unknown action = deny).
The failure mode to avoid is letting *reach* imply *authority* — i.e. "she can see it, so she may
change it". `LYA_VISION.md` states the rule directly: **"Available capabilities do not imply
permission to act."**

---

## Change log

### 2026-09-24 — Reality check written
**Goal:** answer "can she have full access?" and the three concrete tests without exaggeration.
**Changed:** this file created — a verdict scorecard for the three tests, the three access models,
and the refusal of the possession model.
**Verified by:** vendor documentation read on 2026-09-24 (YouTube Data API quota page updated
2026‑09‑15; Instagram Graph API content-publishing-limit reference), and local measurement
(ffmpeg 8.1.2; Intel UHD; 7.71 GB RAM; non-admin account; Windows 11 Home build 26200).
**Left undone / follow-up:** the YouTube API-audit requirement and Instagram app permissions are
**account-level setup tasks for you** and cannot be completed by code in this folder.
**Notes:** the single most counter-intuitive finding is that the **local** part of these tasks is
easy and the **remote** part is hard. Access to your laptop was never the bottleneck.

