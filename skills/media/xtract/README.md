# xtract

Turn a link into one Markdown file: the post text plus a verbatim local transcript.
Handles X/Twitter posts (via the public fxtwitter JSON, no login), and anything yt-dlp can read (YouTube, Loom, Vimeo, TikTok, ...).

## Requirements

- `python3` (3.8+, stdlib only)
- `yt-dlp` and `ffmpeg`: `brew install yt-dlp ffmpeg`
- Optional, for transcripts: the `watch-video` skill from this repo (whisper.cpp, macOS). Without it you still get post text and metadata.

## Install

```bash
cp -r skills/media/xtract ~/.claude/skills/
# optional, for transcripts:
cp -r skills/media/watch-video ~/.claude/skills/
```

## Use

```bash
python3 ~/.claude/skills/media/xtract/scripts/xtract.py <url> [--out DIR] [--keep-video] [--frames]
```

Output defaults to `~/Desktop/xtract/<date>-<author>/xtract.md` (override with `--out` or `XTRACT_OUT`).
