"""Trim and level the voice takes and put the chosen ones in the app (ADR 0040).

Usage: python tv/voice/prepare.py <folder with the takes and manifest.json> [line=take ...]
  e.g. python tv/voice/prepare.py C:/tmp/colors-voice-out one_more=2 good_night=3
Every line ships take 1 unless a pick says otherwise. Writes tv/app/src/main/res/raw/voice_<id>.mp3 and
tv/voice/voice.json (what shipped: line, take, words, model, voice).

Same treatment as the kids app's tools/sounds/prepare.mjs for its narrator: silence trimmed at both ends, levelled
to the same loudness (RMS 0.13, peaks under 0.9), mono 44.1 kHz MP3. Needs ffmpeg (FFMPEG_DIR or on the PATH).
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE.parent / "app" / "src" / "main" / "res" / "raw"
TARGET_RMS = 0.13
PEAK_CAP = 0.9
TRIM = ("silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.005,areverse,"
        "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.03,areverse")


def ffmpeg() -> str:
    d = os.environ.get("FFMPEG_DIR")
    return str(Path(d) / "ffmpeg") if d else (shutil.which("ffmpeg") or "ffmpeg")


def levels(src: Path) -> tuple[float, float]:
    """RMS and peak of the trimmed clip, as amplitudes 0..1."""
    out = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(src), "-af", TRIM + ",astats=metadata=0", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    overall = out[out.rfind("Overall"):]
    rms = float(re.search(r"RMS level dB:\s*(-?[\d.]+|-inf)", overall).group(1))
    peak = float(re.search(r"Peak level dB:\s*(-?[\d.]+|-inf)", overall).group(1))
    return 10 ** (rms / 20), 10 ** (peak / 20)


def prepare(src: Path, dst: Path) -> dict:
    rms, peak = levels(src)
    gain = min(TARGET_RMS / rms, PEAK_CAP / peak)
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", str(src), "-af", f"{TRIM},volume={gain:.4f}",
                    "-ac", "1", "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "96k", "-map_metadata", "-1", str(dst)],
                   check=True)
    return {"gain_db": round(20 * math.log10(gain), 1)}


def main() -> None:
    src = Path(sys.argv[1])
    picks = dict(a.split("=") for a in sys.argv[2:])
    manifest = json.loads((src / "manifest.json").read_text(encoding="utf-8"))
    lines = json.loads((HERE / "lines.json").read_text(encoding="utf-8"))["lines"]
    RAW.mkdir(parents=True, exist_ok=True)
    shipped = []
    for line in lines:
        take = int(picks.get(line["id"], 1))
        clip = src / f"{line['id']}-{take}.mp3"
        if not clip.exists():
            print(f"  {line['id']}: no take {take}, skipped")
            continue
        info = prepare(clip, RAW / f"voice_{line['id']}.mp3")
        shipped.append({"id": line["id"], "take": take, "says": line["show"], "model": manifest["model"],
                        "voice": manifest["voice"], **info})
        print(f"  voice_{line['id']}.mp3 from take {take} ({info['gain_db']:+} dB)")
    (HERE / "voice.json").write_text(json.dumps({"lines": shipped}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
