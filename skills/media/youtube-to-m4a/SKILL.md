---
name: youtube-to-m4a
description: Download the audio track of a YouTube video as a .m4a file (default folder ~/Downloads, configurable via YT_AUDIO_DIR) using yt-dlp plus ffmpeg, with a player-client fallback ladder for HTTP 403 errors and macOS quarantine cleanup. Also covers the .wav opt-in. Use when the user says "youtube to m4a", "youtube to wav", "download this youtube audio", "rip the audio from this video", or pastes a YouTube URL and asks for an audio file.
disable-model-invocation: true
---

# YouTube to M4A

`yt-dlp` pulls the stream, `ffmpeg` packages it.
Default output dir is `~/Downloads` (override with the `YT_AUDIO_DIR` env var or by naming a directory).
Below, `${YT_AUDIO_DIR:-$HOME/Downloads}` is that directory.
Default format is **m4a**, not wav.

## Why m4a is the default

YouTube never serves uncompressed audio.
Every stream you can get is already lossy - AAC (format 18) or Opus (format 251).

Converting that to WAV does **not** recover anything.
It writes the same lossy audio into a container ~14x larger.
A 10-hour audiobook is 558 MB as m4a and 5.9 GB as WAV, bit-for-bit the same sound.

Worse, `--audio-format m4a` on an AAC source is a **stream copy** - ffmpeg remuxes without re-encoding, so there is zero generation loss.
The WAV path is strictly bigger for strictly no gain.

Only produce a WAV when the user explicitly asks for one, or names a tool that requires PCM input (some DAWs, samplers, and analysis scripts).
If they ask for WAV without a reason, say the above in one line and let them decide.

## 1. Check deps

```bash
which yt-dlp ffmpeg
brew install yt-dlp   # if missing (pulls ffmpeg as a dep, else: brew install ffmpeg)
```

`ffmpeg` does the extraction and remux. Without it `-x --audio-format m4a` fails.

## 2. Download

```bash
cd "${YT_AUDIO_DIR:-$HOME/Downloads}" && yt-dlp -x --audio-format m4a --no-playlist -o "%(title)s.%(ext)s" "<URL>"
```

`--no-playlist` is not optional in practice: YouTube share links from a radio or mix carry `&list=RD...`, and without it yt-dlp downloads the entire queue instead of the one video.

The default folder is the landing spot - it is where the user expects to find a fresh file and where AirDrop and Finder sharing start from.
Use another directory only if the user names one in that request.
Avoid the Desktop unless asked: it is for ephemeral things and files there tend to get swept away.

## 3. The 403 fallback ladder

The default player client often 403s. Work down this list, stop at the first that works.

| # | Add to the command | Typical failure |
|---|---|---|
| a | nothing (plain command above) | `ERROR: unable to download video data: HTTP Error 403: Forbidden` |
| b | `--extractor-args "youtube:player_client=web_safari,ios,tv"` | `The page needs to be reloaded`, or PO Token warnings |
| c | `--extractor-args "youtube:player_client=web,mweb"` | usually works; falls back to format 18 |
| d | `--cookies-from-browser chrome` | needs the user's browser profile - ask before using |

Rung **c** is the one that has actually worked. Example:

```bash
cd "${YT_AUDIO_DIR:-$HOME/Downloads}" && yt-dlp -x --audio-format m4a \
  --extractor-args "youtube:player_client=web,mweb" \
  -o "%(title)s.%(ext)s" "<URL>"
```

## 4. Clear the Gatekeeper quarantine (always)

macOS tags CLI-downloaded files with `com.apple.quarantine`.
Opening the file in QuickTime then shows "Apple could not verify ... is free of malware" with only "Move to Trash" / "Done".
Do this automatically every time, do not wait for the user to hit the error:

```bash
xattr -d com.apple.quarantine "<file>"
```

The file is fine. This flag is purely about download provenance.

Do not skip this.
The dialog's only buttons are "Move to Trash" and "Done", so the usual outcome of skipping it is the user trashing a file they wanted.
If a file goes missing later, look in `~/.Trash` before re-downloading.

`com.apple.provenance` may remain after the delete. That one is harmless and cannot be removed - ignore it.

## 5. Verify

```bash
ffprobe -v error -show_entries stream=codec_name,sample_rate,channels \
  -show_entries format=duration -of default=nw=1 "<file>"
```

Expect `aac` / `44100` / `2` channels for m4a.

## Quality caveat - say this out loud

When the `web,mweb` fallback is used, yt-dlp picks **format 18** (360p mp4, 128kbps AAC audio).
That is the ceiling on quality regardless of output format.
The better audio is the Opus stream (format 251), and that is exactly the one that tends to 403.
Tell the user the bitrate they actually got rather than implying the file is master quality.

## If the user does want a WAV

```bash
cd "${YT_AUDIO_DIR:-$HOME/Downloads}" && yt-dlp -x --audio-format wav \
  --extractor-args "youtube:player_client=web,mweb" \
  -o "%(title)s.%(ext)s" "<URL>"
```

Same ladder, same quarantine step.
Verify expects `pcm_s16le` / `44100` / `2`.

Re-download rather than transcoding an existing m4a to WAV or vice versa - going lossy-to-lossy adds a second generation of loss for no reason.

## Gotchas

- **Opus source + m4a target re-encodes.** If rung a or b succeeds and hands you format 251, `--audio-format m4a` transcodes Opus to AAC (one generation of loss). Only matters for music; for speech it is inaudible. Use `--audio-format best` to keep the native `.opus` if the user cares, but note iOS and QuickTime handle `.opus` poorly.
- Titles containing `:` and `|` come out as fullwidth `：` and `｜` in the filename. Always quote paths in every follow-up command.
- Run `yt-dlp -U` (or `brew upgrade yt-dlp`) if every rung of the ladder fails. YouTube changes break old versions constantly.
- Use `-o "<name>.%(ext)s"` to force a specific filename instead of the video title.
- Long downloads: pipe through `grep -v "^\[download\] "` to drop the progress-bar spam, which otherwise floods the tool output.
