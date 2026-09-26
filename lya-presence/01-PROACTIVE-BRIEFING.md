# 01 — PROACTIVE BRIEFING & EVIDENCE POPUP

> The Jarvis reel: *"boss, you told me yesterday to call you at 6 — here are your updates"*,
> with picture evidence shown card by card. Here is how to build it **for real, for free,
> lightweight**, on top of the LYA brain.

---

## 1. The pipeline — five cheap parts, no new platform

```
T-24h  DURING THE DAY
   │   every event writes to L2 (episodic) with provenance — already designed
   │   messages → L2 rows tagged {source: mail/whatsapp/api, category, needs_reply?}
   │   research/updates → L2 rows tagged {source: url, model, benchmark}
   ▼
T-0    06:00  WAKE  (Zone C — scheduled job, laptop asleep is FINE)
   │   trigger: cron/Task Scheduler on always-on box, or ntfy push to phone
   ▼
T+1s   COMPILE the briefing  (a pure function — no model needed for 90% of it)
   │   pull last-24h rows from L2/L3 by rule:
   │     · counts + categories      → "14 messages, replied 9, 2 skipped (pricing)"
   │     · anomalies               → "no mad messages, boss" = zero rows matching a filter
   │     · fetched updates        → rows the watcher stored overnight
   ▼
T+2s   VERIFY  (L6)
   │   every claim must carry provenance; unsourced → label BELIEF or drop
   ▼
T+3s   DELIVER — two channels, both free
   │   a) Voice/screen if owner present (T0 senses say someone is at the desk)
   │   b) ntfy push → phone if owner is away  ("12 updates waiting — say 'start'")
   ▼
T+~4s  DISPLAY the evidence popup (§3)
```

**Why no model is needed:** the briefing is *stored data organised by rules*. The model
appears only in the follow-up conversation ("tell me more about the third one"), and by
then step 4 of the thinking loop may already have the answer in recall.

**Why "no mad messages" works:** it is literally *"SELECT count(*) WHERE category='angry' AND ts>24h ago"* returning 0 and the compiler rendering zero as a sentence. Rules, not intelligence.

---

## 2. Sources — what to wire, all free-tier compatible

| Data | Source | Cost | Notes |
|---|---|---|---|
| Messages / email | IMAP (free), or platform APIs | free | Tag each row: sender, category, needs_reply |
| Reminders/instructions | **L3 semantic memory** — "call me at 6" is a stored fact | free | This is the reel's core trick: yesterday's instruction is a memory row |
| AI news / model releases | RSS feeds (Hugging Face, provider blogs) + GitHub releases API | free | One watcher job, 15-min poll, writes to L2 |
| Benchmarks / rankings | fetch the page, store URL + quote | free | Provenance mandatory |
| Images / screenshots | screenshot files stored locally, referenced by path in the row | free | Never upload biometric data |
| Videos | pre-rendered local clips (ffmpeg already specced) | free | Ship the file path, not a stream |
| "Is the owner at the desk?" | camera/mic presence check OR last-input time on Windows | free, local | Decides voice vs. phone push |

**ntfy.sh** is the delivery channel: free, self-hostable, works with a simple HTTP POST.
It is the same channel already chosen for reminders in `../lya-brain/02-DATA-ROUTING.md`.

---

## 3. The evidence popup — how to make it feel like the reel

The reel's magic is *presentation*. Build it as a **local HTML overlay** that reads a
JSON payload LYA produced. No Electron, no browser extension.

```
Payload (compiled by LYA):
briefing.json
{
  "when": "2026-09-26T06:00",
  "greeting": "you told me yesterday to call you at 6",
  "items": [
    { "kind": "count",    "text": "14 messages came, I replied to 9",
      "evidence": [{type:"table", rows:[...]}] },
    { "kind": "news",     "text": "a new model landed, top in 3 benchmarks",
      "evidence": [{type:"image", src:"shots/modelcard.png", url:"https://..."}] },
    { "kind": "skip",     "text": "2 messages skipped — both about pricing" }
  ]
}
```

The popup (`popup.html`, ~150 lines JS):
- **one card at a time**, auto-advancing every ~6 s — this is what the reel does;
  sequential reveal feels intelligent, a wall of cards feels like a dashboard.
- **image evidence zooms** — CSS `transform: scale()` animation on click (Web Animations
  API, no library — the same finding from `../lya-brain/visual/`).
- **every card shows its source** — small footer line with the URL/path. This is the part
  the reels fake and LYA won't.
- presentation tier: read-only, no network at display time, OWNER-tier to open.

**Popup rules (hard):**
1. Never popup over a fullscreen app — check foreground window first.
2. Never more than once per trigger; a queued second briefing waits.
3. All evidence is a **local file path or stored copy** — the popup never fetches at display time (fast, offline-safe, no tracking pixels).

---

## 4. "Shall I tell you now, or after 5 minutes?" — the wake-up awareness

This is not mind-reading; it is a **decision table**:

| Signal | Inference | Behaviour |
|---|---|---|
| Owner answers in < 3 s | already awake | deliver immediately |
| No answer, but device just unlocked / camera sees person | just woke | ask: "now or in 5 minutes?" |
| No answer, voice groggy (optional, opt-in) | sleepy | same ask |
| No answer at all | away | phone push, retry screen at next unlock |
| Owner says "later" | — | **write "deferred" to L2**, retry in 5 min. The *memory* of the deferral is what makes the retry feel human. |

The ask itself is one canned branch of the turn-taking machine in [`02-TURN-TAKING.md`](02-TURN-TAKING.md).

---

## 5. Effort & tiers

| Piece | Effort | Tier |
|---|---|---|
| Briefing compiler (rules over L2/L3) | ~3 h | OWNER read |
| ntfy push + scheduler wiring | ~1 h | Zone C |
| popup.html reader | ~3 h | OWNER |
| Watcher jobs (RSS/GitHub) | ~2 h | Zone B (network!) |
| Instruction-memory round-trip ("call me at 6" → fired → reported) | ~2 h | L3 |

Total: **~11 h**, all on free platforms, zero new spend. Everything network-facing
(watchers, feeds) belongs in **Zone B workshop**; the briefing compiler stays local.

---

## 6. Fail-safe rules

- If the briefing compiler fails → **no popup**, and the failure is reported at the next interaction. Never show a partial briefing silently.
- If a source is unreachable → that section is marked *"not collected — source down"*, not omitted.
- An instruction remembered wrong ("6 AM" vs "6 PM") → LYA states the exact stored text and its written_at timestamp before acting. Provenance saves the 6-AM-reel from becoming a 6-PM-bug.
