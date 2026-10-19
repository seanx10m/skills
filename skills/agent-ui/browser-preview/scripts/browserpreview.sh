#!/bin/bash
# browserpreview - control surface for Browser Preview.
#
# Two things:
#   • MODE (sticky, global): when ON, any Markdown file Claude writes is rendered to a
#     HTML preview (header with repo/branch badges, Mermaid + tables)
#     and opened in the browser the first time it's seen (needs the optional PostToolUse hook).
#   • ONE-OFF: `open <file.md>` renders + opens a single doc now, regardless of mode,
#     and does NOT change the mode. This is the "preview this" verb.
#
# Usage:
#   browserpreview.sh on | off | toggle | status
#   browserpreview.sh open <file.md>     # one-off: render + open now (mode unchanged)
#   browserpreview.sh live <file.md>     # same page served over http: mermaid fences
#                                        # become editable Excalidraw canvases, and every
#                                        # comment streams to <doc>.notes.md + .notes.jsonl
#   browserpreview.sh listen <file.md>   # print each new comment on a live doc, one line each
#   browserpreview.sh wpm [n]            # default speed-reader speed (blank = show,
#                                        # 'rec' = back to the 250 wpm default)
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_DIR="$SCRIPT_DIR/../state"
FLAG="$STATE_DIR/preview-on"
OPENED_DIR="$STATE_DIR/opened"
MDVIEW="$SCRIPT_DIR/mdview.py"
# Optional: `live` / `listen` need a separate live-server script (not bundled).
# Point BP_LIVE_SERVER at it to enable them.
LIVE_SERVER="${BP_LIVE_SERVER:-}"
need_live() { [ -n "$LIVE_SERVER" ] && [ -f "$LIVE_SERVER" ] || { echo "live/listen need the optional live server; set BP_LIVE_SERVER=/path/to/server.py" >&2; exit 3; }; }
mkdir -p "$STATE_DIR" "$OPENED_DIR"

cmd="${1:-status}"
case "$cmd" in
  on)     : > "$FLAG"; echo "👁 browser preview ON (global)";;
  off)    rm -f "$FLAG"; echo "👁 browser preview OFF";;
  toggle) if [ -f "$FLAG" ]; then rm -f "$FLAG"; echo "👁 browser preview OFF"; else : > "$FLAG"; echo "👁 browser preview ON (global)"; fi;;
  status) if [ -f "$FLAG" ]; then echo "on"; else echo "off"; fi;;
  wpm)
    # The speed reader's default words-per-minute. Empty file / unset = 250, which
    # is average adult silent reading speed; the page offers 400 as an explicit
    # "fast pass" preset. Whatever the reader last dragged the slider to in that
    # browser (localStorage) still wins over this.
    WPMF="$STATE_DIR/speedread-wpm"
    n="${2:-}"
    if [ -z "$n" ]; then
      if [ -s "$WPMF" ]; then echo "$(cat "$WPMF") wpm (your default)"; else echo "250 wpm (default)"; fi
    elif [ "$n" = "rec" ] || [ "$n" = "reset" ]; then
      rm -f "$WPMF"; echo "speed reader default → 250 wpm"
    elif [ "$n" -ge 150 ] 2>/dev/null && [ "$n" -le 800 ]; then
      printf '%s' "$n" > "$WPMF"; echo "speed reader default → $n wpm"
    else
      echo "usage: browserpreview.sh wpm [150-800|rec]"; exit 2
    fi
    ;;
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
  live)
    # Same page, served over http instead of file:// - which is the whole difference:
    # an origin means every ```mermaid fence becomes an editable Excalidraw canvas
    # that autosaves to ./diagrams/<name>.excalidraw. Blocks; ctrl-c to stop.
    f="${2:-}"
    [ -z "$f" ] && { echo "usage: browserpreview.sh live <file.md|folder>"; exit 2; }
    shift 2
    need_live
    exec python3 "$LIVE_SERVER" serve "$f" --doc "$@"
    ;;
  listen)
    # Live mode streams every comment to <doc>.notes.jsonl; this prints each new one as a
    # single line (comment / reply / delete), for a Monitor or a background poll. --all
    # replays the ones already there first.
    f="${2:-}"
    [ -z "$f" ] && { echo "usage: browserpreview.sh listen <file.md|folder> [--all]"; exit 2; }
    shift 2
    need_live
    exec python3 "$LIVE_SERVER" listen "$f" "$@"
    ;;
  *) echo "usage: browserpreview.sh on|off|toggle|status|wpm [n]|open <file.md|folder>|live <file.md|folder>|listen <file.md|folder>"; exit 2;;
esac
