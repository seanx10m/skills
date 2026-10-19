# youtube-to-command

Turn a YouTube track into a zsh command: `purple` toggles it on/off, `purple 3` sets volume, `purple p` pauses, `purple next` skips.
Standalone: downloads with yt-dlp itself, no other skill needed.

## Requirements

- zsh (macOS default)
- `yt-dlp`, `ffmpeg` (with `ffprobe`) and `sox`: `brew install yt-dlp ffmpeg sox`

## Install

```bash
cp -r skills/media/youtube-to-command ~/.claude/skills/
```

## Use

```bash
~/.claude/skills/media/youtube-to-command/scripts/add-track.sh --url "<URL>" --tag mysong --label "my song" [--dir ~/Music/tracks] [--loop]
```

## What it changes

Only `~/.zshrc`, and only by appending (or replacing, on re-run) blocks between `# >>> youtube-to-command: ... >>>` and `# <<< youtube-to-command: ... <<<` markers.
A backup is written to `~/.zshrc.bak-youtube-to-command` and the result is syntax-checked with `zsh -n`.
Playback state is kept under `${XDG_STATE_HOME:-~/.local/state}/youtube-to-command/`.
