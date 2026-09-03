#!/bin/bash
# ⚡️ notify — native macOS notification when Claude finishes a turn (Stop hook,
# kind="done") or needs the user (Notification hook, kind="attention").
# Gated by a global flag + per-session override. Reads the hook JSON on stdin.
#
# Notification layout (both repo + session title always visible, per spec):
#   title    = "<emoji> <repo>"      done=✅  attention=⚡
#   subtitle = "<session title>"     (Claude's own aiTitle from the transcript)
#   body     = why / status          attention=the message, done="turn complete"
#
# ponytail: osascript = zero-dep native path. Upgrade to terminal-notifier
# (brew install terminal-notifier) if you want click-to-focus-the-terminal.
set -uo pipefail

KIND="${1:-done}"

if [ "$KIND" = "--test" ]; then
  # self-check: fire a sample notification bypassing the enable gate
  KIND="attention"; SID="${CLAUDE_CODE_SESSION_ID:-selftest}"; CWD="$PWD"
  TRANSCRIPT=""; MSG="self-test — if you can read this, notify works"; FORCE=1
else
  INPUT=$(cat)
  SID=$(printf '%s' "$INPUT"        | jq -r '.session_id // empty'     2>/dev/null)
  CWD=$(printf '%s' "$INPUT"        | jq -r '.cwd // empty'            2>/dev/null)
  TRANSCRIPT=$(printf '%s' "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
  MSG=$(printf '%s' "$INPUT"        | jq -r '.message // empty'        2>/dev/null)
  FORCE=0
fi

# --- enable gate: session .off  >  session on  >  global flag ---
NDIR="$HOME/.claude/notify"
if [ "$FORCE" != "1" ]; then
  if   [ -n "$SID" ] && [ -f "$NDIR/sessions/$SID.off" ]; then exit 0
  elif [ -n "$SID" ] && [ -f "$NDIR/sessions/$SID" ];     then :
  elif [ -f "$HOME/.claude/notify-on" ];                  then :
  else exit 0
  fi
fi

# --- repo: org/repo from git remote, else git-toplevel basename, else cwd basename ---
REPO=""
if [ -n "$CWD" ]; then
  URL=$(git -C "$CWD" remote get-url origin 2>/dev/null)
  [ -n "$URL" ] && REPO=$(printf '%s' "$URL" | sed -E 's#\.git$##; s#^.*[:/]([^/]+/[^/]+)$#\1#')
  if [ -z "$REPO" ]; then
    TOP=$(git -C "$CWD" rev-parse --show-toplevel 2>/dev/null)
    REPO=$(basename "${TOP:-$CWD}")
  fi
fi
[ -z "$REPO" ] && REPO="claude"

# --- session title: last ai-title, else last prompt (trimmed), else short sid ---
TITLE=""
if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
  TITLE=$(jq -r 'select(.type=="ai-title") | .aiTitle' "$TRANSCRIPT" 2>/dev/null | tail -1)
  [ -z "$TITLE" ] && TITLE=$(jq -r 'select(.type=="last-prompt") | .lastPrompt' "$TRANSCRIPT" 2>/dev/null | tail -1 | cut -c1-60)
fi
[ -z "$TITLE" ] && TITLE="${SID:0:8}"

# --- compose: title = repo (robot icon already signals "Claude"; no status emoji).
#     subtitle = session title. body = empty on done, the ask on attention. ---
HEAD="$REPO"
if [ "$KIND" = "attention" ]; then
  BODY="⚡ ${MSG:-needs your input}"
else
  BODY=""
fi

# origin terminal (for click-to-focus) — from the inherited TERM_PROGRAM
case "${TERM_PROGRAM:-}" in
  iTerm.app)      TERMBID="com.googlecode.iterm2" ;;
  WarpTerminal)   TERMBID="dev.warp.Warp-Stable" ;;
  Apple_Terminal) TERMBID="com.apple.Terminal" ;;
  vscode)         TERMBID="com.microsoft.VSCode" ;;
  *)              TERMBID="" ;;
esac

# Signed helper app carries the robot icon (only reliable custom-icon path on
# Tahoe; see notify/app/ + [[spend-alert-furnace-icon]]). Clicking the banner
# brings TERMBID's app to the front. Falls back to osascript (generic icon, no
# click action) if the app is missing or not yet authorized.
APP="$HOME/Applications/Claude Notify.app/Contents/MacOS/ClaudeNotify"
if [ -x "$APP" ] && "$APP" "$HEAD" "$TITLE" "$BODY" "$TERMBID" 2>/dev/null; then
  exit 0
fi

# ponytail: fallback — osascript can't carry a custom icon, but still notifies.
# argv-passed strings => no quoting/injection worries from titles with quotes.
osascript \
  -e 'on run argv' \
  -e 'display notification (item 3 of argv) with title (item 1 of argv) subtitle (item 2 of argv)' \
  -e 'end run' \
  "$HEAD" "$TITLE" "$BODY" >/dev/null 2>&1

exit 0
