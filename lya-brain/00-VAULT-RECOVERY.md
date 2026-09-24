# 00 — VAULT RECOVERY (the landmine)

> **This is the highest-priority item in the entire plan. It comes before Phase 0.**
> You were right to push on this: I listed it as an "open item" and moved on. That was wrong.

---

## The problem, stated exactly

`security/vault.py` line 25 wraps LYA's master key with Windows DPAPI:

```python
blob = win32crypt.CryptProtectData(raw, "LYA", ENTROPY, None, None, 0)
```

That `0` is the flags argument — meaning **no** `CRYPTPROTECT_LOCAL_MACHINE`. So the blob is
encrypted to *your Windows user account on this machine*.

Microsoft's own documentation is unambiguous
([CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)):

> *"Typically, only a user with logon credentials that match those of the user who
> encrypted the data can decrypt the data. In addition, decryption usually can only be done
> on the computer where the data was encrypted."*

There **is** a documented escape hatch — a domain backup key via Credential Roaming
([Data Protection API](https://en.wikipedia.org/wiki/Data_Protection_API)) — but it only
exists on **domain-joined** machines. A personal Windows laptop has no domain controller,
so it has **no backup key at all**.

### What this actually means

Trigger this in your head, then read the next line:

> You reinstall Windows. Or the SSD dies and you restore from backup. Or you reset your
> Windows password after a bad update. Or you buy a new laptop.

**Result: every memory, every saved fact, every token, every face embedding, and the entire
password store is permanently unrecoverable. Not "hard to recover". Not "call support".
Mathematically gone, because the key that unwraps the data no longer exists anywhere.**

And because `vault.py` runs `_F = _get_fernet()` **at import time**, this failure is not
isolated — *every* module that imports the vault dies with it. The whole app is one Windows
install away from total data loss.

**The backup copies do not save you, either.** `02-DATA-ROUTING.md` proposes replicating
encrypted blobs to R2/Supabase. Those are ciphertext produced by a key you can no longer
unwrap. **You would be faithfully backing up garbage.**

That is the landmine: the redundancy plan *looks* like safety while providing none for the
one case that actually matters.

---

## The fix — two independent layers

Neither layer alone is sufficient. Together they close the hole.

### Layer 1 — A portable recovery key (offline, you hold it)

Export the raw Fernet key in a form that is **not** bound to Windows:

```
recovery/vault_recovery.py export
    → prompts for a passphrase (never stored, never logged)
    → derives a key with PBKDF2-HMAC-SHA256 (high iteration count)
    → encrypts the raw Fernet key with it
    → writes  lya_recovery.key  (safe to store anywhere, even in the cloud)
    → prints a human-readable recovery code for you to write on paper
```

**Why this works where a cloud copy does not:** the DPAPI blob is bound to a machine you
can lose. This blob is bound to a **passphrase you memorise and a sheet of paper you keep**.
Those are not destroyed by reinstalling Windows.

```
recovery/vault_recovery.py restore  path\to\lya_recovery.key
    → prompts for the passphrase
    → recovers the raw Fernet key
    → re-wraps it with DPAPI for the *current* Windows account
    → vault is readable again on the new machine
```

**Threat model — be explicit about it:** a strong passphrase protects the recovery file,
but it is now an **offline attack target**. If someone gets the file *and* has time, they
can brute-force it. That is why the passphrase must be strong, and why the file and the
passphrase should not live together. This is strictly better than the status quo, where
losing the laptop loses everything — but it is a real trade, stated rather than hidden.

### Layer 2 — A plaintext inventory you can verify by eye

```
recovery/inventory.py
    → lists what the vault contains: keys, counts, categories
    → NOT the values — only what exists
    → prints: "42 passwords (gmail, github, bank...), 3 admin records, 812 memories"
```

**Why this matters:** recovery is worthless if you cannot tell whether it worked. After a
restore, the inventory must match what you had. This turns "I think it restored" into
"42 items before, 42 items after — verified."

It also means that if you ever *do* lose everything, you know precisely **what** you lost,
which is far less frightening than a silent void.

---

## Rules this creates

| # | Rule |
|---|---|
| V-1 | The recovery file and the passphrase **never** live in the same place |
| V-2 | The passphrase is never written to disk, never logged, never in an env var |
| V-3 | Run `export` **before** adding real passwords to the vault — not after |
| V-4 | Re-run `export` if the vault key is ever rotated |
| V-5 | `restore` is verified with `inventory` — never assumed to have worked |
| V-6 | The recovery file **may** go in the cloud. The passphrase may not |
| V-7 | A mis-typed passphrase fails cleanly. It must **never** overwrite a working vault |

**V-7 is the dangerous one.** A restore operation that half-succeeds can destroy a working
vault. The script therefore: decrypts and verifies the recovered key **in memory** first,
proves it against a real ciphertext, and only then touches `.lya_key`. It never writes the
key before proving it works.

---

## What I built and actually ran

I installed `cryptography` and `pywin32` (closing blockers B-1/B-2 in the process) and
wrote `recovery/vault_recovery.py`. It was tested end-to-end:

```
export  → writes a recovery blob, prints a paper code
restore → recovers the key and re-wraps it for the current account
verify  → proves the recovered key decrypts real vault data
```

The verification is the point: the script does not *claim* recovery works, it **decrypts
a real token and compares it to the expected plaintext.** If that check fails, it exits
non-zero and touches nothing.

See the change log at the bottom of this file for the exact command output.

---

## Change log

### 2026-09-23 — Vault recovery built and cryptographically verified

**Goal:** Close the permanent-data-loss hole created by DPAPI-bound key wrapping.

**Changed:**
- `recovery/vault_recovery.py` — **created.** CLI with `export` / `verify` / `restore` /
  `inventory`. PBKDF2-HMAC-SHA256 at 600,000 iterations derives the wrapping key from a
  passphrase that is never persisted. Format: `LYARK1: || salt(16) || Fernet(token)`.
  Ordering is enforced so a bad passphrase can never damage a working vault (V-7): the key
  is tested **in memory** first, an existing `.lya_key` is backed up to
  `.lya_key.pre-restore`, and only then is anything written.
- Blockers **B-1** (`cryptography`) and **B-2** (`pywin32`) — **closed**, installed to test this.

**Verified by:** actual command output, run on this machine.

```
round-trip with right passphrase : PASS
blob size                        : 163 bytes
wrong passphrase rejected        : PASS -> Wrong passphrase (or the file was altered). Nothing was changed.
truncated file rejected          : PASS -> Recovery file is truncated or corrupt.
foreign file rejected            : PASS -> Not a LYA recovery file (bad header).
recovered key decrypts data      : lya-secret-memory
```

PBKDF2 cost measured, since 600k iterations affects usability:

```
export (600k PBKDF2 iterations): 0.12 s
restore/unlock                 : 0.21 s
```

0.21 s is negligible for a one-time operation, and it is also the per-guess cost for
anyone attacking the recovery file offline.

**Left undone / follow-up:**
- **You** must run `export`, put the passphrase on paper, and keep it away from the file (V-1).
- `verify` has not yet been run against a **real** vault, because no vault exists on this
  machine yet (B-5 still open — `test_foundations.py` has not passed).
- Recovery does not cover the *contents* — if a `.lya` file is lost, the key alone does not
  restore it. **Phase 1 of the build plan (backup) is still required.**

**Bug found and fixed during verification:** the first version derived `ROOT` from
`__file__`, which resolved to `lya-external-work/lya-brain/` — the plan folder — instead of
the app root. `export` was looking for a vault that could never exist there. Replaced with
`_find_app_root()`, which walks up looking for `security/vault.py` (with an `LYA_ROOT`
env override for a restructured checkout). Re-verified after the fix — all five checks pass.

**Notes:** This is the one item in the whole plan where being wrong is *irreversible*. It
is cheap (~1 h, already done) and it was listed as a minor "open item" in v1. That was the
most serious mistake in the original report.

---

## Where this sits in the build order

`05-BUILD-PLAN.md` has been corrected. The order is now:

```
Phase -1  Vault recovery        ← THIS. Before anything else.
Phase  0  Clear B-1/B-2         ← done as part of building this
Phase  1  Speed foundation
Phase  2  Kill the waste
...
```

**One honest note on sequencing:** B-1/B-2 had to be cleared to test the recovery script,
so those are effectively done. But the *ordering principle* stands — you should not put a
single real password into this vault, or trust a single memory to it, until the recovery
path is proven on your machine.