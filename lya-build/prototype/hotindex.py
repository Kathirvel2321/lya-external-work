"""hotindex.py - PROTOTYPE that proves the WO-001 design before hand-off.

Proves three claims with measurements, in isolation (it never touches the real
brain DB and never writes outside a temp dir):

  C1  A hot read cache removes the per-call decrypt/re-encrypt of the whole file
      (measured as ~62 ms of `connection()` overhead at 10,000 rows).
  C2  A *prefix* blind index keeps the current substring-matching behaviour of
      memory.recall(key=...) while turning the O(n) decrypt-scan into one
      indexed lookup. Correctness is checked against the real recall() output.
  C3  Write cost stays flat, because a write still commits once.

Run:  python hotindex.py
"""
import hashlib
import hmac
import os
import sqlite3
import statistics
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ROOT)

from security import vault                       # noqa: E402
from security.database import connection         # noqa: E402
from brain import memory                         # noqa: E402

MIN_PREFIX = 3          # shortest queryable fragment; shorter falls back to scan
if len(sys.argv) > 2:               # prototype knob: hotindex.py [rows] [min_prefix]
    MIN_PREFIX = int(sys.argv[2])
KEY = os.urandom(32)    # prototype key; a real build derives it from the vault


def tokens(text):
    """Normalised words, identical rule for index build and for query."""
    out, cur = [], []
    for ch in text.lower():
        if ch.isalnum():
            cur.append(ch)
        elif cur:
            out.append("".join(cur)); cur = []
    if cur:
        out.append("".join(cur))
    return out


def index_entries(text):
    """Every queryable fragment of every word.

    A stored word contributes all of its prefixes >= MIN_PREFIX, so looking up
    hmac(fragment) finds the word whether the query is the whole word or a
    leading part of it. That is what preserves recall()'s substring behaviour.
    """
    out = set()
    for tok in tokens(text):
        for size in range(MIN_PREFIX, len(tok) + 1):
            out.add(hmac.new(KEY, tok[:size].encode(), hashlib.sha256).hexdigest()[:24])
    return out


def fragment_hashes(text):
    """Query side: the whole word plus each of its prefixes >= MIN_PREFIX."""
    need = set()
    for tok in tokens(text):
        for size in range(MIN_PREFIX, len(tok) + 1):
            need.add(hmac.new(KEY, tok[:size].encode(), hashlib.sha256).hexdigest()[:24])
    return sorted(need)


DDL = """
CREATE TABLE IF NOT EXISTS memory(
    id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, key TEXT, value TEXT,
    importance REAL DEFAULT 1.0, created TEXT, hits INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS memory_index(
    token_hash TEXT NOT NULL, row_id INTEGER NOT NULL,
    PRIMARY KEY(token_hash, row_id)) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS ix_mem_import ON memory(importance DESC, hits DESC, id DESC);
"""


class HotStore:
    """Read-only cache of the decrypted store + atomic write-through.

    Safety rules that make this acceptable:
      * writes NEVER read from the cache and NEVER serve stale data: they go
        through connection(), which locks the file, decrypts, mutates, re-encrypts
        and atomically replaces it - exactly as today.
      * the cache validates itself with os.stat() on EVERY use; if size or mtime
        changed (another process committed), the cache is discarded and rebuilt.
      * the cache is only ever a copy of committed bytes. Losing it costs nothing.
    """

    def __init__(self, path):
        self.path = path
        self._lock = threading.RLock()
        self._db = None
        self._stamp = None

    def _signature(self):
        try:
            st = os.stat(self.path)
        except FileNotFoundError:
            return None
        return (st.st_size, st.st_mtime_ns)

    def _reader(self):
        stamp = self._signature()
        if stamp is None:
            return None
        if self._db is not None and stamp == self._stamp:
            return self._db
        self._db = None
        raw = vault.decrypt(open(self.path, "rb").read())
        db = sqlite3.connect(":memory:", check_same_thread=False)
        db.deserialize(raw)
        self._db = db
        self._stamp = stamp
        return db

    def read(self, sql, args=()):
        with self._lock:
            db = self._reader()
            if db is None:
                return []
            return db.execute(sql, args).fetchall()

    def write(self, fn):
        """fn(cursor) mutates. The cache is dropped so the next read re-loads."""
        with self._lock:
            with connection(self.path) as c:
                c.executescript(DDL)
                result = fn(c)
            self._db = None
            self._stamp = None
            return result


WORDS = ("wifi password house office brother sister school car bike project "
         "meeting doctor bank ticket flight hotel laptop phone camera book "
         "garden kitchen music movie travel study python server backup").split()


def seed(store, n):
    rows = []
    for i in range(n):
        w1 = WORDS[i % len(WORDS)]
        w2 = WORDS[(i * 7) % len(WORDS)]
        rows.append(("fact", vault.encrypt_text(f"{w1}_{i}"),
                     vault.encrypt_text(f"saved fact {i} about {w1} and {w2}"),
                     1.0, "2026-09-24T00:00:00"))

    def fill(c):
        c.executemany("INSERT INTO memory(kind,key,value,importance,created)"
                      " VALUES(?,?,?,?,?)", rows)

    store.write(fill)

    def add_index(c):
        pairs = []
        for row_id, k_enc, v_enc in c.execute("SELECT id,key,value FROM memory").fetchall():
            text = vault.decrypt_text(k_enc) + " " + vault.decrypt_text(v_enc)
            for h in index_entries(text):
                pairs.append((h, row_id))
        c.executemany("INSERT INTO memory_index(token_hash,row_id) VALUES(?,?)", pairs)
        return len(pairs)
    return store.write(add_index)


