# LYA AGENCY — how far can she actually reach?

> **Status: PROPOSAL, 2026-09-24.** Owner question: *"can LYA have full access to my laptop —
> like Venom on Spider-Man, or Upgrade in Ben 10, taking over any device and using anything it
> wants?"* Then three concrete tests: **(1)** open a platform → generate a video → upload it to
> YouTube then Instagram, one by one; **(2)** my laptop feels corrupted — find out why, whether it
> was attacked, what broke; **(3)** go to a website, buy a ticket, complete payment, notify me.

This folder answers all four honestly, then specifies what to build.

---

## The one-line verdict

**"Full access" is not the hard part — and it is not what you actually want.**

An assistant running in your Windows session can already *reach* nearly everything you can reach:
your screen, keyboard, files, browser, camera, microphone, clipboard, network. What stops LYA from
being "Upgrade" is not the OS. It is four things that have nothing to do with access:

1. **Third-party platforms (YouTube, Instagram, ticket sites, banks) do not grant access from your
   laptop.** They grant it through *their* APIs, *their* account rules and *their* hidden anti-bot
   defenses. Local access changes nothing here.
2. **Some gates are designed so a machine cannot pass them**: CAPTCHA, 3-D Secure OTP, bank risk
   checks. Those exist *specifically* to require a human.
3. **Some automations are illegal or contractually banned**, regardless of technical feasibility.
4. **Safety ≠ capability.** In Ben 10, Upgrade is *permanently merged* with the machine — no
   consent layer, no audit, no rollback. That is the exact design we spent `11`–`13` refusing.

So the honest target is not *possession*. It is **delegated agency**: LYA can do almost anything you
can do, with three differences — **it asks first, it logs everything, and it cannot hold your money
or your secrets.**

## Read in this order

| # | File | What it answers |
|---|---|---|
| **0** | [`00-REALITY-CHECK.md`](00-REALITY-CHECK.md) | The plain yes/no for your three tests, and why "possession" is refused |
| **1** | [`01-ACCESS-TIERS.md`](01-ACCESS-TIERS.md) | The six capability tiers, what Windows actually allows, and the walls that never move |
| **2** | [`02-VIDEO-PIPELINE.md`](02-VIDEO-PIPELINE.md) | open platform → generate video → YouTube → Instagram → notify, step by step with real quotas |
| **3** | [`03-DIAGNOSE-LAPTOP.md`](03-DIAGNOSE-LAPTOP.md) | "why is my laptop slow / was I attacked / what broke" — including what is *unprovable* |
| **4** | [`04-BUY-A-TICKET.md`](04-BUY-A-TICKET.md) | Why she prepares and you authorise — OTP, CAPTCHA, PCI, ToS, BOTS Act |
| **5** | [`05-CAPABILITY-REGISTRY.md`](05-CAPABILITY-REGISTRY.md) | The new capabilities as registry entries (tier, timeout, idempotency, test) |
| — | [`evals/agency.jsonl`](evals/agency.jsonl) | The must-never cases, in the same format as the other eval sets |

---

## What is measured on your machine (2026-09-24)

| Fact | Value | Why it matters here |
|---|---|---|
| **ffmpeg** | **8.1.2 installed** | local video assembly (images + TTS + captions + transitions) is **free and offline** — this is your realistic "generate a video" path |
| GPU | Intel UHD, shared memory, driver 31.0.101.4314 | **no CUDA, no real VRAM** → AI text-to-video generation cannot run locally |
| RAM / CPU | 7.71 GB / i3-1315U | cloud generation or template rendering only |
| Windows account | **not administrator** | keep it (`13-SELF-PROTECTION.md` §1); LYA must never need elevation to do her job |
| OS | Windows 11 Home, build 26200 | UAC secure desktop, DRM and anti-cheat all present |

---

## The three limits that will not move, whatever we build

1. **Money** — the final payment authorisation stays human. 3-D Secure/OTP exists so a machine cannot
   complete it, and automating it would put card data inside LYA's blast radius (PCI scope).
2. **Identity and accounts** — LYA never holds your passwords for third-party platforms as plaintext
   inside a prompt, and never performs account recovery, because that is the exact move an attacker
   would love her to be able to do.
3. **Irreversibility** — anything whose worst case is worse than doing nothing (delete, buy, publish,
   send, install, resize) requires an approved plan first (`ADR-002`).

---

## The honest summary you asked for

You asked whether LYA can be *Upgrade*. **Not without becoming something you would not want on your
laptop.** But the useful part of that fantasy — an assistant that can operate your machine end to
end, across many apps, without you babysitting it — is real, buildable, and mostly blocked by
*paperwork and policy* rather than by technology:

- She can **watch, read, diagnose, render, organise, prepare, and draft** — essentially unlimited.
- She can **publish, send, spend and change** — only behind an approval, an audit entry and a budget.
- She can never **hold your keys to someone else's account**, and never **complete a payment alone**.

That combination is strictly more useful than possession, because you can leave it running.

