# LYA PRESENCE — proactive briefings & human timing

> **Status: RESEARCH DOC — nothing here is wired into the app.**
> Two questions answered from the owner's Jarvis-reel inspiration (2026-09-26):
>
> 1. How does LYA **pop in** with a rich visual briefing (messages, updates, evidence)?
> 2. How does LYA learn **when to pause and wait** — like a real human in conversation?
>
> Read in order: [`01-PROACTIVE-BRIEFING.md`](01-PROACTIVE-BRIEFING.md) → [`02-TURN-TAKING.md`](02-TURN-TAKING.md)

## Why this folder exists

The reels show the demo. This folder specs the **system** underneath:

- A scheduled wake (6 AM), a briefing compiled from real stores, an evidence display,
  and an interrupt channel — all on top of the L0–L7 brain already specced in `../lya-brain/07-NEURAL-SCHEMA.md`.
- A turn-taking state machine so LYA speaks, waits, notices silence, and asks
  *"shall I tell you now, or after 5 minutes?"* — from **rules**, not magic.

## The one rule both features obey

**Never speak (or display) without provenance, and never speak over the owner.**
A briefing LYA can't source is a BELIEF, and it is labelled as one. A popup that arrives
during your call is a bug, not a feature — so every proactive act goes through the
same gate as every other action: tier, matcher, approval, audit.

## Lightweight by design

Zero new heavy dependencies. The briefing is a **nightly job + a JSON payload**;
the popup is **one HTML/JS overlay reading that JSON**; the timing brain is a
**~200-line state machine** in Python. No video streaming, no GPU, no cloud.
