#!/usr/bin/env python3
"""watch.py - turn a video into things an agent can actually read.

Three channels, in ascending order of cost:

  1. TEXT   - the transcript (Whisper) and on-screen text (native macOS OCR).
              Nearly free. Often enough on its own for a slide deck.
  2. NUMBERS- per-frame pixel diffs: how much changed, and where on screen.
              Free, and it decides which frames are worth looking at.
  3. PIXELS - the frames themselves. ~1-1.5k tokens each. Spent last, and only
              where the first two say it matters.

The frame picker is the whole trick. Sampling every N seconds wastes reads on
static stretches and misses fast cuts. Instead every frame is scored against the
previous one, the outliers are kept, and then a real pixel diff throws out the
ones that only changed trivially - a cursor drifting across a screen recording
moves ~0.1% of pixels, a route change moves 40%. That single rule handles a
slide deck and a UI recording without being told which one it got.

Hard deps: ffmpeg/ffprobe, python3+numpy (both already required by Whisper).
Soft deps: whisper.cpp or openai-whisper (skip with --no-audio), swiftc for OCR,
Pillow for labelled contact sheets, yt-dlp for URLs. Each degrades gracefully.
"""
import argparse, glob, json, os, re, shutil, subprocess, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
FFPROBE = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"

# How closely to look, on Claude's own effort scale so it reads the same as the
# rest of the tooling. One dial the user can say out loud ("watch it closely")
# instead of hand-tuning three numbers: frame budget, spacing, sensitivity.
EFFORT = {
    "low":    (8,   2.5, 2.0),
    "medium": (24,  1.0, 1.0),
    "high":   (60,  0.4, 0.5),
    "xhigh":  (150, 0.15, 0.2),
}
# Typed as bare words, in any order, because nobody wants to remember a flag:
#   watch.py <link> xh          watch.py high /clip.mov          watch.py ui h <link>
EFFORT_ALIAS = {
    "l": "low", "m": "medium", "h": "high", "xh": "xhigh", "x": "xhigh",
    "skim": "low", "quick": "low", "fast": "low", "rough": "low",
    "normal": "medium", "default": "medium",
    "close": "high", "closely": "high", "careful": "high", "carefully": "high",
    "forensic": "xhigh", "max": "xhigh", "everything": "xhigh",
}
MODE_ALIAS = {
    "slides": "slides", "deck": "slides", "presentation": "slides",
    "ui": "ui", "screen": "ui", "recording": "ui", "screenshare": "ui",
    "demo": "ui", "app": "ui",
    "footage": "footage", "camera": "footage", "film": "footage", "real": "footage",
    "auto": "auto",
}


def classify(words):
    """Sort bare words into (source, effort, mode). A real path or URL always wins
    over a keyword match, so a file named 'high.mp4' still works."""
    src, eff, mode = None, None, None
    for w in words:
        k = w.lower().strip(",")
        if src is None and (re.match(r"https?://", w) or os.path.exists(os.path.expanduser(w))):
            src = os.path.expanduser(w)
        elif eff is None and k in EFFORT_ALIAS:
            eff = EFFORT_ALIAS[k]
        elif eff is None and k in EFFORT:
            eff = k
        elif mode is None and k in MODE_ALIAS:
            mode = MODE_ALIAS[k]
        elif src is None:
            src = os.path.expanduser(w)      # unresolvable path - let ffprobe complain
    return src, eff, mode

# mode -> (scene-score floor, min seconds between keyframes, min changed area)
# A slide deck and a screen recording genuinely cannot share a threshold: the
# deck's cuts are total, the recording's real transitions are small but local.
MODES = {
    "slides":  (0.05,  4.0, 0.010),
    "ui":      (0.012, 1.5, 0.002),
    "footage": (0.15,  2.5, 0.000),
    "auto":    (0.020, 2.0, 0.004),
}

DIFF_W, DIFF_H = 480, 270          # resolution the pixel diffs run at
PIXEL_DELTA = 16                   # per-pixel 0-255 change that counts as changed
CAPTION_BAND = 0.78                # rows below this are the subtitle/ticker zone
HASH_GRID = 16                     # dhash resolution; coarse grids blur text away
HASH_NEAR = 28                     # hamming distance that makes two frames worth diffing


