#!/usr/bin/env bash
# talktome control — toggle response narration, pick voice/rate, speak on demand.
# Self-locating: resolves all paths relative to the skill folder.
#
# Narration scope is PER-SESSION by default (keyed on $CLAUDE_CODE_SESSION_ID).
# Add "all" to a command to affect every Claude Code session instead.
#
# Usage:
#   talktome.sh                → toggle narration for THIS session
#   talktome.sh on [all]       → narrate this session (or all sessions)
#   talktome.sh off [all]      → stop narrating this session (or all)
#   talktome.sh status         → show state
#   talktome.sh stop           → stop whatever is speaking right now
#   talktome.sh auto           → use any available Personal Voice
#   talktome.sh voice NAME      → use a specific Personal Voice (substring ok)
#   talktome.sh rate N         → set speed multiplier (1.0 = normal)
#   talktome.sh window on|off  → karaoke highlight window vs audio-only
#   talktome.sh say TEXT       → speak TEXT once now (ignores on/off)

set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE="$SKILL_DIR/state"
GFLAG="$STATE/narrate-on"          # global default: narrate every session unless a session opts out
SESSDIR="$STATE/sessions"          # per-session explicit state: sessions/<id> = ON, sessions/<id>.off = OFF
SESSCFG="$STATE/sessions-cfg"      # per-session voice/rate overrides: sessions-cfg/<sid>/{voice,rate}
VOICEFILE="$STATE/voice"           # shared (global) voice — fallback when no session override
RATEFILE="$STATE/rate"             # shared (global) rate  — fallback when no session override
WINFILE="$STATE/window"
PERSFILE="$STATE/personality"      # "on" → color narration with the voice's namesake persona
SID="${CLAUDE_CODE_SESSION_ID:-}"
mkdir -p "$STATE" "$SESSDIR" "$SESSCFG"
find "$SESSDIR" -type f -mtime +7 -delete 2>/dev/null || true  # prune stale session flags
find "$SESSCFG" -mindepth 1 -mtime +7 -delete 2>/dev/null || true  # prune stale session overrides

cmd="${1:-toggle}"; shift || true

is_global() { case "${1:-}" in all|global|-a|--all) return 0 ;; *) return 1 ;; esac; }
sflag()    { [ -n "$SID" ] && echo "$SESSDIR/$SID"; }        # this session's explicit-ON marker
soffflag() { [ -n "$SID" ] && echo "$SESSDIR/$SID.off"; }    # this session's explicit-OFF marker

# Set this session's explicit narration state. $1 = on|off|clear.
#   on    → create the ON marker, drop any OFF marker
#   off   → create the OFF marker, drop any ON marker
#   clear → drop both markers so this session follows the global default
sess_set() {
  [ -n "$SID" ] || return 0
  case "$1" in
    on)    : > "$(sflag)";    rm -f "$(soffflag)" ;;
    off)   : > "$(soffflag)"; rm -f "$(sflag)" ;;
    clear) rm -f "$(sflag)" "$(soffflag)" ;;
  esac
}

# Clear EVERY per-session on/off marker. Used by the `all` verbs so on-all/off-all/toggle-all
# are authoritative GLOBAL resets: no per-session override survives to keep a session talking
# (or muted) against the global default the user just set.
sess_wipe_all() { find "$SESSDIR" -mindepth 1 -delete 2>/dev/null || true; }

# THE one resolution every consumer must use: an explicit per-session marker wins;
# only when this session has NO marker do we fall back to the global default.
# Prints "1" (narrate) or "0". Reads $SID.
narration_on() {
  if [ -n "$SID" ] && [ -f "$SESSDIR/$SID.off" ]; then echo 0; return; fi  # explicit session OFF wins
  if [ -n "$SID" ] && [ -f "$SESSDIR/$SID" ];     then echo 1; return; fi  # explicit session ON wins
  [ -f "$GFLAG" ] && echo 1 || echo 0                                      # else: global default
}

