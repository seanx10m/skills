---
name: xtract
description: Pull the words out of a link - an X/Twitter post or video, a YouTube, Loom, Vimeo or TikTok video, or an article - into one clean Markdown file (post text plus verbatim local transcript), then do whatever was asked with it - save it, summarize it, pull quotes, compare it with a doc. Video files are downloaded only on request. Use when the user says "/xtract", "extract this", "transcribe this post", "what is he saying here", or pastes an x.com / youtube / loom link and wants the content.
---

# xtract

A link in, Markdown out, then the ask.
Markdown is the product. The video file is a by-product, kept only on request.

## 1. Extract

```bash
python3 ~/.claude/skills/xtract/scripts/xtract.py <url> [--out DIR] [--keep-video] [--frames]
```

It prints the path of the `xtract.md` it wrote (default `~/Desktop/xtract/<date>-<author>/`, or set `XTRACT_OUT`; pass a scratchpad dir as `--out` when the file is only a stepping stone).

| Link | How |
|---|---|
| x.com / twitter.com | Public fxtwitter JSON (no login, no browser): the post text, and for a video the smallest mp4, transcribed |
| YouTube, Loom, Vimeo, TikTok... | `yt-dlp`, then transcribed |
| Article / plain page | Exits 2. Use WebFetch and write the Markdown yourself, same header shape |

Transcription uses the optional `watch-video` skill's `watch.py` (whisper.cpp, local, about 10 s for a 6 min clip). If that skill is not installed the script still writes the post text and metadata and says the transcript was skipped (point `WATCH_VIDEO_PY` at a `watch.py` to override the lookup).
`--frames` keeps keyframes + OCR for slides or demos, where the screen carries words the audio does not.
`--keep-video` keeps `source.mp4`.

The file is: title, Source / Author / Posted / Length / Captured, `## Post`, `## Transcript (verbatim, local whisper)`, one sentence per line.
Whisper mishears names; fix obvious ones against the post text, and never "improve" the wording otherwise - it is a verbatim source.

Never use Chrome automation for this. If extraction fails, say exactly which step failed.

## 2. Do the ask

Extraction is step one; what the user asked for is the job.
Common asks:

- **Save it** - copy `xtract.md` into the notes or repo they name, following that location's conventions, and add a short "why it matters" note above the transcript if asked.
- **"Align it with X"** - read X, then say where the source agrees, disagrees, or adds something X lacks. Quote the line.
- **Summary** - 3 lines max in chat, unless more is requested.

When the result is long, write it to a file and give the path instead of pasting it into chat.