# ---------------------------------------------------------------- primitives

def probe(path, key):
    return subprocess.run([FFPROBE, "-v", "error", "-show_entries", key,
                           "-of", "default=nw=1:nk=1", path],
                          capture_output=True, text=True).stdout.strip()


def gray_frame(src, t):
    """One frame as a grayscale numpy array, decoded straight to raw bytes.
    Avoids an image library entirely - numpy ships with Whisper, Pillow may not."""
    r = subprocess.run([FFMPEG, "-v", "error", "-nostdin", "-ss", f"{t:.3f}", "-i", src,
                        "-frames:v", "1", "-vf", f"scale={DIFF_W}:{DIFF_H}",
                        "-pix_fmt", "gray", "-f", "rawvideo", "-"],
                       capture_output=True)
    buf = r.stdout
    if len(buf) < DIFF_W * DIFF_H:
        return None
    return np.frombuffer(buf[:DIFF_W * DIFF_H], np.uint8).reshape(DIFF_H, DIFF_W)


def ts(t):
    return f"{int(t)//60:d}:{int(t)%60:02d}"


def pool(img, rows, cols):
    """Block-average down to a tiny grid. Averaging rather than sampling is what
    makes the hash survive compression noise."""
    ry = np.linspace(0, img.shape[0], rows + 1).astype(int)
    rx = np.linspace(0, img.shape[1], cols + 1).astype(int)
    return np.array([[img[ry[i]:ry[i + 1], rx[j]:rx[j + 1]].mean()
                      for j in range(cols)] for i in range(rows)])


def phash(img):
    """Difference hash, used to compare a frame against every frame already kept -
    decks revisit slides and screen recordings return to the same view after a
    detour, so comparing only against the previous frame misses repeats.

    It is deliberately only a PREFILTER. Any grid coarse enough to be robust to
    compression noise is also coarse enough to average away a line of title text,
    so a hash match means "worth diffing", never "identical"."""
    g = pool(img, HASH_GRID, HASH_GRID + 1)
    bits = (g[:, :-1] > g[:, 1:]).ravel()
    return int("".join("1" if b else "0" for b in bits), 2)


def hamming(a, b):
    return bin(a ^ b).count("1")


def diff(a, b):
    """How much changed between two frames, WHERE, and what shape the change is.

    Total percent-changed is not enough on its own. A slide deck with burned-in
    subtitles changes every second in a thin strip at the bottom while the actual
    slide is untouched; percent-changed cannot tell that from a new slide, but the
    shape and position of the changed region can. Everything here is plain numbers
    so a frame can be judged - and thrown away - without ever being looked at."""
    if a is None or b is None:
        return None
    m = np.abs(a.astype(np.int16) - b.astype(np.int16)) > PIXEL_DELTA
    area = float(m.mean())
    if area == 0:
        return {"area": 0.0, "box": None, "where": "nothing",
                "label": "identical", "kind": "identical"}
    rows, cols = np.where(m.any(1))[0], np.where(m.any(0))[0]
    y0, y1, x0, x1 = rows[0] / DIFF_H, rows[-1] / DIFF_H, cols[0] / DIFF_W, cols[-1] / DIFF_W
    h, w = y1 - y0, x1 - x0
    cy, cx = (y0 + y1) / 2, (x0 + x1) / 2
    where = (["top", "middle", "bottom"][min(int(cy * 3), 2)] + "-" +
             ["left", "centre", "right"][min(int(cx * 3), 2)])
    label = ("trivial" if area < 0.003 else "local" if area < 0.05 else
             "region" if area < 0.25 else "major" if area < 0.60 else "full")

    # What everything ABOVE the caption band did. If that part held still, the
    # only thing that moved was the subtitle strip - same slide, new words.
    above = float(m[:int(DIFF_H * CAPTION_BAND)].mean())
    if y0 >= CAPTION_BAND - 0.04 and above < 0.0015:
        kind = "caption"
    elif w < 0.18 and h < 0.18 and area < 0.02:
        kind = "widget"          # cursor, caret, timer, spinner, badge
    elif h < 0.10 and w > 0.5:
        kind = "strip"           # progress bar, ticker, tab bar
    else:
        kind = "content"
    return {"area": area, "where": where, "label": label, "kind": kind,
            "box": [round(x0, 2), round(y0, 2), round(w, 2), round(h, 2)]}


