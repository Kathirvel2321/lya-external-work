# 02 — TRIGGER PATHS: how LYA actually "wakes" on iOS

> Written 2026-09-26. Research only — no device work done yet.

Three paths, ranked from most to least reliable. All free.

## Path 1 — ntfy push → notification → reply by voice (RECOMMENDED DEFAULT)

**How it works:** LYA's always-on host (Cloudflare Worker / Zone C) sends an HTTP POST to
`ntfy.sh/<your-private-topic>` → your iPhone gets a push notification instantly.

- iPhone app: install **ntfy** from the App Store (free, open source).
- Topic name must be unguessable (it is the password): e.g. `lya-k3x9q2-secret-7421`.
- Verification: [ntfy.sh](https://ntfy.sh) — free pub/sub, no account needed, iOS app
  supports instant delivery via Apple's push relay.

```
LYA host ──POST──▶ ntfy.sh/lya-<secret> ──▶ iPhone notification:
                                            "Boss, 3 messages arrived, 1 needs you."
```

**Limits:** LYA can *speak* only through notification text (or you tap → shortcut runs →
Speak Text). It cannot interrupt an app you are using.

## Path 2 — Alarm-dismissed automation → spoken briefing (the 6-AM reel)

Shortcuts → Automation → **Alarm** → "When I dismiss" → run shortcut:
`GET your-brain-host/briefing` → **Speak Text** → **Ask for Input** ("now or in 5 min?").

- Alarm triggers run without a confirmation prompt — this is the most agency-like trigger
  iOS offers (see [MacStories Shortcuts review](https://www.macstories.net/stories/ios-and-ipados-13-the-macstories-review/17/)).
- The briefing is **precomputed** on the host at 05:55 (Trick 5, 14-GENIUS-TRICKS.md).

## Path 3 — Time-of-day / NFC / charging automations

- **Time of Day** trigger exists but may show "Ask Before Running" confirmation depending on
  iOS version — test first, never depend on it silently.
- **NFC tag**: stick a tag by your bed/desk; tap → full briefing. Reliable, deliberate, and
  zero battery cost. Tags cost ~₹30 for a pack — the only near-free hardware trick available.
- **Charger connected/disconnected**: useful as "home / leaving" signal for LYA's L2 state.

## The reply path (phone → LYA)

| Method | Latency | Free | Notes |
|---|---|---|---|
| Shortcut "Get Contents of URL" POST | ~0.3–1 s | ✅ | primary |
| Dictate Text → send transcript | +2–4 s | ✅ | push-to-talk voice |
| Reply via ntfy action button | instant | ✅ | canned choices only |

## What NOT to attempt

1. **Do not** chase continuous background listening — Apple will not grant it; every reel
   faking it uses Siri itself or an edit.
2. **Do not** build your own APNs app — $99/yr and pointless at this stage.
3. **Do not** store any LYA secret on the phone. The phone holds the ntfy topic name only;
   that is disposable and replaceable (fits 12-ZERO-DISCLOSURE: compromise ≠ disclosure).

## Build order when you have the device

```
Step 1  install ntfy → receive a test push from a browser curl        (~10 min)
Step 2  Alarm automation → canned briefing spoken out loud            (~20 min)
Step 3  point the briefing URL at the real brain host                 (~1 h)
Step 4  two-way: Dictate Text → POST → speak the reply                (~1 h)
```

Nothing above requires the brain to move off the PC. The phone is an ear, a mouth and a
bell — the thinking stays where the vault is.
