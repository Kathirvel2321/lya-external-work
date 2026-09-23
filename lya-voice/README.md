# Lya — Real-Sounding Tamil + English Girl Voice (₹0 start, low-spec laptop)

Your laptop: **Intel i3-1315U, 7.7 GB RAM, Intel UHD Graphics (no GPU), Windows 11**.
Verdict up front: **a real, smooth, expressive Tamil+English girl voice is possible on
this laptop — but not by training or cloning a model locally.** That door is shut
by hardware, not by skills. Anyone selling a "train your own voice on your laptop"
path on 7.7 GB / no GPU is either renting a cloud GPU or lying.

The way around it is the hacker route: **do the neural work on someone else's
free servers, and make it sound human locally with ffmpeg.** That is exactly what
this folder does. Nothing heavy is installed here.

---

## 0. Test it in 2 minutes (no API key needed)

**You do not need any API key to hear Lya talk.** The free engine is already
working on your machine. Do exactly this:

```powershell
cd C:\Users\ipvis\Documents\lya-voice

python lya_voice.py --doctor          # checks everything AND makes a test file
python lya_voice.py --preview         # 10 mood samples -> out/preview/
python lya_tune.py --only pitch       # younger/older -> out/tune/
```

Then listen. `--doctor` ends by printing the exact play command for you, e.g.:

```powershell
ffplay -nodisp -autoexit "C:\Users\ipvis\Documents\lya-voice\out\doctor_test.mp3"
```

If you hear a young Tamil woman speaking Tamil + English, Lya works. That is the
whole test. `--doctor` is also the thing to run later when something breaks — it
tells you which link in the chain failed instead of leaving you guessing.

### Where the keys go (when you decide you want them)

Nothing is required. When you do get keys, put them in **one file**:

```powershell
cd C:\Users\ipvis\Documents\lya-voice
copy keys.env.example keys.env
notepad keys.env          # paste after the "=" signs, save
```

`keys.env` is read automatically by every Lya script — no `setx`, no restart, no
terminal changes. Rules it follows:

- A real Windows environment variable **always wins** over a line in the file, so
  you can override for one session without editing anything.
- Empty lines are skipped, so you only fill in what you actually have.
- Keep it private: it is your billing credential. Do not screenshot it or paste
  it into a chat.

Which key unlocks what:

| Key | What it unlocks | Needed for testing? |
|---|---|---|
| *(none)* | Free Edge voices, mood engine, phone realism, tuning | **Yes — this is all you need** |
| `SARVAM_API_KEY` | Bulbul voice engine (`--engine sarvam`) **and** Tamil speech-to-text (`lya_chat.py --mic`) | Optional |
| `LYA_BRAIN_BASE_URL` + `LYA_BRAIN_API_KEY` (+ model) | A real brain for `lya_chat.py` instead of the offline echo brain | Optional |

Where to get them:

- **Sarvam** — https://dashboard.sarvam.ai (new accounts get free credits).
  Costs afterwards: ₹30 per 10,000 characters of speech, ₹30/hour of listening.
- **Brain** — any OpenAI-compatible endpoint, free options: Google Gemini
  (base URL `https://generativelanguage.googleapis.com/v1beta/openai/`, model
  `gemini-3.8-flash`), NVIDIA NIM (`https://integrate.api.nvidia.com/v1`),
  Groq (`https://api.groq.com/openai/v1`), or local Ollama
  (`http://localhost:11434/v1`). All four are pre-written in `keys.env.example`.

---

## 1. Why local training is out (be clear about this)

| Attempt | Disk | RAM | GPU | Verdict on your laptop |
|---|---|---|---|---|
| RVC / GPT-SoVITS / XTTS-v2 fine-tune (own voice) | 15–60 GB | 12–32 GB | 6–12 GB VRAM | **Impossible.** Won't even load. |
| IndicF5 (AI4Bharat, Tamil zero-shot clone, 0.4B) | ~10 GB PyTorch | ~8–12 GB | realistically 8 GB VRAM | **Too slow/unstable on CPU**, needs PyTorch + Python 3.10/3.11 (you have 3.14). |
| Kokoro-82M (lightest real local TTS) | ~1 GB | ~2 GB | none (CPU ok) | Runs, **but it does not support Tamil.** Hindi/English only. |
| Piper (classic light local TTS) | small | small | none | **No usable Tamil voice**; quality is clearly robotic. |
| **Cloud neural TTS + local ffmpeg polish** | ~20 MB | ~150 MB | none | ✅ **This is the answer.** |

