#!/bin/bash
# Status-line wrapper: runs your previous status line command (saved by install.sh to
# state/base-statusline, if you had one), then appends the session name and any pinned note
# (~/.claude/statusline-notes/<session-id> or .../global).
set -uo pipefail

INPUT=$(cat)

# base line from the status line that was configured before install
BASE=""
BASEFILE="$HOME/.claude/skills/talk-to-me/state/base-statusline"
if [ -s "$BASEFILE" ]; then
  BASE=$(printf '%s' "$INPUT" | bash -c "$(cat "$BASEFILE")" 2>/dev/null)
fi

SID=$(printf '%s' "$INPUT" | jq -r '.session_id // empty' 2>/dev/null)

# --- Agent address: this session's name (~/.claude/sessions/<pid>.json) ---
addr=""
if [ -n "$SID" ]; then
  name=$(jq -rs --arg sid "$SID" '[.[] | select(.sessionId==$sid) | .name] | last // empty' "$HOME/.claude/sessions/"*.json 2>/dev/null)
  [ -n "$name" ] && addr=" 🏷 $name"
fi

# --- /note: free-text line pinned by you (per-session wins, else global) ---
ND="$HOME/.claude/statusline-notes"
note=""
if [ -n "$SID" ] && [ -s "$ND/$SID" ]; then
  note=$(head -c 300 "$ND/$SID")
elif [ -s "$ND/global" ]; then
  note=$(head -c 300 "$ND/global")
fi

printf '%s%s' "$BASE" "$addr"
if [ -n "$note" ]; then
  # wrap: Claude Code truncates each line instead of wrapping, so fold it ourselves
  W=$( { tput cols < /dev/tty; } 2>/dev/null ) || W=""
  [ -z "$W" ] && W=${COLUMNS:-100}
  printf '%s' "$note" | fold -s -w $((W - 4)) | while IFS= read -r l || [ -n "$l" ]; do
    printf '\n\033[2m▏\033[0m %s' "$l"
  done
fi
exit 0
