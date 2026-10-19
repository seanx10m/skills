# youtube-to-mp4

Download a YouTube video as an `.mp4` (or `.mov`) that opens everywhere: H.264 + AAC preferred, 403 fallback ladder, macOS quarantine cleanup, ffprobe verification.

## Requirements

- `yt-dlp` and `ffmpeg` (includes `ffprobe`): `brew install yt-dlp ffmpeg`
- macOS for the quarantine step (`xattr`); everything else works on Linux too.

## Install

```bash
cp -r skills/media/youtube-to-mp4 ~/.claude/skills/
```

Output defaults to `~/Desktop`; set `YT_VIDEO_DIR` to change it.
