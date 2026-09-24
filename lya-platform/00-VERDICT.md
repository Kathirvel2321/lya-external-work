# 00 — VERDICT: is the plan useful?

> **Yes.** Isolating LYA's work from the machine that holds your life is the correct instinct, and
> it happens to be the cheapest high-value change available. But four of the things people assume
> about "a separate platform" are wrong, and one of them is wrong about **your** machine
> specifically. Read those first.

---

## The six corrections

### 1. Your Windows edition blocks the easiest option
**Windows Sandbox is not supported on Windows Home.** Microsoft's own documentation says so
directly: *"Windows Sandbox is currently not supported on Windows Home edition."* It needs
**Pro, Enterprise, Pro Education/SE, or Education**. Your machine is **Windows 11 Home Single
Language**, so this door is closed — not a disaster, because three better options exist.

### 2. "Linux is automatically safer" — only partly true
Linux gives you a **smaller attack surface** and far better automation tooling (shell, `ffmpeg`,
`git`, `cron`, containers), which is why the workshop should be Linux. But:

- The **isolation** comes from the boundary (separate kernel/disk/network), not from the distro.
- A Linux sandbox with `/mnt/c` mounted and interop enabled can read your Windows files. That is
  not isolation, it is a second door.
- Root inside a disposable VM is fine. Root inside a container that shares your kernel is not.

### 3. WSL2 is a *work* environment, not a *security* boundary
WSL2 is fast, light (~0.5–2 GB), and excellent for coding and automation. But by default it can
reach your Windows filesystem and Windows can reach into it. Treat it as **a clean workbench**,
not as a vault wall: it protects your system from *messy experiments*, not from a *determined
attacker who is already on Windows*.

### 4. The fanless VivoBook is the best *test rig* and the worst *server*
A fanless laptop dissipates heat through the chassis. Sustained 100 % CPU load = thermal
throttling, shortened component life, and heat near the battery. That makes it **ideal** for
"run this risky thing and see what happens, then wipe it" (a compromised test rig costs you
nothing) and **unsuitable** as a 24/7 host. `04-HARDWARE-REALITY.md` has the thermal rules.

### 5. You cannot conjure hardware — and you do not need to
The heavy lifting does not happen on either laptop. It happens on the **free Oracle ARM VM**
(2 OCPU / 12 GB), which is a real separate machine in a datacenter and costs nothing. Both laptops
stay light. That is the answer to *"will this put pressure on my laptop?"* — **yes, if we host it
locally. So we don't.**

### 6. Isolation is not a substitute for the data protection work
A workshop protects the **machine**. It does nothing for a stolen backup, a coerced passphrase, or
one shared key. `ADR-SEC-001` (compartments) and `ADR-SEC-002` (off-device factor) remain
mandatory regardless of how many sandboxes we build.

---

## What you gain (honestly, in order of value)

| Gain | Why it matters |
|---|---|
| **A real blast radius boundary** | the single biggest reduction in *consequence* available |
| **Freedom to experiment** | you can let LYA run generated code, scrapers, and network tools — today's biggest risk |
| **Thermal and RAM relief** | the laptops stop being the bottleneck; heavy work moves off-device |
| **Fast recovery** | a broken sandbox is a rebuild (`03` §6), not a reinstall |
| **Honest capability testing** | you can measure what LYA can do without risking the real environment |
| **A clean story for the "full access" question** | she gets *full access to the workshop*, and none to your life — which is what you actually want |

## What you give up

- **Convenience:** a second environment means moving artifacts deliberately, and it will feel
  slower for the first week.
- **RAM/complexity on the laptop** if you run a local VM instead of using the cloud VM.
- **Nothing else.** No security property is lost by isolating; several are gained.

---

## The decision, stated plainly

> **Build the workshop. Put the risky 80 % of LYA's work there. Keep the vault, the identity and
> the audit on your laptop, where they are already small and boring.**
>
> At the testing stage this is exactly right — and unlike most "right" architectures, this one is
> free and can start tonight.

---

## Change log

### 2026-09-24 — Isolation plan assessed
**Goal:** decide whether "give LYA her own platform" is useful or over-engineering.
**Changed:** this file created — six corrections, the gain/give-up tables, and the decision.
**Verified by:** Microsoft Learn (Windows Sandbox page, updated 2026‑03‑29: *"Windows Sandbox is
currently not supported on Windows Home edition"*; WSL install page) and the VMware blog
(Workstation/Fusion free from 2024‑11‑11, personal **and** commercial use, no Global Support
entitlement). Local measurement: `Win32_OperatingSystem` → **Windows 11 Home Single Language**,
build 26200; `HypervisorPresent = True`; **WSL not installed**; no VirtualBox, VMware or Docker
Desktop present; 7.71 GB RAM; 210.6 GB free on C:.
**Left undone / follow-up:** the VivoBook's specs and thermals are **unmeasured** (it is a different
machine) — `04-HARDWARE-REALITY.md` lists exactly what to measure.
**Notes:** disclosure — while checking WSL, Windows offered an interactive "press any key to install
WSL" prompt. **It was not accepted**, and it times out on its own; nothing was installed.
