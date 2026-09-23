#!/usr/bin/env python3
"""
Smoke test for the Lya voice engine.
Exercises every code path (normal, split-lang, studio, no-ambience, direct API)
and checks the output files are real audio with sane durations.

Run:  python tests/smoke_test.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lya_voice  # noqa: E402

OUT = ROOT / "out" / "smoke"
OUT.mkdir(parents=True, exist_ok=True)

TANGLISH = ("வணக்கம்! நான் லியா. உங்களுக்கு ஒரு website வேணுமா? "
            "Call pannunga, price five thousand only.")

results: list[tuple[str, bool, str]] = []


def check(name: str, path: Path, min_seconds: float = 1.0) -> None:
    ok = path.exists() and path.stat().st_size > 2000
    detail = ""
    if ok:
        dur = float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, check=True).stdout.strip())
        ok = dur >= min_seconds
        detail = f"{dur:.2f}s, {path.stat().st_size // 1024} KB"
    results.append((name, ok, detail or "missing/too small"))


# 1. Normal path: one voice, Tanglish, phone band, fillers.
check("normal (phone + fillers)", lya_voice.render(
    TANGLISH, mood_name="warm", fillers=True, seed=11,
    out=OUT / "t1_normal.mp3"))

# 2. Split-language path: Tamil voice + Indian-English voice.
check("split-lang", lya_voice.render(
    TANGLISH, mood_name="teasing", split_lang=True, seed=12,
    out=OUT / "t2_splitlang.mp3"))

# 3. Studio path, no noise bed.
check("studio + no ambience", lya_voice.render(
    TANGLISH, mood_name="serious", phone=False, ambience=False, seed=13,
    out=OUT / "t3_studio.mp3"))

# 4. Same girl, different seat + alternative Tamil voice.
check("personality=soft + ta-LK voice", lya_voice.render(
    TANGLISH, mood_name="caring", personality="soft",
    voice=lya_voice.TAMIL_FEMALE_ALT, seed=14,
    out=OUT / "t4_altvoice.mp3"))

# 5. Deterministic repeats: same seed -> identical bytes (cache proof).
a = lya_voice.render(TANGLISH, mood_name="happy", seed=99,
                     out=OUT / "t5_seed_a.mp3")
b = lya_voice.render(TANGLISH, mood_name="happy", seed=99,
                     out=OUT / "t5_seed_b.mp3")
same = a.read_bytes() == b.read_bytes()
results.append(("same seed -> same audio", same,
                "identical" if same else "differs"))

# 7. Pure English and pure Tamil still work through one voice.
check("pure English", lya_voice.render(
    "Hello, this is Lya calling. Is this a good time to talk?", seed=15,
    out=OUT / "t6_english.mp3"))
check("pure Tamil", lya_voice.render(
    "நாளைக்கு காலையில call பண்ணுங்க, நான் ready ஆ இருக்கேன்.", mood_name="happy",
    seed=16, out=OUT / "t7_tamil.mp3"))

# 8. Paid engine (Sarvam) without a key must fail clearly, not crash mysteriously.
no_key_exit = False
if not lya_voice.sarvam_key():
    try:
        lya_voice.require_tools("sarvam")
    except SystemExit as exc:
        no_key_exit = "API key" in str(exc)
results.append(("sarvam needs a key (clear error)", no_key_exit,
                "SystemExit with guidance" if no_key_exit
                else "unexpected behaviour"))

# 9. Sarvam dry-run must be provable without a key and write nothing.
dry_target = OUT / "t9_dryrun.mp3"
if dry_target.exists():
    dry_target.unlink()
dry_result = lya_voice.render(TANGLISH, mood_name="warm", engine="sarvam",
                              dry_run=True, seed=17, out=dry_target)
results.append(("sarvam dry-run writes nothing",
                dry_result is None and not dry_target.exists(),
                "printed request, no file"))

# 10. Mood rate -> Bulbul pace mapping, including the API clamp.
pace_ok = (abs(lya_voice.mood_pace({"rate": "+8%"}) - 1.08) < 1e-9
           and lya_voice.mood_pace({"rate": "+150%"}) == 2.0
           and lya_voice.mood_pace({"rate": "-60%"}) == 0.5)
results.append(("pace mapping + clamp 0.5-2.0", pace_ok,
                "1.08 / 2.0 (from +150%) / 0.5"))

# 11. Engine guard rejects a bogus engine name.
bad_engine_ok = False
try:
    lya_voice.require_tools("nope")
except SystemExit:
    bad_engine_ok = True
results.append(("unknown engine rejected", bad_engine_ok, "SystemExit"))

# 12. keys.env loader: parses KEY=VALUE, skips comments/empties, env wins.
import os  # noqa: E402
import tempfile  # noqa: E402
with tempfile.TemporaryDirectory() as tmp:
    probe = Path(tmp) / "keys.env"
    probe.write_text("# comment\nLYA_TEST_KEY=abc123\n\nBROKEN LINE\n"
                     "QUOTED=\"xyz\"\n", encoding="utf-8")
    os.environ.pop("LYA_TEST_KEY", None)
    os.environ.pop("QUOTED", None)
    loaded = lya_voice.load_keys_env(probe)
    ok = (loaded == ["LYA_TEST_KEY", "QUOTED"]
          and os.environ.get("LYA_TEST_KEY") == "abc123"
          and os.environ.get("QUOTED") == "xyz")
    os.environ["LYA_TEST_KEY"] = "override"
    lya_voice.load_keys_env(probe)  # must NOT clobber a real env var
    ok = ok and os.environ["LYA_TEST_KEY"] == "override"
results.append(("keys.env loader + env precedence", ok,
                "2 keys parsed, env wins"))
for k in ("LYA_TEST_KEY", "QUOTED"):
    os.environ.pop(k, None)

# 13. Full doctor: checks every link and proves audio renders for real.
doctor_rc = lya_voice.doctor()
doctor_file = lya_voice.OUT_DIR / "doctor_test.mp3"
results.append(("doctor() end-to-end + test render",
                doctor_rc == 0 and doctor_file.exists()
                and doctor_file.stat().st_size > 2000,
                f"exit {doctor_rc}, {doctor_file.stat().st_size // 1024 if doctor_file.exists() else 0} KB"))

print("\nLya voice smoke test")
print("-" * 62)
failed = 0
for name, ok, detail in results:
    print(f"{'PASS' if ok else 'FAIL'}  {name:32s} {detail}")
    failed += 0 if ok else 1
print("-" * 62)
print(f"{len(results) - failed}/{len(results)} passed -> {OUT}")
raise SystemExit(1 if failed else 0)
