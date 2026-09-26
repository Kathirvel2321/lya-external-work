# LYA MOBILE — research pack

> Written 2026-09-26. Status: **PROPOSAL — nothing is built, nothing is installed.**
> This folder answers one question: *can LYA live in / reach your phone, and how?*

Read order:

| # | File | What it answers |
|---|---|---|
| 1 | [`01-IPHONE-REALITY.md`](01-IPHONE-REALITY.md) | What an iPhone can and **cannot** do in the background — with sources |
| 2 | [`02-TRIGGER-PATHS.md`](02-TRIGGER-PATHS.md) | The realistic ways LYA "wakes" on iOS: alarm, ntfy push, Shortcuts |
| 3 | [`03-ANDROID-TERMUX.md`](03-ANDROID-TERMUX.md) | The easy path most reel-builders actually use (Android) |
| 4 | [`04-ARCHITECTURE-DECISION.md`](04-ARCHITECTURE-DECISION.md) | **The verdict:** brain stays on PC, phone is a sensor+speaker+notification endpoint |
| 5 | [`04-HOW-DEVELOPERS-BUILD-JARVIS.md`](04-HOW-DEVELOPERS-BUILD-JARVIS.md) | The 4 patterns every Jarvis build uses, incl. how they show images/video in pop-ups |

## The one-line verdict (don't skip this)

**LYA's brain never runs on the phone.** Your iPhone cannot run a background daemon, cannot
listen continuously for a wake word, and Shortcuts automations fire on *triggers*, not as a
persistent assistant. What the Instagram "Jarvis on iPhone" reels do is:

1. Pre-compute the briefing on a **server/PC** (your Zone C / Cloudflare Worker),
2. Push it to the phone as a **notification** (ntfy or similar), or
3. Use a **Shortcuts automation** (alarm-dismissed, time-of-day, NFC tap) that calls the
   brain over HTTP and **speaks the reply out loud**.

That is achievable on your phone, for free, today — with honest limits documented in `01`.
