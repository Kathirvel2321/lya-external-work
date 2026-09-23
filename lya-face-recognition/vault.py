"""Encrypted template store — biometric data never sits on disk in plaintext.

Layers, deliberately the same approach as LYA's own vault so there is one story
to reason about:

1. **AES-256 (Fernet)** encrypts the template file. Stealing the file yields
   unreadable bytes, and Fernet is authenticated, so tampering is detected
   instead of silently accepted.
2. **The key itself is protected by Windows DPAPI**, bound to *this* Windows
   user account. Copying `private/` to another PC or another user makes it
   useless. This is the practical answer to "someone copies my face file".

Honest limits, stated because the owner is building for real security:

* Any process running as the same Windows user can call DPAPI too, so this
  protects data at rest and against file theft, **not** against malware already
  running inside your own session.
* These are templates (512-d vectors), not photos - but a template is still
  personal data, so it is encrypted and never logged in raw form.

Nothing here stores images. An optional face-photo gallery is deliberately not
implemented: a vector cannot be turned back into a face, a JPEG can.
"""
from __future__ import annotations

import json
import os
import time

import numpy as np

import config

# Fernet key, itself wrapped by DPAPI. Separate from LYA's key on purpose: two
# independent keys mean a compromise of one store does not open the other.
_ENTROPY = b"LYA-face-recognition-2026"


class VaultError(RuntimeError):
    """Raised when the store cannot be read or written safely."""


def dpapi_available() -> bool:
    try:
        import win32crypt  # noqa: F401
        return True
    except Exception:
        return False


def _protect(raw: bytes) -> bytes:
    import win32crypt
    return win32crypt.CryptProtectData(raw, "LYA-face", _ENTROPY, None, None, 0)


def _unprotect(blob: bytes) -> bytes:
    import win32crypt
    _, raw = win32crypt.CryptUnprotectData(blob, _ENTROPY, None, None, 0)
    return raw


def _fernet():
    """Load or create the DPAPI-wrapped Fernet key."""
    from cryptography.fernet import Fernet

    os.makedirs(config.PRIVATE_DIR, exist_ok=True)
    if os.path.exists(config.KEY_PATH):
        with open(config.KEY_PATH, "rb") as handle:
            blob = handle.read()
        try:
            raw = _unprotect(blob)
        except Exception as exc:
            raise VaultError(
                "the template key could not be unwrapped by Windows DPAPI. "
                "This normally means the file was copied from another user or "
                "machine. Re-enroll to create a new key."
            ) from exc
    else:
        raw = Fernet.generate_key()
        with open(config.KEY_PATH, "wb") as handle:
            handle.write(_protect(raw))
        try:                                            # best effort, Windows only
            os.chmod(config.KEY_PATH, 0o600)
        except Exception:
            pass
    return Fernet(raw)


_F = None


def _fernet_cached():
    global _F
    if _F is None:
        _F = _fernet()
    return _F


# ----------------------------------------------------------------------
# template file
# ----------------------------------------------------------------------
def empty_store() -> dict:
    return {
        "version": 2,
        "created": time.time(),
        "owner": None,                 # name of the one primary owner, or None
        "people": [],                  # [{name, role, templates:[{vector, bucket,
                                       #   quality, yaw, added}]}]
    }


def store_exists() -> bool:
    return os.path.exists(config.TEMPLATE_STORE)


def load_store() -> dict:
    """Read and decrypt the store. A missing store is simply empty."""
    if not store_exists():
        return empty_store()
    with open(config.TEMPLATE_STORE, "rb") as handle:
        blob = handle.read()
    try:
        data = _fernet_cached().decrypt(blob)
    except Exception as exc:
        raise VaultError(
            "the template store could not be decrypted (wrong user/machine or "
            "the file was modified). Refusing to guess."
        ) from exc
    store = json.loads(data.decode("utf-8"))
    store.setdefault("people", [])
    store.setdefault("owner", None)
    return store


def save_store(store: dict):
    """Encrypt and write atomically so a crash cannot leave a half-written file."""
    os.makedirs(config.PRIVATE_DIR, exist_ok=True)
    store["version"] = 2
    store["saved"] = time.time()
    payload = json.dumps(store, separators=(",", ":")).encode("utf-8")
    token = _fernet_cached().encrypt(payload)

    tmp = config.TEMPLATE_STORE + ".tmp"
    with open(tmp, "wb") as handle:
        handle.write(token)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, config.TEMPLATE_STORE)               # atomic on Windows


# ----------------------------------------------------------------------
# vector helpers (the only place raw vectors are converted)
# ----------------------------------------------------------------------
def vector_to_list(vector) -> list[float]:
    """Quantise to float32 and store as a plain list.

    float32 (not float16) because a smaller dtype was previously found to
    corrupt face templates in this project's history - accuracy matters more
    than a few kilobytes here.
    """
    return np.asarray(vector, dtype=np.float32).astype(np.float32).ravel().tolist()


def list_to_vector(values) -> np.ndarray:
    return np.asarray(values, dtype=np.float32).ravel()


