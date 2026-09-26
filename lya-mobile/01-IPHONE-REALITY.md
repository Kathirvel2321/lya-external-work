# 01 — IPHONE REALITY: what iOS actually allows

> Written 2026-09-26. Sourced, dated. Status: research only.

You asked: *"how can LYA wake up on my iPhone like the Jarvis reels?"* Here is the honest
engineering answer, from Apple's own documentation and developer forums.

## What iOS allows (confirmed)

| Ability | How | Verified? |
|---|---|---|
| Run a shortcut when an alarm is dismissed/snoozed | Shortcuts → Automation → **Alarm** trigger, "Ask Before Running" can be OFF | ✅ Alarm is one of the confirmation-less triggers |
| Run a shortcut at a time of day | Shortcuts → Automation → **Time of Day** trigger | ✅ but historically this one showed a confirmation prompt; test on your iOS version |
| Push notifications from a free server | ntfy.sh, Pushover, Bark (iOS app), Pushcut | ✅ free tiers exist |
| Speak text out loud | Shortcuts → "Speak Text" action (uses the system TTS voice) | ✅ no third-party needed |
| Microphone input from a shortcut | Shortcuts → "Dictate Text" | ✅ push-to-talk only |
| Fetch data from your PC | Shortcuts → "Get Contents of URL" (HTTPS to your Cloudflare Worker / Oracle) | ✅ |

Sources: Apple's Shortcuts automation model — personal automations run after a trigger, and
[Apple's own Shortcuts review shows which triggers support background execution](https://www.macstories.net/stories/ios-and-ipados-13-the-macstories-review/17/)
(time-of-day needs confirmation; **alarm** does not). Also see
[Apple Support: travel triggers](https://support.apple.com/guide/shortcuts/travel-triggers-apd8ebfc4e8e/ios)
for arrive/leave/time-range automation structure.

## What iOS does NOT allow (this is the reel-illusion)

| Ability | Why not |
|---|---|
| A persistent background process / daemon | iOS suspends background apps within seconds-to-minutes. There is no equivalent of a Windows service. |
| Continuous wake-word listening ("Hey LYA" with the screen off) | Microphone background access is locked down; only Siri itself has that privilege. |
| LYA spontaneously *interrupting* you mid-task | iOS apps cannot spawn windows/overlays over other apps at will. What the reels show is either a **notification with actions** or a video edit. |
| Trusted, arbitrary automation when a *transaction* happens | Apple Pay transaction triggers have been reported broken in iOS 18 on the [Apple Developer Forums](https://developer.apple.com/forums/thread/758053) — never depend on flaky triggers. |
| Running Python / your brain | No native Python daemon. Termux-style environments don't exist on iOS (iSH/a-Shell are emulated and background-suspended). |

**Conclusion:** the 6-AM "boss, wake up" Jarvis moment on iPhone is achievable — but the
**thinking happened elsewhere** (PC / free VM / Worker), and iOS only delivers the result.
That is exactly the Zone A / Zone C split your architecture already uses.

## The honest wake-chain for iOS

```
[Alarm dismissed]  ──Shortcuts──▶  GET https://your-worker/briefing
                                         │
                          your brain host returns the prepared JSON
                                         │
                   Shortcuts → "Speak Text" says it out loud
                                         │
                   Shortcuts → "Ask for Input"  (the "tell me now / in 5 min" beat)
                                         │
                   reply sent back to the brain host as the next turn
```

The "shall I tell you now or in 5 minutes?" feel is **not** comprehension — it is a
shortcut branch on `time since alarm > X` plus a stored instruction from L3. Grounded,
honest, and indistinguishable from the reels to anyone watching.

## What costs money (avoid for now)

| Option | Cost | Needed? |
|---|---|---|
| Apple Developer account (own push app) | $99/yr | ❌ use Bark/ntfy free tiers |
| Pushcut premium | ~subscription | ❌ |
| HomeKit hub automations | hardware | ❌ |

## Next step (when you are at the build device)

1. Create one Shortcuts automation: **Alarm dismissed → Get Contents of URL → Speak Text**.
2. Point the URL at a temporary Cloudflare Worker that returns a canned sentence.
3. If the phone speaks it — the entire wake-chain is proven in under 30 minutes, ₹0.

Do not build more until that chain says one real sentence out loud.
