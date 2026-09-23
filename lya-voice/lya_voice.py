#!/usr/bin/env python3
"""
Lya Voice Engine
================
An expressive Tamil / Tanglish / English voice for the "Lya" agent, designed for
a small CPU-only laptop (no GPU, ~8 GB RAM).

Why it is built this way
------------------------
Neural voice synthesis happens 100% cloud-side (free Microsoft Edge neural
voices, no API key). This machine only downloads a 24 kHz mono MP3 and runs
light ffmpeg post-processing. Nothing heavy is ever installed locally, so a
low-spec laptop can sound like a high-end one.

What makes it sound like a real girl instead of an AI agent
-----------------------------------------------------------
1. ONE voice identity (Pallavi, Tamil female) handles Tamil AND English words,
   the way a real Tamil speaker code-switches on a phone call ("site, price,
   link" said in her own accent). No robotic accent swapping mid-sentence.
2. Mood presets shape rate / pitch / volume the way humans actually shift.
3. Per-sentence micro pitch jitter removes the "every line read identically"
   tell that gives almost all TTS away.
4. Human micro-pauses + optional Tamil filler words ("ம்ம்", "ஆமா") between
   sentences, exactly like real speech.
5. "Phone" mode applies a real telephone band (250-3400 Hz) + compression +
   loudness normalisation. This masks synthesis artefacts AND literally
   delivers the "talking through mobile" sound that was asked for.

Usage
-----
  python lya_voice.py --text "வணக்கம்! நான் லியா." --mood warm --phone --play
  python lya_voice.py --text "Call pannunga, price five thousand only." --mood teasing
  python lya_voice.py --file script.txt --mood caring --split-lang --fillers --out lya.mp3
  python lya_voice.py --preview            # renders one sample per mood
  python lya_voice.py --list-moods
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import random
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / "cache"
OUT_DIR = ROOT / "out"

SR = 24000  # edge-tts output sample rate

TAMIL_FEMALE = "ta-IN-PallaviNeural"            # primary identity: Tamil female
TAMIL_FEMALE_ALT = "ta-LK-SaranyaNeural"        # alternate Tamil female (LK)
TAMIL_FEMALE_MY = "ta-MY-KaniNeural"            # alternate Tamil female (MY)
EN_IN_FEMALE = "en-IN-NeerjaExpressiveNeural"   # Indian-English female
EN_US_AVA_MULTI = "en-US-AvaMultilingualNeural"  # multilingual female (experimental)
EN_US_EMMA_MULTI = "en-US-EmmaMultilingualNeural"

# ---------------------------------------------------------------------------
# Engines
# ---------------------------------------------------------------------------
# edge   : free Microsoft Edge neural voices, no account/key. Default. Handles
#          Romanised Tamil ("Tanglish") fine.
# sarvam : Sarvam AI Bulbul (India-made, 11 Indian languages). Needs a key and
#          a paid/free-credit balance. Wants NATIVE script for Indic words;
#          Romanised Tamil degrades quality - so feed it Tamil script, not
#          "vanakkam".
ENGINES = ("edge", "sarvam")
DEFAULT_ENGINE = "edge"

SARVAM_URL = "https://api.sarvam.ai/text-to-speech"
SARVAM_KEY_ENV = "SARVAM_API_KEY"
SARVAM_MODEL = "bulbul:v3"
SARVAM_LANGUAGE = "ta-IN"
# Confirmed female Bulbul v3 speaker that is documented for Tamil. Other
# female-sounding names to try via --sarvam-speaker: priya, ritu, roopa, simran.
SARVAM_SPEAKER = "ishita"
SARVAM_MAX_CHARS = 2500  # hard API limit for bulbul:v3


def load_keys_env(path: Path | None = None) -> list[str]:
    """Load KEY=VALUE lines from keys.env (stdlib only, no shell changes).

    Why a file: you paste a key once and every terminal sees it, with no
    `setx` and no restart. A real environment variable always wins, so you can
    still override a file entry for one session.
    """
    import os
    path = path or (ROOT / "keys.env")
    loaded: list[str] = []
    if not path.exists():
        return loaded
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and not os.environ.get(key):
            os.environ[key] = value
            loaded.append(key)
    return loaded


KEYS_LOADED = load_keys_env()

# Mood = how a real person shifts when they feel something.
# rate/pitch/volume are Edge TTS prosody values; gap is the pause AFTER a
# sentence in seconds; jitter is the +- per-sentence pitch drift (fraction);
# fillers are Tamil interjections inserted at sentence boundaries.
MOODS: dict[str, dict] = {
    "warm":    {"rate": "+8%",  "pitch": "+15Hz", "volume": "+0%",  "gap": 0.20, "jitter": 0.010, "fillers": ["ம்ம்", "ஆமா"]},
    "happy":   {"rate": "+12%", "pitch": "+35Hz", "volume": "+4%",  "gap": 0.16, "jitter": 0.014, "fillers": ["ஓ", "அப்படியா"]},
    "excited": {"rate": "+20%", "pitch": "+45Hz", "volume": "+8%",  "gap": 0.10, "jitter": 0.018, "fillers": ["ஓ", "நிஜமா"]},
    "caring":  {"rate": "+2%",  "pitch": "+5Hz",  "volume": "+0%",  "gap": 0.32, "jitter": 0.008, "fillers": ["ம்", "பாருங்க"]},
    "calm":    {"rate": "+0%",  "pitch": "-5Hz",  "volume": "+0%",  "gap": 0.30, "jitter": 0.008, "fillers": ["ம்"]},
    "shy":     {"rate": "+4%",  "pitch": "+25Hz", "volume": "-8%",  "gap": 0.26, "jitter": 0.012, "fillers": ["ம்"]},
    "teasing": {"rate": "+14%", "pitch": "+30Hz", "volume": "+2%",  "gap": 0.18, "jitter": 0.016, "fillers": ["ஹே", "அட"]},
    "serious": {"rate": "+2%",  "pitch": "-10Hz", "volume": "+0%",  "gap": 0.24, "jitter": 0.006, "fillers": []},
    "sad":     {"rate": "-6%",  "pitch": "-20Hz", "volume": "-4%",  "gap": 0.36, "jitter": 0.008, "fillers": ["ம்"]},
    "whisper": {"rate": "-4%",  "pitch": "+5Hz",  "volume": "-22%", "gap": 0.28, "jitter": 0.008, "fillers": []},
}

# Same girl, different read: a tiny global pitch/formant shift changes the
# "seat" of her voice without changing who she is.
PERSONALITIES: dict[str, dict] = {
    "lya":    {"shift": 1.000, "tilt": None, "note": "default, neutral-bright"},
    "soft":   {"shift": 0.982, "tilt": "lowshelf=f=220:g=1.5", "note": "gentler, rounder"},
    "bright": {"shift": 1.018, "tilt": "treble=g=2", "note": "livelier, crisp"},
    "deep":   {"shift": 0.965, "tilt": "lowshelf=f=200:g=2.5", "note": "slightly lower, calmer"},
}

TAMIL_RANGE = re.compile(r"[\u0B80-\u0BFF]")
LATIN_RANGE = re.compile(r"[A-Za-z]")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?\u2026\u0964])\s+|\n{2,}")


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def log(msg: str) -> None:
    """Print that never crashes on a non-UTF8 Windows console."""
    try:
        print(f"[lya] {msg}", flush=True)
    except UnicodeEncodeError:
        safe = msg.encode("ascii", "replace").decode("ascii")
        print(f"[lya] {safe}", flush=True)


FFMPEG: str | None = None


def require_tools(engine: str = DEFAULT_ENGINE, dry_run: bool = False) -> None:
    global FFMPEG
    FFMPEG = shutil.which("ffmpeg")
    if not FFMPEG:
        sys.exit("[lya] ERROR: ffmpeg not found on PATH. Install ffmpeg, then retry.")
    if engine not in ENGINES:
        sys.exit(f"[lya] ERROR: unknown engine {engine!r}. Use one of {ENGINES}.")
    if engine == "edge":
        try:
            import edge_tts  # noqa: F401
        except ImportError:
            sys.exit("[lya] ERROR: edge-tts not installed. Run: pip install edge-tts")
    elif engine == "sarvam":
        if not sarvam_key() and not dry_run:
            sys.exit(
                "[lya] Sarvam engine needs an API key.\n"
                f"      Set it once with:  $env:{SARVAM_KEY_ENV} = \"your-key\"\n"
                "      Get a key at https://dashboard.sarvam.ai (new accounts get\n"
                "      free credits). Use --dry-run --engine sarvam to preview the\n"
                "      exact request without a key."
            )


def sarvam_key() -> str | None:
    import os
    key = os.environ.get(SARVAM_KEY_ENV, "").strip()
    return key or None


def ffmpeg(*args: str) -> subprocess.CompletedProcess:
    assert FFMPEG
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args]
    return subprocess.run(cmd, capture_output=True, text=True)


def checksum(*parts: str) -> str:
    h = hashlib.sha1()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:16]


def split_sentences(text: str) -> list[str]:
    """Break text into natural sentence chunks (<= ~200 chars each)."""
    text = text.replace("\r\n", "\n").strip()
    raw = [s.strip() for s in SENTENCE_SPLIT.split(text) if s and s.strip()]
    out: list[str] = []
    for chunk in raw:
        if len(chunk) <= 200:
            out.append(chunk)
            continue
        buf = ""
        for part in re.split(r"(?<=[,;:])\s+", chunk):
            if len(buf) + len(part) + 1 <= 200:
                buf = f"{buf} {part}".strip()
            else:
                if buf:
                    out.append(buf)
                buf = part
        if buf:
            out.append(buf)
    return out or [text]


def split_scripts(text: str) -> list[tuple[str, str]]:
    """Split a mixed sentence into runs of Tamil script vs Latin script."""
    runs: list[tuple[str, str]] = []
    for tok in re.findall(r"\S+\s*", text):
        if TAMIL_RANGE.search(tok):
            kind = "ta"
        elif LATIN_RANGE.search(tok):
            kind = "en"
        else:
            kind = runs[-1][0] if runs else "ta"
        if runs and runs[-1][0] == kind:
            runs[-1] = (kind, runs[-1][1] + tok)
        else:
            runs.append((kind, tok))
    return [(k, v.strip()) for k, v in runs if v.strip()]


# ----------------------------------------------------------------------------
# Synthesis (cloud neural voice -> local cache)
# ----------------------------------------------------------------------------

async def _tts_to_file(text: str, voice: str, rate: str, pitch: str,
                       volume: str, dest: Path) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch,
                                       volume=volume)
    await communicate.save(str(dest))


def sarvam_synth(text: str, dest: Path, *, speaker: str = SARVAM_SPEAKER,
                 model: str = SARVAM_MODEL, pace: float = 1.0,
                 language: str = SARVAM_LANGUAGE, dry_run: bool = False) -> Path | None:
    """One Bulbul request -> WAV file.

    Verified against the Sarvam docs: POST /text-to-speech with the
    `api-subscription-key` header, JSON body, and a response of
    {"request_id": ..., "audios": ["<base64 wav>", ...]}.

    NOTE: this path cannot be exercised without a real key, so it is written to
    be provable: `--dry-run` prints the exact request, and every failure is
    raised with the HTTP status and response body instead of being swallowed.
    """
    import base64
    import json
    import urllib.error
    import urllib.request

    payload = {
        "text": text[:SARVAM_MAX_CHARS],
        "language_code": language,
        "speaker": speaker,
        "model": model,
        "pace": round(max(0.5, min(2.0, pace)), 3),
        "speech_sample_rate": SR,
    }
    if len(text) > SARVAM_MAX_CHARS:
        log(f"warning: text trimmed to {SARVAM_MAX_CHARS} chars for the Sarvam API")

    if dry_run:
        masked = (sarvam_key() or "NO-KEY-SET")[:4] + "..."
        log("[dry-run] POST " + SARVAM_URL)
        log(f"[dry-run] api-subscription-key: {masked}")
        log("[dry-run] " + json.dumps(payload, ensure_ascii=True))
        return None

    key = sarvam_key()
    if not key:
        raise RuntimeError("SARVAM_API_KEY is not set")

    request = urllib.request.Request(
        SARVAM_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"api-subscription-key": key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"Sarvam HTTP {exc.code}: {detail}") from exc
    except Exception as exc:
        raise RuntimeError(f"Sarvam request failed: {exc}") from exc

    audios = body.get("audios") or []
    if not audios:
        raise RuntimeError(f"Sarvam returned no audio: {str(body)[:300]}")
    dest.write_bytes(base64.b64decode("".join(audios)))
    if dest.stat().st_size == 0:
        raise RuntimeError("Sarvam returned empty audio")
    log(f"Sarvam request_id={body.get('request_id', 'unknown')}")
    return dest


def mood_pace(mood: dict) -> float:
    """Mood 'rate' (+8%) -> Bulbul 'pace' (1.08), clamped to the API range."""
    pct = int(mood["rate"].replace("%", "").replace("+", ""))
    return max(0.5, min(2.0, 1.0 + pct / 100.0))


def synth_chunk(text: str, voice: str, mood: dict, jitter: float,
                seed: int, retries: int = 3, engine: str = DEFAULT_ENGINE,
                sarvam_speaker: str = SARVAM_SPEAKER,
                sarvam_model: str = SARVAM_MODEL,
                dry_run: bool = False) -> Path | None:
    """Synthesise one sentence chunk to a cached file (24 kHz mono).

    edge: a cached MP3 from the free Edge service, jitter applied through the
          pitch parameter.
    sarvam: a cached WAV from Bulbul. Bulbul v3 has no pitch parameter (pitch
          and loudness are v2-only), so Bulbul v3 takes only `pace`; the jitter
          and seat shift are applied later, in the audio domain, by to_wav().
    """
    if engine == "sarvam":
        key = checksum("sarvam", text, sarvam_speaker, sarvam_model, mood["rate"])
        cached = CACHE_DIR / f"{key}.wav"
        if cached.exists() and cached.stat().st_size > 0:
            return cached
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        if dry_run:
            return sarvam_synth(text, cached, speaker=sarvam_speaker,
                                model=sarvam_model, pace=mood_pace(mood),
                                dry_run=True)
        last_err: Exception | None = None
        for attempt in range(retries):
            try:
                return sarvam_synth(text, cached, speaker=sarvam_speaker,
                                    model=sarvam_model, pace=mood_pace(mood))
            except Exception as exc:
                last_err = exc
                log(f"retry {attempt + 1}/{retries} for: {text[:40]!r} ({exc})")
        raise RuntimeError(f"Sarvam TTS failed for {text[:60]!r}: {last_err}")

    # jitter is applied by nudging the pitch parameter itself: cheaper and
    # cleaner than re-sampling later, and it changes nothing else.
    base_hz = int(mood["pitch"].replace("Hz", ""))
    if jitter:
        rng = random.Random(seed)
        base_hz += rng.randint(-int(jitter * 400), int(jitter * 400))
    pitch = f"{base_hz:+d}Hz"

    key = checksum(text, voice, mood["rate"], pitch, mood["volume"])
    cached = CACHE_DIR / f"{key}.mp3"
    if cached.exists() and cached.stat().st_size > 0:
        return cached

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    last_err = None
    for attempt in range(retries):
        try:
            asyncio.run(_tts_to_file(text, voice, mood["rate"], pitch,
                                     mood["volume"], cached))
            if cached.exists() and cached.stat().st_size > 0:
                return cached
            raise RuntimeError("empty audio returned")
        except Exception as exc:  # network hiccup / voice hiccup
            last_err = exc
            log(f"retry {attempt + 1}/{retries} for: {text[:40]!r} ({exc})")
    raise RuntimeError(f"TTS failed for {text[:60]!r}: {last_err}")


def silence(seconds: float, dest: Path) -> Path:
    key = checksum("silence", f"{seconds:.3f}")
    cached = CACHE_DIR / f"{key}.wav"
    if cached.exists():
        return cached
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ffmpeg("-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=mono",
           "-t", f"{seconds:.3f}", "-c:a", "pcm_s16le", str(cached))
    return cached


def to_wav(src: Path, dest: Path, shift: float = 1.0) -> Path:
    """Normalise every chunk to identical WAV params so concat is lossless.

    `shift` != 1.0 applies a small audio-domain pitch/formant shift
    (asetrate changes pitch and speed together; atempo restores the speed).
    Used for engines that have no pitch parameter of their own.
    """
    if abs(shift - 1.0) < 1e-6:
        ffmpeg("-i", str(src), "-ar", str(SR), "-ac", "1",
               "-c:a", "pcm_s16le", str(dest))
    else:
        ffmpeg("-i", str(src),
               "-af", f"asetrate={int(SR * shift)},aresample={SR},"
                      f"atempo={1.0 / shift:.6f}",
               "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", str(dest))
    return dest


# ----------------------------------------------------------------------------
# Post-processing: the part that stops it sounding like an AI agent
# ----------------------------------------------------------------------------

def build_chain(mode: str, personality: dict, depth: float = 0.5) -> str:
    """ffmpeg filter chain applied once, to the whole assembled take."""
    filters: list[str] = []

    # 1. Personality tilt: same girl, slightly different "seat".
    tilt = personality.get("tilt")
    if tilt:
        filters.append(tilt)

    # 2. Pitch/formant seat shift (asetrate changes pitch+speed together,
    #    atempo restores the original speed -> a real pitch shift).
    shift = personality.get("shift", 1.0)
    if abs(shift - 1.0) > 1e-6:
        filters.append(f"asetrate={int(SR * shift)}")
        filters.append(f"aresample={SR}")
        filters.append(f"atempo={1.0 / shift:.6f}")

    if mode == "phone":
        # 3a. Real telephone band: this is the "talking through mobile" sound,
        #     and it also hides most neural synthesis artefacts.
        filters += ["highpass=f=250", "lowpass=f=3400"]
        # 3b. Phone AGC feel: compress hard, then normalise loudness.
        filters.append(
            "acompressor=threshold=-20dB:ratio=4:attack=8:release=180:makeup=3"
        )
        filters.append("afftdn=nr=8:nf=-45")          # gentle de-hiss
        filters.append("loudnorm=I=-16:TP=-1.5:LRA=7")  # mobile-call loudness
    elif mode == "studio":
        filters.append("highpass=f=70")
        filters.append(
            "acompressor=threshold=-18dB:ratio=2.5:attack=12:release=250:makeup=2"
        )
        if depth > 0.5:
            filters.append("treble=g=1")
        filters.append("loudnorm=I=-16:TP=-1.5:LRA=9")
    else:  # raw: only loudness, for A/B comparison and for feeding other tools
        filters.append("loudnorm=I=-16:TP=-1.5:LRA=9")

    return ",".join(filters)


def ambience_chain(mode: str, seed: int = -1) -> str:
    """Very low level room/line noise so it is not *too* clean.

    Seeded so that the same --seed reproduces the exact same take.
    """
    level = "-42dB" if mode == "phone" else "-48dB"
    if mode == "phone":
        return (f"anoisesrc=r={SR}:a=0.35:color=pink:seed={seed},"
                f"lowpass=f=3000,volume={level}")
    return (f"anoisesrc=r={SR}:a=0.25:color=brown:seed={seed},"
            f"lowpass=f=1200,volume={level}")




# ----------------------------------------------------------------------------
# Main render pipeline
# ----------------------------------------------------------------------------

def render(text: str, *, mood_name: str = "warm", voice: str = TAMIL_FEMALE,
           phone: bool = True, personality: str = "lya",
           fillers: bool = False, split_lang: bool = False,
           english_voice: str = EN_IN_FEMALE, seed: int | None = None,
           out: Path | None = None, ambience: bool = True,
           depth: float = 0.5, engine: str = DEFAULT_ENGINE,
           sarvam_speaker: str = SARVAM_SPEAKER, sarvam_model: str = SARVAM_MODEL,
           dry_run: bool = False, raw: bool = False) -> Path | None:
    """Render text to one natural-sounding audio file. Returns the file path."""
    if dry_run:
        engine = engine if engine != DEFAULT_ENGINE else "sarvam"
    require_tools(engine, dry_run)
    if mood_name not in MOODS:
        sys.exit(f"[lya] Unknown mood {mood_name!r}. Try --list-moods.")
    mood = MOODS[mood_name]
    pers = PERSONALITIES.get(personality, PERSONALITIES["lya"])
    mode = "raw" if raw else ("phone" if phone else "studio")
    seed = seed if seed is not None else random.randrange(1, 10_000_000)
    rng = random.Random(seed)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = out or (OUT_DIR /
                  f"lya_{mood_name}_{checksum(text, mood_name, personality)[:8]}.mp3")

    sentences = split_sentences(text)
    log(f"{len(sentences)} chunk(s), engine={engine}, voice={voice}, "
        f"mood={mood_name}, personality={personality}, mode={mode}, seed={seed}")

    def chunk(text_part: str, use_voice: str, jitter: float, seed_part: int,
              tag: str) -> Path | None:
        """Synthesise + normalise one piece, applying Sarvam-side jitter."""
        audio = synth_chunk(text_part, use_voice, mood, jitter, seed_part,
                            engine=engine, sarvam_speaker=sarvam_speaker,
                            sarvam_model=sarvam_model, dry_run=dry_run)
        if audio is None:  # dry-run for a paid engine: nothing to assemble
            return None
        # Bulbul v3 has no pitch parameter, so its micro-jitter lives here.
        shift = 1.0
        if engine == "sarvam" and sarvam_model == "bulbul:v3" and jitter:
            local = random.Random(seed_part)
            shift = 1.0 + local.uniform(-jitter, jitter)
        return to_wav(audio, tmpdir / f"{tag}.wav", shift)

    with tempfile.TemporaryDirectory(prefix="lya_") as tmp:
        tmpdir = Path(tmp)
        pieces: list[Path] = []

        for i, sentence in enumerate(sentences):
            # Optional Tamil filler at a sentence boundary, the way people
            # actually say "ம்ம்" before answering.
            if fillers and mood["fillers"] and i > 0 and rng.random() < 0.35:
                filler = rng.choice(mood["fillers"])
                got = chunk(filler, voice, 0.0, seed + i, f"p{i}_fill")
                if got is None:
                    return None
                pieces.append(got)
                pieces.append(silence(round(rng.uniform(0.12, 0.22), 3),
                                      tmpdir / f"p{i}_g1.wav"))

            if split_lang:
                runs = split_scripts(sentence)
                for j, (kind, run) in enumerate(runs):
                    use_voice = voice if kind == "ta" else english_voice
                    got = chunk(run, use_voice, mood["jitter"], seed + i * 31 + j,
                                f"p{i}_{j}")
                    if got is None:
                        return None
                    pieces.append(got)
                    if j < len(runs) - 1:
                        pieces.append(silence(0.06, tmpdir / f"p{i}_g{j}.wav"))
            else:
                got = chunk(sentence, voice, mood["jitter"], seed + i, f"p{i}")
                if got is None:
                    return None
                pieces.append(got)

            if i < len(sentences) - 1:
                gap = mood["gap"] * rng.uniform(0.75, 1.35)
                pieces.append(silence(round(gap, 3), tmpdir / f"p{i}_gap.wav"))

        # Lossless concat: every piece is 24 kHz mono s16 WAV.
        concat_list = tmpdir / "concat.txt"
        concat_list.write_text(
            "\n".join(f"file '{p.as_posix()}'" for p in pieces), encoding="utf-8"
        )
        joined = tmpdir / "joined.wav"
        res = ffmpeg("-f", "concat", "-safe", "0", "-i", str(concat_list),
                     "-c", "copy", str(joined))
        if res.returncode != 0:
            raise RuntimeError(f"concat failed: {res.stderr.strip()}")

        chain = build_chain(mode, pers, depth)
        if ambience:
            # Very low noise bed, generated as a source inside the graph and
            # truncated to the voice length by amix duration=first.
            filt = (f"[0:a]{chain}[v];"
                    f"{ambience_chain(mode, seed)}[n];"
                    f"[v][n]amix=inputs=2:duration=first:dropout_transition=0:"
                    f"normalize=0,alimiter=limit=0.95[a]")
            res = ffmpeg("-i", str(joined),
                         "-filter_complex", filt, "-map", "[a]",
                         "-ar", str(SR), "-ac", "1",
                         "-c:a", "libmp3lame", "-b:a", "96k", str(out))
        else:
            res = ffmpeg("-i", str(joined), "-af", chain,
                         "-ar", str(SR), "-ac", "1",
                         "-c:a", "libmp3lame", "-b:a", "96k", str(out))
        if res.returncode != 0:
            raise RuntimeError(f"post-processing failed: {res.stderr.strip()}")

    log(f"wrote {out}")
    return out


def play(path: Path) -> None:
    ffplay = shutil.which("ffplay")
    if not ffplay:
        log("ffplay not found - open the file manually.")
        return
    subprocess.run([ffplay, "-nodisp", "-autoexit", "-loglevel", "error",
                    str(path)])


def doctor() -> int:
    """Report what works right now, what each optional key unlocks, and prove
    audio actually renders by making a real test file."""
    import os

    print("\nLya setup check")
    print("=" * 66)

    hard_fail = 0

    def row(label: str, value: str, ok: bool | None = None) -> None:
        nonlocal hard_fail
        mark = "" if ok is None else ("PASS" if ok else "FAIL")
        if ok is False:
            hard_fail += 1
        print(f"{mark:5s} {label:38s} {value}")

    row("Python", sys.version.split()[0], True)
    ff = shutil.which("ffmpeg")
    row("ffmpeg (required)", ff or "NOT FOUND - install ffmpeg", bool(ff))
    row("ffplay (playback)", shutil.which("ffplay") or "not found (optional)",
        None)
    try:
        import edge_tts
        row("edge-tts (free voice engine)", f"installed (v{getattr(edge_tts, '__version__', '?')})", True)
    except ImportError:
        row("edge-tts (free voice engine)", "pip install edge-tts", False)

    if KEYS_LOADED:
        row("keys.env", f"loaded {len(KEYS_LOADED)} key(s): {', '.join(KEYS_LOADED)}", None)
    else:
        row("keys.env", "not used (fine - the free engine needs no key)", None)

    row("SARVAM_API_KEY", "set -> Bulbul voice + Tamil speech-to-text ON"
        if sarvam_key() else "not set (optional; unlocks Bulbul + STT)", None)

    base = os.environ.get("LYA_BRAIN_BASE_URL", "").strip()
    bkey = os.environ.get("LYA_BRAIN_API_KEY", "").strip()
    model = os.environ.get("LYA_BRAIN_MODEL", "not set")
    if base and bkey:
        row("LLM brain", f"{model} @ {base}", None)
    else:
        row("LLM brain", "not set (lya_chat.py uses the offline echo brain)", None)

    print("-" * 66)
    if hard_fail:
        print(f"{hard_fail} required item(s) missing - fix those first.")
        return 1

    print("Everything required is present. Now making a real test file...")
    line = "வணக்கம்! நான் லியா. இந்த voice work ஆகுதா? Test number one."
    out = OUT_DIR / "doctor_test.mp3"
    path = render(line, mood_name="warm", fillers=True, seed=7, out=out)
    if path and path.exists() and path.stat().st_size > 2000:
        size_kb = path.stat().st_size // 1024
        print(f"\nPASS  audio rendered: {path}  ({size_kb} KB)")
        print("\nLISTEN TO IT NOW (this is the whole test):")
        print(f'  ffplay -nodisp -autoexit "{path}"')
        print("\nIf you hear a young Tamil woman speaking Tamil + English, Lya works.")
        print("Then run:  python lya_voice.py --preview      (10 moods)")
        print("           python lya_tune.py --play         (pick her by ear)")
        return 0
    print("\nFAIL  the test render did not produce audio.")
    return 1


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

PREVIEW_LINE = ("வணக்கம்! நான் லியா. உங்களுக்கு எப்படி உதவலாம்? "
                "Call pannunga, நான் பார்த்துக்கிறேன்.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Lya expressive Tamil/English voice")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--text", "-t", help="text to speak (Tamil, English or mixed)")
    src.add_argument("--file", "-f", help="read text from a UTF-8 file")
    p.add_argument("--mood", "-m", default="warm", choices=sorted(MOODS),
                   help="emotional read (default: warm)")
    p.add_argument("--voice", default=TAMIL_FEMALE,
                   help=f"primary voice (default: {TAMIL_FEMALE})")
    p.add_argument("--personality", default="lya", choices=sorted(PERSONALITIES),
                   help="same girl, different seat (default: lya)")
    p.add_argument("--engine", default=DEFAULT_ENGINE, choices=sorted(ENGINES),
                   help="edge = free, no key (default); sarvam = needs SARVAM_API_KEY")
    p.add_argument("--sarvam-speaker", default=SARVAM_SPEAKER,
                   help=f"Bulbul speaker (default: {SARVAM_SPEAKER}); "
                        "try priya, ritu, roopa, simran")
    p.add_argument("--sarvam-model", default=SARVAM_MODEL,
                   help=f"Bulbul model (default: {SARVAM_MODEL}; bulbul:v2 adds "
                        "pitch/loudness but is older)")
    p.add_argument("--dry-run", action="store_true",
                   help="print the exact paid-engine request and write nothing")
    p.add_argument("--raw", action="store_true",
                   help="no phone/studio processing at all (for analysis)")
    p.add_argument("--doctor", action="store_true",
                   help="check every part of the chain and run a live test render")
    p.add_argument("--phone", dest="phone", action="store_true",
                   help="telephone-band realism")
    p.add_argument("--studio", dest="phone", action="store_false",
                   help="clean wideband instead of phone band")
    p.set_defaults(phone=True, ambience=True)
    p.add_argument("--split-lang", action="store_true",
                   help="use a separate Indian-English voice for Latin words")
    p.add_argument("--english-voice", default=EN_IN_FEMALE)
    p.add_argument("--fillers", action="store_true", help="insert Tamil filler words")
    p.add_argument("--no-ambience", dest="ambience", action="store_false",
                   help="disable the low room/line noise bed")
    p.add_argument("--seed", type=int, help="fix randomness for repeatable output")
    p.add_argument("--out", "-o", help="output mp3 path")
    p.add_argument("--play", action="store_true", help="play when finished")
    p.add_argument("--preview", action="store_true",
                   help="render one sample per mood into out/preview/")
    p.add_argument("--list-moods", action="store_true")
    p.add_argument("--list-voices", action="store_true",
                   help="list Tamil/English female voices")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.doctor:
        return doctor()

    if args.list_moods:
        for name, cfg in sorted(MOODS.items()):
            print(f"{name:9s} rate={cfg['rate']:>5s} pitch={cfg['pitch']:>6s} "
                  f"volume={cfg['volume']:>5s} gap={cfg['gap']:.2f}s "
                  f"jitter=+-{cfg['jitter']:.3f}")
        print("\npersonalities:")
        for name, cfg in sorted(PERSONALITIES.items()):
            print(f"  {name:7s} shift={cfg['shift']:.3f} tilt={cfg['tilt']} "
                  f"({cfg['note']})")
        return 0

    if args.list_voices:
        print("Edge voices (free, no key):")
        for v in (TAMIL_FEMALE, TAMIL_FEMALE_ALT, TAMIL_FEMALE_MY, EN_IN_FEMALE,
                  EN_US_AVA_MULTI, EN_US_EMMA_MULTI):
            print(f"  {v}")
        print(f"\nSarvam Bulbul speaker (needs {SARVAM_KEY_ENV}):")
        print(f"  {SARVAM_SPEAKER}  (model {SARVAM_MODEL}, {SARVAM_LANGUAGE})")
        print("  alternates to try: priya, ritu, roopa, simran")
        return 0

    if args.preview:
        require_tools()
        target = OUT_DIR / "preview"
        target.mkdir(parents=True, exist_ok=True)
        for name in sorted(MOODS):
            path = render(PREVIEW_LINE, mood_name=name, voice=args.voice,
                          phone=args.phone, personality=args.personality,
                          fillers=True, seed=4242,
                          out=target / f"mood_{name}.mp3",
                          ambience=args.ambience)
            log(f"  {name:9s} -> {path.name}")
        log(f"preview written to {target}")
        return 0

    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    elif args.text:
        text = args.text
    else:
        build_parser().print_help()
        return 2

    out = Path(args.out).resolve() if args.out else None
    path = render(text, mood_name=args.mood, voice=args.voice, phone=args.phone,
                  personality=args.personality, fillers=args.fillers,
                  split_lang=args.split_lang, english_voice=args.english_voice,
                  seed=args.seed, out=out, ambience=args.ambience,
                  engine=args.engine, sarvam_speaker=args.sarvam_speaker,
                  sarvam_model=args.sarvam_model, dry_run=args.dry_run,
                  raw=args.raw)
    if path is None:
        log("dry-run only - nothing was written and nothing was charged.")
        return 0
    if args.play:
        play(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

