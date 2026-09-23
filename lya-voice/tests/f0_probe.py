#!/usr/bin/env python3
"""
Voice age probe
===============
Estimates the fundamental frequency (F0, "pitch") of a voice recording, which is
the main measurable cue for perceived age and gender of a voice.

Method: decode to 16 kHz mono PCM with ffmpeg, then autocorrelation over voiced
40 ms frames. Pure Python (no numpy). This is a measurement, not a claim of
perceptual age - formants (vocal-tract size) also matter, and this tool does not
measure them.

Typical adult female F0 is about 165-255 Hz. Adult male 85-155 Hz. A young
child is 250-400 Hz. So where a voice lands here is real evidence, not a guess.

Usage:  python tests/f0_probe.py out/raw/*.mp3
"""

from __future__ import annotations

import shutil
import statistics
import subprocess
import sys
from pathlib import Path

SR = 16000
FRAME = int(SR * 0.04)      # 40 ms analysis frame
HOP = int(SR * 0.02)        # 20 ms hop
EVERY = 3                   # analyse every 3rd frame (speed)
F0_MIN, F0_MAX = 90, 400    # plausible range for this probe
MIN_CORR = 0.30             # voicing threshold
MAX_SECONDS = 14


def decode(path: Path) -> list[float]:
    ff = shutil.which("ffmpeg")
    if not ff:
        sys.exit("ffmpeg not found")
    raw = subprocess.run(
        [ff, "-hide_banner", "-loglevel", "error", "-i", str(path),
         "-t", str(MAX_SECONDS), "-ac", "1", "-ar", str(SR),
         "-f", "s16le", "-"],
        capture_output=True).stdout
    import struct
    count = len(raw) // 2
    ints = struct.unpack(f"<{count}h", raw[:count * 2])
    return [v / 32768.0 for v in ints]


def frame_f0(frame: list[float]) -> float | None:
    n = len(frame)
    mean = sum(frame) / n
    x = [v - mean for v in frame]
    energy = sum(v * v for v in x)
    if energy <= 1e-5:
        return None
    min_lag = SR // F0_MAX
    max_lag = SR // F0_MIN
    best_lag, best = 0, 0.0
    for lag in range(min_lag, max_lag):
        corr = 0.0
        for i in range(0, n - lag, 2):     # step 2: half the work, same accuracy
            corr += x[i] * x[i + lag]
        if corr > best:
            best, best_lag = corr, lag
    if not best_lag:
        return None
    # normalise against zero-lag energy (approximate, step-2 consistent)
    norm = best / (energy / 2)
    if norm < MIN_CORR:
        return None
    return SR / best_lag


def probe(path: Path) -> None:
    samples = decode(path)
    if len(samples) < FRAME * 2:
        print(f"{path.name:28s} too short / silent")
        return
    f0s: list[float] = []
    for start in range(0, len(samples) - FRAME, HOP * EVERY):
        value = frame_f0(samples[start:start + FRAME])
        if value:
            f0s.append(value)
    if not f0s:
        print(f"{path.name:28s} no voiced frames detected")
        return
    f0s.sort()
    median = statistics.median(f0s)
    p10 = f0s[int(len(f0s) * 0.10)]
    p90 = f0s[min(len(f0s) - 1, int(len(f0s) * 0.90))]
    voiced_pct = 100.0 * len(f0s) / max(1, (len(samples) // (HOP * EVERY)))
    print(f"{path.name:28s} median {median:6.1f} Hz   p10-p90 {p10:6.1f}-{p90:6.1f} Hz"
          f"   voiced {voiced_pct:4.1f}%")


def main() -> int:
    files = [Path(a) for a in sys.argv[1:]]
    if not files:
        print(__doc__)
        return 2
    print("\nF0 (pitch) estimate - higher = brighter / younger-sounding")
    print("-" * 78)
    for f in files:
        if f.exists():
            probe(f)
        else:
            print(f"{f.name:28s} missing")
    print("-" * 78)
    print("Adult female reference: 165-255 Hz | adult male: 85-155 Hz | child: 250-400 Hz")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
