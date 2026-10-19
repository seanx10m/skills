---
name: watch-video
description: Watch a video - a local file, a screen recording, a Loom or YouTube URL - by extracting keyframes at moments the picture actually changed, reading on-screen text with native macOS OCR, and transcribing the audio locally, so Claude can see and quote what happened. Use when the user says "/watch-video", "watch this video", "look at this recording", "what happens in this clip", "review this screen recording", drops a .mp4/.mov path, or asks Claude to check a demo, bug repro, or walkthrough recording.
---

# watch-video

I cannot play a video, and **I never hear audio** - not tone, not music, not
whether something is loud. Only words survive, via transcription. Say that
plainly rather than implying otherwise.

"Watching" is reconstructing the video from three channels, cheapest first:

| Channel | Cost | What it gives |
|---|---|---|
| **Text** - transcript + OCR of on-screen text | ~free | Usually answers the question outright |
| **Numbers** - per-frame pixel diffs | free | *Which* frames are worth looking at, and where on screen it changed |
| **Pixels** - the frames themselves | ~1-1.5k tokens each | Spent last, only where the first two point |

The ordering is the whole design. Most video questions are answered without
opening a single image.

## Run it

```bash
python3 ~/.claude/skills/watch-video/scripts/watch.py <path-or-URL> [effort] [mode]
```

Effort and mode are **bare words in any order** - no flags to remember:

```bash
watch.py https://youtu.be/abc123 xh          # xhigh effort
watch.py ~/Desktop/demo.mov high ui          # screen recording, look closely
watch.py deck.mp4 l                          # quick skim
```

`low`/`medium`/`high`/`xhigh`, or `l`/`m`/`h`/`xh`, or plain English
(`skim`, `closely`, `forensic`). Mode words: `slides`/`deck`, `ui`/`screen`/`demo`,
`footage`/`camera`. Anything that resolves to a real path or URL is the source, so
a file named `high.mp4` still works.

Output lands in `~/Desktop/watch-<name>/`.

| Option | Default | Why |
|---|---|---|
| `-e`, `--effort low\|medium\|high\|xhigh` | `medium` | **The main dial**, on Claude's own effort scale. Shorthands `l` / `m` / `h` / `xh`. "Watch it closely" → `-e high`. Sets frame budget, spacing and sensitivity together: 8 / 24 / 60 / 150 frames. |
| `--mode slides\|ui\|footage\|auto` | `auto` | What kind of video it is. See below - this matters. |
| `--max-frames N` | per effort | Override the budget directly. |
| `--from` / `--to` | whole file | Seconds. Zoom into one stretch on a second pass. |
| `--every N` | off | Ignore change-detection, sample every N seconds. For one continuous shot. |
| `--no-audio` / `--no-ocr` | off | Skip a channel. |
| `--keep-captions` | off | Keep frames where only the subtitle strip changed. |
| `--model` | `auto` | `auto` uses whisper.cpp + a local ggml model if present, else openai-whisper. |
| `--selftest` | - | Checks the picker and the diff classifier. No video, no network. |

## How frames get picked

Two passes, both in code, before anything is looked at:

1. **Scene scoring** - every frame is compared to the previous one at 4fps and
   320px. Only the highest-scoring frames survive, subject to a minimum gap.
   Taking the *top N* rather than everything above a threshold is what keeps
   cost fixed no matter how busy the video is.
2. **Real pixel diff, shape-aware** - each surviving candidate is diffed in numpy
   against the frames already kept. Anything the heuristics reject is **dropped
   without ever being read**, and the reason is logged.

That second pass is the point, and *percent changed is not enough on its own*.
The ladder, in order:

| Rejected as | Because |
|---|---|
| repeat | Genuinely the same picture as a frame already kept. Decks revisit slides; recordings return to a view. |
| caption | Everything above the bottom strip held still - **same slide, new subtitles**. |
| widget | Only a cursor / caret / timer / spinner-sized box moved. |
| below floor | Compression noise. |

A perceptual hash finds *which* kept frame a candidate might repeat, but only as
a prefilter - a real diff makes the call. Any hash grid coarse enough to survive
compression noise is also coarse enough to average away a line of title text, so
hash-alone would happily merge two slides that differ only in their heading.

Every rejection is listed in `index.md` under "Rejected without being looked at",
so a misfiring heuristic is visible rather than silent. `--keep-captions` turns
the caption rule off when the subtitles *are* the content.

The frame budget is a **ceiling, not a quota** - it never pads with junk. A
10-minute video with 32 real cuts yields 20 keyframes at `-e medium` and 26 at
`-e high`, not 60, because everything below the floor is genuinely nothing.

Modes only set the thresholds:

- **slides** - hard cuts, static in between. High floor, wide gap.
- **ui** - screen recordings and demos. Real transitions are small but local, so
  the floor drops to `0.012`. A slide deck and a screen recording genuinely
  cannot share a threshold - this is why `--mode` exists.
- **footage** - moving camera, every frame scores high, so the floor rises and
  frames get spread out instead.
- **auto** - middle ground, and the floor self-raises to 3x the median score,
  which handles noisy footage without being told.

## Reading the result - in this order

1. **`index.md`** - the full transcript, then every keyframe annotated with what
   changed (`trivial` / `local` / `region` / `major` / `full`, with % and screen
   position), the OCR'd on-screen text, and what was being said while it was up.
   **Start here. Often you can stop here.**
2. **`timeline.jpg`** - when things happen. A grid hides time: four frames in ten
   seconds look identical to four spread over ten minutes. This shows speech
   blocks, change magnitude, and keyframe indices against a minute ruler.
3. **`contact.jpg`** - one labelled grid, one image read, the whole shape of the
   video. Paginated at 24 tiles.
4. **`f_*.jpg`** - individual frames, only where `index.md` says it matters.
   This is where the token budget goes, so spend it deliberately.

## Dependencies

Hard: `ffmpeg`/`ffprobe`, `python3` + `numpy`. Both already required by Whisper.

Soft, each degrading gracefully: `whisper-cli` + a local `ggml-*.bin` (auto-found
in common local app caches - **much** faster than the
Python backend, Metal-accelerated), else `whisper`; `swiftc` for OCR; `Pillow` for
the contact sheet and timeline; `yt-dlp` for URLs.

## Gotchas

- OCR is a small Swift binary using the macOS Vision framework, compiled on first
  use from `scripts/ocr.swift` into `scripts/ocr` (needs `swiftc`, i.e. Xcode command line tools).
  No pip, no brew. Delete the binary to force a rebuild. To build manually:
  `swiftc -O -o scripts/ocr scripts/ocr.swift`.
- This ffmpeg build has **no libass and no libfreetype**, so the `subtitles` and
  `drawtext` filters do not exist. Labels are drawn with Pillow for that reason -
  do not "fix" it back to `drawtext`.
- URLs go through `yt-dlp` and may hit 403s from YouTube; the
  `web,mweb` client is already the default here.
- `~/Desktop` collects these folders and they are large. Clean up when done.
