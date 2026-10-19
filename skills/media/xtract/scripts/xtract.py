#!/usr/bin/env python3
"""xtract - turn a link into one Markdown file: the words, verbatim.

  xtract.py <url> [--out DIR] [--keep-video] [--frames]

X/Twitter posts go through the public fxtwitter JSON (no login, no browser):
the post text, and for a video the smallest mp4, transcribed locally.
Anything yt-dlp can read (YouTube, Loom, Vimeo, TikTok...) is transcribed the
same way. Transcription is the optional watch-video skill's watch.py (whisper.cpp,
local); without it you still get the post text and metadata.
Prints the path of the .md it wrote. Exits 2 for a page with no media
(an article): fetch that with WebFetch instead.
"""
import argparse, datetime, glob, json, os, re, shutil, subprocess, sys, urllib.request

# Optional: the sibling watch-video skill does the local transcription.
_HERE = os.path.dirname(os.path.abspath(__file__))
WATCH = next((p for p in (
    os.environ.get("WATCH_VIDEO_PY", ""),
    os.path.join(_HERE, "..", "..", "watch-video", "scripts", "watch.py"),
    os.path.expanduser("~/.claude/skills/watch-video/scripts/watch.py"),
) if p and os.path.exists(p)), None)
UA = {"User-Agent": "xtract/1.0"}


def get_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return json.load(r)


def x_post(url):
    m = re.search(r"(?:x|twitter)\.com/([^/]+)/status/(\d+)", url)
    if not m:
        return None
    t = get_json(f"https://api.fxtwitter.com/{m.group(1)}/status/{m.group(2)}")["tweet"]
    vids = [v for v in (t.get("media") or {}).get("all", []) if v.get("type") in ("video", "gif")]
    mp4 = None
    if vids:  # audio is all that matters: take the lowest-bitrate mp4
        fm = [f for f in vids[0].get("formats", []) if f.get("container") == "mp4"]
        mp4 = min(fm, key=lambda f: f.get("bitrate", 1e12))["url"] if fm else vids[0]["url"]
    return {"title": f"{t['author']['name']} (@{t['author']['screen_name']})",
            "author": t["author"]["name"], "posted": t.get("created_at", ""),
            "url": t.get("url", url), "text": t.get("text", ""), "video": mp4,
            "duration": vids[0].get("duration") if vids else None}


def transcribe(src, work, frames):
    if not WATCH:
        print("watch-video skill not found - skipping transcript "
              "(install it or set WATCH_VIDEO_PY=/path/to/watch.py)", file=sys.stderr)
        return None
    cmd = [sys.executable, WATCH, src, "l", "--out", work]
    if not frames:
        cmd.append("--no-ocr")
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    for name in ("transcript.json", "audio16k.json"):
        p = os.path.join(work, name)
        if os.path.exists(p):
            d = json.load(open(p))
            segs = d.get("transcription") or d.get("segments") or []
            words = " ".join((s.get("text") or "").strip() for s in segs)
            # one sentence per line
            return re.sub(r"(?<=[.!?])\s+(?=[A-Z\"'])", "\n", re.sub(r"\s+", " ", words)).strip()
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--out", default=os.path.expanduser(os.environ.get("XTRACT_OUT", "~/Desktop/xtract")))
    ap.add_argument("--keep-video", action="store_true")
    ap.add_argument("--frames", action="store_true", help="also keep keyframes + OCR (slides, demos)")
    a = ap.parse_args()

    post = x_post(a.url) or {"title": a.url, "url": a.url, "text": "", "video": a.url,
                             "author": "", "posted": "", "duration": None}
    stamp = datetime.date.today().isoformat()
    slug = re.sub(r"\W+", "-", (post["author"] or post["title"]).lower()).strip("-")[:40] or "link"
    work = os.path.join(a.out, f"{stamp}-{slug}")
    os.makedirs(work, exist_ok=True)

    transcript = None
    if post["video"]:
        src = post["video"]
        if src != a.url:  # a direct mp4 (X): fetch it ourselves, watch.py's yt-dlp is for pages
            src = os.path.join(work, "source.mp4")
            with urllib.request.urlopen(urllib.request.Request(post["video"], headers=UA), timeout=300) as r, open(src, "wb") as f:
                shutil.copyfileobj(r, f)
        try:
            transcript = transcribe(src, work, a.frames)
        except subprocess.CalledProcessError:
            if not post["text"]:
                print("no media and no post text - an article? use WebFetch", file=sys.stderr)
                sys.exit(2)
        junk = ["source.*", "audio16k.wav"] if not a.keep_video else []
        if not a.frames:  # Markdown is the product; pictures only when asked
            junk += ["f_*.jpg", "contact*.jpg", "timeline.jpg", "index.md"]
        for p in (q for g in junk for q in glob.glob(os.path.join(work, g))):
            os.remove(p)

    lines = [f"# {post['title']}", "",
             f"- Source: {post['url']}"]
    if post["author"]:
        lines.append(f"- Author: {post['author']}")
    if post["posted"]:
        lines.append(f"- Posted: {post['posted']}")
    if post["duration"]:
        lines.append(f"- Length: {int(post['duration'])//60}:{int(post['duration'])%60:02d}")
    lines.append(f"- Captured: {stamp} (xtract)")
    if post["text"]:
        lines += ["", "## Post", "", post["text"]]
    if transcript:
        lines += ["", "## Transcript (verbatim, local whisper)", "", transcript]
    md = os.path.join(work, "xtract.md")
    open(md, "w").write("\n".join(lines) + "\n")
    print(md)


if __name__ == "__main__":
    main()
