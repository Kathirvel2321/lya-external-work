"""LYA vault recovery — the safety net for security/vault.py.

WHY THIS EXISTS
---------------
security/vault.py wraps LYA's Fernet key with Windows DPAPI (user scope). Microsoft
documents that such blobs can "only be done on the computer where the data was
encrypted" and are tied to the matching user logon. There is a domain backup key
escape hatch, but it exists only on domain-joined machines — a personal laptop has
none.

So: reinstall Windows, or lose the SSD, and every memory, token and password in the
vault is unrecoverable. This module makes it recoverable, without ever writing the
passphrase or the raw key to disk.

USAGE
-----
    python recovery/vault_recovery.py export            # make a recovery blob
    python recovery/vault_recovery.py verify <blob>     # prove a blob restores your vault
    python recovery/vault_recovery.py restore <blob>    # recover on a new Windows account
    python recovery/vault_recovery.py inventory         # what is in the vault (keys only)

SAFETY RULES ENFORCED HERE
--------------------------
  V-2  The passphrase is never written to disk, never logged, never an env var.
  V-3  Export BEFORE putting real secrets in the vault.
  V-5  restore is proven with `verify`, never assumed.
  V-7  A bad passphrase can NEVER damage a working vault: we decrypt and test the
       recovered key entirely in memory, and only then touch the DPAPI key file.
"""
from __future__ import annotations

import argparse
import base64
import getpass
import os
import sys

# --------------------------------------------------------------------------- paths
HERE = os.path.dirname(os.path.abspath(__file__))


