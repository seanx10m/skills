#!/usr/bin/env bash
# UserPromptSubmit hook: a new prompt no longer cancels narration - the panel keeps
# speaking whatever is still queued. We only clear `.done` so the reader does not close
# itself mid-stream, and re-seed the watermark at the transcript tip.
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
input=$(cat)
sid=$(printf '%s' "$input" | jq -r '.session_id // empty')
[ -n "$sid" ] || exit 0
# ponytail: keep the live reader alive; dropping .done is the whole fix
QDIR="$BASE/state/queue/$sid"
rm -f "$QDIR/.done" 2>/dev/null || true

# Spool the prompt itself as a ".me.txt" block: the reader renders it as a quote above the
# reply and speaks it in the user's own voice, so an answer keeps its question on screen.
# Only when narration is on for this session - same resolution the other hooks use.
STATE="$BASE/state"
on=0
if   [ -f "$STATE/sessions/$sid.off" ]; then on=0
elif [ -f "$STATE/sessions/$sid" ];     then on=1
elif [ -f "$STATE/narrate-on" ];        then on=1
fi
if [ "$on" = 1 ]; then
  prompt=$(printf '%s' "$input" | jq -r '.prompt // empty')
  # drop hook-injected context blocks; keep only what was actually typed
  prompt=$(printf '%s' "$prompt" | perl -0777 -pe '
    s{<[a-z][a-z0-9-]*>.*?</[a-z][a-z0-9-]*>}{}gs;
    s/\A\s+//; s/\s+\z//; s/\n{3,}/\n\n/g;')
  if [ "${#prompt}" -gt 700 ]; then prompt="${prompt:0:700}..."; fi
  if [ -n "$(printf '%s' "$prompt" | tr -d '[:space:]')" ]; then
    mkdir -p "$QDIR"
    # The harness can fire this hook twice for one submit. A still-unread block with the
    # same text is that double, not a repeated prompt - the reader deletes what it reads.
    dup=0
    for f in "$QDIR"/*.me.txt; do
      [ -f "$f" ] || continue
      [ "$(cat "$f")" = "$prompt" ] && dup=1
    done
    [ "$dup" = 1 ] || printf '%s' "$prompt" > "$QDIR/$(date +%s%N)-0.me.txt"
  fi
fi
transcript=$(printf '%s' "$input" | jq -r '.transcript_path // empty')
if [ -n "$transcript" ] && [ -f "$transcript" ]; then
  mkdir -p "$BASE/state/spoken"
  jq -rs '[ .[] | select(.type=="assistant"
                         and (.message.content | type=="array")
                         and (any(.message.content[]?; .type=="text"))) ]
          | last | .uuid // empty' "$transcript" > "$BASE/state/spoken/$sid" 2>/dev/null || true
fi
exit 0
