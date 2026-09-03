#!/bin/bash
# PostToolUse hook (matcher: Write|Edit|MultiEdit).
# When Browser Preview mode is ON and the edited file is Markdown, render it to a
# branded HTML preview. Open the browser only the FIRST time a given file is seen
# this run (manual-refresh model); later edits silently re-render so Cmd-R shows them.
set -uo pipefail

STATE_DIR="$HOME/.claude/skills/browser-preview/state"
FLAG="$STATE_DIR/preview-on"
OPENED_DIR="$STATE_DIR/opened"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/mdview.py" ]; then MDVIEW="$SCRIPT_DIR/mdview.py"; else MDVIEW="$HOME/.claude/scripts/mdview.py"; fi

[ -f "$FLAG" ] || exit 0          # mode off → do nothing
mkdir -p "$OPENED_DIR"
bash "$SCRIPT_DIR/prune-old.sh" "$OPENED_DIR" 2 &   # rolling 2-day cleanup, don't block the write

INPUT=$(cat)
FP=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty' 2>/dev/null)
[ -z "$FP" ] && exit 0
case "$FP" in
  *.md|*.markdown|*.mdx) ;;
  *) exit 0 ;;
esac
[ -f "$FP" ] || exit 0

# Preview artifacts never sit next to the source. They land in <root>/scratch/.previews/,
# flattened by their path relative to the repo root so same-named files don't collide.
ABS="$(cd "$(dirname "$FP")" 2>/dev/null && pwd)/$(basename "$FP")"
ROOT="$(git -C "$(dirname "$ABS")" rev-parse --show-toplevel 2>/dev/null || dirname "$ABS")"
REL="${ABS#"$ROOT"/}"
FLAT="$(printf '%s' "${REL%.*}" | sed 's#/#__#g')"
PREVIEW_DIR="$ROOT/scratch/.previews"
mkdir -p "$PREVIEW_DIR" 2>/dev/null || exit 0
bash "$SCRIPT_DIR/prune-old.sh" "$PREVIEW_DIR" 2 &
OUT="$PREVIEW_DIR/$FLAT.preview.html"
python3 "$MDVIEW" "$FP" --no-open -o "$OUT" >/dev/null 2>&1 || exit 0

# stable marker per absolute path → open once, then silent re-render
KEY=$(printf '%s' "$FP" | shasum | awk '{print $1}')
MARK="$OPENED_DIR/$KEY"
if [ ! -f "$MARK" ]; then
  : > "$MARK"
  open "file://$OUT" >/dev/null 2>&1 || true
fi
exit 0