So: **local synthesis = no. Cloud synthesis driven from this laptop = yes, free, today.**

---

## 2. The stack, in order of use

### Tier 1 — NOW, ₹0, nothing to install beyond two small packages (this folder)
**Microsoft Edge neural voices**, reached through the `edge-tts` Python library.
No API key, no account, no billing, no credit card. Their servers do the work;
you download a 24 kHz MP3.

Verified available Tamil/Indian female voices (queried live from your machine):

| Voice | Notes |
|---|---|
| `ta-IN-PallaviNeural` | **Primary Lya.** Tamil (India), female. |
| `ta-LK-SaranyaNeural` | Tamil (Sri Lanka), female — a second flavour. |
| `ta-MY-KaniNeural` | Tamil (Malaysia), female. |
| `ta-SG-VenbaNeural` | Tamil (Singapore), female. |
| `en-IN-NeerjaExpressiveNeural` | Indian-English female (for `--split-lang` mode). |
| `en-US-AvaMultilingualNeural`, `en-US-EmmaMultilingualNeural` | Multilingual female voices (experimental with Tamil — try by ear). |

**The single most important design decision here:** Lya keeps **one voice
identity** and speaks English words *in that same Tamil voice*. That is how a
real Tamil girl actually talks on the phone ("link, price, site" in her own
accent). Swapping to an American voice mid-sentence is the #1 thing that makes
an agent sound fake.

### Tier 2 — when you want a Tamil-native, more emotional engine (₹100 free credits)
**Sarvam AI Bulbul v3** — built in India, 11 Indian languages including Tamil,
30+ voices, emotion/prosody control, WebSocket streaming for live conversation.
Verified pricing: **₹30 per 10,000 characters** of speech synthesis, and
**every new developer gets ₹100 in free credits** — about **30+ minutes of
speech free**, plus speech-to-text at ₹30/hour (so ~3 hours of listening free).
This is the strongest paid-but-cheap upgrade for a Tamil-speaking agent.

### Tier 3 — your own unique cloned voice (later, once Lya earns)
- **ElevenLabs**: Tamil is supported in the multilingual v2 and Flash v2.5
  models. Docs confirm Instant Voice Cloning needs a paid plan (Starter ~$5/mo)
  and Voice Library voices are **not** available to free-tier API users. Free
  tier is 10k characters/month with no commercial licence.
- **Google Cloud Chirp 3 HD / Instant custom voice**: Tamil (`ta-IN`) available;
  1M characters/month free for Chirp 3 HD, but instant custom voice is paid-only.
- **IndicF5** (free, MIT-ish terms, 11 Indian languages incl. Tamil, zero-shot
  cloning from a few seconds of audio) — the correct long-term play, but run it
  on a **rented GPU** or a future machine, not on this laptop.

### Ruled out
**Gemini 2.5 / 2.5 Pro TTS**: great expressive control in theory (director's-note
style prompts, multi-speaker), but the official pricing page lists the free tier
for TTS as **"Not available"** — it is paid-only. Fine later at roughly
$0.015 per minute of audio, but it is not a ₹0 path.

---

## 3. The five tricks that remove the "AI agent voice"

1. **Phone-band realism.** A real telephone only carries 300–3400 Hz. Applying
   that band (`--- phone` mode, default) does two things at once: it gives you
   the literal "talking on a mobile" sound you asked for, **and** it hides
   almost every neural synthesis artefact. This is the single biggest
   anti-robotic move in the whole pipeline.
2. **One identity, many moods.** Ten mood presets change rate, pitch and volume
   the way a real person does — `warm, happy, excited, caring, calm, shy,
   teasing, serious, sad, whisper`.
3. **Per-sentence micro pitch jitter.** Real speech never repeats the same
   pitch contour twice. Most TTS does, and that is what your ear recognises as
   "AI". Lya nudges pitch a little on every sentence.
4. **Human pauses + Tamil filler words.** Sentence gaps scale with the mood
   (0.10 s when excited, 0.36 s when sad) and optional fillers ("ம்ம்", "ஆமா",
   "அப்படியா") land at sentence boundaries where a real person puts them.
5. **A barely-there noise bed.** -42 dB of filtered pink noise. Pure digital
   silence is unnatural; a faint line-noise floor is what a phone call has.

Bonus: **same girl, different seat.** The `--personality` flag applies a tiny
global pitch/formant shift, so you can have "Lya soft" / "Lya bright" /
"Lya deep" without ever changing who she is.

---

## 4. How to use it

Two commands to get running (both already done on this machine):

