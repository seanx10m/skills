---
name: youtube-to-mp4
description: Download a YouTube video as a real video file (.mp4 by default, .mov on request) using yt-dlp plus ffmpeg, with QuickTime-safe codec selection, a player-client fallback ladder for HTTP 403 errors, and macOS quarantine cleanup. Output goes to ~/Desktop unless YT_VIDEO_DIR or the request says otherwise. Use when the user says "youtube to mp4", "youtube to mov", "download this video", "save this YouTube video", or pastes a YouTube URL and asks for a video file. For audio-only use the youtube-to-m4a skill.
---

# YouTube to MP4

`yt-dlp` pulls the video and audio streams, `ffmpeg` muxes them into one container.
Default output dir is `~/Desktop` (override with the `YT_VIDEO_DIR` env var or by naming a directory) - these are files to watch or drag somewhere, not a library.
In the commands below, `${YT_VIDEO_DIR:-$HOME/Desktop}` is that directory.

## 1. Check deps

```bash
which yt-dlp ffmpeg
brew install yt-dlp   # if missing (pulls ffmpeg as a dep, else: brew install ffmpeg)
```

`ffmpeg` does the mux.
Without it yt-dlp can only hand back whichever single pre-muxed format YouTube offers, which is 360p.

## 2. Download

```bash
yt-dlp -f "bv*[vcodec^=avc1]+ba[acodec^=mp4a]/bv*+ba/b" \
  --merge-output-format mp4 --no-playlist \
  -o "${YT_VIDEO_DIR:-$HOME/Desktop}/%(title)s.%(ext)s" "<URL>"
```

The format selector asks for **H.264 video + AAC audio first**, and only falls back to
"best anything" if that pair does not exist.
That preference is the whole point - see the codec section below.

`--no-playlist` is not optional in practice: share links from a radio or mix carry
`&list=RD...`, and without it yt-dlp downloads the entire queue.

## 3. Codecs - why the selector looks like that

YouTube's highest-resolution streams are **VP9 or AV1** video with **Opus** audio.
Those go into an `.mp4` container fine as far as ffmpeg is concerned, but the result is not
a file every Mac app will open - Opus in particular is not something QuickTime handles.
H.264 + AAC is the pair that plays everywhere without thinking about it.

The cost is a resolution ceiling: **YouTube stops shipping H.264 above 1080p.**
Measured on a 4K test video:

| Selector | Result |
|---|---|
| `bv*[vcodec^=avc1]+ba[acodec^=mp4a]/bv*+ba/b` (default here) | `avc1` + `mp4a`, 1920x1080 |
| `bv*+ba/b` | `av01` + `mp4a`, 3840x2160 |

So: if the user explicitly wants max resolution, swap in `-f "bv*+ba/b"` and **tell them**
the file may not open in QuickTime and is aimed at VLC or an editor.
Otherwise stay on the default and mention the 1080p cap only if the source was higher.

Check what you actually got before reporting success - do not assume the first branch won.

## 4. MOV instead

Use `--remux-video mov`, **not** `--merge-output-format mov`.

```bash
yt-dlp -f "bv*[vcodec^=avc1]+ba[acodec^=mp4a]/b[ext=mp4]" \
  --remux-video mov --no-playlist \
  -o "${YT_VIDEO_DIR:-$HOME/Desktop}/%(title)s.%(ext)s" "<URL>"
```

`--merge-output-format` only fires when two streams are actually merged.
When yt-dlp falls back to a single pre-muxed stream (format 18, the common 403 outcome)
nothing is merged, so the flag is silently ignored and you get a `.mp4` while telling the
user you made a `.mov`.
`--remux-video` runs after the download either way.

MOV is a container swap, not a conversion - it stays a copy, no re-encode, as long as the
codecs are H.264/AAC.
Ask whether MOV is really needed first: MP4 opens in QuickTime, Final Cut, and Premiere
just as well.

## 5. The 403 fallback ladder

The default player client often 403s.
Work down this list, stop at the first that works.

| # | Add to the command | Typical failure |
|---|---|---|
| a | nothing (plain command above) | `ERROR: unable to download video data: HTTP Error 403: Forbidden` |
| b | `--extractor-args "youtube:player_client=web_safari,ios,tv"` | `This video is drm protected and only images are available`, or PO Token warnings |
| c | `--extractor-args "youtube:player_client=web,mweb"` | usually works, but see the quality caveat |
| d | `--cookies-from-browser chrome` | needs the user's browser profile - ask before using |

## 6. Clear the Gatekeeper quarantine (always)

macOS tags CLI-downloaded files with `com.apple.quarantine`.
Opening the file in QuickTime then shows "Apple could not verify ... is free of malware"
with only "Move to Trash" / "Done".
Do this automatically every time, do not wait for the user to hit the error:

```bash
xattr -c "<file>"
```

Do not skip this.
The dialog's only buttons are "Move to Trash" and "Done", so the usual outcome of skipping
it is the user trashing a file they wanted.
If a file goes missing later, look in `~/.Trash` before re-downloading.

## 7. Verify

```bash
ffprobe -v error -show_entries stream=codec_type,codec_name,width,height \
  -show_entries format=duration,format_name -of default=nw=1 "<file>"
```

Expect a `video` stream and an `audio` stream.
Only one of them means the merge silently failed - re-run rather than handing it over.
Read the codec and resolution off this output and report them, rather than assuming the
command did what you asked for.

## Quality caveat - say this out loud

When the `web,mweb` fallback at rung **c** is used, yt-dlp usually drops to **format 18**:
360p, pre-muxed, H.264/AAC.
That is a real playable file, but it is 360p and no container change recovers the
resolution.
Say so plainly rather than handing over a 360p file and calling it done.

## Gotchas

- Titles containing `:` and `|` come out as fullwidth `：` and `｜` in the filename. Quote every path in every follow-up command, and copy the real filename from `ls` rather than retyping it.
- Run `yt-dlp -U` (or `brew upgrade yt-dlp`) if every rung of the ladder fails. YouTube changes break old versions constantly.
- Use `-o "${YT_VIDEO_DIR:-$HOME/Desktop}/<name>.%(ext)s"` to force a specific filename instead of the video title.
- Long videos are large. A 1080p hour is several GB - report the size after the download rather than letting the output folder quietly fill up.
- Subtitles are a separate fetch: add `--write-auto-subs --sub-langs en --embed-subs` if the user wants captions in the container.
- To preview which streams a selector will pick without downloading: `yt-dlp -f "<selector>" --print "%(format_id)s | %(vcodec)s | %(acodec)s | %(resolution)s" "<URL>"`.
