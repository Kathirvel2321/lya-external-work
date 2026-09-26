# LYA — Neural Schema visual

**File:** [`lya-brain-visual.html`](lya-brain-visual.html) — open it in any browser. Self-contained, no build step.

> **This is a reading aid for the research documents, not a claim that anything is implemented.**
> Every figure, file:line reference and layer name comes from `07`–`13`. The two security
> findings (W-1, W-2) were confirmed by reading the code.

---

## What it shows

A single scrolling page with **10 sections**, animated so you can watch the brain work:

| § | Section | Motion |
|---|---|---|
| 01 | **The eight layers** (L0–L7) | Cycles L0 → L7, one layer lighting at a time |
| 02 | **The ten-step thinking loop** | Lights each step, with a live caption of what she is doing |
| 03 | **Where a question actually goes** | A glowing token travels the rail: registry → cache → recall → check → *then* model |
| 04 | The abstention contract | — saved / belief / refusal |
| 05 | Write rules | what may become memory |
| 06 | L7 "sleep" cycle | nightly consolidation |
| 07 | Capability registry | the "plug" — matcher, tier, test |
| 08 | Three zones | A laptop · B workshop · C forever |
| 09 | The security claim | includes W-1 and W-2, and what is *not* guaranteed |
| 10 | How we prove it | the 6 offline tests + the 5 first red tests |

**The three animated sections are the point** — the static tables are already in the docs,
but watching the token *skip the model* is what makes "the model is the last resort" land.

---

## Design notes

- **Dark palette** matches `docs/diagrams/lya-diagrams.html` (GitHub-dark: `#0d1117` / `#161b22`.
- **Layer colours** are distinct per layer so the stack is readable at a glance.
- **Tailwind** is loaded from CDN, but is *not required* — the layout is carried by
  hand-written CSS in `<style>`. Removing the Tailwind tag changes nothing structural.
- **Motion** (the library) is loaded opportunistically and is **also not required**. Every
  animation uses the native **Web Animations API** (`element.animate`), which needs no CDN.

### Why the animations don't depend on a library

Three things were tried and measured while building this, and all three are worth knowing
because they cost real time:

1. **`motion@11/dist/motion.js` is a UMD build** — a dynamic `import()` of it succeeds but
   yields **zero exports**, so `m.animate` is `undefined`.
2. **An inline `<script type="module">` cannot resolve a cross-origin import when the page is
   opened over `file://`** — the module never executes at all (not an error, just silence).
3. **An injected classic `<script>` loaded (HTTP 200) but its global was not reachable in
   time** over `file://`.

So the page uses native WAAPI, which works from `file://` and `http://`, online or offline.
**A demo that goes blank offline is worse than one with simple motion.**

---

## Verified by running it

```
node <browser-automation>/browser.mjs file:///<path>/lya-brain-visual.html \
     --wait "[data-id='L3']" --script ./qa-visual.mjs
```

Result — every assertion passed:

```
http            200
title           "LYA — Neural Schema · How the Brain Works"
bodyChars       8850
console errors  0
requests failed 0

layers          8      steps 10      nodes 8
tables          2      registers 3   zones 3
waapi           true

layersAnimated  ["L0","L1","L2","L3","L4","L5","L6"]   <- cycle works
loopStepsSeen   [0..9]                                 <- all 10 steps fire
nodesSeen       ["IN","REG","CAC","REC","CHK","MDL","VFY","ANS"]  <- token travels
liveAnimations  29
allHonest       true   <- says PROPOSAL, "not wired", refuses "unhackable",
                          lists W-1/W-2, names the measured hardware
```

**Re-run `qa-visual.mjs` after any edit.** It asserts the honesty claims too — if someone
later removes "not wired into the app" or starts overpromising, the check goes red.

---

## Honest limits

- It renders the **proposal**, not the product. Nothing in it is implemented.
- The layer names and budgets come from `07`. Where `07` and the code disagree, the code wins.
- `W-1` and `W-2` are shown as **open findings**, because they are still open.
- This page is **not** evidence that the architecture is buildable — only that it is
  describable. Proof of buildability is a working vertical slice (`device_health`), which
  does not exist yet.