```powershell
pip install edge-tts          # ~2 MB, no GPU, no account
# ffmpeg is already installed (8.1.2)
```

Then:

```powershell
cd C:\Users\ipvis\Documents\lya-voice

# basic Tamil line, phone realism, plays when done
python lya_voice.py --text "வணக்கம்! நான் லியா." --mood warm --play

# mixed Tamil + English, teasing tone, Tamil filler words
python lya_voice.py --text "Call pannunga, price five thousand only." --mood teasing --fillers --play

# a whole script from a file, caring tone, different seat for the voice
python lya_voice.py --file samples/sample_01_warm.txt --mood caring --personality soft --out out/reply.mp3

# if you prefer Tamil voice for Tamil + Indian-English voice for Latin words
python lya_voice.py --file samples/sample_01_warm.txt --split-lang --play

# hear every mood side by side
python lya_voice.py --preview        # -> out/preview/mood_*.mp3
python lya_voice.py --list-moods
```

Key flags: `--mood` (10 moods), `--personality` (lya/soft/bright/deep),
`--phone` / `--studio`, `--fillers`, `--split-lang`, `--seed` (repeatable output),
`--no-ambience`, `--out`, `--play`, `--preview`.

### 4b. Pick her voice by ear (`lya_tune.py`)

Instead of describing what you want in words, listen to labelled variants:

```powershell
python lya_tune.py --play                # full grid (~19 variants)
python lya_tune.py --only pitch          # younger/older ladder (4 files)
python lya_tune.py --only rate --only seat
python lya_tune.py --only voice          # the 4 Tamil female voices
```

It writes `out/tune/NN_label.mp3` plus `out/tune/index.md`, which lists exactly
what changed in each file. Then you just say **"use 03"** or "03 pace with 06
seat" and I make that the default. Only the knob you changed differs, because
every variant uses the same line and the same seed.

### 4c. Talk to her (`lya_chat.py`)

Listen → think → answer in her voice:

```powershell
python lya_chat.py                                # typed chat, she answers in audio
python lya_chat.py --text "சொல்லுங்க"              # one turn then exit
python lya_chat.py --mic --seconds 6              # speak; needs STT (below)
python lya_chat.py --mic --loop                   # keep talking
python lya_chat.py --list-mic                     # confirm the mic works
python lya_chat.py --no-audio --text "hi"         # text only, fast testing
```

- **Listening:** the mic is recorded by ffmpeg (already installed — no Python
  audio library). Speech-to-text needs **`SARVAM_API_KEY`** (Sarvam Saaras,
  best for Tamil) or a local `pip install faster-whisper`. Without either, it
  tells you so instead of failing silently.
- **Thinking:** any OpenAI-compatible endpoint via `LYA_BRAIN_BASE_URL` +
  `LYA_BRAIN_API_KEY` + `LYA_BRAIN_MODEL` — that covers free NVIDIA NIM, Groq,
  OpenAI-compatible local Ollama, etc. With no key set it uses an offline echo
  brain, so the whole loop is testable at ₹0.
- **Speaking:** the same engine, with the mood auto-picked from her reply text
  (`pick_mood()` — a documented keyword heuristic, not a claim of emotion AI).

**Note on PowerShell + Tamil:** passing Tamil directly on the command line can get
mangled by the shell encoding. Use `--text` with ASCII/simple text, or put Tamil
in a UTF-8 file and use `--file` (recommended — that is what `samples/` is for).
Python code that calls `render()` directly never has this problem.

### 4d. The paid engine (`--engine sarvam`)

Built and verified against Sarvam's own docs. It needs a key, so the honest
statement is: **the request is provable without spending anything.**

```powershell
# preview the exact request, no key, nothing sent, nothing charged
python lya_voice.py --file samples/sample_01_warm.txt --engine sarvam --dry-run

# then, once you have a key (new accounts get ₹100 free credits):
$env:SARVAM_API_KEY = "your-key"
python lya_voice.py --file samples/sample_01_warm.txt --engine sarvam --out out/bulbul.mp3
python lya_tune.py --engine sarvam --only voice --play
```

Verified facts from the Sarvam docs (not guesses):

