# ADR-SEC-001 — Compartmental key hierarchy (T0–T3)

- **Status:** PROPOSED
- **Date:** 2026-09-24
- **Owner decision required:** yes
- **Supersedes:** —
- **Related:** `11-THREAT-MODEL.md` (W‑1), `12-ZERO-DISCLOSURE.md` §1, `ADR-001`, `ADR-004`,
  `security/vault.py`, `contracts/memory_record.schema.json`

## Context

Verified by reading the code on 2026-09-24:

- `security/vault.py:31` builds **one** Fernet instance at import time (`_F = _get_fernet()`), and
  `encrypt`/`decrypt` use it for everything: the memory DB, the password store, the phone token,
  the security word, the audit log, and the recovery material.
- Therefore **one key opens every store**: passwords, personal memory, biometrics and logs share a
  single blast radius. An attacker who obtains process memory, the DPAPI blob (from your unlocked
  session), or a coerced passphrase receives *everything* at once.
- The DPAPI wrap also means the key dies with the Windows install (`00-VAULT-RECOVERY.md`), so the
  current design is simultaneously *over-coupled* (one key for all data) and *fragile* (bound to one
  machine).

## Decision

**We will split storage into four compartments — T0 secrets, T1 personal, T2 biometric, T3 system —
each encrypted under its own data key, wrapped by a root KEK that is derived at unlock time and
never written to disk. T0 additionally requires an off-device factor (`ADR-SEC-002`).**

## Why

- It converts "if he gets in, he gets everything" into "he gets one compartment", which is the
  achievable form of the owner's request (`11-THREAT-MODEL.md` §0).
- It fixes the *fragility* problem at the same time: rotating one compartment no longer touches the
  others, and a lost device does not imply total loss.
- Rejected alternative: keep one key, add more checks around it. Rejected because the checks all run
  *inside* the process — an attacker who owns the process owns the checks.
- Rejected alternative: per-file keys with no hierarchy. Rejected because it explodes the number of
  secrets to escrow and makes recovery (already the hardest problem in this project) worse.

## Consequences

- **Good:** blast radius bounded; key rotation becomes routine; T0 can require a stronger factor
  than T1 without penalising daily use; a future move to hardware-backed keys becomes possible.
- **Bad:** migration is required for every existing `.lya` file (**six exist today** — measured via
  `vault_recovery.py inventory`), and a failed migration is a data-loss event. It must be done
  file-by-file, with verification *before* deleting any original.
- **Bad:** the unlock path gains steps (passphrase + factor for T0), which is a usability cost paid
  every time. Mitigate: unlock T0 lazily and briefly, not at boot.
- **Reversible?** Migration is reversible only while the original files are kept. **Keep them until
  verification passes** — this is a one-way door otherwise.

## How we will know it worked

- `R-01` — copy `security/*.lya` + `.lya_key` to a clean machine: T0 decryption **fails**.
- `R-02` — same machine with the passphrase but **no** phone factor: T0 decryption **fails**.
- `R-03` — rename a T1 file to a T0 name: rejected by header/key id, no plaintext.
- `test_foundations.py` still green after migration (existing behaviour preserved).

## Open questions

- Is a separate T3 key worth the complexity, or can T3 ride the device key? (Measure the unlock
  cost; prefer fewer keys if the security gain is small.)
- Does `security/` keep one file per compartment, or one file with four sections? (Files are simpler
  to reason about; sections are simpler to atomically update.)
- Where does the compartment identifier live — filename, ciphertext header, or both? (Both is
  safer; header alone survives renaming.)

## Change log

| Date | Change |
|---|---|
| 2026-09-24 | Created (PROPOSED) |
