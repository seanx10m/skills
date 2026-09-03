#!/bin/bash
# pdslides — render one Markdown file as a progressive-disclosure deck and open it.
#
# Deck mode is a flag on the browser-preview renderer, not a second renderer: the
# slide face, the "More detail" drawer, the comment rail and the copy buttons are
# all the same machine. One-shot only, no sticky mode.
#
#   pdslides.sh <deck.md> [paper.md] [-o out.html]
set -uo pipefail

f="${1:-}"
[ -z "$f" ] && { echo "usage: pdslides.sh <deck.md> [paper.md]"; exit 2; }
[ -f "$f" ] || { echo "not found: $f"; exit 1; }
shift
PAPER=()
if [ $# -gt 0 ] && [ -f "$1" ]; then
  PAPER=(--paper "$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"); shift
fi

MDVIEW="$HOME/.claude/skills/browser-preview/scripts/mdview.py"
[ -f "$MDVIEW" ] || { echo "pd-slides needs the browser-preview skill (missing $MDVIEW)"; exit 1; }

ABS="$(cd "$(dirname "$f")" && pwd)/$(basename "$f")"
ROOT="$(git -C "$(dirname "$ABS")" rev-parse --show-toplevel 2>/dev/null || dirname "$ABS")"
REL="${ABS#"$ROOT"/}"
if [ "$REL" = "$ABS" ]; then FLAT="$(basename "${ABS%.*}")"; else FLAT="$(printf '%s' "${REL%.*}" | sed 's#/#__#g')"; fi
PREVIEW_DIR="$ROOT/scratch/.previews"
mkdir -p "$PREVIEW_DIR"
bash "$HOME/.claude/skills/browser-preview/scripts/prune-old.sh" "$PREVIEW_DIR" 2 &   # rolling 2-day cleanup
OUT="$PREVIEW_DIR/$FLAT.deck.html"

NOOPEN=0
REST=()
for a in "$@"; do if [ "$a" = "--no-open" ]; then NOOPEN=1; else REST+=("$a"); fi; done

python3 "$MDVIEW" "$ABS" --deck "${PAPER[@]}" --no-open -o "$OUT" ${REST+"${REST[@]}"} >/dev/null \
  && { echo "$OUT"; [ "$NOOPEN" = 1 ] || open "file://$OUT"; }
