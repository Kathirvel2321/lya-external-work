#!/usr/bin/env python3
"""
Lya talk loop (Phase 3)
=======================
Makes Lya listen and answer: your voice (or typing) in, her voice out.

  you speak  ->  ffmpeg records the mic (no extra install)
             ->  speech-to-text: Sarvam Saaras (needs SARVAM_API_KEY)
                                 or local faster-whisper if installed
                                 or you just type
             ->  brain: any OpenAI-compatible endpoint (free NVIDIA NIM,
                        Groq, local Ollama...) or an offline echo brain
             ->  her reply read in Lya's voice by lya_voice.py

Run:
  python lya_chat.py                        # typed chat, echo brain, voice replies
  python lya_chat.py --text "சொல்லுங்க"      # one turn, then exit
  python lya_chat.py --mic --seconds 6      # talk to her, one turn
  python lya_chat.py --mic --loop           # keep talking until you quit
  python lya_chat.py --no-audio             # text only (fast testing)

Environment (all optional):
  SARVAM_API_KEY       enables Sarvam speech-to-text (and --engine sarvam voice)
  LYA_BRAIN_BASE_URL   OpenAI-compatible base, e.g. https://integrate.api.nvidia.com/v1
  LYA_BRAIN_API_KEY    key for that endpoint
  LYA_BRAIN_MODEL      model name, e.g. meta/llama-3.1-8b-instruct
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import lya_voice as lv  # noqa: E402

# Tamil/Unicode output on a Windows console: prefer UTF-8, never crash.
if sys.platform == "win32":
    for stream in (sys.stdout, sys.stdin):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # redirected stream, older Python, etc.
            pass

CHAT_DIR = ROOT / "out" / "chat"
MIC_DIR = ROOT / "out" / "mic"

SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"
SARVAM_STT_MODEL = "saaras:v3"     # recommended; 30 second limit per request
SARVAM_STT_MAX_SECONDS = 30

# Lya's character. Kept honest on purpose: she never claims to be a human.
PERSONA = (
    "You are Lya, a cheerful young Tamil-speaking assistant from Tamil Nadu. "
    "You talk like a real girl on a phone call: short sentences, warm, a little "
    "playful, never formal or robotic. "
    "Write Tamil words in Tamil script and English words in English script, mixed "
    "naturally the way Tamil speakers really talk (example: 'சரி, நான் அந்த "
    "website-ஐ பார்த்தேன். Looks good!' ). "
    "Use an occasional natural filler like 'ம்ம்' or 'ஆமா', but not in every line. "
    "Never use emoji, markdown, bullet points or headings - your words are spoken "
    "aloud, so write only what a voice can say. Keep replies under 3 sentences "
    "unless asked to explain. "
    "If anyone asks whether you are a human or an AI, say plainly that you are "
    "Lya, an AI assistant. Never pretend to be a real person."
)


def log(msg: str) -> None:
    lv.log(msg)


def say(msg: str = "") -> None:
    """print() that never crashes on a console that cannot encode Tamil."""
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"), flush=True)



# ----------------------------------------------------------------------------
# Listening: microphone -> text
# ----------------------------------------------------------------------------

def mic_device() -> str | None:
    """Find the default DirectShow audio input name via ffmpeg."""
    result = subprocess.run(
        [lv.FFMPEG, "-hide_banner", "-list_devices", "true",
         "-f", "dshow", "-i", "dummy"],
        capture_output=True, text=True, errors="replace")
    names = re.findall(r'"([^"]+)"\s*\(audio\)', result.stderr or "")
    return names[0] if names else None

def record(seconds: int, dest: Path) -> Path:
    """Record from the mic with ffmpeg. No Python audio library needed."""
    device = mic_device()
    if not device:
        sys.exit("[lya] No microphone visible to ffmpeg. Check Windows mic "
                 "permissions (Settings > Privacy > Microphone).")
    if seconds > SARVAM_STT_MAX_SECONDS:
        log(f"note: Sarvam STT only takes {SARVAM_STT_MAX_SECONDS}s per request; "
            f"recording {seconds}s will need a local whisper model")
    dest.parent.mkdir(parents=True, exist_ok=True)
    log(f"recording {seconds}s from: {device}")
    subprocess.run(
        [lv.FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
         "-f", "dshow", "-i", f"audio={device}",
         "-t", str(seconds), "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", str(dest)],
        capture_output=True, text=True)
    if not dest.exists() or dest.stat().st_size < 1000:
        sys.exit("[lya] Recording failed or produced silence.")
    return dest


def sarvam_stt(audio: Path, mode: str = "transcribe",
               model: str = SARVAM_STT_MODEL) -> str:
    """Sarvam Saaras speech-to-text: multipart POST, returns the transcript."""
    key = lv.sarvam_key()
    if not key:
        raise RuntimeError("SARVAM_API_KEY is not set")
    boundary = "----lya" + uuid.uuid4().hex
    parts: list[bytes] = []
    for name, value in (("model", model), ("mode", mode)):
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"'
            f"\r\n\r\n{value}\r\n".encode("utf-8"))
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{audio.name}"\r\nContent-Type: audio/wav\r\n\r\n'.encode())
    parts.append(audio.read_bytes())
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    body = b"".join(parts)

    request = urllib.request.Request(
        SARVAM_STT_URL, data=body, method="POST",
        headers={"api-subscription-key": key,
                 "Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"Sarvam STT HTTP {exc.code}: {detail}") from exc
    except Exception as exc:
        raise RuntimeError(f"Sarvam STT failed: {exc}") from exc

    log(f"STT request_id={payload.get('request_id', 'unknown')} "
        f"lang={payload.get('language_code')}")
    return (payload.get("transcript") or "").strip()


def local_stt(audio: Path, model: str) -> str | None:
    """Optional local fallback if faster-whisper happens to be installed."""
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError:
        return None
    log(f"local whisper model={model} (CPU, may be slow)")
    engine = WhisperModel(model, device="cpu", compute_type="int8")
    segments, info = engine.transcribe(str(audio), language="ta", beam_size=1)
    text = " ".join(seg.text.strip() for seg in segments).strip()
    log(f"local STT language={info.language} p={info.language_probability:.2f}")
    return text


def transcribe(audio: Path, whisper_model: str = "base") -> str:
    """Sarvam first (best for Tamil), then local whisper, else ask the user."""
    if lv.sarvam_key():
        return sarvam_stt(audio)
    text = local_stt(audio, whisper_model)
    if text is not None:
        return text
    sys.exit(
        "[lya] I recorded your voice but have no way to transcribe it yet.\n"
        "      Pick one:\n"
        "      1) Set SARVAM_API_KEY (best Tamil accuracy, free credits on "
        "signup):\n"
        f"           $env:{lv.SARVAM_KEY_ENV} = \"your-key\"\n"
        "      2) Install a small local model (no key, slower):\n"
        "           pip install faster-whisper\n"
        "      3) Skip voice input:  python lya_chat.py --text \"...\""
    )


# ----------------------------------------------------------------------------
# Thinking: any OpenAI-compatible endpoint, or an offline brain for testing
# ----------------------------------------------------------------------------

ECHO_REPLIES = [
    "ம்ம், கேட்டேன். இன்னும் கொஞ்சம் விவரமா சொல்லுங்க?",
    "சரி! அதை நான் பார்த்துக்கிறேன், நீங்க கவலைப்படாதீங்க.",
    "ஆமா, அது நல்ல idea. அதை எப்படி start பண்ணலாம்னு யோசிக்கிறேன்.",
]


def brain_mode() -> tuple[str, str, str]:
    """Return (mode, base_url, api_key) based on the environment."""
    base = os.environ.get("LYA_BRAIN_BASE_URL", "").strip().rstrip("/")
    key = os.environ.get("LYA_BRAIN_API_KEY", "").strip()
    if base and key:
        return "openai", base, key
    return "echo", "", ""


def brain_echo(text: str, history: list[dict], turn: int) -> str:
    if "?" in text:
        return ECHO_REPLIES[0]
    return ECHO_REPLIES[turn % len(ECHO_REPLIES)]


def brain_openai(text: str, history: list[dict], base: str, key: str,
                 model: str) -> str:
    """POST /chat/completions - works with NIM, Groq, OpenAI, Ollama, Sarvam."""
    messages = [{"role": "system", "content": PERSONA}]
    messages += history[-8:]
    messages.append({"role": "user", "content": text})
    payload = {"model": model, "messages": messages, "temperature": 0.7,
               "max_tokens": 300}
    request = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"brain HTTP {exc.code}: {detail}") from exc
    except Exception as exc:
        raise RuntimeError(f"brain request failed: {exc}") from exc
    choices = body.get("choices") or []
    if not choices:
        raise RuntimeError(f"brain returned no reply: {str(body)[:200]}")
    return (choices[0]["message"]["content"] or "").strip()


def strip_for_speech(text: str) -> str:
    """Remove anything a voice should not read out loud."""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"[*_#`>]+", "", text)
    text = re.sub(r"^\s*[-•]\s*", "", text, flags=re.M)
    text = re.sub(r"\((?:laughs?|smiles?|chuckles?)\)", "", text, flags=re.I)
    return " ".join(text.split()).strip()


SAD_WORDS = ("கஷ்டம்", "வருத்தம்", "sorry", "problem", "பிரச்சனை", "கவலை")
TEASE_WORDS = ("கிண்டல்", "hehe", "haha", "ஜோக்", "joke", "comedy")


def pick_mood(text: str) -> str:
    """A deterministic, documented heuristic - not a claim of emotion AI."""
    low = text.lower()
    if any(w in text or w in low for w in TEASE_WORDS):
        return "teasing"
    if any(w in text or w in low for w in SAD_WORDS):
        return "caring"
    if "!" in text:
        return "happy"
    if "?" in text:
        return "warm"
    if len(text) < 25:
        return "shy"
    return "warm"



# ----------------------------------------------------------------------------
# One turn: input -> brain -> voice
# ----------------------------------------------------------------------------

def reply_audio(text: str, turn: int, *, engine: str, mood: str | None,
                personality: str, phone: bool, fillers: bool) -> Path | None:
    CHAT_DIR.mkdir(parents=True, exist_ok=True)
    chosen = mood or pick_mood(text)
    target = CHAT_DIR / f"turn_{turn:02d}_{chosen}.mp3"
    return lv.render(text, mood_name=chosen, personality=personality,
                     phone=phone, fillers=fillers, seed=1000 + turn,
                     out=target, engine=engine)


def run_turn(user_text: str, history: list[dict], turn: int, args) -> None:
    mode, base, key = brain_mode()
    if mode == "openai":
        reply = brain_openai(user_text, history, base, key, args.model)
    else:
        reply = brain_echo(user_text, history, turn)
    reply = strip_for_speech(reply)
    if not reply:
        reply = "ம்ம், சொல்லுங்க."

    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": reply})

    say(f"\nYOU  : {user_text}")
    say(f"LYA  : {reply}\n")
    if args.no_audio:
        return
    path = reply_audio(reply, turn, engine=args.engine, mood=args.mood,
                       personality=args.personality, phone=args.phone,
                       fillers=args.fillers)
    if path and args.play:
        lv.play(path)



def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Talk with Lya (voice in, voice out)")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--text", "-t", help="one typed message, then exit")
    src.add_argument("--mic", action="store_true", help="speak instead of typing")
    p.add_argument("--seconds", type=int, default=6,
                   help="mic recording length per turn (default 6)")
    p.add_argument("--loop", action="store_true",
                   help="keep the conversation going")
    p.add_argument("--model", default=os.environ.get(
        "LYA_BRAIN_MODEL", "meta/llama-3.1-8b-instruct"),
        help="brain model name (env LYA_BRAIN_MODEL)")
    p.add_argument("--mood", default=None, choices=sorted(lv.MOODS),
                   help="force a mood; default is auto-picked from her reply")
    p.add_argument("--personality", default="lya",
                   choices=sorted(lv.PERSONALITIES))
    p.add_argument("--engine", default=lv.DEFAULT_ENGINE,
                   choices=sorted(lv.ENGINES))
    p.add_argument("--studio", dest="phone", action="store_false",
                   help="clean wideband instead of phone band")
    p.add_argument("--fillers", action="store_true", default=True,
                   help="Tamil filler words (default on)")
    p.add_argument("--no-fillers", dest="fillers", action="store_false")
    p.add_argument("--no-audio", action="store_true", help="text only")
    p.add_argument("--quiet", dest="play", action="store_false",
                   help="write audio but do not play it")
    p.add_argument("--list-mic", action="store_true", help="show mic devices")
    p.set_defaults(phone=True, play=True)
    args = p.parse_args(argv)

    if args.list_mic:
        lv.require_tools()
        print(f"mic: {mic_device() or 'none found'}")
        return 0

    lv.require_tools(args.engine)
    mode, base, _ = brain_mode()
    if mode == "openai":
        log(f"brain={args.model} @ {base}")
    else:
        log("brain=echo (set LYA_BRAIN_BASE_URL + LYA_BRAIN_API_KEY for a real brain)")
    log(f"speech-to-text={'sarvam' if lv.sarvam_key() else 'local/none'}  "
        f"voice engine={args.engine}")

    history: list[dict] = []
    turn = 1

    if args.text:
        run_turn(args.text, history, turn, args)
        return 0

    if args.mic:
        if not args.loop:
            audio = record(args.seconds, MIC_DIR / f"in_{turn:02d}.wav")
            spoken = transcribe(audio)
            if not spoken:
                log("nothing transcribed (silence?)")
                return 1
            run_turn(spoken, history, turn, args)
            return 0
        while True:
            try:
                audio = record(args.seconds, MIC_DIR / f"in_{turn:02d}.wav")
                spoken = transcribe(audio)
                if spoken:
                    run_turn(spoken, history, turn, args)
                    turn += 1
                else:
                    log("heard nothing - still listening")
            except KeyboardInterrupt:
                log("bye!")
                return 0

    print("Type your message. Blank line or 'exit' to stop.\n")
    while True:
        try:
            typed = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not typed or typed.lower() in {"exit", "quit", "bye"}:
            return 0
        run_turn(typed, history, turn, args)
        turn += 1


if __name__ == "__main__":
    raise SystemExit(main())

