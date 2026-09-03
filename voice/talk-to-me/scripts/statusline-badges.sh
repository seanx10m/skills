#!/bin/bash
# Status-line wrapper: runs the context-guardian statusline (which renders claude-hud),
# then appends mode badges:
#   🗣 <voice>  when Talk to Me narration is on (global flag OR this session's flag)
#   🦴 CAVE     when caveman mode is on (~/.claude/caveman-on, maintained by /caveman)
set -uo pipefail

INPUT=$(cat)

# base line from the existing statusline (claude-hud)
BASE=$(printf '%s' "$INPUT" | bash "$HOME/.claude/skills/context-guardian/scripts/statusline.sh" 2>/dev/null)

SID=$(printf '%s' "$INPUT" | jq -r '.session_id // empty' 2>/dev/null)

# --- Talk to Me: always show on/off ---
# Resolution: an explicit per-session marker wins, else fall back to the global default.
# (An explicit session OFF reads as off even when the global flag is on.)
TT="$HOME/.claude/skills/talk-to-me/state"
if [ -n "$SID" ] && [ -f "$TT/sessions/$SID.off" ]; then
  talk=" 🗣 off"
elif [ -n "$SID" ] && [ -f "$TT/sessions/$SID" ]; then
  talk=" 🗣 on"
elif [ -f "$TT/narrate-on" ]; then
  talk=" 🗣 on"
else
  talk=" 🗣 off"
fi

# --- Caveman: always show on/off ---
if [ -f "$HOME/.claude/caveman-on" ] || { [ -n "$SID" ] && [ -f "$HOME/.claude/caveman/sessions/$SID" ]; }; then
  cave=" 🦴 on"
else
  cave=" 🦴 off"
fi

# --- Bullet: short-reply mode (global ~/.claude/bullet-on OR per-session) ---
if [ -f "$HOME/.claude/bullet-on" ] || { [ -n "$SID" ] && [ -f "$HOME/.claude/bullet/sessions/$SID" ]; }; then
  bullet=" 🔹 on"
else
  bullet=" 🔹 off"
fi

# --- Browser preview: global eyeball toggle ---
if [ -f "$HOME/.claude/skills/browser-preview/state/preview-on" ]; then
  doc=" 👁 on"
else
  doc=" 👁 off"
fi

# --- Multitask: per-session parallel-subagents toggle (~/.claude/multitask/sessions/$SID, maintained by /multitask) ---
# Off by default; a marker exists only for the session that ran /multitask, so it never leaks across sessions.
if [ -n "$SID" ] && [ -f "$HOME/.claude/multitask/sessions/$SID" ]; then
  multi=" 👥 on"
else
  multi=" 👥 off"
fi

# --- Loop pre-flight: per-session launch-gate toggle (~/.claude/loop-pre-flight/sessions/$SID, maintained by /loop-pre-flight) ---
# Off by default; marker exists only for the session that turned it on, so it never leaks across sessions.
if [ -n "$SID" ] && [ -f "$HOME/.claude/loop-pre-flight/sessions/$SID" ]; then
  preflight=" ✈️ on"
else
  preflight=" ✈️ off"
fi

# --- Dream outcome: session OFF override > session ON > global flag (~/.claude/dream-outcome-on) ---
if [ -n "$SID" ] && [ -f "$HOME/.claude/dream-outcome/sessions/$SID.off" ]; then
  dream=" 🏝️ off"
elif [ -n "$SID" ] && [ -f "$HOME/.claude/dream-outcome/sessions/$SID" ]; then
  dream=" 🏝️ on"
elif [ -f "$HOME/.claude/dream-outcome-on" ]; then
  dream=" 🏝️ on"
else
  dream=" 🏝️ off"
fi

# --- Notify: 4-way mode over sound + banner. banner = session OFF > session ON > global. ---
if [ -n "$SID" ] && [ -f "$HOME/.claude/notify/sessions/$SID.off" ]; then
  b=0
elif [ -n "$SID" ] && [ -f "$HOME/.claude/notify/sessions/$SID" ]; then
  b=1
elif [ -f "$HOME/.claude/notify-on" ]; then
  b=1
else
  b=0
fi
[ -f "$HOME/.claude/sound-on" ] && s=1 || s=0
if   [ "$s" = 1 ] && [ "$b" = 1 ]; then notify=" 🤖 both"
elif [ "$s" = 1 ];                 then notify=" 🤖 sound"
elif [ "$b" = 1 ];                 then notify=" 🤖 banner"
else                                    notify=" 🤖 off"
fi

# --- Ponytail: lazy-mode level (~/.claude/.ponytail-active holds full|lite|ultra; absent = off) ---
PT="$HOME/.claude/.ponytail-active"
if [ -s "$PT" ]; then
  pony=" 🥱 $(tr -d '[:space:]' < "$PT")"
else
  pony=" 🥱 off"
fi

# --- /note: free-text line pinned by the user (per-session wins, else global) ---
ND="$HOME/.claude/statusline-notes"
note=""
if [ -n "$SID" ] && [ -s "$ND/$SID" ]; then
  note=$(head -c 300 "$ND/$SID")
elif [ -s "$ND/global" ]; then
  note=$(head -c 300 "$ND/global")
fi

printf '%s%s%s%s%s%s%s%s%s%s' "$BASE" "$talk" "$cave" "$bullet" "$doc" "$multi" "$preflight" "$dream" "$notify" "$pony"
if [ -n "$note" ]; then
  # wrap: Claude Code truncates each line instead of wrapping, so fold it ourselves
  W=$( { tput cols < /dev/tty; } 2>/dev/null ) || W=""
  [ -z "$W" ] && W=${COLUMNS:-100}
  printf '%s' "$note" | fold -s -w $((W - 4)) | while IFS= read -r l || [ -n "$l" ]; do
    printf '\n\033[2m▏\033[0m %s' "$l"
  done
fi
exit 0
