---
name: youtube-to-command
description: Download a YouTube track as an .mp3 and bind it to a named zsh command that toggles playback on and off, with a volume digit, pause/resume, skip, and resume-at-position. Self-contained (yt-dlp + ffmpeg + sox); appends clearly delimited blocks to ~/.zshrc and touches nothing else. Use when the user says "make a terminal command that plays this", "give me a `foo` command for this song", "bind playing to the command X", or asks to turn a song into a shell command.
---

# YouTube to Command

One script does both halves: download the audio, then register a toggle function in `~/.zshrc`.

```bash
~/.claude/skills/youtube-to-command/scripts/add-track.sh \
  --url "<URL>" --tag mysong --label "my song" [--dir DIR] [--loop]
```

## What to pick first

- **tag** - the command name (`^[a-z][a-z0-9_-]*$`), e.g. `mysong`. The script refuses a name that already exists as a command unless `--force`.
- **label** - what gets echoed, e.g. `my song`. Defaults to the tag.
- **--dir** - where the mp3 lives. Default `~/Music/tracks` (or `$YT2CMD_DIR`). Do not use the Desktop: the command depends on this file long-term.
- **--loop** - for ambient tracks (noise, rain). Looping tracks restart from 0 on volume change and ignore `next`/`prev`.
- **--file** - skip the download and bind an mp3 you already have.

## What the script does

1. **Download** with yt-dlp (`-x --audio-format mp3 --audio-quality 2 --no-playlist`), walking the 403 fallback ladder (default client, then `web_safari,ios,tv`, then `web,mweb`). `--no-playlist` matters: radio/mix links carry `&list=` and would otherwise pull the whole queue.
2. Clears the macOS quarantine flag (`xattr -c`) so Gatekeeper does not offer to trash the file.
3. Reads the duration with ffprobe.
4. **Edits `~/.zshrc`** (or `$ZDOTDIR/.zshrc`, or `--zshrc FILE`), only by writing blocks between markers:

   ```zsh
   # >>> youtube-to-command: core >>>      shared player, written once, refreshed on re-run
   # <<< youtube-to-command: core <<<
   # >>> youtube-to-command: <tag> >>>      one small function per command
   # <<< youtube-to-command: <tag> <<<
   ```

   Anything outside those markers is left untouched. A backup is saved as `.zshrc.bak-youtube-to-command`, and the file is syntax-checked with `zsh -n`; on failure the backup is restored. Re-running with the same tag replaces just that tag's block.
5. Prints the command name. Tell the user to open a new terminal or `source ~/.zshrc`.

## Resulting command

```
mysong         toggle on/off
mysong 0-9     volume 10%-100% (keeps position if playing; starts it if stopped)
mysong p       pause / resume at the same spot
mysong next|prev [mins]   skip forward/back (default 3 min)
```

Volume persists in `${XDG_STATE_HOME:-~/.local/state}/youtube-to-command/<tag>.vol`.
A missing file errors loudly instead of silently "playing" nothing.

## Removing a command

Delete the lines between its `# >>> youtube-to-command: <tag> >>>` and `# <<< ... <<<` markers.
The `core` block can go once no tag blocks remain.

## Verify

```bash
zsh -n ~/.zshrc && echo SYNTAX OK
zsh -ic '<tag> 2; sleep 2; <tag>'   # starts, then the bare call stops it
```

## Gotchas

- Needs `sox` (`play`) on PATH, not just ffmpeg: `brew install sox`. It plays MP3 natively with `trim` (resume) and `repeat` (loop); sox cannot read AAC, which is why the file is mp3, not m4a.
- If a command reports a missing file, check `~/.Trash` first (Gatekeeper's prompt only offers "Move to Trash"), then move it back and `xattr -c` it.
- YouTube titles turn `:` and `|` into fullwidth `：` and `｜`. The script quotes paths safely; when running manual commands, copy the real filename from `ls`.
- Run `yt-dlp -U` / `brew upgrade yt-dlp` if every client in the ladder fails.