| Fact | Value |
|---|---|
| Endpoint / auth | `POST https://api.sarvam.ai/text-to-speech`, header `api-subscription-key` |
| Model | `bulbul:v3` (default), `bulbul:v2` legacy |
| Response | JSON with `audios`: base64 **WAV** |
| `pace` | 0.5–2.0 (mood `+8%` → `pace 1.08`; our code clamps) |
| `pitch` / `loudness` | **v2 only** — so on v3 the micro-jitter is applied in the audio domain instead |
| SSML | **Not supported** — use `pace` and sentence splitting |
| Max text | 2,500 chars per request |
| Price | **₹30 per 10,000 characters**; new accounts get **₹100 free credits** |
| Speech-to-text | `POST /speech-to-text`, multipart, `saaras:v3`, **30 s max per request**, ₹30/hour |

**Important limitation found in their docs:** Romanised Indic input degrades
output quality — Bulbul wants **native Tamil script**, so feed it `வணக்கம்`,
not `vanakkam`. That is the opposite of Edge TTS, which handles "Tanglish" fine.

---

### 4e. How old does she sound? (measured, not guessed)

I measured the actual fundamental frequency (pitch) of her voice at each setting
with `python tests/age_probe.py`, on unfiltered renders (no phone band masking
anything). The measuring tool was first **validated against known test tones** —
150 Hz tone → read 149.5 Hz, 220 Hz → 219.2 Hz, 300 Hz → 301.9 Hz, so it is
accurate to about ±2%.

| Setting | Measured median pitch | Reads as |
|---|---|---|
| `--pitch -25Hz` | **206 Hz** | mature adult woman, calm (late 20s–30s feel) |
| `--pitch -10Hz` | 232 Hz | adult woman |
| `--pitch +0Hz` | 250 Hz | young adult woman |
| **default (`warm`, +15 Hz)** | **264 Hz** | **young adult woman, bright — early 20s** |
| `--pitch +25Hz` | 278 Hz | very young / bubbly teen-leaning |
| `--pitch +45Hz` | 296 Hz | teen-bright, nearing cartoon — this is the ceiling |
| `ta-LK-Saranya` at +15 | 260 Hz | young adult woman (Sri Lankan Tamil) |
| `ta-MY-Kani` at +15 | 276 Hz | younger-leaning woman (Malaysian Tamil) |

For reference: typical adult female speech sits around 165–255 Hz, adult male
85–155 Hz, and a young child 250–400 Hz.

**So, plainly: the default voice agent is a young adult woman, early 20s,
bright and youthful.** Her spread within a sentence is roughly 198–356 Hz
(p10–p90), which is normal expressive human range, not a flat monotone.

Two honest caveats:

1. **Pitch is only half of "age".** Perceived age also comes from *formants*
   (vocal-tract size), and those stay adult at every setting — that is why
   `+45Hz` sounds bright-and-young rather than like an actual child. Pitch moves
   the *read* of her age by a few years; it does not turn her into a child.
2. **There is no Tamil child voice available.** The only "Cute"/child-style voice
   in the free catalogue (`en-US-AnaNeural`) is English-only and cartoon-toned.
   If you truly need a child voice in Tamil, that is not a knob — it is a paid
   cloned voice (Phase 4) or a different provider.

If early-20s is too young for you, the honest fix is one command:
`--pitch 0` or `--pitch -10` (232–250 Hz) lands her in clear adult-woman range.

---

## 5. What was verified on this machine (not assumed)

| Check | Result |
|---|---|
| `edge-tts` installs and runs on Python 3.14.6 / Windows 11 | ✅ |
| Tamil female voices actually offered by the service | ✅ `ta-IN-PallaviNeural`, `ta-LK-SaranyaNeural`, `ta-MY-KaniNeural`, `ta-SG-VenbaNeural` |
| Tamil synthesis + prosody params (`rate`/`pitch`/`volume`) | ✅ 24 kHz mono MP3 produced |
| All 10 moods render, and mood genuinely changes pacing | ✅ excited 7.9 s → caring 11.2 s for the same text |
| Phone band truly applied | ✅ energy above 4 kHz: **-40.5 dB** (phone) vs **-34.6 dB** (studio) |
| Mobile-call loudness target | ✅ **-16.1 LUFS** integrated, true peak **-1.4 dBFS** |
| Mixed Tamil + Latin text in one take | ✅ renders without errors |
| Same seed → byte-identical audio (repeatable takes) | ✅ identical |
| Tuning grid renders labelled variants + index | ✅ 7 variants, `out/tune/index.md` |
| Mic visible to ffmpeg (no Python audio lib needed) | ✅ `Microphone Array (Intel Smart Sound Technology)` |
| Chat loop produces a voice reply | ✅ `out/chat/turn_01_warm.mp3` |
| Sarvam request shape (provable without a key) | ✅ dry-run prints POST + header + full JSON payload |
| Sarvam without a key fails with guidance, not a stack trace | ✅ |
| Unknown engine name rejected | ✅ |
| Full suite | ✅ **11/11 passing** (`python tests/smoke_test.py`) |
| `--doctor` end-to-end check + live test render | ✅ reports each link, writes `out/doctor_test.mp3` |
| Pitch/age measuring tool accuracy | ✅ validated on test tones: 150→149.5 Hz, 220→219.2 Hz, 300→301.9 Hz |
| Voice age measured (not guessed) | ✅ default **264 Hz**, `-25Hz` → 206 Hz, `+45Hz` → 296 Hz |
| `keys.env` loader | ✅ loads KEY=VALUE lines; real env vars still win |

