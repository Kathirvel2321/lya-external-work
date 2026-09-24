# 04 — HARDWARE REALITY: are we squeezing these laptops?

> **Yes — you are right to worry.** This file puts numbers on it, and states which machine should do
> which job. Everything about the MSI laptop below was **measured**; everything about the VivoBook is
> **unmeasured** and labelled as such.

---

## 1. The honest pressure accounting

| Workload | Approx. cost | Where it should run |
|---|---|---|
| Windows 11 baseline + a browser with tabs | **2.5–4 GB** | Zone A (unavoidable) |
| LYA orb (Tk) + worker thread + SQLite | ~150–400 MB | Zone A |
| Vision stack (InsightFace + anti-spoof ONNX), when loaded | 300 MB–1 GB | Zone A, **lazy only** |
| Local LLM (a ≤1B Q4 model via Ollama) | **0.8–1.5 GB** | ⛔ **not on this laptop with Windows** (see §2) |
| ffmpeg render (1080p, CPU-only) | 1–2 cores, sustained → **heat** | Zone B |
| Browser automation (Playwright/Chromium) | 0.5–1.5 GB per instance | Zone B |
| Long scrapes / batch jobs | sustained CPU → **heat** | Zone C |
| A local Windows VM guest | **4 GB+** | ⛔ impossible on 7.71 GB with the host running |
| A local headless Linux VM guest | 1.5–2 GB, capped | 🟡 viable, one at a time |

**The pattern:** almost everything new you add competes for the same ~3–4 GB of headroom and the
same two performance cores. That is exactly why the fix is **moving work off the laptop**, not
buying more software for it.

---

## 2. The MSI laptop — measured 2026-09-24

| Fact | Value | Consequence |
|---|---|---|
| CPU | **Intel i3-1315U**, 6 cores (2P + 4E) / 8 threads | only **2 performance cores**; sustained heavy work hits a wall fast |
| RAM | **7.71 GB usable** (not 8 GB — the iGPU reserves some) | a local LLM + Windows + browser is already at the limit |
| GPU | Intel UHD, shared memory, driver 31.0.101.4314 | **no CUDA, no VRAM** → no local AI video/image generation |
| Disk | 242.8 GB used / **210.6 GB free** | fine today; video renders will eat it — put them in Zone B |
| OS | Windows 11 Home Single Language, build 26200 | **no Windows Sandbox**, no Hyper-V role (`01`) |
| Virtualisation | `HypervisorPresent = True` | WSL2/VMware will work |
| Account | **not administrator** | keep it — it is a security control (`../lya-brain/13` §1) |
| Already present | **ffmpeg 8.1.2**, Python 3.11.9 | local rendering works **today** |
| Missing | WSL, Docker, VirtualBox, VMware | nothing isolation-related is set up yet |

**Verdict for this machine:** excellent as **Zone A** and as a **thin client** to the workshop.
Not a render farm, not a model host, not a 24/7 server.

---

## 3. The ASUS VivoBook (fanless i3) — unmeasured

I cannot query it from here, so these are **unknowns, not facts**. Measure before assigning it a
role:

```powershell
Get-CimInstance Win32_Processor | Select Name,NumberOfCores,NumberOfLogicalProcessors
'RAM_GB=' + [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,2)
(Get-CimInstance Win32_OperatingSystem).Caption
Get-PSDrive C | Select @{n='FreeGB';e={[math]::Round($_.Free/1GB,1)}}
Get-CimInstance Win32_ComputerSystem | Select HypervisorPresent
powercfg /batteryreport     # battery wear — tells you how old the machine really is
```

### The fanless rule

A fanless laptop sheds heat through its chassis. Under **sustained** load it throttles, the chassis
gets hot, and the battery suffers. So:

| ✅ Right role | ⛔ Wrong role |
|---|---|
| sacrificial test rig for risky experiments | an always-on LYA host |
| short jobs (minutes, not hours) | long renders, model inference, 24/7 services |
| wiped without regret after a mess | holding anything you would miss |

