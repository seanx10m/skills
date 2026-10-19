#!/usr/bin/env bash
# Usage: transcript.sh <youtube-url> [out-dir]
# Pulls YouTube's own captions (no API key) and writes clean plain text.
set -euo pipefail
url="${1:?usage: transcript.sh <youtube-url> [out-dir]}"
out="${2:-${YT_TRANSCRIPT_DIR:-$HOME/Downloads}}"
mkdir -p "$out"
command -v yt-dlp >/dev/null || { echo "yt-dlp not found (brew install yt-dlp)" >&2; exit 1; }
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT

# No --cookies-from-browser: on macOS it reads the browser key from the Keychain,
# which pops a prompt on every call. A 429 here is transient rate limiting - wait and retry.
# en-orig = auto captions in the original language, untranslated; fall back to any English.
for langs in "en-orig" "en.*"; do
  yt-dlp --skip-download --write-subs --write-auto-subs \
    --sub-langs "$langs" --sub-format vtt -o "$tmp/%(title)s.%(ext)s" "$url" >/dev/null 2>&1 || true
  vtt="$(ls "$tmp"/*.vtt 2>/dev/null | head -1 || true)"
  [ -n "$vtt" ] && break
done
[ -n "${vtt:-}" ] || { echo "NO_CAPTIONS: video has no English captions - transcribe the audio locally instead (e.g. whisper.cpp)" >&2; exit 2; }

title="$(basename "$vtt" | sed -E 's/\.[^.]+\.vtt$//')"
dest="$out/$title.txt"
# Drop VTT header/timestamps/inline tags; auto-captions repeat each line, so dedupe.
sed -E '/^(WEBVTT|Kind:|Language:|[0-9:.]+ -->|[[:space:]]*$)/d; s/<[^>]*>//g' "$vtt" \
  | awk '!seen[$0]++' | tr '\n' ' ' | sed -E 's/  +/ /g; s/^ //' | fold -s -w 100 > "$dest"
echo "$dest"
