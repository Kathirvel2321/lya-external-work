# 03 — ANDROID / TERMUX: the path the reel-builders actually use

> Written 2026-09-26. Research only.

Most "Jarvis on my phone" Instagram builders are on **Android**, and the reason is one app:
**Termux** — a full Linux terminal that is *allowed to keep running in the background* with
a persistent notification. iOS has no equivalent. That is the honest gap.

## What Android gives that iOS cannot

| Ability | iOS | Android (Termux) |
|---|---|---|
| Persistent background process (LYA brain agent) | ❌ | ✅ `termux-wake-lock` |
| Run Python 24/7 on the device | ❌ | ✅ `pkg install python` |
| Listen for intents/notifications of other apps | ❌ | ✅ via Termux:API / Notification Listener apps |
| Auto-run at boot | ❌ | ✅ Termux:Boot |
| Always-on hotword (with battery cost) | ❌ | ⚠️ possible (Vosk/Porcupine), drains battery |

## Recommended shape (if you ever use an Android device)

```
Termux + termux-wake-lock
  └── lya-agent.py  (light: scheduler + notifier, NOT the brain)
        ├── calls the real brain host over HTTP
        ├── termux-notification  → speaks via termux-tts-speak
        └── cron-style loop (every N minutes / alarm times)
```

Rules carried over from the security docs:
- **No vault, no keys on the phone.** Same zero-disclosure stance as iOS.
- The agent is Zone-B-like: assume it can be lost, rebuild in <15 min.
- Battery: wake-lock + 1 light HTTP poll per interval ≈ tolerable; always-on mic is not.

## Comparison table for the decision doc

| | iPhone (this project) | Android + Termux |
|---|---|---|
| Background agent | no — push + shortcuts only | yes |
| 6-AM spoken briefing | yes (alarm automation) | yes (own scheduler) |
| Spontaneous mid-task pop-in | notification only | notification + TTS |
| Effort to build | low (Shortcuts UI) | medium (Python + API perms) |
| Security surface | tiny (nothing stored) | small (topic name only) |

## Verdict

Your current phone is an iPhone → **Path 1/2 from 02-TRIGGER-PATHS.md is the plan.**
Keep this file so that if LYA ever meets an Android device (a spare phone becomes a Zone-C
satellite), the design is already written and matches the same contracts — nothing to
re-architect, just a different ear and mouth.