# Per-session-first settings (voice, rate). Resolution: this session's override →
# shared global file → built-in default. Mirrors the on/off per-session scope so three
# parallel sessions can each hold a different voice without stomping each other. The voice
# NAME is still matched personal-first inside the engines (system voices never win a match).
cfgget() {  # $1=key  $2=default
  local key="$1" def="$2"
  if [ -n "$SID" ] && [ -f "$SESSCFG/$SID/$key" ]; then cat "$SESSCFG/$SID/$key"; return; fi
  cat "$STATE/$key" 2>/dev/null || printf '%s' "$def"
}
cfgset() {  # $1=key  $2=value  $3=scope("all" → shared/global, else this session)
  local key="$1" val="$2" scope="${3:-}"
  if is_global "$scope" || [ -z "$SID" ]; then
    printf '%s' "$val" > "$STATE/$key"
    [ -n "$SID" ] && rm -f "$SESSCFG/$SID/$key"   # drop my override so I follow the shared value
  else
    mkdir -p "$SESSCFG/$SID"; printf '%s' "$val" > "$SESSCFG/$SID/$key"
  fi
}

engine() {
  if [ "$(cat "$WINFILE" 2>/dev/null || echo on)" = "off" ]; then
    echo "$SKILL_DIR/scripts/personal-say"
  else
    echo "$SKILL_DIR/scripts/talk-reader-live"
  fi
}

kill_all() { pkill -x personal-say 2>/dev/null || true; pkill -x talk-reader-live 2>/dev/null || true; }

status() {
  local sess glob="OFF"
  # this session's effective state, tagged with where it came from (explicit vs inherited)
  if [ "$(narration_on)" = 1 ]; then sess="ON"; else sess="OFF"; fi
  if [ -n "$SID" ] && { [ -f "$(sflag)" ] || [ -f "$(soffflag)" ]; }; then
    sess="$sess (this session)"
  else
    sess="$sess (inherited)"
  fi
  [ -f "$GFLAG" ] && glob="ON"
  local v r w p vscope="shared" rscope="shared"
  v=$(cfgget voice auto)
  r=$(cfgget rate 1.0)
  w=$(cat "$WINFILE" 2>/dev/null || echo "on")
  p=$(cat "$PERSFILE" 2>/dev/null || echo "off")
  [ -n "$SID" ] && [ -f "$SESSCFG/$SID/voice" ] && vscope="session"
  [ -n "$SID" ] && [ -f "$SESSCFG/$SID/rate" ]  && rscope="session"
  local sid_disp="${SID:0:8}"; [ -z "$sid_disp" ] && sid_disp="(unknown)"
  echo "this session [$sid_disp]: $sess | all sessions: $glob | voice: $v ($vscope) | rate: ${r}x ($rscope) | window: $w | personality: $p"
}