# ----------------------------------------------------------------------
# people and templates
# ----------------------------------------------------------------------
def find_person(store: dict, name: str) -> dict | None:
    lowered = (name or "").strip().lower()
    for person in store["people"]:
        if person["name"].strip().lower() == lowered:
            return person
    return None


def upsert_person(store: dict, name: str, role: str = "owner") -> dict:
    person = find_person(store, name)
    if person is None:
        person = {"name": name.strip(), "role": role, "templates": [],
                  "created": time.time()}
        store["people"].append(person)
    else:
        person["role"] = role
    return person


def add_template(store: dict, name: str, reading: dict, role: str = "owner") -> dict:
    """Append one enrollment sample (a vector plus how it was captured)."""
    person = upsert_person(store, name, role)
    templates = person["templates"]
    if len(templates) >= config.ENROLL_MAX_PER_PERSON:
        # Keep the pool bounded: drop the oldest sample of the most crowded
        # bucket so quality does not decay into "hundreds of near-identical
        # frontal shots and nothing from the sides".
        bucket = reading.get("bucket", "front")
        same = [i for i, t in enumerate(templates) if t.get("bucket") == bucket]
        if len(same) > config.ENROLL_TARGET_PER_BUCKET:
            templates.pop(same[0])
        else:
            templates.pop(0)
    templates.append({
        "vector": vector_to_list(reading["embedding"]),
        "bucket": reading.get("bucket", "front"),
        "yaw": reading.get("pose", {}).get("yaw"),
        "quality": reading.get("quality", {}).get("score"),
        "added": time.time(),
    })
    return store


def bucket_counts(person: dict) -> dict:
    counts = {name: 0 for name in config.POSE_LABELS}
    for template in person.get("templates", []):
        counts[template.get("bucket", "front")] = \
            counts.get(template.get("bucket", "front"), 0) + 1
    return counts


# Samples each direction needs before enrollment counts as covered. This uses
# the dedicated minimum (not the wizard target) so the rule is one number in
# config rather than a magic value duplicated here.
COVERAGE_PER_BUCKET = config.POSE_MIN_PER_BUCKET


def coverage_complete(person: dict) -> bool:
    """True when every direction bucket has at least the minimum samples."""
    counts = bucket_counts(person)
    return all(counts.get(label, 0) >= COVERAGE_PER_BUCKET
               for label in config.POSE_LABELS)


def target_reached(person: dict) -> bool:
    """True when every direction has the wizard's full target, not just the minimum."""
    counts = bucket_counts(person)
    return all(counts.get(label, 0) >= config.ENROLL_TARGET_PER_BUCKET
               for label in config.POSE_LABELS)


def missing_buckets(person: dict) -> list[str]:
    counts = bucket_counts(person)
    return [label for label in config.POSE_LABELS
            if counts.get(label, 0) < COVERAGE_PER_BUCKET]


def owner_person(store: dict) -> dict | None:
    """The single primary owner, or ``None`` when the store is not set up.

    Exactly one owner is allowed. Two owners would mean two people who can
    unlock the same private material, which is a policy decision, not a
    technical one - so it is refused rather than quietly allowed.
    """
    owners = [p for p in store["people"] if p.get("role") == "owner"]
    if len(owners) == 1:
        return owners[0]
    return None


def set_owner(store: dict, name: str) -> dict:
    for person in store["people"]:
        if person["name"].strip().lower() == name.strip().lower():
            person["role"] = "owner"
        elif person.get("role") == "owner":
            person["role"] = "known"
    store["owner"] = name.strip()
    return store


def forget(name: str) -> bool:
    """Remove a person entirely (and their templates) from the store."""
    store = load_store()
    before = len(store["people"])
    store["people"] = [p for p in store["people"]
                       if p["name"].strip().lower() != name.strip().lower()]
    if store.get("owner") and store["owner"].strip().lower() == name.strip().lower():
        store["owner"] = None
    if len(store["people"]) == before:
        return False
    save_store(store)
    return True


def wipe() -> bool:
    """Destroy templates and the key. Irreversible, on purpose."""
    removed = False
    for path in (config.TEMPLATE_STORE, config.KEY_PATH):
        if os.path.exists(path):
            try:
                size = os.path.getsize(path)
                with open(path, "wb") as handle:          # overwrite before delete
                    handle.write(os.urandom(max(size, 1)))
                os.remove(path)
                removed = True
            except Exception:
                pass
    return removed


def summary() -> dict:
    """Non-sensitive overview for the UI: who, how many samples, which angles."""
    if not store_exists():
        return {"exists": False, "owner": None, "people": []}
    store = load_store()
    people = []
    for person in store["people"]:
        counts = bucket_counts(person)
        people.append({
            "name": person["name"],
            "role": person.get("role"),
            "samples": len(person.get("templates", [])),
            "buckets": counts,
            "missing": missing_buckets(person),
        })
    return {"exists": True, "owner": store.get("owner"),
            "people": people, "dpapi": dpapi_available()}
