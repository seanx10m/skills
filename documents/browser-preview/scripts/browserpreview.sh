#!/bin/bash
# browserpreview — control surface for Browser Preview.
#
# Two things (mirrors talk-to-me's toggle + one-off 'say'):
#   • MODE (sticky, global): when ON, any Markdown file Claude writes is rendered to a
#     branded HTML preview (Claude + brand header, repo/branch badges, Mermaid + tables)
#     and opened in the browser the first time it's seen. Surfaced as 👁 in the statusline.
#   • ONE-OFF: `open <file.md>` renders + opens a single doc now, regardless of mode,
#     and does NOT change the mode. This is the "preview this" verb.
#
# Usage:
#   browserpreview.sh on | off | toggle | status
#   browserpreview.sh open <file.md>     # one-off: render + open now (mode unchanged)
set -uo pipefail

STATE_DIR="$HOME/.claude/skills/browser-preview/state"
FLAG="$STATE_DIR/preview-on"
OPENED_DIR="$STATE_DIR/opened"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# bundled copy first (self-contained on a fresh install), else the shared one
# other skills (rich-artifact) also point at.
if [ -f "$SCRIPT_DIR/mdview.py" ]; then MDVIEW="$SCRIPT_DIR/mdview.py"; else MDVIEW="$HOME/.claude/scripts/mdview.py"; fi
mkdir -p "$STATE_DIR" "$OPENED_DIR"

cmd="${1:-status}"
case "$cmd" in
  on)     : > "$FLAG"; echo "👁 browser preview ON (global)";;
  off)    rm -f "$FLAG"; echo "👁 browser preview OFF";;
  toggle) if [ -f "$FLAG" ]; then rm -f "$FLAG"; echo "👁 browser preview OFF"; else : > "$FLAG"; echo "👁 browser preview ON (global)"; fi;;
  status) if [ -f "$FLAG" ]; then echo "on"; else echo "off"; fi;;
  open)
    f="${2:-}"
    [ -z "$f" ] && { echo "usage: browserpreview.sh open <file.md|folder>"; exit 2; }
    # One-off: render + open, mode unchanged. Output goes to <root>/scratch/.previews/,
    # never next to the source (mirrors the hook). A folder renders every .md under it
    # into one page with a file sidebar.
    if [ -d "$f" ]; then
      ABS="$(cd "$f" && pwd)"; GITDIR="$ABS"
    else
      ABS="$(cd "$(dirname "$f")" 2>/dev/null && pwd)/$(basename "$f")"; GITDIR="$(dirname "$ABS")"
    fi
    ROOT="$(git -C "$GITDIR" rev-parse --show-toplevel 2>/dev/null || echo "$GITDIR")"
    REL="${ABS#"$ROOT"/}"
    if [ "$REL" = "$ABS" ]; then FLAT="root"; else FLAT="$(printf '%s' "${REL%.*}" | sed 's#/#__#g')"; fi
    [ -z "$FLAT" ] && FLAT="root"
    PREVIEW_DIR="$ROOT/scratch/.previews"
    mkdir -p "$PREVIEW_DIR"
    OUT="$PREVIEW_DIR/$FLAT.preview.html"
    python3 "$MDVIEW" "$f" --no-open -o "$OUT" && open "file://$OUT"
    ;;
  *) echo "usage: browserpreview.sh on|off|toggle|status|open <file.md|folder>"; exit 2;;
esac
