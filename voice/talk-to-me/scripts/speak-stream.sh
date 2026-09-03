#!/usr/bin/env bash
# Streaming narration hook: speaks each assistant text block as it lands.
# Fires on BOTH PreToolUse and Stop. Speaks every assistant text block as soon as it
# lands in the transcript, instead of only the last one at end of turn.
#
# Owns the spoken-watermark and the per-session speech queue; voice, rate, face and the
# on/off state are the shared skill state next door.

set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE="$BASE/state"
TSTATE="$STATE"
SESSDIR="$STATE/sessions"
SESSCFG="$STATE/sessions-cfg"

input=$(cat)
sid=$(printf '%s' "$input" | jq -r '.session_id // empty')

# subagents share the parent transcript path; narrating them would double-speak
printf '%s' "$input" | jq -e '.agent_id // .agent_type' >/dev/null 2>&1 && exit 0

# on/off resolution: identical to talk-to-me, so /talk-to-me on|off still controls this
on=0
if   [ -n "$sid" ] && [ -f "$SESSDIR/$sid.off" ]; then on=0
elif [ -n "$sid" ] && [ -f "$SESSDIR/$sid"     ]; then on=1
elif [ -f "$STATE/narrate-on" ];                   then on=1
fi
[ "$on" = 1 ] || exit 0

# window on (default) -> the LIVE karaoke panel: one long-lived reader per session that is
# fed from the spool. window off -> audio-only, a fresh personal-say per block.
WINDOW=$(cat "$STATE/window" 2>/dev/null || echo on)
if [ "$WINDOW" = "off" ]; then BIN="$BASE/scripts/personal-say"; else BIN="$BASE/scripts/talk-reader-live"; fi
BIN="${TALKTOME_BIN:-$BIN}"
[ -x "$BIN" ] || BIN="$BASE/scripts/personal-say"
[ -x "$BIN" ] || exit 0

event=$(printf '%s' "$input" | jq -r '.hook_event_name // empty')

transcript=$(printf '%s' "$input" | jq -r '.transcript_path // empty')
[ -n "$transcript" ] && [ -f "$transcript" ] || exit 0
[ -n "$sid" ] || exit 0

