# 03 — SANDBOX SPEC: what the workshop actually is

> Concretely, this is the thing you build. Target: **rebuildable in under 15 minutes from a written
> recipe**, so that "destroy and recreate" is a routine action rather than a disaster.

---

## 1. Choose the host (per `01-OPTIONS-MATRIX.md`)

| Stage | Host | Why |
|---|---|---|
| **First** | **WSL2 on the laptop** | one evening to set up, instant to use, perfect for trying this out |
| **Second** | **Oracle ARM VM** | the real workshop: off-laptop, always available, zero laptop pressure |
| **Optional** | **VivoBook** | sacrificial rig for experiments you would not run anywhere else |

---

## 2. Base recipe (WSL2 variant — build this first)

```bash
# Inside WSL2, as your normal user (NOT root for daily work)
sudo apt update && sudo apt install -y \
  python3 python3-venv python3-pip git curl ffmpeg build-essential jq ripgrep
python3 -m venv ~/lyawork/venv && source ~/lyawork/venv/bin/activate
pip install httpx playwright
python3 -m playwright install --with-deps chromium
```

**Then apply the isolation settings — these matter more than the packages:**

| Setting | Why |
|---|---|
| `/etc/wsl.conf` → disable Windows interop (`interop.enabled=false`, `appendWindowsPath=false`) | stops the sandbox calling Windows programs |
| **Do not use `/mnt/c`**; unmount or ignore it | the single most important rule: no window into your profile |
| Create one exchange folder (e.g. `~/lyawork/exchange`) as the **only** shared path | the bridge from `02` |
| Keep the firewall in the default deny-incoming posture | no services listening for the world |
| Cap resources in `.wslconfig` (`memory=2GB`, `processors=2`) | protects the 7.71 GB host |

---

## 3. What is installed vs forbidden

| Installed (expected) | Forbidden (never) |
|---|---|
| python, git, ffmpeg, curl, jq, ripgrep | vault files, `.lya_key`, any `.lya` ciphertext |
| playwright + a **sandbox-only** browser profile | biometrics (face/voice templates) |
| build tools for compiling small utilities | the phone token / escalation grants |
| optional: docker (packaging), node | your Windows browser profile, cookies, saved passwords |
| optional: a small local model **only if RAM allows** | long-lived cloud API keys |

**Test that proves the boundary:** from inside the sandbox, try to read a Windows file
(`ls /mnt/c/Users`) → it must **fail**. If it succeeds, the sandbox is not isolated yet.

---

## 4. Resource caps (thermal and RAM protection)

| Guard | Setting | Protects |
|---|---|---|
| Memory | 2 GB (WSL) / 4 GB (VM) hard cap | the host from swapping to death |
| CPUs | 2 of 8 threads | thermals; the i3-1315U has only 2 performance cores |
| `nice`/`ionice` for batch jobs | low priority | keeps the laptop usable while she renders |
| Long-job policy | no job > 30 min without an explicit approval | a runaway task cannot cook the machine |
| Disk | cap the VM disk; alert at 80 % | a full disk is the #1 silent breaker |

---

## 5. Network policy

- **Outbound allow-list** for the domains a task genuinely needs; everything else denied.
- **No inbound ports.** Nothing in the sandbox should be reachable from the LAN or the internet.
- **No home-LAN access** from the sandbox — the workshop must not be able to scan your own network
  or your router.
- **API keys are per-task and expiring**; a key that survives its task is a bug.

---

## 6. Snapshot, rebuild, wipe

| Action | When | How |
|---|---|---|
| **Snapshot** | before every experiment that installs something | VM snapshot / WSL export (`wsl --export`) |
| **Rebuild** | after any suspicious behaviour | restore the snapshot, or re-run the recipe above |
| **Wipe** | after risky experiments on the VivoBook | reinstall or reset, no attempt to "clean" |
| **Verify** | monthly | re-run the boundary test, confirm the cap, confirm no keys present |

**Store the recipe itself in the repo** (`lya-platform/` is exactly the right place). A sandbox
whose build steps exist only in your memory is not rebuildable.

---

## 7. What LYA gains, and what stays impossible

| Gains | Still impossible |
|---|---|
| Run generated code without risking the vault | Reading `/mnt/c` (by design) |
| Scrape, automate, render, publish from a disposable box | Completing a payment (`../lya-agency/04`) |
| Experiment with networking tools safely | Escaping to your home LAN |
| Rebuild in minutes after a mess | Holding your keys — ever |

---

## Change log

### 2026-09-24 — Sandbox spec written
**Goal:** turn the isolation plan into a recipe someone can follow tonight.
**Changed:** this file created — host choice, a copy-paste WSL2 recipe, the isolation settings that
matter more than the packages, forbidden-content list, resource caps, network policy, snapshot/
rebuild rules, and a boundary test.
**Verified by:** prerequisites confirmed on this machine — `HypervisorPresent = True`, WSL not yet
installed, 7.71 GB RAM (hence the 2 GB cap), 210.6 GB free, ffmpeg 8.1.2 already present on the
Windows side. Package names are standard Ubuntu LTS names; **no command in this file has been run
yet**.
**Left undone / follow-up:** the recipe must be executed once and corrected against reality before
anyone trusts it. The `.wslconfig` settings and the interop-disable step are the two that are most
often skipped — and they are the two that matter.
**Notes:** the boundary test (`ls /mnt/c/Users` must fail) is the acceptance criterion for the whole
document. Without it, this is a shell with a nice story attached.
