#!/usr/bin/env python3
"""
Age probe
=========
Renders the SAME line unfiltered (raw, no phone band, so nothing masks the
voice) at every pitch setting, then measures the fundamental frequency of each
file. This answers "what age is the voice agent?" with numbers instead of a
guess, and shows exactly how much the --pitch knob moves her.

Run:  python tests/age_probe.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import lya_voice as lv          # noqa: E402
import f0_probe                 # noqa: E402

OUT = ROOT / "out" / "raw"
LINE = ("வணக்கம்! நான் லியா. உங்க business-க்கு ஒரு website பண்ணி தர்றேன். "
        "Call pannunga.")

# (label, mood key to register, pitch in Hz, voice)
VARIANTS = [
    ("pitch_-25Hz", -25, lv.TAMIL_FEMALE),
    ("pitch_-10Hz", -10, lv.TAMIL_FEMALE),
    ("pitch_+0Hz", 0, lv.TAMIL_FEMALE),
    ("pitch_+15Hz_default", 15, lv.TAMIL_FEMALE),
    ("pitch_+25Hz", 25, lv.TAMIL_FEMALE),
    ("pitch_+45Hz", 45, lv.TAMIL_FEMALE),
    ("voice_ta-LK-Saranya_+15", 15, lv.TAMIL_FEMALE_ALT),
    ("voice_ta-MY-Kani_+15", 15, lv.TAMIL_FEMALE_MY),
]


def main() -> int:
    lv.require_tools()
    OUT.mkdir(parents=True, exist_ok=True)

    targets: list[Path] = []
    for i, (label, hz, voice) in enumerate(VARIANTS, start=1):
        mood_key = f"_age{abs(hz)}{'p' if hz >= 0 else 'm'}_{i}"
        lv.MOODS[mood_key] = {
            "rate": "+0%", "pitch": f"{hz:+d}Hz", "volume": "+0%",
            "gap": 0.20, "jitter": 0.0, "fillers": [],
        }
        target = OUT / f"{i:02d}_{label}.mp3"
        path = lv.render(LINE, mood_name=mood_key, voice=voice, raw=True,
                         ambience=False, seed=555, out=target)
        if path:
            targets.append(path)

    print("\nMeasured pitch of each variant (raw = nothing masking the voice)")
    print("=" * 78)
    for path in targets:
        f0_probe.probe(path)
    print("=" * 78)
    print("Reference: adult female 165-255 Hz | adult male 85-155 Hz | "
          "young child 250-400 Hz")
    print(f"\nFiles: {OUT}")
    print("Listen to them in order to hear the age/gender read yourself.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
