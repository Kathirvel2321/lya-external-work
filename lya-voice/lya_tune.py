#!/usr/bin/env python3
"""
Lya voice tuning grid
=====================
Renders the SAME line many times with one knob changed each time, so you can
pick her voice by ear instead of describing it in words.

Instead of "make her warmer" -> you listen to out/tune/*.mp3, then say
"use variant 07", or "like 03 but slower".

Run:
  python lya_tune.py                 # quick grid (default, ~10 variants)
  python lya_tune.py --pitch         # only the pitch ladder (younger/older)
  python lya_tune.py --rate          # only the speed ladder
  python lya_tune.py --voice         # compare the 4 Tamil female voices
  python lya_tune.py --text "..."    # tune on your own line
  python lya_tune.py --engine sarvam # once a Sarvam key exists

Everything is written to out/tune/ with an index.md that explains each file.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import lya_voice as lv  # noqa: E402

OUT = ROOT / "out" / "tune"

# One fair comparison line: Tamil + English words, a question and a statement.
DEFAULT_TEXT = ("வணக்கம்! நான் லியா. உங்க business-க்கு ஒரு website வேணுமா? "
                "Call pannunga, நான் பார்த்துக்கிறேன்.")

# ---------------------------------------------------------------------------
# Knob ladders. Each entry: (label, what changed, render kwargs)
# ---------------------------------------------------------------------------

PITCH_LADDER = [
    ("pitch_-25Hz", "older / lower voice", {"mood_name": "_p-25"}),
    ("pitch_0Hz", "neutral pitch", {"mood_name": "_p0"}),
    ("pitch_+25Hz", "younger / brighter (current default)", {"mood_name": "_p+25"}),
    ("pitch_+45Hz", "very young / cartoonish - use to find the ceiling", {"mood_name": "_p+45"}),
]

RATE_LADDER = [
    ("rate_-8pct", "slower, calmer delivery", {"mood_name": "_r-8"}),
    ("rate_0pct", "neutral speed", {"mood_name": "_r0"}),
    ("rate_+8pct", "current default pace", {"mood_name": "_r+8"}),
    ("rate_+18pct", "fast, energetic phone voice", {"mood_name": "_r+18"}),
]

SEAT_LADDER = [
    ("seat_lya", "default seat", {"personality": "lya"}),
    ("seat_soft", "gentler, rounder", {"personality": "soft"}),
    ("seat_bright", "livelier, crisp", {"personality": "bright"}),
    ("seat_deep", "slightly lower, calmer", {"personality": "deep"}),
]

VOICE_LADDER = [
    ("voice_ta-IN-Pallavi", "Tamil (India) female - the current Lya",
     {"voice": lv.TAMIL_FEMALE}),
    ("voice_ta-LK-Saranya", "Tamil (Sri Lanka) female", {"voice": lv.TAMIL_FEMALE_ALT}),
    ("voice_ta-MY-Kani", "Tamil (Malaysia) female", {"voice": lv.TAMIL_FEMALE_MY}),
    ("voice_en-IN-NeerjaExpressive", "Indian-English female (for --split-lang)",
     {"voice": lv.EN_IN_FEMALE}),
]

OUTPUT_LADDER = [
    ("out_phone", "telephone band - call realism (default)", {"phone": True}),
    ("out_studio", "clean wideband - video / voice note", {"phone": False}),
    ("out_phone_dry", "phone band, no noise bed", {"phone": True, "ambience": False}),
]

GROUPS = {
    "pitch": PITCH_LADDER,
    "rate": RATE_LADDER,
    "seat": SEAT_LADDER,
    "voice": VOICE_LADDER,
    "output": OUTPUT_LADDER,
}


def _key(prefix: str, value: int, unit: str) -> str:
    """Mood key for a ladder value; 0 becomes '_p0' / '_r0' (no sign)."""
    return f"_{prefix}0" if value == 0 else f"_{prefix}{value:+d}{unit}"


def register_ladder_moods() -> None:
    """Inject the ladder presets as temporary moods (base rate/pitch neutral)."""
    for hz in (-25, 0, 25, 45):
        lv.MOODS[_key("p", hz, "")] = {
            "rate": "+6%", "pitch": f"{hz:+d}Hz", "volume": "+0%",
            "gap": 0.20, "jitter": 0.010, "fillers": [],
        }
    for pct in (-8, 0, 8, 18):
        lv.MOODS[_key("r", pct, "")] = {
            "rate": f"{pct:+d}%", "pitch": "+15Hz", "volume": "+0%",
            "gap": 0.20, "jitter": 0.010, "fillers": [],
        }



def build_groups(which: list[str]) -> list[tuple[str, str, dict]]:
    """Return the flat list of (label, note, kwargs) variants to render."""
    out: list[tuple[str, str, dict]] = []
    for name in which:
        for label, note, kwargs in GROUPS[name]:
            out.append((label, note, kwargs))
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Lya voice tuning grid")
    p.add_argument("--text", "-t", help="line to compare variants with")
    p.add_argument("--file", "-f", help="read the line from a UTF-8 file")
    p.add_argument("--only", "-o", action="append", choices=sorted(GROUPS),
                   help="render only this group (repeatable). Default: all")
    p.add_argument("--engine", default=lv.DEFAULT_ENGINE, choices=sorted(lv.ENGINES))
    p.add_argument("--fillers", action="store_true",
                   help="add Tamil filler words (recommended for realism)")
    p.add_argument("--seed", type=int, default=4242,
                   help="fixed seed so only the knob you changed differs")
    p.add_argument("--play", action="store_true",
                   help="play each variant as it lands")
    args = p.parse_args(argv)

    lv.require_tools()
    register_ladder_moods()

    text = Path(args.file).read_text(encoding="utf-8") if args.file else (
        args.text or DEFAULT_TEXT)
    groups = args.only or list(GROUPS)
    variants = build_groups(groups)

    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[str] = []
    print(f"\nRendering {len(variants)} variants into {OUT}\n")

    for i, (label, note, kwargs) in enumerate(variants, start=1):
        target = OUT / f"{i:02d}_{label}.mp3"
        lv.render(text, seed=args.seed, fillers=args.fillers, engine=args.engine,
                  out=target, **kwargs)
        rows.append(f"| {i:02d} | `{label}` | {note} | `{target.name}` |")
        print(f"  {i:02d}  {note}")
        if args.play:
            lv.play(target)

    index = OUT / "index.md"
    lines = [
        "# Lya voice tuning grid",
        "",
        "Same line every time; only the listed knob changed. Listen in order and",
        "tell me a number or a combination (e.g. \"03 pace with 05 seat\").",
        "",
        f"Line used: {text.strip()}",
        f"Engine: `{args.engine}`  |  fillers: {args.fillers}  |  seed: {args.seed}",
        "",
        "| # | Variant | What changed | File |",
        "|---|---------|--------------|------|",
        *rows,
        "",
        "Everyday knobs once you pick a base:",
        "",
        "- `--mood` + `--personality` in `lya_voice.py`.",
        "- `--phone` = call realism, `--studio` = video/voice-note clarity.",
        "- `--split-lang` only if you want a separate English voice for Latin words.",
        "",
    ]
    index.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nIndex written: {index}")
    print("Play them in order:\n  Get-ChildItem out\\tune\\*.mp3 | "
          "Sort-Object Name | ForEach-Object { ffplay -nodisp -autoexit "
          "$_.FullName }")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