# never block Claude: everything below runs detached
(
  # let the just-finished block flush to the transcript
  sleep 0.25

  WM="$TSTATE/spoken/$sid"
  mkdir -p "$(dirname "$WM")"
  last=$(cat "$WM" 2>/dev/null || echo "")

  # cold start: seed the watermark at the current tip so we never replay the backlog
  if [ -z "$last" ]; then
    jq -rs '[ .[] | select(.type=="assistant"
                           and (.message.content | type=="array")
                           and (any(.message.content[]?; .type=="text"))) ]
            | last | .uuid // empty' "$transcript" > "$WM" 2>/dev/null || true
    [ "$event" = "Stop" ] && : > "$TSTATE/queue/$sid/.done" 2>/dev/null || true
    exit 0
  fi

  # every assistant TEXT block newer than the watermark, oldest first, as uuid<TAB>text
  rows=$(jq -rs --arg last "$last" '
    [ .[] | select(.type=="assistant"
                   and (.message.content | type=="array")
                   and (any(.message.content[]?; .type=="text"))) ]
    | (. as $a | ([ range(0; $a|length) | select($a[.].uuid == $last) ] | last) as $i
       | if $i == null then [] else $a[$i+1:] end)
    | .[]
    | [ .uuid, (.message.content | map(select(.type=="text") | .text) | join(" ")) ]
    | @tsv
  ' "$transcript" 2>/dev/null || true)
  [ -n "$rows" ] || [ "$event" = "Stop" ] || exit 0

  # Running under the terminal tap? It is already speaking every sentence live, so the
  # hook only advances the watermark. A heartbeat older than 15s means the tap died and
  # this path takes over again - that is the fallback, and it is automatic.
  TAPPED=0
  if [ -n "${TALKTOME_TAP_SPOOL:-}" ] && [ -f "$TALKTOME_TAP_SPOOL/.beat" ]; then
    age=$(( $(date +%s) - $(stat -f %m "$TALKTOME_TAP_SPOOL/.beat" 2>/dev/null || echo 0) ))
    [ "$age" -lt 15 ] && TAPPED=1
  fi

  QDIR="$TSTATE/queue/$sid"; mkdir -p "$QDIR"
  n=0
  while IFS=$'\t' read -r uuid raw; do
    [ -n "$uuid" ] || continue
    text=$(printf '%b' "$raw")
    clean=$(printf '%s' "$text" | perl -0777 -pe '
      s/```.*?```//gs;
      s/\[([^\]]*)\]\([^)]*\)/$1/g;
      s/^[ \t]*#{1,6}[ \t]*//mg;
      s/^[ \t]*>[ \t]?//mg;
      s/^([ \t]*)[-+*][ \t]+/$1/mg;
      s/[ \t]+$//mg;
      s/[ \t]{2,}/ /g;
      s/\n{3,}/\n\n/g;
      s/\A\s+//; s/\s+\z//;
    ')
    printf '%s' "$uuid" > "$WM"
    [ "$TAPPED" = 1 ] && continue
    [ -n "$(printf '%s' "$clean" | tr -d '[:space:]')" ] || continue
    n=$((n+1))
    printf '%s' "$clean" > "$QDIR/$(date +%s%N)-$n.txt"
  done <<< "$rows"

  if [ -n "$sid" ] && [ -f "$SESSCFG/$sid/voice" ]; then voice=$(cat "$SESSCFG/$sid/voice"); else voice=$(cat "$STATE/voice" 2>/dev/null || echo auto); fi
  if [ -n "$sid" ] && [ -f "$SESSCFG/$sid/rate"  ]; then rate=$(cat "$SESSCFG/$sid/rate");   else rate=$(cat "$STATE/rate"  2>/dev/null || echo 1.0);  fi
  if [ -n "$sid" ] && [ -f "$SESSCFG/$sid/face"  ]; then face=$(cat "$SESSCFG/$sid/face");   else face=$(cat "$STATE/face"  2>/dev/null || echo "");   fi

  # the user's own voice for their echoed prompts - locked, never the reply voice
  me_voice=$(cat "$STATE/me-voice" 2>/dev/null || echo "me")

  # panel chrome, identical to talk-to-me: /rename name, else ai-title, else project dir
  cwd=$(printf '%s' "$input" | jq -r '.cwd // empty')
  title=""
  [ -n "$sid" ] && title=$(jq -rs --arg s "$sid" '[.[] | select(.sessionId==$s) | .name // empty] | last // empty' "$HOME/.claude/sessions/"*.json 2>/dev/null || true)
  [ -n "$title" ] || title=$(jq -rs '[.[] | select(.type=="ai-title")] | last | .aiTitle // empty' "$transcript" 2>/dev/null || true)
  [ -n "$title" ] || title=$(basename "$cwd" 2>/dev/null || true)
  [ -n "$title" ] || title="Claude Code"
  branch=$(git -C "${cwd:-.}" rev-parse --abbrev-ref HEAD 2>/dev/null || true)
  top=$(git -C "${cwd:-.}" rev-parse --show-toplevel 2>/dev/null || true); [ -n "$top" ] && repo=$(basename "$top") || repo=""

  # end of turn: tell the reader the stream is over so it closes once it catches up
  [ "$event" = "Stop" ] && : > "$QDIR/.done"

  case "$BIN" in
    *talk-reader-live)
      # ONE reader per session, fed by the spool. Already alive? it will pick the files up.
      PIDF="$TSTATE/queue/$sid.pid"
      if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF" 2>/dev/null)" 2>/dev/null; then exit 0; fi
      ( TALKTOME_VOICE="$voice" TALKTOME_RATE="$rate" TALKTOME_TITLE="$title" \
        TALKTOME_BRANCH="$branch" TALKTOME_REPO="$repo" TALKTOME_FACE="$face" \
        TALKTOME_SPOOL="$QDIR" TALKTOME_ME_VOICE="$me_voice" "$BIN" >/dev/null 2>&1 ) &
      echo $! > "$PIDF"
      ;;
    *)
      # audio-only: drain serially, one process per block; mkdir is the lock
      LOCK="$TSTATE/queue/$sid.lock"
      mkdir "$LOCK" 2>/dev/null || exit 0
      trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT
      while :; do
        f=$(find "$QDIR" -name '*.txt' 2>/dev/null | sort | head -1)
        [ -n "$f" ] || break
        txt=$(cat "$f"); rm -f "$f"
        TALKTOME_VOICE="$voice" TALKTOME_RATE="$rate" "$BIN" "$txt" >/dev/null 2>&1 || true
      done
      ;;
  esac
) >/dev/null 2>&1 &

exit 0
