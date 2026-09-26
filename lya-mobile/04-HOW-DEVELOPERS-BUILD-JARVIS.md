# 04 — HOW DEVELOPERS BUILD THEIR JARVIS: the honest patterns

> Written 2026-09-26. Patterns distilled from public builds and documentation; sources at the end.

You asked: *"what are the ways people and big developers implemented their Jarvis, and how
do they show images/video in those pop-ups?"* Every impressive reel reduces to one of four
patterns. None of them requires the money people assume.

## Pattern 1 — Speech-only agent (fastest to build)

```
trigger → gather state → text-to-speech → wait for reply → next turn
```
- TTS: on-device (Windows SAPI, iOS Speak Text) or a free API voice (ElevenLabs free tier,
  Edge-TTS is free).
- The "understanding the situation" feel = reading L2 (`last_seen`, idle time) + L3
  (remembered instructions) into a template. See 14-GENIUS-TRICKS §Trick 8.

## Pattern 2 — The evidence card (this is the image/video trick)

When Jarvis in the reels "shows the projects, zooms, details" — that is not the AI drawing.
It is a **pre-assembled card**: the agent already scraped screenshots/thumbnails (URLs),
and the UI is a template that displays them one by one with a zoom animation.

```
agent finds N items → for each: { title, image_url, summary, source }
UI: full-screen card carousel, Ken-Burns zoom on the image, TTS narrates in sync
```

How to get it on your ₹0 stack:
| Piece | Free option |
|---|---|
| Card UI on the laptop | a local web page (same stack as `lya-brain/visual/`) — LYA opens it, or it appears in an always-on-top window |
| Card UI on the phone | **Bark / ntfy with image attachment**, or a Shortcut that opens a URL |
| Images | the scraped URLs themselves — never copy media, just link it |
| Sync of narration to visuals | the card page polls a tiny JSON from the brain host; TTS timing comes from the same file |

This is exactly your Trick 5 (precomputation): the "wow" moment is assembled at 05:55,
delivered at 06:00.

## Pattern 3 — Push notification as the interruption

The mid-task "boss, one thing" pop-in is a **notification with actions**, full stop.
- iOS: ntfy/Bark push → tap → shortcut chain.
- Windows: toast notification via PowerShell/`win10toast` — LYA can already do this locally.
- Rule from 07-NEURAL-SCHEMA: interruption is allowed only for the PRIORITY register
  (calendar conflicts, security events), never chatter — otherwise it becomes spam and you
  will mute her.

## Pattern 4 — Server-side brain, thin clients (what the big builds do)

Alexa/Siri-style architecture, and the correct target for LYA:

```
thin clients (phone, laptop mic, watch)  →  brain host (PC / Worker)  →  answer back
```

- The client never holds secrets (12-ZERO-DISCLOSURE).
- The host precomputes, indexes, and routes cheaply (Trick 1, 2, 5).
- The client is disposable: if the phone is lost, nothing is lost.

## What the reels hide (be smarter than the reel)

1. Editing cuts hide latency: the 2–5 s model round-trip is trimmed out. Your latency
   budget (04-SPEED-BUDGET) must be *honest* — precompute instead of hiding.
2. "It understood I was sleeping" = three variables, not cognition. Build the state, get
   the same effect.
3. Some reels use paid APIs (GPT-4 class) per message — your free-tier plan needs the
   verification/council trick (Trick 7) instead, and abstention when unsure.
4. Continuous hotword on iPhone is not real. Alarm/NFC/push triggers are.

## Sources

- Free push infra: [ntfy.sh docs](https://docs.ntfy.sh/) — HTTP POST to publish, free iOS app.
- Alarm/time automations background behaviour: [MacStories iOS Shortcuts review](https://www.macstories.net/stories/ios-and-ipados-13-the-macstories-review/17/)
- Broken Apple Pay triggers (why not to trust flaky triggers): [Apple Developer Forums](https://developer.apple.com/forums/thread/758053)
- Termux background execution + wake lock: [Termux wiki](https://wiki.termux.com/wiki/Termux-wake-lock)
- Windows toasts from scripts: `powershell -c "[Windows.UI.Notifications.ToastNotificationManager, ... ]"` (standard WinRT API, no install)

## Build order for LYA (₹0)

1. Windows toast + TTS already on the PC → prove Pattern 3 locally. *(do first, tonight)
2. ntfy → iPhone push. Prove one tap. *(next device session)
3. Alarm automation → spoken briefing from the brain host.
4. Evidence-card page (Pattern 2) for the daily briefing — your "wow", built honestly.
