# youtube-to-m4a

Download the audio of a YouTube video as `.m4a` (stream copy when the source is AAC, so no generation loss). WAV on request. Includes the 403 player-client fallback ladder and macOS quarantine cleanup.

## Requirements

- `yt-dlp` and `ffmpeg`: `brew install yt-dlp ffmpeg`
- macOS for the quarantine step (`xattr`); everything else works on Linux too.

## Install

```bash
cp -r skills/media/youtube-to-m4a ~/.claude/skills/
```

The skill is invoke-only (`disable-model-invocation: true`): run it as `/youtube-to-m4a <url>`.
Output defaults to `~/Downloads`; set `YT_AUDIO_DIR` to change it.
