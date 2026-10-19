# youtube-transcript

Get a clean plain-text transcript of a YouTube video from YouTube's own captions. No API key, no audio download.

## Requirements

- `yt-dlp`: `brew install yt-dlp`
- `bash`, `sed`, `awk`, `fold` (standard)

## Install

```bash
cp -r skills/media/youtube-transcript ~/.claude/skills/
```

```bash
~/.claude/skills/media/youtube-transcript/scripts/transcript.sh "<url>" [out-dir]
```

Output defaults to `~/Downloads`; set `YT_TRANSCRIPT_DIR` to change it.
Exit 2 (`NO_CAPTIONS`) means the video has no English captions.
The skill is invoke-only (`disable-model-invocation: true`).