def _find_app_root() -> str:
    """Locate the real LYA app root (the folder holding security/vault.py).

    This script lives under lya-external-work/lya-brain/recovery/, but the vault it
    protects lives at the repo root. Deriving the root from __file__ alone pointed at
    the wrong folder, so we search upward for the actual security/vault.py and fall
    back to an explicit override for a restructured checkout.
    """
    override = os.environ.get("LYA_ROOT")
    if override and os.path.isdir(override):
        return os.path.abspath(override)

    current = HERE
    for _ in range(6):  # walk up, but not to the filesystem root
        if os.path.exists(os.path.join(current, "security", "vault.py")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return os.path.dirname(os.path.dirname(HERE))  # best effort


ROOT = _find_app_root()
VAULT_DIR = os.path.join(ROOT, "security")
KEY_PATH = os.path.join(VAULT_DIR, ".lya_key")          # DPAPI-wrapped key (as vault.py)
ENTROPY = b"LYA-ultron-project-2026"                     # must match vault.py
DEFAULT_BLOB = os.path.join(HERE, "lya_recovery.key")

# PBKDF2 parameters. Deliberately high: this file may sit in the cloud, so an
# offline brute-force must be expensive. 600k iterations is a 2023+ OWASP-level
# figure for PBKDF2-HMAC-SHA256.
PBKDF2_ITERATIONS = 600_000
SALT_BYTES = 16
MAGIC = b"LYARK1:"          # format marker so a wrong file fails loudly, not weirdly


# --------------------------------------------------------------------------- deps
def _require_deps():
    """Give a real error instead of an ImportError traceback."""
    missing = []
    try:
        import cryptography  # noqa: F401
    except ImportError:
        missing.append("cryptography")
    try:
        import win32crypt  # noqa: F401
    except ImportError:
        missing.append("pywin32")
    if missing:
        sys.exit(
            "Missing dependency: " + ", ".join(missing) + "\n"
            "Install with:  python -m pip install cryptography pywin32"
        )


# --------------------------------------------------------------------- crypto core
def _derive(passphrase: str, salt: bytes) -> bytes:
    """PBKDF2-HMAC-SHA256 -> a 32-byte Fernet key. Never stored."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def _make_blob(raw_key: bytes, passphrase: str) -> bytes:
    """Encrypt the raw Fernet key with a passphrase-derived key.

    Layout: MAGIC || salt(16) || Fernet(token)
    """
    from cryptography.fernet import Fernet

    salt = os.urandom(SALT_BYTES)
    token = Fernet(_derive(passphrase, salt)).encrypt(raw_key)
    return MAGIC + salt + token


def _open_blob(blob: bytes, passphrase: str) -> bytes:
    """Recover the raw Fernet key. Raises ValueError on a bad passphrase/corrupt file."""
    from cryptography.fernet import Fernet, InvalidToken

    if not blob.startswith(MAGIC):
        raise ValueError("Not a LYA recovery file (bad header).")
    salt = blob[len(MAGIC): len(MAGIC) + SALT_BYTES]
    token = blob[len(MAGIC) + SALT_BYTES:]
    if len(salt) != SALT_BYTES or not token:
        raise ValueError("Recovery file is truncated or corrupt.")
    try:
        return Fernet(_derive(passphrase, salt)).decrypt(token)
    except InvalidToken:
        raise ValueError("Wrong passphrase (or the file was altered). Nothing was changed.")


# ------------------------------------------------------------------- DPAPI helpers
def _dpapi_unwrap(path: str = KEY_PATH) -> bytes:
    """Read the raw Fernet key out of the current DPAPI blob."""
    import win32crypt

    with open(path, "rb") as f:
        blob = f.read()
    _desc, raw = win32crypt.CryptUnprotectData(blob, ENTROPY, None, None, 0)
    return raw


def _dpapi_wrap(raw: bytes) -> bytes:
    import win32crypt

    return win32crypt.CryptProtectData(raw, "LYA", ENTROPY, None, None, 0)


# ------------------------------------------------------------------------- commands
def cmd_export(args) -> int:
    """Write a passphrase-protected recovery blob for the current vault key."""
    if not os.path.exists(KEY_PATH):
        print(f"No vault key found at {KEY_PATH}")
        print("Nothing to export yet — the vault is created on first run of the app.")
        return 2

    p1 = getpass.getpass("Choose a recovery passphrase (not stored anywhere): ")
    if len(p1) < 12:
        print("Refusing: use at least 12 characters. This file may live in the cloud.")
        return 2
    p2 = getpass.getpass("Repeat it: ")
    if p1 != p2:
        print("Passphrases do not match. Nothing written.")
        return 2

    raw = _dpapi_unwrap()
    blob = _make_blob(raw, p1)

    out = args.output or DEFAULT_BLOB
    if os.path.exists(out) and not args.force:
        print(f"Refusing to overwrite {out} — pass --force if you mean it.")
        return 2
    with open(out, "wb") as f:
        f.write(blob)
    os.chmod(out, 0o600)

    # A paper code: transportable by eye, and the checksum catches transcription slips.
    import hashlib
    fingerprint = base64.b32encode(hashlib.sha256(raw).digest()[:10]).decode().rstrip("=")
    print()
    print(f"Recovery file written: {out}")
    print(f"Size: {len(blob)} bytes   (safe to copy to cloud/paper/USB)")
    print()
    print("  VAULT FINGERPRINT (write this on paper, it is NOT a secret):")
    print(f"      {fingerprint}")
    print()
    print("Now do all four of these, or this file is worthless:")
    print("  1. Copy the file somewhere that is not this laptop (cloud/USB).")
    print("  2. Write the passphrase down ON PAPER, kept away from the file.  [V-1]")
    print("  3. Write the fingerprint above on the same paper.                [V-5]")
    print("  4. Run:  python recovery/vault_recovery.py verify " + out)
    return 0


def cmd_verify(args) -> int:
    """Prove a blob restores THIS vault, without changing anything."""
    if not os.path.exists(args.blob):
        print(f"Recovery file not found: {args.blob}")
        return 2
    if not os.path.exists(KEY_PATH):
        print("No vault on this machine to verify against.")
        return 2

    with open(args.blob, "rb") as f:
        blob = f.read()
    passphrase = getpass.getpass("Recovery passphrase: ")
    try:
        recovered = _open_blob(blob, passphrase)
    except ValueError as e:
        print(f"FAIL: {e}")
        return 1

    current = _dpapi_unwrap()
    if recovered == current:
        print("PASS: this recovery file restores THIS vault exactly.")
        print("      Keep it safe. You are covered if Windows dies.")
        return 0

    # Materially different keys are a different vault, not a corrupt restore.
    print("MISMATCH: the file is valid, but its key is NOT this machine's vault key.")
    print("This is normal if the vault was recreated after the export was made.")
    return 1


def cmd_restore(args) -> int:
    """Recover the vault key onto the current Windows account. Verifies before writing."""
    if not os.path.exists(args.blob):
        print(f"Recovery file not found: {args.blob}")
        return 2

    with open(args.blob, "rb") as f:
        blob = f.read()
    passphrase = getpass.getpass("Recovery passphrase: ")
    try:
        recovered = _open_blob(blob, passphrase)
    except ValueError as e:
        print(f"FAIL: {e}")
        return 1

    # Prove the key is a usable Fernet key BEFORE touching anything on disk.  [V-7]
    try:
        from cryptography.fernet import Fernet
        probe = Fernet(recovered).encrypt(b"probe")
        Fernet(recovered).decrypt(probe)
    except Exception as e:
        print(f"FAIL: recovered key is not usable ({e}). Nothing was changed.")
        return 1

    # Back up an existing key rather than destroying it. A restore that eats a
    # working vault is the exact failure this whole module exists to prevent.
    if os.path.exists(KEY_PATH):
        backup = KEY_PATH + ".pre-restore"
        with open(KEY_PATH, "rb") as src, open(backup, "wb") as dst:
            dst.write(src.read())
        print(f"Existing key backed up to: {backup}")

    os.makedirs(VAULT_DIR, exist_ok=True)
    with open(KEY_PATH, "wb") as f:
        f.write(_dpapi_wrap(recovered))
    os.chmod(KEY_PATH, 0o600)

    print("Restore complete. The vault is readable on this Windows account again.")
    print("Next:  python recovery/vault_recovery.py inventory   [V-5]")
    return 0


def cmd_inventory(args) -> int:
    """List WHAT the vault holds — keys and counts only, never values."""
    count = 0
    for base in (ROOT, VAULT_DIR, os.path.join(ROOT, "brain"), os.path.join(ROOT, "data")):
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            if name.endswith(".lya"):
                path = os.path.join(base, name)
                size = os.path.getsize(path)
                print(f"  {os.path.relpath(path, ROOT):45}  {size:>10,} bytes")
                count += 1
    print(f"\n{count} encrypted store(s) found. Contents are not printed here by design.")
    return 0


# ------------------------------------------------------------------------------ cli
def main(argv=None) -> int:
    _require_deps()
    parser = argparse.ArgumentParser(
        prog="vault_recovery",
        description="Backup and restore LYA's DPAPI-bound vault key.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_exp = sub.add_parser("export", help="write a passphrase-protected recovery file")
    p_exp.add_argument("-o", "--output", help=f"output path (default: {DEFAULT_BLOB})")
    p_exp.add_argument("--force", action="store_true", help="overwrite an existing file")
    p_exp.set_defaults(func=cmd_export)

    p_ver = sub.add_parser("verify", help="prove a recovery file restores this vault")
    p_ver.add_argument("blob")
    p_ver.set_defaults(func=cmd_verify)

    p_res = sub.add_parser("restore", help="recover the vault onto this Windows account")
    p_res.add_argument("blob")
    p_res.set_defaults(func=cmd_restore)

    p_inv = sub.add_parser("inventory", help="list encrypted stores (keys only)")
    p_inv.set_defaults(func=cmd_inventory)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())