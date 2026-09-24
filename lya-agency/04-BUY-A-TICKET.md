# 04 — BUY A TICKET: what she can do, and the one step that must stay yours

> Your request: *"go to this website, buy a ticket for me, do all the steps for payment, notify me."*
> Direct answer: **she can do almost all of it — and the payment authorisation is the step that
> cannot, and should not, be automated.** Here is exactly why, and what to build instead.

---

## The four walls (not laziness, not missing features)

| Wall | What it is | Why it does not bend |
|---|---|---|
| **1. Strong customer authentication / 3-D Secure** | an OTP or biometric step the *cardholder* performs | it exists precisely so a machine cannot complete a card payment alone. In the EU/UK this is a legal requirement (PSD2 SCA); card networks apply it widely elsewhere |
| **2. CAPTCHA / anti-bot** | deliberate human-detection at checkout and on ticket sites | defeating it is both a ToS violation and, on ticket sites, the exact behaviour anti-bot law targets |
| **3. Card data + PCI scope** | if LYA stores or transmits card numbers, your laptop becomes a payment-data environment | a personal assistant holding a PAN/CVV is a liability with no upside |
| **4. Terms of service and law** | automated purchasing breaches most site ToS; in the US the **BOTS Act (2016)** targets circumventing access controls to buy tickets, and the FTC has enforced it since 2021 | account bans, cancelled orders, and legal exposure — with *you* as the account holder |

**None of these are about access to your laptop.** They are deliberate design decisions by other
parties. No amount of local permission changes them.

---

## What she *can* do — and honestly, it is the valuable part

| Capability | Tier | Notes |
|---|---|---|
| **Watch** a page/event for availability or a price change | A0/A1 | poll politely, respect rate limits, no logging in with your credentials in a prompt |
| **Alert you instantly** with a push (ntfy) containing the link | A1 | this is the real product: **she does the waiting so you do not** |
| **Pre-fill** the entire form: name, address, seat preference, saved details | A2/A3 | everything up to the payment page |
| **Open the checkout, ready to pay**, and hold it | A3 | you press *Pay* |
| **Record the confirmation** and file it (receipt, date, reference) | A2 | after you confirm |
| **Remind you** about the deadline/date afterwards | A1 | calendar + ntfy |
| ~~Enter card details, complete 3DS, click Pay~~ | **A5** | ⛔ **owner-only, always** |

**If you want to reduce the manual step as far as safely possible:** use a **virtual/single-use card
with a hard spending cap** issued by your bank for that one purchase. LYA can pre-fill it; you
authorise; the card dies after use. The instrument never lives inside LYA.

---

## The design decision (proposal, for the owner to accept or reject)

> **A5 (spend / authorise) is owner-only. LYA may prepare, watch, alert, and record — never
> authorise.**

Rationale, in one line each:

- It keeps card data and 3-D Secure out of LYA's blast radius, so a compromise of LYA cannot spend.
- It satisfies `12-ZERO-DISCLOSURE.md` (no secret ever needs to reach a model or an adapter).
- It satisfies the existing project rule: **D‑2 — model output is never authority.**
- It is strictly better for you: she removes the *waiting* and the *typing*, which is 90 % of the
  effort, and leaves you the 3 seconds that carry all the risk.

**What you lose:** unattended purchases (e.g. a ticket drop at 3 a.m.). If you need that later, the
correct answer is a **bank-side mechanism** — a standing order, a saved payment method with
merchant-side 3DS step-up, or a prepaid balance — not LYA holding your card.

---

## Where "notify me" fits (fully automatable, build this first)

Notification is the half of the request with **no** legal, PCI or ToS problem:

```
watch (A0) → condition met → ntfy push with link + price + deadline → you tap → purchase
```

Deliver it through **ntfy** (free, self-hostable) with a short message and a deep link. Add a
deadline reminder so a missed alert does not become a missed ticket. Record every alert in the audit
log so "she told me" is verifiable.

---

## What to say to LYA instead

| Instead of | Say |
|---|---|
| "buy me a ticket for X" | **"watch X and alert me the moment tickets open; pre-fill everything and leave the payment page ready"** |
| "pay this bill for me" | **"prepare the payment, tell me the exact amount and reference, and remind me to authorise it"** |
| "book a table" | **"check availability for 8 pm and hold the page ready"** |

Same outcome, none of the risk, and it is buildable **this week** rather than in a future where
banks allow unattended card use.

---

## Change log

### 2026-09-24 — Ticket/payment automation assessed
**Goal:** answer "can she buy a ticket and complete the payment" without overpromising.
**Changed:** this file created — the four hard walls, the prepare/watch/alert/record capability set,
the A5 owner-only proposal, and the notify-first build order.
**Verified by:** reasoning from documented controls (PSD2 strong customer authentication; 3-D Secure
OTP; PCI DSS scope for card data; the US BOTS Act 2016 with FTC enforcement actions since 2021) plus
the tier model in `01-ACCESS-TIERS.md`. **No site terms were tested and no purchase was attempted.**
**Left undone / follow-up:**
- If a specific site is named, its ToS and robots/anti-bot policy must be read **before** any
  watching or pre-filling is automated.
- Spending caps and the alert budget belong in the resource guards (`13-SELF-PROTECTION.md` §3).
**Notes:** the honest framing is that the *waiting* is the expensive part and the *paying* is the
risky part. LYA should take the waiting.
