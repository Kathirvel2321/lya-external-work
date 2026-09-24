# 06 — SKILL LIBRARY: A to Z, without the dead weight

> You want LYA to have a **massive skill library from A to Z** so she can handle any task.
> This is how to do that without repeating a mistake the project has already made.

---

## The mistake already on disk

`LYAPROJECTBRAIN.md` §2 records `skills/` as **22 modules**, and says:

> *"WIRED: files, device, forge, reminder. The other 18 are legacy."*

`LYA_RESEARCH.md` §4 classifies most of them ❌ Legacy, and notes **3.6 MB of skill
corpora present on disk but never loaded** (`book_knowledge.txt.gz`, `security_brain.txt.gz`).

So the project already *tried* "many skills". The result was 22 modules of which 4 work,
plus 3.6 MB nobody reads. **The lesson is not "fewer skills" — it is "skills that are
verifiable".**

---

## The distinction that matters

There are **two completely different things** being called "skills", and conflating them
is what produces the dead weight:

| | **Capabilities** | **Knowledge** |
|---|---|---|
| What | Code that *does* something | Text that LYA *knows* |
| Examples | open an app, set a reminder, read a file | security concepts, book summaries, how-to notes |
| Format | Python function, declared tier | Markdown document |
| Stored in | `skills/` (code) | Obsidian + HF (text) |
| Risky? | **Yes** — can act on your system | No — it is just reading |
| Speed | Must be < 100 ms | Retrieved on demand |

**Knowledge is cheap, safe and unlimited.** **Capabilities are expensive, risky and must be
few and proven.** Plan them separately and the "A to Z" goal stops being scary.

---

## Layer A — Knowledge library (unlimited, cheap, safe)

This is where "A to Z" belongs, and it can genuinely be enormous.

**Structure — Obsidian vault, one folder per domain:**

```
LYA-Knowledge/
├── A-admin/          accounts, procedures, contacts, IDs
├── B-business/       projects, clients, decisions
├── C-code/           snippets, patterns, gotchas
├── D-devices/        hardware, network map, configs
├── E-everyday/       recipes, travel, shopping, routines
├── F-finance/        budgets, bills, subscriptions
├── G-guides/         step-by-step procedures
├── H-health/         appointments, medications, fitness
├── I-ideas/          brainstorms, plans, wishlists
├── J-jobs/           tasks, work, meetings
├── K-knowledge/      research notes, summaries, references
├── L-learning/       courses, books, skills in progress
├── M-media/          films, music, games, reading list
├── N-notes/          everything that has no home yet
├── O-ops/            system operations, backups, recovery
├── P-people/         (non-sensitive) relationships, birthdays
├── R-research/       source-cited material
├── S-security/       defensive notes, hardening, threat models
├── T-tools/          software, licenses, configs
└── Z-archive/        done, old, historical
```

**Why plain Markdown:** it outlives every app. No vendor lock-in, greppable, diffable,
version-controlled. If Notion shuts down tomorrow your knowledge survives.

**Make it fast with an index, not with a bigger model.** The retrieval plan:

```
index_build.py  (proposed)
  for each .md file:
      extract headings + keywords + tags
      write  path, heading, keyword_hash, line_no  →  SQLite FTS index
```

This gives **full-text search across the entire library in milliseconds** — because
SQLite FTS5 is built into Python's `sqlite3` and needs *zero* extra dependencies. Cheetah,
not snail, with no model call at all.

**Do NOT** vector-embed the whole library for now. Embeddings mean a model load, a vector
store, and a slow approximate search — for data you can search exactly with FTS5. Revisit
semantic search only when keyword search demonstrably fails.

**Sync:** the vault folder → **private GitHub repo** (versioned, free) → and/or R2.
Unlike Obsidian-on-your-laptop, this survives the laptop dying.

---

## Layer B — Capabilities (few, proven, tiered)

**The rule: a capability exists only when it has (1) a declared permission tier,
(2) a test, and (3) a fast path.**

Your project already enforces the first two — `LYAPROJECTBRAIN.md` §0.2:

> *"Never introduce a new private action without adding it to a tier in `security/policy.py`"*
> *"Never enable a disabled capability without adding a test to `test_foundations.py`"*

**Keep that rule. It is the thing that makes "A to Z" safe rather than reckless.**

### Interface contract — one shape for every capability

```python
# Every capability declares: name, tier, matcher, and its handler.
CAPABILITY = {
    "name":  "reminder.add",
    "tier":  "OWNER",              # must exist in security/policy.py
    "match": (r"^remind me to (.+?) (in|at|on) (.+)$",),
    "fast":  True,                 # True = never calls a model
    "run":   add_reminder,
}
```

**`fast: True` is the cheetah property.** A capability marked fast must complete without a
model call. The router can then answer in milliseconds and only fall back to an LLM when
no capability matches.

### The A-to-Z capability roadmap

Grouped by domain, in build order. Tier shows the permission level required.

