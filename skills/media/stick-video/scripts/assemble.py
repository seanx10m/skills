#!/usr/bin/env python3
"""frames/ + vo_full.m4a -> video.mp4. Optional side-by-side against a reference clip.
usage: assemble.py [--intro-sfx pop.wav [--sfx-lead 0.2]] [--genz --broll clip.mp4 [--genz-width 150]] [--ref reference.mp4 [--ref-start S]]
--genz: writes video-genz.mp4 (video.mp4 is left alone). Muted B-roll (REQUIRED: you supply
  your own --broll file, e.g. footage you made or are licensed to use; none is bundled or downloaded) loops in a small rounded, feathered box fixed in the
  bottom-right for the whole video (where viewers expect picture-in-picture). The rendered frame is
  scaled down and shifted left on the white canvas, so the box sits in its own gutter and can never
  cover text or drawings.
B-roll audio is NEVER used: its audio stream is not mapped, only the voiceover plays.
writes video.mp4, and with --ref: sbs.mp4 (left = reference, right = ours, our audio)"""
import argparse, os, subprocess
ap = argparse.ArgumentParser()
ap.add_argument("--genz", action="store_true")
ap.add_argument("--broll", help="path to your own B-roll video (required with --genz)")
ap.add_argument("--genz-width", type=int, default=150)
ap.add_argument("--ref"); ap.add_argument("--ref-start", type=float, default=0.0)
ap.add_argument("--intro-sfx", help="sound effect played at 0s; the voiceover is delayed by --sfx-lead so they don't collide")
ap.add_argument("--sfx-lead", type=float, default=0.2)
a = ap.parse_args()
if a.genz and not (a.broll and os.path.isfile(os.path.expanduser(a.broll))):
    raise SystemExit("--genz needs --broll /path/to/your-own-clip.mp4 (no footage is bundled)")
if a.broll: a.broll = os.path.expanduser(a.broll)
run = lambda c: subprocess.run(c, check=True)
AUDIO = "vo_full.m4a"
if a.intro_sfx:
    # pre-mix once so every cut (normal, genz, sbs) gets the same track
    ms = int(a.sfx_lead * 1000)
    run(["ffmpeg", "-v", "error", "-y", "-i", AUDIO, "-i", os.path.expanduser(a.intro_sfx), "-filter_complex",
         f"[0:a]adelay={ms}:all=1[v];[1:a]aformat=sample_rates=48000:channel_layouts=stereo[s];"
         f"[v]aformat=sample_rates=48000:channel_layouts=stereo[v2];[v2][s]amix=inputs=2:duration=first:normalize=0[a]",
         "-map", "[a]", "-c:a", "aac", "-b:a", "192k", "vo_mix.m4a"])
    AUDIO = "vo_mix.m4a"
FPS, MARGIN, GAP = 24, 16, 14
VW, VH = map(int, subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0",
    "frames/00000.png"], capture_output=True, text=True).stdout.strip().split(",")[:2])
enc = lambda out: ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "aac", "-b:a", "160k", "-shortest", out]

if a.genz and VH > VW:
    # vertical 9:16: TikTok's own UI covers the bottom-right (buttons) and bottom (caption), so a corner box
    # would be hidden. Use the native split-screen instead: scene scaled into the top, B-roll band below.
    sc = 0.78
    sw, sh = round(VW * sc / 2) * 2, round(VH * sc / 2) * 2
    band = VH - sh
    run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", "frames/%05d.png", "-i", AUDIO,
         "-stream_loop", "-1", "-an", "-i", a.broll, "-filter_complex",
         f"[0:v]scale={sw}:{sh}:flags=lanczos,pad={VW}:{VH}:{(VW - sw) // 2}:0:white[s];"
         f"[2:v]fps={FPS},scale={VW}:-2,crop={VW}:{band}:0:ih*0.62,setsar=1[b];"
         f"[s][b]overlay=0:{sh}:shortest=1[v]",
         "-map", "[v]", "-map", "1:a", "-af", "loudnorm=I=-16"] + enc("video-genz.mp4"))
    out = "video-genz.mp4"
elif a.genz:
    from PIL import Image, ImageDraw, ImageFilter
    bw, bh = map(int, subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
        "stream=width,height", "-of", "csv=p=0", a.broll], capture_output=True, text=True).stdout.strip().split(",")[:2])
    W = a.genz_width
    H = round(W * bh / bw / 2) * 2
    # rounded corners + feathered edge, as an alpha mask
    feather, radius = max(4, W // 30), max(12, W // 10)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((feather, feather, W - feather, H - feather), radius, fill=255)
    mask.filter(ImageFilter.GaussianBlur(feather / 2)).save("genz_mask.png")
    # bottom-right box; the scene keeps everything left of it: scale to fit, center vertically on white
    gx = 8
    bx, by = VW - MARGIN - W, VH - MARGIN - H
    sw = (bx - GAP - gx) // 2 * 2
    sh = round(sw * VH / VW / 2) * 2
    sy = (VH - sh) // 2
    run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", "frames/%05d.png", "-i", AUDIO,
         "-stream_loop", "-1", "-an", "-i", a.broll, "-loop", "1", "-i", "genz_mask.png", "-filter_complex",
         f"[0:v]scale={sw}:{sh}:flags=lanczos,pad={VW}:{VH}:{gx}:{sy}:white[s];"
         f"[2:v]fps={FPS},scale={W}:{H},setsar=1,format=rgba[b];[3:v]format=gray[m];[b][m]alphamerge[bm];"
         f"[s][bm]overlay={bx}:{by}:shortest=1[v]",
         "-map", "[v]", "-map", "1:a", "-af", "loudnorm=I=-16"] + enc("video-genz.mp4"))
    out = "video-genz.mp4"
else:
    run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", "frames/%05d.png", "-i", AUDIO,
         "-af", "loudnorm=I=-16"] + enc("video.mp4"))
    out = "video.mp4"
dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out], capture_output=True, text=True).stdout.strip()
print(out, dur, "s")
if a.ref:
    run(["ffmpeg", "-v", "error", "-y", "-ss", str(a.ref_start), "-i", a.ref, "-i", out, "-filter_complex",
         "[0:v]scale=1280:720,setsar=1[l];[1:v]setsar=1[r];[l][r]hstack=inputs=2,drawbox=x=1278:y=0:w=4:h=720:color=black:t=fill[v]",
         "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-t", dur, "sbs.mp4"])
    print("sbs.mp4")
