# ADR-SEC-002 — Off-device factor required for the T0 secrets compartment

- **Status:** PROPOSED
- **Date:** 2026-09-24
- **Owner decision required:** yes
- **Supersedes:** —
- **Related:** `ADR-SEC-001`, `11-THREAT-MODEL.md` (G1), `12-ZERO-DISCLOSURE.md` §2,
  `security/escalation.py`, `web_server.py`, `companion: 00-VAULT-RECOVERY.md`

## Context

- Today the vault is protected by **one factor**: DPAPI binding to the Windows account
  (`security/vault.py:25`). Copy the files to another account or machine and they are unreadable —
  but *on this machine, in this session*, the vault opens without further proof.
- A local attacker with your Windows session (adversary **A3**, the project's own stated threat
  model in `README`) is therefore inside the vault.
- The recovery path (`00-VAULT-RECOVERY.md`) protects against **loss**, not against **theft** — it
  deliberately creates a portable wrap of the *same* key, so anyone holding both the recovery file
  and the passphrase can open everything. That is correct for recovery and dangerous as the only
  design.
- The existing phone escalation machinery is already strong and reusable: nonce-bound challenges,
  one-time grants, expiring, fail-closed lockout on 5 failures (`security/escalation.py`), and
  HTTPS-only transport with a per-client session (`web_server.py`).

## Decision

**We will require a second factor that is not stored on the laptop — released by the paired phone
(owner biometrics first) or a FIDO2 hardware key with an HMAC-secret — before the T0 secrets
compartment can be unwrapped. Two offline escrow paths will exist so a lost factor never means
permanent loss.**

## Why

- It is the only control that survives a full software compromise of the laptop: without the
  off-device secret, T0 ciphertext stays closed — the literal form of the owner's requirement
  ("even if he hacks it, he cannot reach my passwords").
- It reuses proven components instead of inventing a new protocol; the phone challenge/grant path
  already exists and is tested.
- Rejected alternative: passphrase alone. A passphrase is captured by a keylogger at the moment of
  use and can be brute-forced offline if the KDF is weak — it is one factor pretending to be two.
- Rejected alternative: **TPM-sealed** key only. It binds the secret to this machine, so it
  reintroduces the "dies with the laptop" failure and offers no protection against an attacker who
  is already *on* the machine. Useful as an *additional* binding, not as the second factor.
- Rejected alternative: cloud password manager for T0. That returns the secrets to a third-party web
  account — strictly worse, as `02-DATA-ROUTING.md` already argues.

## Consequences

- **Good:** T0 survives total laptop compromise; the factor is portable to a new device (solve the
  reinstall problem and the theft problem with one mechanism).
- **Bad:** T0 needs the phone (or key) present. **If both factors are lost, T0 is gone forever** —
  hence the two escrows, which are themselves a confidentiality risk if stored carelessly.
- **Bad:** new failure modes to test: phone offline, phone replaced, escrow used, factor revoked,
  clock skew on grant expiry.
- **Reversible?** Yes — T0 can be re-wrapped with a single factor, but that deliberately lowers the
  guarantee, so it must be recorded as an ADR, not a config toggle.

## How we will know it worked

- `R-01`: files + `.lya_key` on a clean machine → T0 fails to decrypt.
- `R-02`: passphrase present, phone factor absent → T0 fails to decrypt.
- `R-03`: escrow path restores access on a bare machine using only offline material.
- Replay and expiry behaviour stays as already tested for escalation grants.

## Open questions

- **Phone or hardware key first?** A FIDO2 key is stronger and does not depend on the phone being
  charged or online; the phone is already integrated. Recommendation: **phone first** (zero new
  hardware), with the hardware-key path designed in from the start so it can be added without a
  rewrite.
- What exactly lives on the phone — the raw factor, or a wrapped key released after biometrics?
  (Prefer a wrapped key released after phone biometrics; the raw factor never leaves the phone.)
- How is the factor revoked if the phone is lost *and* an escrow is used? (Needs a documented
  rotation procedure — `ADR-SEC-012`.)
- Does T0 unlock time out (e.g. 15 minutes) or stay open until lock? (Shorter is safer; measure the
  annoyance cost before deciding.)

## Change log

| Date | Change |
|---|---|
| 2026-09-24 | Created (PROPOSED) |
