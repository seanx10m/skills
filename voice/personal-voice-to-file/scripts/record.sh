#!/usr/bin/env bash
# record.sh — render macOS Personal Voice speech to a real audio (m4a) file.
#
# Personal Voice cannot be exported via AVSpeechSynthesizer's offline write()
# API (Apple blocks it deliberately — verified 2026-07-07, see NOTES.md).
# The only way to get it into a file is to route live playback through a
# loopback audio device (BlackHole) and capture that with ffmpeg.
#
# Usage:
#   record.sh <output.m4a> <voice-name-or-auto> <rate-multiplier> [text-file]
#   echo "some text" | record.sh out.m4a morgan 1.0
#
# Requires (one-time, see SKILL.md):
#   brew install blackhole-2ch switchaudio-osx
#   sudo installer -pkg <blackhole .pkg> -target /   (interactive, needs sudo password)
#   sudo killall coreaudiod   (or reboot) so BlackHole appears as a device
set -euo pipefail

OUT="${1:?usage: record.sh <output.m4a> <voice> <rate> [text-file]}"
VOICE="${2:-auto}"
RATE="${3:-1.0}"
TEXTFILE="${4:-}"

PERSONAL_SAY="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../talk-to-me/scripts" && pwd)/personal-say"
WORKDIR="$(mktemp -d)"
WAV="$WORKDIR/capture.wav"

if ! command -v SwitchAudioSource >/dev/null || ! command -v ffmpeg >/dev/null; then
    echo "record.sh: needs SwitchAudioSource (switchaudio-osx) and ffmpeg on PATH" >&2
    exit 1
fi

if ! SwitchAudioSource -a -t output | grep -qx "BlackHole 2ch"; then
    echo "record.sh: 'BlackHole 2ch' is not a visible output device." >&2
    echo "  Run: brew install blackhole-2ch switchaudio-osx" >&2
    echo "  Then: sudo installer -pkg <the .pkg from brew's cache> -target /" >&2
    echo "  Then: sudo killall coreaudiod   (or reboot)" >&2
    exit 1
fi

# Capture the device list into a var first: piping ffmpeg straight into
# grep|head sends ffmpeg SIGPIPE when head closes early, and under
# `set -o pipefail` that aborted the whole script (exit 251) before recording.
DEVICE_LIST="$(ffmpeg -f avfoundation -list_devices true -i "" 2>&1 || true)"
BH_INDEX="$(printf '%s\n' "$DEVICE_LIST" | grep "BlackHole 2ch" | grep -oE '\[[0-9]+\]' | head -1 | tr -d '[]')"

ORIG_DEVICE="$(SwitchAudioSource -c)"
trap 'SwitchAudioSource -s "$ORIG_DEVICE"' EXIT

SwitchAudioSource -s "BlackHole 2ch"
sleep 0.5

ffmpeg -f avfoundation -i ":$BH_INDEX" -y "$WAV" >"$WORKDIR/ffmpeg.log" 2>&1 &
FFPID=$!
sleep 1

if [ -n "$TEXTFILE" ]; then
    TALKTOME_VOICE="$VOICE" TALKTOME_RATE="$RATE" "$PERSONAL_SAY" < "$TEXTFILE"
else
    TALKTOME_VOICE="$VOICE" TALKTOME_RATE="$RATE" "$PERSONAL_SAY"
fi

sleep 1
kill -INT "$FFPID" 2>/dev/null || true
wait "$FFPID" 2>/dev/null || true

ffmpeg -i "$WAV" -c:a aac -b:a 192k -y "$OUT"
rm -rf "$WORKDIR"

echo "wrote $OUT"
