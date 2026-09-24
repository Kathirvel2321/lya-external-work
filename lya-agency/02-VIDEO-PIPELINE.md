# 02 — THE VIDEO PIPELINE: platform → render → YouTube → Instagram → notify

> Your exact request: *"open this platform, generate a video, then upload to YouTube and Instagram
> one by one."* Here is what actually happens at each step, with the **real** 2026 limits.
> Verified 2026-09-24.

---

## The pipeline

```
1 BRIEF        you describe the video (topic, length, style, voice, language)
2 ASSETS       script → images/clips → narration → captions        [A2]
3 RENDER       ffmpeg assembles the file locally                    [A2]  ← works today, free
4 METADATA     title, description, tags, thumbnail, visibility      [A2]
5 REVIEW       you watch it and approve the PUBLISH (not the render)[A4 gate]
6 YOUTUBE      videos.insert (resumable) → optional publishAt       [A4]
7 INSTAGRAM    create container → publish (2 steps)                 [A4]
8 NOTIFY       ntfy push with links + what happened                 [A1]
9 LOG          one audit entry per platform, with the returned IDs  [A1]
```

---

## Step-by-step feasibility

| Step | How | Feasible on your machine? | Blocker |
|---|---|---|---|
| 1–2 Script, images, captions | cloud model (Groq free) + free stock/generated images + Groq Whisper for captions | ✅ yes | image generation may need a paid/free-tier service — check per use |
| **3 Render** | **ffmpeg 8.1.2 (installed)** — slideshow/clips, TTS narration, captions, transitions, intro/outro | ✅ **yes, offline, free** | narration via local TTS (`pyttsx3`, not installed yet) |
| 4 Metadata | plain text templates | ✅ yes | none |
| **6 YouTube** | Data API v3 `videos.insert`, resumable upload, OAuth 2.0 | 🟡 **yes, with walls** | see below |
| **7 Instagram** | Graph API content publishing (container → publish) | 🟡 **yes, with setup** | see below |
| 8 Notify | ntfy push | ✅ yes | phone app install |
| — AI text-to-video (Veo/Sora-class) | cloud only | ⚠️ cloud, limited free tiers | **no GPU + 7.71 GB RAM** — cannot run locally |

---

## YouTube — the real numbers (page updated 2026-09-15)

| Fact | Detail | Consequence |
|---|---|---|
| Auth | **OAuth 2.0 required** with `youtube.upload` (or `youtube.force-ssl`) | **no API-key path, no service account** — you consent once, LYA stores a refresh token |
| Quota | `videos.insert` now sits in its **own bucket: 100 calls/day, 1 unit each** (the old model was 1,600 units against a shared 10,000/day ≈ 6 uploads) | **~100 uploads/day** — quota is no longer the practical limit |
| **The audit wall** | Projects created after **2020-07-28** have **every upload forced to `private` until the project passes YouTube's API audit**, whatever `privacyStatus` you send | **This is the real blocker.** Until the audit clears, LYA can upload but *cannot publish publicly* |
| Long videos | anything over **15 minutes** requires phone verification on the channel | one-time manual step |
| Large files | use **resumable** upload (session URI, chunked, resumable) | naive multipart uploads fail on real connections |
| Scheduling | `publishAt` in the video status | lets LYA queue instead of posting instantly |

**Honest read:** the technical part is easy and the *policy* part is slow. Plan for the audit as a
one-time owner task; until then the pipeline ends with "uploaded privately, awaiting your click".

---

## Instagram — the real numbers

| Fact | Detail |
|---|---|
| Account type | **Professional (Business or Creator)** required — a personal account cannot publish via API |
| Path A | Instagram API with Instagram Login: `instagram_business_basic` + `instagram_business_content_publish` |
| Path B | Instagram API with Facebook Login: connected Page + `instagram_basic`, `instagram_content_publish`, `pages_read_engagement` |
| Limit | **`quota_total` = 50 containers per 86,400 seconds (24 h)**, queryable via `GET /<IG_USER_ID>/content_publishing_limit` |
| Flow | **two steps**: create a media container (image/video/Reel/carousel), then publish it |
| App review | needed for permissions beyond your own accounts — again an owner task, not a code task |

**Honest read:** 50 posts/day is plenty for a personal workflow. The friction is the professional
account plus permissions, and app review if you ever publish on someone else's behalf.

---

## The trap you must avoid

**Do not automate the upload by clicking the website.** It violates the platforms' terms, breaks on
every layout change, and is the fastest route to an account ban or a CAPTCHA wall. The APIs above
exist precisely so that this is unnecessary. Rule from `01`: **API → native integration → UI
automation, in that order.**

---

## Failure handling (this is where naive pipelines break)

| Failure | Correct behaviour |
|---|---|
| Render succeeds, upload fails | retry with the **same** idempotency key; never re-render |
| Upload succeeds, publish fails | do **not** re-upload; check the existing container/video state and publish it |
| YouTube uploads as private (no audit yet) | report *exactly* that — never claim "published" |
| Instagram container created, publish times out | record the container id; retry the publish, not the container |
| Partial success across platforms | report per-platform status; **never** a blanket "done" (the project's own rule: never claim saved when the write failed) |

## What stays human (non-negotiable)

1. **First-time OAuth consent** for YouTube and Instagram — you grant it, in your browser, once.
2. **The YouTube API audit submission** — without it, everything stays private.
3. **The publish decision** for public visibility (A4 gate) — the render is cheap, the publication is
   permanent.
4. **Any video containing a person's face, voice, or private information** — extra approval, because
   publishing is irreversible.

---

## Change log

### 2026-09-24 — Video pipeline specified
**Goal:** answer whether LYA can "generate a video and upload it to YouTube and Instagram".
**Changed:** this file created — the nine-step pipeline, per-step feasibility, real 2026 quota facts,
the audit/permission walls, the ToS trap, and a failure-handling table.
**Verified by:** vendor documentation read on 2026-09-24 — YouTube Data API quota page (page updated
2026‑09‑15: `videos.insert` and `search.list` now have separate daily buckets of **100 calls/day**,
cost 1 each; default 10,000 units/day for other endpoints; projects created after 2020‑07‑28 upload
**private until audited**; >15‑minute videos need phone verification) and the Instagram Graph API
`content_publishing_limit` reference (`quota_total` **50** per **86,400 s**, professional account +
`instagram_business_content_publish` / `instagram_content_publish`). Local: `ffmpeg 8.1.2` present,
Intel UHD (no usable GPU), 7.71 GB RAM.
**Left undone / follow-up:** OAuth client creation, the YouTube audit, and Instagram permissions are
**owner account tasks**; local TTS (`pyttsx3`) is not installed yet.
**Notes:** the practical ceiling is **not** quota — it is the **audit and permission paperwork**.
Budget days, not hours, for the first public upload.

