#!/usr/bin/env python3
"""Verify a loop seam: the encoded jump from the last frame to the first must be
no bigger than an ordinary frame-to-frame step.

Usage: seam-check.py <project-dir>   (reads <dir>/renders/loop.mp4)
Exit 0 = seam passes.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


def frame(mp4, n, out):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(mp4), "-vf", f"select=eq(n\\,{n})",
                    "-vframes", "1", str(out)], check=True)
    return Image.open(out).convert("RGB")


def diff(a, b):
    return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3


def main():
    d = Path(sys.argv[1])
    mp4 = d / "renders" / "loop.mp4"
    n = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                            "stream=nb_read_frames", "-of", "csv=p=0", str(mp4)],
                           capture_output=True, text=True, check=True).stdout.strip())
    with tempfile.TemporaryDirectory() as t:
        f0, f1 = frame(mp4, 0, f"{t}/a.png"), frame(mp4, 1, f"{t}/b.png")
        fl, fl1 = frame(mp4, n - 1, f"{t}/c.png"), frame(mp4, n - 2, f"{t}/d.png")
        wrap, step_a, step_b = diff(fl, f0), diff(f0, f1), diff(fl1, fl)
    ref = max(step_a, step_b, 0.5)
    ok = wrap <= ref * 1.6
    print(f"frames={n} wrap={wrap:.2f} normal-step={step_a:.2f}/{step_b:.2f} -> {'PASS' if ok else 'FAIL: visible pop at the loop point'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
