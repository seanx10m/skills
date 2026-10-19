---
name: youtube-transcript
description: Get the text transcript of a YouTube video with no API key, by pulling YouTube's own captions with yt-dlp and cleaning them to plain text (default folder ~/Downloads). Optionally summarize it. Use when the user says "get the transcript of this video", "transcribe this youtube", "what does this video say", or pastes a YouTube URL and asks for its text or a summary.
disable-model-invocation: true
---

# YouTube Transcript

Run the script:

```sh
~/.claude/skills/youtube-transcript/scripts/transcript.sh "<url>" [out-dir]
```

It prints the path of the `.txt` (default `~/Downloads/<video title>.txt`; pass an out-dir or set `YT_TRANSCRIPT_DIR`).
Then read the file and do what the user asked - summary, quotes, Q&A.
Never paste the full transcript into chat; give the path.

## How it works

- `yt-dlp --skip-download --write-auto-subs` fetches the caption track only.
- Do not pass `--cookies-from-browser` by default: on macOS yt-dlp reads the browser key from the Keychain, which pops a prompt on every call. Only use it if the user asks, and only once.
- Prefers `en-orig` (original-language auto captions), falls back to any `en.*` track.
- VTT is stripped of timestamps and tags, and deduped (auto captions repeat every line).

## When it fails

- Exit 2 `NO_CAPTIONS`: the video has no English captions. Transcribe the audio locally instead (the optional `watch-video` skill does this with Whisper, if installed).
- HTTP 429: transient YouTube rate limiting - wait a minute and retry. 403: run `yt-dlp -U` and retry; the optional `youtube-to-m4a` skill documents the player-client fallback ladder (`--extractor-args "youtube:player_client=web,mweb"`).