| Domain | Capability | Tier | Fast | Phase |
|---|---|---|---|---|
| **A — Apps** | open/close whitelisted apps | TRUSTED | ✅ | exists |
| **A — Apps** | volume / mute | TRUSTED | ✅ | exists |
| **B — Browse** | folder browse (paged, scoped) | OWNER | ✅ | exists |
| **C — Calendar** | add / list / cancel reminder | OWNER | ✅ | exists |
| **C — Calendar** | real calendar integration (ICS) | OWNER | ✅ | later |
| **D — Devices** | screenshot | OWNER | ✅ | exists |
| **D — Devices** | device status (battery, disk, network) | TRUSTED | ✅ | **next** |
| **E — Everything** | notes: create / append / search | OWNER | ✅ | **next** |
| **F — Files** | scoped file search | OWNER | ✅ | exists |
| **G — Goals** | task list, mark done | OWNER | ✅ | **next** |
| **H — Help** | "what can you do" from live registry | PUBLIC | ✅ | **next** |
| **I — Info** | time / date / calculations | PUBLIC | ✅ | trivial |
| **J — Journal** | daily log entry | OWNER | ✅ | next |
| **K — Knowledge** | FTS search the vault | PUBLIC | ✅ | **next** |
| **L — Learning** | `learn <topic>` draft | OWNER | ❌ | exists (unverified) |
| **M — Media** | play/pause local media | TRUSTED | ✅ | later |
| **N — Network** | wifi status, connectivity check | TRUSTED | ✅ | later |
| **O — Ops** | backup now, restore check | OWNER | ✅ | later |
| **P — People** | visitor naming | OWNER | ✅ | exists (unrouted) |
| **Q — Queries** | memory: remember / recall / forget | OWNER | ✅ | exists |
| **R — Research** | web research **with source tracking** | OWNER | ❌ | later |
| **S — Security** | permission report, audit log view | OWNER | ✅ | exists |
| **T — Timer** | countdown, pomodoro | TRUSTED | ✅ | next |
| **U — Units** | convert currency/units | PUBLIC | ✅ | later |
| **V — Voice** | tone control, TTS speed | PUBLIC | ✅ | exists |
| **W — Weather** | forecast (needs API) | PUBLIC | ❌ | later |
| **X — eXport** | export memories to Markdown | OWNER | ✅ | **next** |
| **Y — Yields** | summaries of the day/week | OWNER | ✅ | later |
| **Z — Zone** | theme / orb appearance | OWNER | ✅ | exists |

**Count the fast ones: 24 of 29.** Two-thirds of the library needs no model at all — which
is exactly how you get cheetah speed on a library this size.

---

## The seven capabilities I would build next

Highest value, lowest risk, no new accounts, all `fast: True`:

| # | Capability | Why it is next |
|---|---|---|
| 1 | **Device status** (battery/disk/CPU) | Uses only `psutil`-free stdlib. Genuinely useful daily |
| 2 | **Notes create/append/search** | Bridges LYA to the Obsidian layer — makes Phase 4 pay off |
| 3 | **Knowledge FTS search** | Unlocks the whole A-to-Z library in milliseconds |
| 4 | **Task list** | Natural daily-driver feature, trivial storage |
| 5 | **"What can you do" from live registry** | Ends the guessing; self-documenting |
| 6 | **Export memories to Markdown** | Your data escapes to a readable, permanent format |
| 7 | **Timer / countdown** | Pure stdlib, instantly useful, zero risk |

**#6 is quietly the most important.** An assistant whose memories can be exported to plain
Markdown can never hold your data hostage — and it is the single best insurance against
your own project becoming unusable.

---

## Anti-patterns to avoid (learned from the 18 legacy skills)

| Anti-pattern | Why it happened here | Rule going forward |
|---|---|---|
| Skill written but never routed | 18 modules, no commands | **No capability without a registered matcher** |
| Corpora added but never loaded | 3.6 MB of `.gz` sitting idle | Text goes in the vault + FTS index, not a dead `.gz` |
| Skill that shells out | `device.run_command` uses `shell=True` (S-3) | **No shell interpolation. Ever.** |
| Skill with no tier | Would bypass `policy.py` | **Not in a tier = does not exist** |
| Skill with no test | Cannot be marked ✅ | **No test = 🟡 at best** |
| "A to Z" as a target itself | Produces breadth, not usefulness | **Usefulness first; A-to-Z is the byproduct** |

**On that last row — a genuine disagreement worth stating.** You asked for A-to-Z
coverage so LYA "can handle any rounding task". Broad coverage sounds impressive but
performs worse than narrow depth: 29 half-working skills feel broken, while 8 working ones
feel powerful. The registry above is A-to-Z *shaped* on purpose — but build the seven in
the next-table first, and let the alphabet fill in as real needs appear.

---

## Open decisions

| # | Decision | Proposal |
|---|---|---|
| S-1 | Knowledge format | Markdown in Obsidian vault + FTS5 index |
| S-2 | Knowledge storage | Local vault + private GitHub + R2 |
| S-3 | Retrieval | SQLite FTS5 first; embeddings only if it fails |
| S-4 | Capability rule | tier + test + `fast` flag, or it does not ship |
| S-5 | Existing 18 legacy skills | Keep unrouted (D-15) and rebuild the wanted ones properly |
| S-6 | Dead `.gz` corpora | Decompress into the vault; delete the `.gz` |
| S-7 | Export | Markdown export of all memories — build early, not last |