**Rules if you do use it:** cap threads to half the cores, keep jobs under ~30 minutes, sit it on a
hard surface with airflow, never on a bed or cushion, and stop at the first sign of throttling.
Measure throttling with `Get-Counter '\Processor Information(_Total)\% Processor Performance'` —
sustained values **below 100 %** mean the CPU is being held back by thermals.
(Note: the WMI thermal-zone query returned nothing on the MSI here and typically needs elevation, so
use a hardware monitor such as HWiNFO for real temperatures.)

## 4. How to measure the pressure (rather than guess)

| Question | Command | What "bad" looks like |
|---|---|---|
| Is RAM the problem? | `Get-Counter '\Memory\% Committed Bytes In Use'` | sustained **> 85 %** → everything swaps, the machine "feels corrupted" |
| Which process eats RAM? | `Get-Process \| Sort WorkingSet -Desc \| Select -First 10 Name,WorkingSet` | a browser or a model process dominating |
| Is the CPU throttling? | `Get-Counter '\Processor Information(_Total)\% Processor Performance'` | sustained **< 100 %** = thermal limit |
| Is the disk the bottleneck? | `Get-Counter '\PhysicalDisk(_Total)\Avg. Disk sec/Read'` | **> 0.02 s** on an SSD means something is wrong |
| Is the battery/age an issue? | `powercfg /batteryreport` | design capacity vs full-charge capacity |

Record these **before** adding anything else. Then the same numbers after each change — that is how
you prove the isolation actually relieved the laptop instead of just sounding tidy.
(`../lya-brain/04-SPEED-BUDGET.md` already asks for this discipline; this gives it the hardware half.)

---

## 5. The cheap wins (all of them reduced *pressure*, none reduce capability)

| Win | Effect |
|---|---|
| **Runtime moves off-laptop** (Zone B/C) | the single biggest relief |
| Vision stack stays **lazy** — never loads at boot | 300 MB–1 GB saved most of the time |
| **No local LLM** while Windows is up | ~1 GB saved; Groq does the thinking (`../lya-brain/03`) |
| WSL capped at **2 GB / 2 CPUs** | protects the host during renders |
| Renders and long jobs → **Zone B** | no sustained heat, no 210 GB creeping away |
| **Retention purge** for `shots/` + `debug/` | removes ~2.3 MB of *unencrypted* media that is a security finding anyway (S‑8) |
| Quarantine the **18 legacy skills + offensive toolkit** | less startup surface, smaller attack surface, lower legal risk (`../lya-brain/13` §6) |
| LYA **does not autostart** until the system is stable | you choose when the heat happens |
| Keep **15–20 % of the disk free** | SSDs slow down sharply when nearly full |
| One heavy thing at a time (render **or** model **or** camera) | the machines are simply small |

**What NOT to do to relieve pressure:** do not disable Defender or Windows Update "for speed", do
not run LYA elevated, and do not add more features to Zone A. Those trade a real risk for a
temporary illusion of speed.

---

## Change log

### 2026-09-24 — Hardware reality documented
**Goal:** answer "are we putting too much pressure on these laptops?" with measurements rather than
opinions.
**Changed:** this file created — a workload cost table, the measured MSI profile, an
unmeasured-VivoBook section with a measurement script and fanless rules, five pressure-measurement
commands, and ten concrete relief wins.
**Verified by:** local measurement on the MSI — `Win32_Processor` (i3-1315U, 6C/8T),
`TotalPhysicalMemory` (7.71 GB), `Win32_VideoController` (Intel UHD, driver 31.0.101.4314),
`Get-PSDrive C` (210.6 GB free), `Win32_OperatingSystem` (Windows 11 Home, build 26200),
`HypervisorPresent = True`, `ffmpeg -version` (8.1.2), `wsl --status` (**not installed**), and
absence checks for VirtualBox/VMware/Docker. The WMI thermal-zone query returned no data (needs
elevation / unsupported).
**Left undone / follow-up:**
- **The VivoBook has not been measured at all** — run the script in §3 on it.
- The RAM figures in §1 are **estimates** for planning; replace them with measured values.
- Thermal behaviour under a real render has not been observed on either machine yet.
**Notes:** the honest summary is that these are **two small laptops**, not two workstations. The plan
works precisely because it stops trying to make them do a server's job.

