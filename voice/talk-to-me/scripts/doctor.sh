#!/usr/bin/env bash
# Is the terminal tap actually working? Answers in one screen.
TOO="$HOME/.claude/skills/talk-to-me"
ok(){ printf '  OK    %s\n' "$1"; }; bad(){ printf '  BROKEN %s\n' "$1"; }
echo "talk-to-me doctor"
[ -x "$TOO/.venv/bin/python" ] && ok "python env" || bad "python env - run: python3 -m venv $TOO/.venv"
"$TOO/.venv/bin/python" -c 'import pyte' 2>/dev/null && ok "screen model (pyte)" || bad "pyte - run: $TOO/.venv/bin/pip install pyte"
[ -x "$TOO/scripts/talk-reader-live" ] && ok "live panel binary" || bad "panel binary - run: bash $TOO/scripts/build.sh"
[ -x "$HOME/.claude/skills/talk-to-me/scripts/personal-say" ] && ok "voice engine" || bad "voice engine (talk-to-me not installed)"
if [ -n "${TALKTOME_TAP_SPOOL:-}" ]; then
  ok "tap ATTACHED to this session"
  b="$TALKTOME_TAP_SPOOL/.beat"
  if [ -f "$b" ]; then
    echo "        heartbeat $(( $(date +%s) - $(stat -f %m "$b") ))s old (under 15s = hooks stood down)"
  else
    bad "no heartbeat yet - tap started but has not scanned"
  fi
else
  echo "  NOTE  tap NOT attached - this session was started as plain 'claude'."
  echo "        per-sentence speech needs: $TOO/scripts/claude-talk"
fi
echo "  panel processes running: $(pgrep -x talk-reader-live | wc -l | tr -d ' ')"