# ------------------------------------------------------------ frame selection

def score_frames(src, fps, t0, t1):
    """One low-res decode pass. Returns [(time, scene_score)]."""
    cmd = [FFMPEG, "-v", "info", "-nostdin"]
    if t0:
        cmd += ["-ss", str(t0)]
    if t1:
        cmd += ["-to", str(t1)]
    cmd += ["-i", src, "-an",
            "-vf", f"fps={fps},scale=320:-2,select='gt(scene,0)',metadata=print:file=-",
            "-f", "null", "-"]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    scores, t = [], None
    for line in out.splitlines():
        m = re.search(r"pts_time:([0-9.]+)", line)
        if m:
            t = float(m.group(1)) + (t0 or 0)
            continue
        m = re.search(r"lavfi\.scene_score=([0-9.]+)", line)
        if m and t is not None:
            scores.append((t, float(m.group(1))))
            t = None
    return scores


def pick(scores, floor, gap, budget, dur):
    """Greedy: highest-scoring frames first, never two within `gap`.

    Taking the top N rather than everything over a threshold is what keeps the
    cost fixed no matter how busy the video is."""
    med = sorted(s for _, s in scores)[len(scores) // 2] if scores else 0.0
    floor = max(floor, med * 3)              # noisy footage raises its own floor
    keep = [0.0]                              # opening frame is always context
    for t, s in sorted(scores, key=lambda x: -x[1]):
        if len(keep) >= budget or s < floor:
            break
        if all(abs(t - k) >= gap for k in keep):
            keep.append(t)
    if len(keep) < 3:                         # nothing moved - fall back to a spread
        n = min(budget, 8)
        keep = [dur * i / n for i in range(n)]
    return sorted(keep), floor


def select(src, times, min_area, keep_captions=False):
    """The 'look before you look' pass. Every candidate is judged against what has
    already been kept and dropped for a stated reason - in code, for free, before
    a single frame is ever read as an image.

    The hash finds which kept frame a candidate MIGHT repeat; a real pixel diff
    then decides. Hash alone is not trustworthy enough - it would happily merge
    two slides that differ only in their title.

    The ladder, in order:
      1. genuinely the same picture as a frame already kept -> a repeat
      2. same picture except the subtitle strip             -> same slide, new words
      3. only a cursor / caret / timer-sized box moved      -> nothing happened
      4. changed less than the mode's floor                 -> compression noise
    """
    if not times:
        return [], [], []
    first = gray_frame(src, times[0])
    if first is None:
        return [], [], []
    kept, diffs, imgs, dropped = [times[0]], [None], [first], []

    def against(img, ref, i):
        """Verdict of `img` measured against kept frame `i`, or None to keep."""
        d = diff(ref, img)
        if not d:
            return None
        if d["area"] < min_area:
            return f"same picture as keyframe [{i}] at {ts(kept[i])} ({d['area']*100:.2f}%)"
        if d["kind"] == "caption" and not keep_captions:
            return (f"same as keyframe [{i}] at {ts(kept[i])} except the subtitle "
                    f"strip ({d['area']*100:.1f}%)")
        if d["kind"] == "widget":
            return f"only a {d['where']} widget moved vs [{i}] ({d['area']*100:.1f}%)"
        return None

    for t in times[1:]:
        img = gray_frame(src, t)
        if img is None:
            continue
        hp = phash(img)
        # cheapest first: only frames the hash says are close get a real diff
        near = sorted((hamming(hp, phash(k)), i) for i, k in enumerate(imgs))
        why = None
        for dist, i in near:
            if dist > HASH_NEAR:
                break
            why = against(img, imgs[i], i)
            if why:
                break
        if why is None:                       # nothing matched - judge against the last kept
            why = against(img, imgs[-1], len(imgs) - 1)
        if why:
            dropped.append((t, why))
            continue
        diffs.append(diff(imgs[-1], img))
        kept.append(t)
        imgs.append(img)
    return kept, diffs, dropped


# ------------------------------------------------------------------ text side

def find_ggml():
    for p in ("~/.cache/openwhispr/whisper-models", "~/Library/Application Support/superwhisper",
              "~/.cache/hyperframes/whisper/models", "~/.cache/ipad-code-graph/models",
              "/opt/homebrew/share/whisper.cpp/models"):
        for size in ("large-v3-turbo", "large", "medium", "small.en", "small", "base.en", "base"):
            hit = glob.glob(os.path.join(os.path.expanduser(p), f"ggml-{size}.bin"))
            if hit:
                return hit[0]
    return None


def transcribe(src, outdir, model):
    """whisper.cpp with a local ggml model if one exists (Metal, several times
    faster), else the Python openai-whisper CLI. Normalises both to segments."""
    wav = os.path.join(outdir, "audio16k.wav")
    if subprocess.run([FFMPEG, "-y", "-v", "error", "-nostdin", "-i", src,
                       "-vn", "-ac", "1", "-ar", "16000", wav]).returncode != 0:
        return None, "no audio track"
    cli, ggml = shutil.which("whisper-cli"), find_ggml()
    if cli and ggml and model == "auto":
        pre = os.path.join(outdir, "transcript")
        # -ml/-sow force sentence-sized segments; the default chunks are whole
        # paragraphs, which makes per-keyframe pairing useless.
        subprocess.run([cli, "-m", ggml, "-f", wav, "-oj", "-osrt", "-of", pre,
                        "-l", "en", "-np", "-nt", "-ml", "90", "-sow"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        j = json.load(open(pre + ".json"))
        segs = [{"start": s["offsets"]["from"] / 1000, "end": s["offsets"]["to"] / 1000,
                 "text": s["text"]} for s in j["transcription"]]
        return segs, f"whisper.cpp {os.path.basename(ggml)}"
    if not shutil.which("whisper"):
        return None, "no whisper backend found"
    m = "large-v3-turbo" if model == "auto" else model
    subprocess.run(["whisper", wav, "--model", m, "--language", "en",
                    "--output_format", "json", "--output_dir", outdir, "--fp16", "False"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return json.load(open(os.path.join(outdir, "audio16k.json")))["segments"], f"openai-whisper {m}"


def ocr(paths):
    """On-screen text via the macOS Vision framework. A slide's words arrive as
    words - no image read needed to know what it says."""
    binp = os.path.join(HERE, "ocr")
    if not os.path.exists(binp):
        if not shutil.which("swiftc"):
            return {}
        if subprocess.run(["swiftc", "-O", "-o", binp, os.path.join(HERE, "ocr.swift")],
                          capture_output=True).returncode != 0:
            return {}
    out = subprocess.run([binp] + paths, capture_output=True, text=True).stdout
    res, cur = {}, None
    for line in out.splitlines():
        m = re.match(r"<<<FILE:(.*)>>>$", line)
        if m:
            cur = m.group(1)
            res[cur] = []
        elif cur and line.strip():
            res[cur].append(line.strip())
    return {k: "\n".join(v) for k, v in res.items()}


# -------------------------------------------------------------------- output

def extract(src, times, outdir):
    frames = []
    for t in times:
        p = os.path.join(outdir, f"f_{int(t)//60:02d}m{int(t)%60:02d}s.jpg")
        subprocess.run([FFMPEG, "-y", "-v", "error", "-nostdin", "-ss", f"{t:.3f}", "-i", src,
                        "-frames:v", "1", "-vf", "scale=1280:-2", "-q:v", "3", p], check=True)
        frames.append((t, p))
    return frames


PER_SHEET = 24      # more tiles than this in one image and the thumbs go unreadable


def contact_sheets(frames, outdir, cols=4):
    """Labelled grids - one image read instead of N. Paginated, because a
    forensic pass produces more frames than fit legibly on one sheet."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return []
    tw, bar = 480, 26
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    sheets, pages = [], [frames[i:i + PER_SHEET] for i in range(0, len(frames), PER_SHEET)]
    for pi, page in enumerate(pages, 1):
        thumbs = [(t, Image.open(p).convert("RGB")) for t, p in page]
        thumbs = [(t, im.resize((tw, int(im.height * tw / im.width)))) for t, im in thumbs]
        th = max(i.height for _, i in thumbs)
        rows = (len(thumbs) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * tw, rows * (th + bar)), (18, 18, 18))
        d = ImageDraw.Draw(sheet)
        for i, (t, im) in enumerate(thumbs):
            x, y = (i % cols) * tw, (i // cols) * (th + bar)
            sheet.paste(im, (x, y + bar))
            d.text((x + 8, y + 4), f"{int(t)//60:d}:{int(t)%60:02d}", fill=(255, 210, 90), font=font)
        name = "contact.jpg" if len(pages) == 1 else f"contact-{pi}.jpg"
        sheet.save(os.path.join(outdir, name), quality=88)
        sheets.append(os.path.join(outdir, name))
    return sheets


def timeline(frames, diffs, segs, dur, outdir):
    """A time track. The contact sheet shows what happened; a grid hides *when* -
    four frames in ten seconds look identical to four spread over ten minutes."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None
    W, H, pad = 1800, 200, 40
    im = Image.new("RGB", (W, H), (18, 18, 18))
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 14)
    except OSError:
        font = ImageFont.load_default()
    x_of = lambda t: pad + (W - 2 * pad) * (t / dur)
    d.text((pad, 8), f"0:00  -  {ts(dur)}   {len(frames)} keyframes", fill=(160, 160, 160), font=font)
    # speech blocks: where the talking is, and where the silences are
    d.text((pad, 34), "speech", fill=(120, 160, 220), font=font)
    for s in (segs or []):
        d.rectangle([x_of(s["start"]), 52, max(x_of(s["end"]), x_of(s["start"]) + 1), 72],
                    fill=(70, 110, 180))
    # change magnitude per keyframe, as a bar
    d.text((pad, 84), "change", fill=(220, 180, 90), font=font)
    for (t, _), df in zip(frames, diffs):
        h = int(46 * min(1.0, (df or {}).get("area", 1.0)))
        d.rectangle([x_of(t) - 2, 148 - h, x_of(t) + 2, 148], fill=(230, 180, 70))
    d.line([pad, 150, W - pad, 150], fill=(90, 90, 90))
    for i, (t, _) in enumerate(frames):     # tick + index, staggered so labels fit
        x, y = x_of(t), 154 + (i % 2) * 16
        d.line([x, 146, x, 154], fill=(255, 210, 90))
        d.text((x + 3, y), f"{i}", fill=(200, 200, 200), font=font)
    for mnt in range(0, int(dur) + 1, 60):  # minute ruler
        d.line([x_of(mnt), 176, x_of(mnt), 184], fill=(140, 140, 140))
        d.text((x_of(mnt) + 3, 182), ts(mnt), fill=(140, 140, 140), font=font)
    p = os.path.join(outdir, "timeline.jpg")
    im.save(p, quality=90)
    return p


def said_between(segs, t0, t1, cap=320):
    """What is spoken while this frame is on screen - from it appearing to the
    next keyframe replacing it."""
    txt = " ".join(s["text"].strip() for s in (segs or [])
                   if s["end"] > t0 and s["start"] < t1).strip()
    return txt[:cap] + ("..." if len(txt) > cap else "")


def index_md(frames, diffs, texts, segs, outdir, src, dur, meta, dropped):
    """Pairs every keyframe with what changed, what it says, and what was being
    said - so most questions get answered without opening a single image."""
    L = [f"# watch: {os.path.basename(src)}", "",
         f"- duration **{ts(dur)}**, {len(frames)} keyframes",
         f"- {meta}", ""]
    if segs:
        L += ["## Transcript", ""] + [f"[{ts(s['start'])}] {s['text'].strip()}" for s in segs] + [""]
    L += ["## Keyframes", "",
          "`changed` is a real pixel diff against the previous keyframe: fraction of "
          "the frame that moved, and roughly where. `trivial` means don't bother looking.", ""]
    for i, ((t, p), df) in enumerate(zip(frames, diffs)):
        nxt = frames[i + 1][0] if i + 1 < len(frames) else dur
        said = said_between(segs, t, nxt)
        L.append(f"### [{i}] {ts(t)}  -  `{os.path.basename(p)}`")
        if df:
            L.append(f"- changed: **{df['label']}** ({df['area']*100:.1f}% of frame, {df['where']})")
        if texts.get(p):
            L.append("- on screen:\n```\n" + texts[p] + "\n```")
        if said:
            L.append(f"- said here: {said}")
        L.append("")
    if dropped:
        L += ["## Rejected without being looked at", "",
              f"{len(dropped)} candidate frames the pixel heuristics threw out. "
              "Listed so a misfire is visible rather than silent.", ""]
        L += [f"- {ts(t)}  -  {why}" for t, why in dropped] + [""]
    out = os.path.join(outdir, "index.md")
    open(out, "w").write("\n".join(L))
    return out


# ------------------------------------------------------------------- selftest

def selftest():
    scores = [(i * 0.25, 0.001) for i in range(400)]
    for t in (10.0, 10.25, 40.0, 70.0):
        scores[int(t * 4)] = (t, 0.6)
    keep, _ = pick(scores, 0.02, 2.0, 24, 100.0)
    assert keep[0] == 0.0 and {40.0, 70.0} <= set(keep), keep
    assert all(b - a >= 2.0 for a, b in zip(keep, keep[1:])), keep
    assert 10.25 not in keep, "min gap must drop the adjacent duplicate"
    assert len(pick([(i * 0.25, 0.9) for i in range(400)], 0.15, 2.5, 6, 100.0)[0]) <= 6

    a = np.zeros((DIFF_H, DIFF_W), np.uint8)
    b = a.copy(); b[:, :] = 0; b[10:14, 10:14] = 255          # a cursor-sized speck
    assert diff(a, b)["label"] == "trivial", diff(a, b)
    c = a.copy(); c[:, :] = 255                                # whole screen
    assert diff(a, c)["label"] == "full", diff(a, c)
    e = a.copy(); e[0:60, 0:100] = 255                         # a corner panel
    r = diff(a, e)
    assert r["label"] in ("local", "region") and r["where"] == "top-left", r
    assert diff(a, a)["label"] == "identical"

    # shape heuristics: same slide + new subtitles must not read as a new slide
    cap = a.copy(); cap[int(DIFF_H * 0.86):int(DIFF_H * 0.95), 80:400] = 255
    assert diff(a, cap)["kind"] == "caption", diff(a, cap)
    assert diff(a, b)["kind"] == "widget", diff(a, b)
    bar = a.copy(); bar[int(DIFF_H * 0.5):int(DIFF_H * 0.53), :] = 255
    assert diff(a, bar)["kind"] == "strip", diff(a, bar)
    slide = a.copy(); slide[20:200, 20:400] = 255
    assert diff(a, slide)["kind"] == "content", diff(a, slide)

    # hashing: a repeated slide is a repeat even after compression noise
    rng = np.random.default_rng(0)
    base = rng.integers(0, 255, (DIFF_H, DIFF_W), dtype=np.uint8)
    noisy = np.clip(base.astype(np.int16) + rng.integers(-6, 6, base.shape), 0, 255).astype(np.uint8)
    assert hamming(phash(base), phash(noisy)) <= HASH_NEAR, "noise must not defeat the hash"
    other = rng.integers(0, 255, (DIFF_H, DIFF_W), dtype=np.uint8)
    assert hamming(phash(base), phash(other)) > HASH_NEAR, "unrelated frames must not collide"
    print("selftest ok")


# ----------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Watch a video: keyframes + OCR + transcript.")
    ap.add_argument("words", nargs="*", metavar="SOURCE [EFFORT] [MODE]",
                    help="a path or URL, plus optional bare words: low|medium|high|xhigh "
                         "(or l|m|h|xh) and slides|ui|footage. Any order.")
    ap.add_argument("--mode", default=None, choices=list(MODES), help=argparse.SUPPRESS)
    ap.add_argument("--max-frames", type=int, default=None, help="override the effort budget")
    ap.add_argument("--min-gap", type=float, default=None)
    ap.add_argument("--every", type=float, default=None, help="ignore scoring, sample every N sec")
    ap.add_argument("--from", dest="t0", type=float, default=None)
    ap.add_argument("--to", dest="t1", type=float, default=None)
    ap.add_argument("--sample-fps", type=float, default=4.0)
    ap.add_argument("--keep-captions", action="store_true",
                    help="do not drop frames where only the subtitle strip changed")
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--no-ocr", action="store_true")
    ap.add_argument("--model", default="auto", help="auto = whisper.cpp ggml if present")
    ap.add_argument("--out", default=None)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    src, eff, mode = classify(a.words)
    if not src:
        ap.error("give me a video path or URL")
    a.effort = eff or "medium"
    a.mode = a.mode or mode or "auto"
    out = a.out or os.path.join(os.path.expanduser("~/Desktop"), "watch-" +
                                re.sub(r"\W+", "-", os.path.splitext(os.path.basename(src))[0])[:40].strip("-"))
    os.makedirs(out, exist_ok=True)

    if re.match(r"https?://", src):
        print("downloading...", flush=True)
        subprocess.run(["yt-dlp", "--no-playlist", "--extractor-args",
                        "youtube:player_client=web,mweb", "-f", "bv*+ba/b",
                        "--merge-output-format", "mp4",
                        "-o", os.path.join(out, "source.%(ext)s"), src], check=True)
        src = next(os.path.join(out, f) for f in os.listdir(out) if f.startswith("source."))
        subprocess.run(["xattr", "-d", "com.apple.quarantine", src], capture_output=True)

    dur = float(probe(src, "format=duration"))
    budget, gap_mult, sens = EFFORT[a.effort]
    budget = a.max_frames or budget
    floor, gap, min_area = MODES[a.mode]
    floor *= sens
    min_area *= sens
    gap = a.min_gap if a.min_gap is not None else gap * gap_mult
    print(f"effort={a.effort} mode={a.mode} budget={budget} gap>={gap:.2f}s", flush=True)

    if a.every:
        t0, t1 = a.t0 or 0.0, a.t1 or dur
        times = [t0 + i * a.every for i in range(int((t1 - t0) / a.every) + 1)][:budget]
    else:
        print("scoring frames...", flush=True)
        times, floor = pick(score_frames(src, a.sample_fps, a.t0, a.t1), floor, gap, budget, dur)
    print(f"{len(times)} candidates; diffing pixels...", flush=True)
    times, diffs, dropped = select(src, times, min_area, a.keep_captions)
    print(f"{len(times)} keyframes ({len(dropped)} rejected without being read)", flush=True)

    frames = extract(src, times, out)
    texts = {} if a.no_ocr else ocr([p for _, p in frames])
    sheets = contact_sheets(frames, out)
    segs, how = (None, "audio skipped")
    if not a.no_audio:
        print("transcribing...", flush=True)
        segs, how = transcribe(src, out, a.model)
    tl = timeline(frames, diffs, segs, dur, out)
    meta = f"transcript: {how}; OCR: {'on' if texts else 'off'}"
    idx = index_md(frames, diffs, texts, segs, out, src, dur, meta, dropped)

    print("\nWROTE", out)
    print("read in this order:")
    print("  1.", os.path.basename(idx), "(text - usually enough)")
    if tl:
        print("  2.", os.path.basename(tl), "(when things happen)")
    for s in sheets:
        print("  3.", os.path.basename(s), "(what they look like)")
    print("  4. individual f_*.jpg - only where index.md says it matters")


if __name__ == "__main__":
    main()
