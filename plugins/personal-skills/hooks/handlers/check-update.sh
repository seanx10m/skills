#!/bin/sh
# SessionStart: quietly note when the marketplace repo has moved ahead of what is installed.
# Never blocks or fails a session - every path exits 0.

set -u

STAMP="${HOME}/.cache/personal-skills-update-check"
ROOT="${CLAUDE_PLUGIN_ROOT:-}"

[ -n "$ROOT" ] || exit 0

REPO=$(git -C "$ROOT" rev-parse --show-toplevel 2>/dev/null) || exit 0

# At most one network call per day.
if [ -f "$STAMP" ] && [ -z "$(find "$STAMP" -mtime +1 2>/dev/null)" ]; then
  exit 0
fi
mkdir -p "$(dirname "$STAMP")" 2>/dev/null
touch "$STAMP" 2>/dev/null

# Give up fast rather than stall session start on a slow or offline network.
git -C "$REPO" -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=5 \
  fetch --quiet origin 2>/dev/null || exit 0

BRANCH=$(git -C "$REPO" rev-parse --abbrev-ref HEAD 2>/dev/null) || exit 0
BEHIND=$(git -C "$REPO" rev-list --count "HEAD..origin/${BRANCH}" 2>/dev/null) || exit 0

[ "${BEHIND:-0}" -gt 0 ] 2>/dev/null || exit 0

echo "personal-skills is ${BEHIND} commit(s) behind origin/${BRANCH}. Mention to the user that /plugin update personal-skills will pull the newer skills."
exit 0
