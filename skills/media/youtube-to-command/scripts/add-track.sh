#!/usr/bin/env bash
# Download a YouTube track as .mp3 and bind a toggle command to it in ~/.zshrc.
#
#   add-track.sh --url URL --tag NAME [--label TEXT] [--dir DIR] [--loop]
#                [--file EXISTING.mp3] [--zshrc FILE] [--force]
#
# Only ever appends/replaces blocks delimited by
#   # >>> youtube-to-command: ... >>>   /   # <<< youtube-to-command: ... <<<
# Everything else in the zshrc is left byte-for-byte alone. A backup is made first.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
url="" tag="" label="" dir="${YT2CMD_DIR:-$HOME/Music/tracks}" loop="-" file="" rc="${ZDOTDIR:-$HOME}/.zshrc" force=0
while [ $# -gt 0 ]; do
  case "$1" in
    --url) url="$2"; shift 2;;
    --tag) tag="$2"; shift 2;;
    --label) label="$2"; shift 2;;
    --dir) dir="$2"; shift 2;;
    --loop) loop="loop"; shift;;
    --file) file="$2"; shift 2;;
    --zshrc) rc="$2"; shift 2;;
    --force) force=1; shift;;
    *) echo "unknown arg: $1" >&2; exit 64;;
  esac
done
[ -n "$tag" ] || { echo "--tag is required" >&2; exit 64; }
[ -n "$url" ] || [ -n "$file" ] || { echo "need --url or --file" >&2; exit 64; }
[[ "$tag" =~ ^[a-z][a-z0-9_-]*$ ]] || { echo "tag must match ^[a-z][a-z0-9_-]*\$" >&2; exit 64; }
[ -n "$label" ] || label="$tag"

for t in ffprobe zsh; do command -v "$t" >/dev/null || { echo "missing: $t" >&2; exit 1; }; done
command -v sox >/dev/null || echo "warning: sox not found - the command needs it to play (brew install sox)" >&2

# Refuse to shadow a real command unless it is our own block or --force.
if [ "$force" -eq 0 ] && ! grep -qF "# >>> youtube-to-command: $tag >>>" "$rc" 2>/dev/null; then
  if zsh -fc "whence -w -- '$tag' >/dev/null 2>&1"; then
    echo "'$tag' is already a command on this system; pick another tag or pass --force" >&2; exit 1
  fi
fi

# 1. Download (inlined yt-dlp step)
if [ -z "$file" ]; then
  for t in yt-dlp ffmpeg; do command -v "$t" >/dev/null || { echo "missing: $t (brew install yt-dlp ffmpeg)" >&2; exit 1; }; done
  mkdir -p "$dir"
  ladder=("" "youtube:player_client=web_safari,ios,tv" "youtube:player_client=web,mweb")
  file=""
  for ea in "${ladder[@]}"; do
    args=(-x --audio-format mp3 --audio-quality 2 --no-playlist -o "$dir/%(title)s.%(ext)s" --print after_move:filepath --no-simulate)
    [ -n "$ea" ] && args+=(--extractor-args "$ea")
    if out="$(yt-dlp "${args[@]}" "$url" 2>/dev/null | tail -1)" && [ -f "$out" ]; then file="$out"; break; fi
  done
  [ -n "$file" ] || { echo "download failed on every player client; try 'yt-dlp -U' or --cookies-from-browser" >&2; exit 1; }
fi
[ -f "$file" ] || { echo "no such file: $file" >&2; exit 1; }
xattr -c "$file" 2>/dev/null || true   # clear macOS quarantine (no-op elsewhere)

# 2. Duration
secs="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$file")"
secs="${secs%.*}"
mmss="$(printf '%d:%02d' $((secs/60)) $((secs%60)))"

# 3. Write delimited blocks into the zshrc
shq() { local q="'\\''"; printf "'%s'" "${1//\'/$q}"; }
path_expr="$(shq "$file")"
case "$file" in "$HOME"/*) path_expr="\"\$HOME\"$(shq "${file#"$HOME"}")";; esac

touch "$rc"
cp "$rc" "$rc.bak-youtube-to-command"

replace_block() { # name, body
  local name="$1" body="$2" tmp
  tmp="$(mktemp)"
  awk -v s="# >>> youtube-to-command: $name >>>" -v e="# <<< youtube-to-command: $name <<<" \
    '$0==s{skip=1} !skip{print} $0==e{skip=0}' "$rc" > "$tmp"
  { cat "$tmp"; printf '\n# >>> youtube-to-command: %s >>>\n%s\n# <<< youtube-to-command: %s <<<\n' "$name" "$body" "$name"; } > "$rc"
  rm -f "$tmp"
}

replace_block core "$(cat "$here/core.zsh")"
replace_block "$tag" "$(printf '# %s: toggle | %s 0-9 volume | %s p pause/resume | %s next|prev [mins]\n%s() { _yt2cmd %s %s %s %s %s %s "$*"; }' \
  "$label" "$tag" "$tag" "$tag" "$tag" "$(shq "$tag")" "$(shq "$label")" "$path_expr" "$secs" "$(shq "$mmss")" "$loop")"

if ! zsh -n "$rc"; then
  echo "syntax error in $rc - restoring backup" >&2
  cp "$rc.bak-youtube-to-command" "$rc"; exit 1
fi
echo "file: $file"
echo "command: $tag  ($mmss)  - open a new terminal or run: source $rc"
echo "backup: $rc.bak-youtube-to-command"
