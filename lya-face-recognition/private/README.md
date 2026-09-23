# private/ — encrypted biometric store (never committed)

This folder holds the owner's enrolled face templates and the key that protects
them. It is in `.gitignore`. **Do not commit anything in here, and do not copy
it to another machine for backup** — the key is bound to this Windows account
via DPAPI, so a copy is useless anyway.

## Files

| File | What it is |
| --- | --- |
| `face_templates.lya` | AES-256 (Fernet) encrypted ArcFace vectors + metadata |
| `face.key` | Fernet key, itself wrapped by Windows DPAPI |
| `*.tmp` | a transient file during an atomic write; safe to delete if stale |

## What is stored

Only **512-number float32 vectors** and non-identifying metadata (which
direction the sample came from, its quality score, a timestamp). **No images.**

A vector cannot be turned back into a face. That is why a face-photo gallery is
deliberately not implemented even though it would be easy: a vector is far
safer to store than a JPEG.

## How the layers work

1. `face_templates.lya` is encrypted with Fernet, which is authenticated — a
   modified file is detected and refused rather than silently accepted.
2. `face.key` holds the raw key wrapped by **Windows DPAPI**
   (`CryptProtectData`), bound to the current Windows user.
3. Writes are atomic: encrypt to `.tmp`, `fsync`, then `os.replace`, so a crash
   cannot leave a half-written store.

Honest limitation: any process running as the same Windows user can also call
DPAPI. This protects the data at rest and against someone copying the files —
**not** against malware already running in your session.

## Inspecting and destroying

```powershell
C:\Python314\python.exe -B cli.py templates   # names, sample counts, coverage
C:\Python314\python.exe -B cli.py forget ipvis
C:\Python314\python.exe -B cli.py wipe        # destroys templates AND the key
```

`forget`/`wipe` overwrite the files with random bytes before deleting, so a
simple undelete cannot recover them.

## If the key cannot be unwrapped

The code raises a clear error instead of failing silently, and says the store
was probably copied from another user or machine. The recovery is to re-enroll:
delete this folder's contents and run `cli.py enroll <name>` again. It is
deliberately impossible to decrypt a store whose key belongs to another
account — that is the security property, not a bug.