speak_now() {
  local v r bin title proj tdir tfile branch repo top
  v=$(cfgget voice auto)
  r=$(cfgget rate 1.0)
  # session name: prefer the user's `/rename` name (in ~/.claude/sessions/<pid>.json under
  # .name, keyed to .sessionId), then the latest ai-title in this session's transcript, then
  # the project dir name. Claude Code names the project dir by turning every non-alphanumeric
  # char in the cwd into '-'.
  proj=$(printf '%s' "$PWD" | sed 's/[^a-zA-Z0-9]/-/g')
  tdir="$HOME/.claude/projects/$proj"
  tfile="$tdir/$SID.jsonl"
  [ -f "$tfile" ] || tfile=$(ls -t "$tdir"/*.jsonl 2>/dev/null | head -1)   # fallback: newest transcript
  title=""
  [ -n "$SID" ] && title=$(jq -rs --arg s "$SID" '[.[] | select(.sessionId==$s) | .name // empty] | last // empty' "$HOME/.claude/sessions/"*.json 2>/dev/null)
  [ -n "$title" ] || { [ -n "$tfile" ] && [ -f "$tfile" ] && title=$(jq -rs '[.[] | select(.type=="ai-title")] | last | .aiTitle // empty' "$tfile" 2>/dev/null); }
  [ -n "$title" ] || title=$(basename "$PWD" 2>/dev/null)
  [ -n "$title" ] || title="Claude Code"
  # current git branch + repo (empty when not in a repo; never abort under set -e)
  branch=$(git -C "$PWD" rev-parse --abbrev-ref HEAD 2>/dev/null || true)
  top=$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null || true); [ -n "$top" ] && repo=$(basename "$top") || repo=""
  bin=$(engine); [ -x "$bin" ] || bin="$SKILL_DIR/scripts/personal-say"
  kill_all
  TALKTOME_VOICE="$v" TALKTOME_RATE="$r" TALKTOME_TITLE="$title" TALKTOME_BRANCH="$branch" TALKTOME_REPO="$repo" "$bin" "$*" >/dev/null 2>&1 &
  echo "speaking…"
}

case "$cmd" in
  on)
    # Plain `on` is THIS session only; `on all` turns it on EVERYWHERE — sets the global
    # default AND wipes per-session markers so no session stays muted against it. With no
    # session id we cannot scope per-session, so require explicit `all`.
    if is_global "$@"; then : > "$GFLAG"; sess_wipe_all
    elif [ -n "$SID" ]; then sess_set on
    else echo "(no session id — use 'on all' to enable globally)"; fi
    status ;;
  off)
    # Plain `off` records an explicit per-session OFF (so it beats a global ON); `off all`
    # turns it off EVERYWHERE — clears the global default AND wipes per-session markers so no
    # explicitly-on session keeps talking through it. With no session id, require explicit `all`.
    if is_global "$@"; then rm -f "$GFLAG"; sess_wipe_all
    elif [ -n "$SID" ]; then sess_set off
    else echo "(no session id — use 'off all' to disable globally)"; fi
    kill_all; status ;;
  toggle)
    # Toggle on the SAME axis the resolver reads: flip this session's effective state by
    # writing an explicit per-session marker. `toggle all` flips the global default.
    # With NO session id we cannot scope per-session, so refuse and require explicit `all`
    # rather than silently flipping the global flag — mirrors the `on`/`off` guard below so
    # a bare toggle can never bleed into every session.
    if is_global "$@"; then
      # flip the global default, then wipe per-session markers so the result is uniform
      # everywhere — no session survives the flip still set the old way.
      if [ -f "$GFLAG" ]; then rm -f "$GFLAG"; else : > "$GFLAG"; fi
      sess_wipe_all; kill_all
    elif [ -n "$SID" ]; then
      if [ "$(narration_on)" = 1 ]; then sess_set off; kill_all; else sess_set on; fi
    else
      echo "(no session id — use 'toggle all' or 'on all'/'off all' to change the global default)"
    fi
    status ;;
  stop)   kill_all; echo "stopped" ;;
  status) status ;;
  auto)
    scope=""; [ "${1:-}" = "all" ] && scope="all"
    cfgset voice "auto" "$scope"; status ;;
  voice)
    raw="$*"; scope=""
    case "$raw" in
      *" all") scope="all"; raw="${raw% all}" ;;   # `voice <name> all` → set the shared default
      all)     scope="all"; raw="" ;;
    esac
    cfgset voice "$raw" "$scope"; status ;;
  rate)
    scope=""; [ "${2:-}" = "all" ] && scope="all"
    cfgset rate "${1:-1.0}" "$scope"; status ;;
  window) printf "%s" "${1:-on}" > "$WINFILE"; status ;;
  personality)
    case "${1:-toggle}" in
      on)  printf "on"  > "$PERSFILE" ;;
      off) printf "off" > "$PERSFILE" ;;
      *)   [ "$(cat "$PERSFILE" 2>/dev/null)" = "on" ] && printf "off" > "$PERSFILE" || printf "on" > "$PERSFILE" ;;
    esac
    status ;;
  say)    speak_now "$*" ;;
  *)      echo "unknown command: $cmd"; status; exit 2 ;;
esac