**Not verified (only your ears can):** whether the result sounds like the girl
you want. I have no speakers — this is where you listen and we tune. Start with
`out/tune/` (labelled) and `out/preview/`, then say "use 03" or "slower".
Everything is a parameter, nothing is hardcoded psychology.

**Not verified (needs a key I do not have):** the live Sarvam TTS/STT calls
themselves, and any real LLM brain. The request shape is doc-verified and
dry-run provable; the network round-trip is untested until you add a key.

---

## 6. Roadmap

**Phase 1 (today, ₹0):** Edge TTS + this engine. Get a voice you are happy with
by ear. Use `--phone` for call-style, `--studio` for video/voice-note style.

**Phase 2 (built, needs a key):** the Sarvam Bulbul v3 adapter exists now
(`--engine sarvam`), with the ₹100 free credits for A/B comparison on the same
script. If Bulbul wins, keep it as the "high-quality" path and Edge as the free
unlimited one. Note the native-script requirement for Tamil words.

**Phase 3 (built, needs a key for the brain/STT):** `lya_chat.py` wires
listen → think → speak:
- STT: Sarvam Saaras (`saaras:v3`, 30 s per request, ₹30/hour, inside the free
  credits) or local `faster-whisper`.
- Brain: any OpenAI-compatible endpoint (free NVIDIA NIM, Groq, local Ollama);
  offline echo brain for ₹0 testing.
- Voice: `render()` from this engine, mood auto-picked from her reply.
- Real-time streaming: still deliberately not attempted. Edge TTS is fine for
  voice notes and turn-by-turn replies, not for natural live phone conversation.

**Phase 4 (paid, only once Lya earns):** own unique cloned voice —
ElevenLabs Instant Voice Cloning (Starter ~$5/mo, Tamil via multilingual v2)
or a rented GPU running **IndicF5** for a Tamil-native clone you own outright.

---

## 7. Honest limitations

1. **Do not put this voice on a phone line claiming to be a human.** In India,
   and in most places, undisclosed AI voices are a legal and ethical problem
   (and worse for cold outreach). Keep Lya clearly an assistant, or disclose.
2. **Edge TTS is a Microsoft service with no contract.** Today it is free with
   no key; it can rate-limit, change voices, or stop working. That is why
   Phase 2/4 exist — do not build the business on a single undefended free tier.
3. **Free tier = the voice is not exclusively yours.** Someone else could pick
   the same voice. Uniqueness only arrives at Phase 4 (cloning).
4. **Whisper/soft moods are the weakest.** Whispering is not what neural TTS
   does best; treat `--mood whisper` as experimental and use `--volume`-style
   softness (`--mood shy`) instead if it sounds wrong.
5. **Never clone a real person's voice without written permission.** IndicF5's
   own terms say this explicitly.
6. **The live paid paths are untested by me.** No `SARVAM_API_KEY` and no LLM key
   exist on this machine, so Sarvam TTS/STT and any real brain have never made a
   network call here. The request shapes are doc-verified and dry-run provable —
   the round-trip is your first test.
7. **Sarvam speech-to-text caps at 30 seconds per request** and costs ₹30/hour.
   Longer recordings need chunking or the batch API.
8. **Sarvam wants native Tamil script.** Romanised Tamil ("vanakkam") measurably
   degrades its output. Edge TTS is the opposite — it handles Tanglish fine.
   Keep that in mind if you switch engines: same script, different best practice.
9. **She tells the truth about being an AI.** `lya_chat.py`'s persona explicitly
   answers "you are Lya, an AI assistant" if anyone asks. If you want that
   changed, ask me in plain words — I will not quietly remove it.
10. **The mic depends on Windows privacy settings.** If `--list-mic` finds nothing,
   check Settings → Privacy → Microphone, and make sure no other app is holding
   the device exclusively.
