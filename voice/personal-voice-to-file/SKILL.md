---
name: personal-voice-to-file
description: Render macOS Personal Voice (or any system TTS voice) speech into a real audio (m4a) file instead of just playing it live. Use when the user asks to record, save, export, or turn into an audio file something spoken in their Personal Voice, or a Morgan-Freeman-style / cloned voice, or a talk script / narration file.
---

# Personal Voice → file

## Why this isn't a one-liner

Apple deliberately blocks `AVSpeechSynthesizer`'s offline `write(_:toBufferCallback:)`
API for Personal Voices — the callback never fires (confirmed: ordinary system
voices export fine with the same code; only Personal Voice hangs). Signing,
codesigning, and app-bundling do not change this. See NOTES.md for the full
investigation.

The only working path: play the voice live through **BlackHole** (a virtual
loopback audio device) instead of speakers, and capture that stream with ffmpeg.

## One-time setup (per machine)

```bash
brew install blackhole-2ch switchaudio-osx
# BlackHole's installer needs an interactive sudo password — user must run this themselves:
sudo installer -pkg "$(brew --cache blackhole-2ch)" -target /
# Then either reboot, or try this first (sometimes enough, briefly cuts system audio):
sudo killall coreaudiod
```

Verify it worked: `SwitchAudioSource -a -t output` should list `BlackHole 2ch`.

## Recording

```bash
scripts/record.sh <output.m4a> <voice-name-or-auto> <rate-multiplier> [text-file]
```

- `voice-name-or-auto`: substring match against installed Personal Voices (e.g. `morgan`), or `auto`.
- `rate-multiplier`: `1.0` = normal Apple speaking rate. `talk-to-me`'s shared default is `1.25` — ask the user which they want, don't assume.
- `text-file`: optional; omit to read text from stdin.

The script: switches system audio output to BlackHole, records via `ffmpeg -f avfoundation`,
runs `personal-say` (from the `talk-to-me` skill) with the given voice/rate, stops the
capture, **always restores the original output device** (even on failure, via a trap),
and transcodes the WAV to an AAC-in-MP4 file.

For long scripts (talk tracks, narration): strip markdown headers, stage directions
in brackets, and horizontal rules before piping the text in — `personal-say` speaks
raw text verbatim, punctuation and all.

## Gotchas

- If `SwitchAudioSource -c` isn't "the device you expect" before you start, note it —
  the trap restores to whatever was captured at start, not a hardcoded default.
- Homebrew sometimes purges the downloaded `.pkg` from `Caskroom/` after a failed
  install attempt. If the installer path 404s, re-run `brew install blackhole-2ch`
  (or `brew fetch`) and use the path it reports, or check `~/Library/Caches/Homebrew/downloads/`.
- `ffmpeg -f avfoundation -list_devices true -i ""` re-numbers devices per machine —
  don't hardcode `:0` for BlackHole; `record.sh` looks it up by name each run.
- **`talk-to-me`'s Stop hook will kill your recording mid-sentence.** `speak-response.sh`
  runs a global `pkill -x personal-say` so a new response interrupts old narration — and
  it is not scoped to a session, so *any* Claude Code session ending a turn silently
  SIGTERMs the `personal-say` your capture is driving. The recording just stops
  (exit 143, `Terminated: 15`). Turning narration off does not help: other sessions still
  fire the hook. Fix: copy `personal-say` to a different filename (e.g. `rec-say`) and run
  the capture through that — `pkill -x` matches the exact process name, so a renamed copy
  is invisible to it. Turn this session's narration off too, or your own narration gets
  captured into the file.
- **A long dialogue needs its own long settle times.** BlackHole becoming the default
  output does not propagate to CoreAudio instantly; give it ~3s before starting ffmpeg
  and ~2s after, or `personal-say` renders to the *old* device and you capture pure
  silence. This failure is intermittent, which makes it read like a BlackHole problem
  when it is really a race.
- **Don't inline the device lookup as a pipe into `head`.** Under `set -o pipefail`,
  `head` closing early sends ffmpeg SIGPIPE and aborts the script with exit 251 and no
  output. Capture the device list into a variable first — `record.sh` already does this
  and says why.

## Rate: the single biggest quality lever

`TALKTOME_RATE` is a multiplier on Apple's default, and Apple's default is already brisk.
Anything at or above `1.15` makes Personal Voice **slur words together and emit click
artifacts** — it sounds exactly like overlapping speech layered over a ticking background,
which invites a long and wrong hunt through BlackHole, sample rates, and dropped buffers.
Measured on this machine: `1.15` → ~277 wpm (unintelligible), `0.92` → ~197 wpm (clean).

**For anything a human will actually sit and listen to, use `0.9`–`1.0`.** `talk-to-me`'s
1.25 default is tuned for skimming live narration, not for a recorded file.

Verify a finished file rather than trusting it — decode to mono and check three things:
the count of >0.7s silences matches the number of turns, words-per-minute is under ~210,
and the loudest sample *inside* a turn gap is 0 (real ticking shows up there; speech
plosives do not).