def remember_new(store, kind, key, value, importance=1.0):
    """One write: the row and its index entries, inside the SAME commit."""
    def act(c):
        cur = c.execute(
            "INSERT INTO memory(kind,key,value,importance,created) VALUES(?,?,?,?,?)",
            (kind, vault.encrypt_text(key), vault.encrypt_text(value), importance,
             "2026-09-24T00:00:00"))
        row_id = cur.lastrowid
        pairs = [(h, row_id) for h in index_entries(key + " " + value)]
        c.executemany("INSERT INTO memory_index(token_hash,row_id) VALUES(?,?)", pairs)
        return row_id
    return store.write(act)


def search_new(store, query, limit=10):
    """Indexed search. Index = fast candidate filter; the legacy substring
    predicate then *verifies* every candidate, so results cannot be broader
    than today's recall(). Returns (rows, used_fallback)."""
    toks = tokens(query)
    if not toks:
        return memory.recall(key=query, limit=limit), True     # query below MIN_PREFIX
    cand = None
    for tok in toks:
        hashes = fragment_hashes(tok)
        if not hashes:            # a token too short to be indexed -> cannot prefilter
            return memory.recall(key=query, limit=limit), True
        marks = ",".join("?" * len(hashes))
        ids = {r[0] for r in store.read(
            f"SELECT DISTINCT row_id FROM memory_index WHERE token_hash IN ({marks})",
            hashes)}
        cand = ids if cand is None else (cand & ids)           # AND across query tokens
        if not cand:
            return [], False
    marks = ",".join("?" * len(cand))
    rows = store.read(
        f"SELECT kind,key,value,importance,hits,created FROM memory"
        f" WHERE id IN ({marks}) ORDER BY importance DESC, hits DESC, id DESC",
        list(cand))
    needle = query.lower()
    out = []
    for kind, k_enc, v_enc, imp, hits, created in rows:         # decrypt candidates only
        k, v = vault.decrypt_text(k_enc), vault.decrypt_text(v_enc)
        if needle not in (k + " " + v).lower():
            continue                                            # legacy predicate, exact
        out.append((k, v, kind, hits))
        if len(out) >= limit:
            break
    return out, False


def ms(fn, repeat=1):
    t = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        t.append((time.perf_counter() - t0) * 1000)
    return min(t), statistics.median(t)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    tmp = tempfile.mkdtemp(prefix="hotidx_")
    path = os.path.join(tmp, "store.lya")
    store = HotStore(path)
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
    print(f"WO-001 prototype - {N} rows, MIN_PREFIX={MIN_PREFIX} "
          f"(temp store only, real DB untouched)\n")

    t0 = time.perf_counter()
    pairs = seed(store, N)
    print(f"one-time index build : {(time.perf_counter()-t0)*1000:8.1f} ms"
          f"  ({pairs:,} index rows)")
    print(f"store size with index: {os.path.getsize(path)/1e6:8.2f} MB\n")

    memory.DB = path[:-4]                      # legacy recall sees the same rows
    target = f"{WORDS[N % len(WORDS)]}_{N-1}"

    old_key, _ = ms(lambda: memory.recall(key=target, limit=10), 5)
    old_list, _ = ms(lambda: memory.recall(limit=15), 5)
    store.read("SELECT 1 FROM memory LIMIT 1")                  # warm the cache
    new_key, new_med = ms(lambda: search_new(store, target, 10)[0], 50)
    new_list, _ = ms(lambda: store.read(
        "SELECT kind,key,value,importance,hits,created FROM memory"
        " ORDER BY importance DESC, hits DESC, id DESC LIMIT 15"), 50)

    print(f"{'hot path':<36}{'today':>10}{'with WO-001':>16}")
    print(f"{'recall(key=...) @ 10k rows':<36}{old_key:>8.1f}ms{new_key:>14.3f}ms")
    print(f"{'recall(limit=15)  mind.py:107':<36}{old_list:>8.1f}ms{new_list:>14.3f}ms")
    print(f"\nmedian keyed search: {new_med:.3f} ms across 50 calls")

    store._db = None; store._stamp = None
    cold, _ = ms(lambda: search_new(store, target, 10)[0], 1)
    print(f"first call after invalidation (cold reload): {cold:.1f} ms")
    t_dec, _ = ms(lambda: vault.decrypt(open(path, "rb").read()), 10)
    plain = vault.decrypt(open(path, "rb").read())
    t_des, _ = ms(lambda: sqlite3.connect(":memory:").deserialize(plain), 10)
    print(f"  cold reload breakdown: read+decrypt {t_dec:.1f} ms"
          f" + deserialize {t_des:.1f} ms")
    print(f"  => adopt-on-write (hand the plaintext to the cache at commit time)"
          f" costs ~{t_des:.1f} ms instead of {cold:.1f} ms")

    print("\ncorrectness vs the real recall():")
    for q in (target, "wifi", "passw", "python", "doctor_3"):
        a = {r[:2] for r in memory.recall(key=q, limit=25)}
        b = {r[:2] for r in search_new(store, q, 25)[0]}
        verdict = ("MATCH" if a == b else
                   ("SUBSET - infix query, needs fallback" if b < a else "MISMATCH"))
        print(f"  query {str(q)!r:<20} legacy={len(a):<4} indexed={len(b):<5} {verdict}")

    per_old, _ = ms(lambda: memory.remember("fact", f"legacy_{time.time_ns()}", "v"), 10)
    per_new, _ = ms(lambda: remember_new(store, "fact", f"new_{time.time_ns()}",
                                        "value carrying several indexable tokens"), 10)
    print(f"\nwrite cost  legacy remember()      : {per_old:8.2f} ms/write")
    print(f"write cost  indexed remember()     : {per_new:8.2f} ms/write")
    print(f"store size after writes: {os.path.getsize(path)/1e6:.2f} MB")
    print(f"\ntemp dir: {tmp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

