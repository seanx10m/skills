#!/usr/bin/env zsh
# Idempotent installer: adds shell shortcuts to ~/.zshrc and drops bundled
# audio assets in place. Safe to re-run — each block is skipped if its
# marker is already present.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${(%):-%x}")/.." && pwd)"
ZSHRC="$HOME/.zshrc"
touch "$ZSHRC"

# --- preflight: report missing binaries, don't block on them ---------
# name:command:brew-hint
typeset -a DEPS=(
  "claude:claude:official installer, see claude.com/code"
  "gcloud:gcloud:brew install --cask google-cloud-sdk"
  "slack:slack:brew install slack-cli"
  "cursor-agent:cursor-agent:official installer, see cursor.com"
  "codex:codex:npm install -g @openai/codex"
  "sf:sf:npm install -g @salesforce/cli  (or: brew install salesforce-cli)"
  "sox (play):play:brew install sox"
)
missing=0
for dep in "${DEPS[@]}"; do
  IFS=: read -r label bin hint <<< "$dep"
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "missing: $label -> $hint"
    missing=$((missing + 1))
  fi
done
if (( missing > 0 )); then
  echo "$missing dependencies missing — the matching aliases/functions will install but won't run until you install them."
fi
echo ""

add_block() {
  local name="$1" body="$2"
  if grep -qF "# >>> setup-shortcuts:$name >>>" "$ZSHRC"; then
    echo "skip: $name (already installed)"
    return
  fi
  {
    echo ""
    echo "# >>> setup-shortcuts:$name >>>"
    echo "$body"
    echo "# <<< setup-shortcuts:$name <<<"
  } >> "$ZSHRC"
  echo "added: $name"
}

# --- audio assets -----------------------------------------------------
mkdir -p "$HOME/Music/tracks"
[[ -f "$HOME/.brownnoise.wav" ]] || cp "$SKILL_DIR/assets/brownnoise.wav" "$HOME/.brownnoise.wav"
[[ -f "$HOME/.bn-tail.wav" ]]    || cp "$SKILL_DIR/assets/bn-tail.wav" "$HOME/.bn-tail.wav"
LENNY_WAV="$HOME/Music/tracks/Lenny Kravitz - It Ain't Over 'Til It's Over (Official Music Video).wav"
[[ -f "$LENNY_WAV" ]] || cp "$SKILL_DIR/assets/lenny.wav" "$LENNY_WAV"
echo "audio assets in place"

# --- shell blocks -------------------------------------------------------
add_block "claude-code-launchers" '# Claude Code launcher aliases (model x effort)
alias c="claude --dangerously-skip-permissions --model sonnet"
alias cc="claude --dangerously-skip-permissions --model opus"
alias ccc="claude --dangerously-skip-permissions --model fable"

alias cl="claude --dangerously-skip-permissions --model sonnet --effort low"
alias cm="claude --dangerously-skip-permissions --model sonnet --effort medium"
alias ch="claude --dangerously-skip-permissions --model sonnet --effort high"
alias cxh="claude --dangerously-skip-permissions --model sonnet --effort xhigh"
alias cmx="claude --dangerously-skip-permissions --model sonnet --effort max"

alias ccl="claude --dangerously-skip-permissions --model opus --effort low"
alias ccm="claude --dangerously-skip-permissions --model opus --effort medium"
alias cch="claude --dangerously-skip-permissions --model opus --effort high"
alias ccxh="claude --dangerously-skip-permissions --model opus --effort xhigh"
alias ccmx="claude --dangerously-skip-permissions --model opus --effort max"
alias ccu="claude --dangerously-skip-permissions --model opus --effort xhigh"

alias cccl="claude --dangerously-skip-permissions --model fable --effort low"
alias cccm="claude --dangerously-skip-permissions --model fable --effort medium"
alias ccch="claude --dangerously-skip-permissions --model fable --effort high"
alias cccxh="claude --dangerously-skip-permissions --model fable --effort xhigh"
alias cccmx="claude --dangerously-skip-permissions --model fable --effort max"'

add_block "cloud-auth" '# Cloud / platform auth
alias g="gcloud auth login"                        # Google Cloud
alias a="ant auth login"                            # Anthropic Claude Platform CLI
alias ga="gcloud auth application-default login"
alias sl="slack login"                              # Slack CLI login flow'

add_block "cg" '# cg <name>: jump to a project dir (mapped name, else fuzzy find under ~/code)
typeset -A PROJECT_DIRS=(
  proj    "$HOME/code/my-project"
  canary  "$HOME/code/canary_alerts"
  scraper "$HOME/code/other/other projects/Planter/DiningOut Scraping"
)
cg() {
  if [[ -n "${PROJECT_DIRS[$1]}" ]]; then
    cd "${PROJECT_DIRS[$1]}"
  else
    local hit
    hit=$(find ~/code -maxdepth 5 -iname "*$1*" -type d -not -path "*/archive/*" -not -path "*/.git/*" 2>/dev/null | head -1)
    if [[ -n "$hit" ]]; then
      echo "cg: no map entry for '"'"'$1'"'"', guessed: $hit"
      cd "$hit"
    else
      echo "cg: no match for '"'"'$1'"'"'"
    fi
  fi
}'

add_block "caf" '# caf: caffeinate -d, 24h cap, re-running resets the timer
caf() {
  pkill -f "caffeinate -d -t 86400" 2>/dev/null
  [[ "$1" == off ]] && { echo "caf off"; return; }
  nohup caffeinate -d -t 86400 >/dev/null 2>&1 &
  disown
  echo "caf on - display awake until $(date -v+24H "+%a %H:%M")"
}
alias cafd=caf'

add_block "dev-tool-aliases" '# Dev tool CLI aliases
alias ca="cursor-agent --model composer-2.5"  # agent mode (default) + Composer 2.5
alias cx="codex"
alias s="sf org login web --instance-url https://YOUR_ORG.my.salesforce.com --alias my-org-prod"'

add_block "sound-toggles" '# --- sound toggles: bn (brown noise), lenny, shared helpers ---
_audio_gain() { printf "%.2f" $(( ($1 + 1) / 10.0 )); }

# brown noise: 20s fade in on start, 1s fade out on stop
#   bn       toggle on/off
#   bn 0-9   set volume 10%-100% (starts it if not already playing)
bn() {
  local volfile="$HOME/.bn-vol" gain pct
  gain=$(cat "$volfile" 2>/dev/null || echo 1.00)

  if [[ -n "$1" ]]; then
    [[ "$1" == [0-9] ]] || { echo "bn: volume is a single digit 0-9 (10%-100%)"; return 1; }
    gain=$(_audio_gain "$1"); pct=$(( ($1 + 1) * 10 ))
    print -r -- "$gain" > "$volfile"
    if pgrep -f "play.*brownnoise\.wav" >/dev/null 2>&1; then
      pkill -9 -f "play.*brownnoise\.wav" >/dev/null 2>&1
      (play -q "$HOME/.brownnoise.wav" repeat 999 vol "$gain" fade t 1 >/dev/null 2>&1 &)
      echo "brown noise vol ${pct}%"
    else
      (play -q "$HOME/.brownnoise.wav" repeat 999 vol "$gain" fade t 20 >/dev/null 2>&1 &)
      echo "brown noise on (20s fade in) - vol ${pct}%"
    fi
    return
  fi

  if pgrep -f "play.*brownnoise\.wav" >/dev/null 2>&1; then
    (play -q "$HOME/.bn-tail.wav" >/dev/null 2>&1 &)   # 1s fade-out tail
    sleep 0.15
    pkill -9 -f "play.*brownnoise\.wav" >/dev/null 2>&1
    echo "brown noise off"
  else
    (play -q "$HOME/.brownnoise.wav" repeat 999 vol "$gain" fade t 20 >/dev/null 2>&1 &)
    echo "brown noise on (20s fade in)"
  fi
}

# _track: toggle/resume player for one finite track (shared by lenny)
#   _track <tag> <label> <file> <secs> <mm:ss> <ps-match> [0-9] [loop]
_track() {
  local tag=$1 label=$2 f=$3 dur=$4 len=$5 match=$6 arg=$7 loop=$8
  local volfile="$HOME/.${tag}-vol" statef="$HOME/.${tag}-start"
  local gain pct pos pid t0 off
  local -a rep; [[ -n "$loop" ]] && rep=(repeat 9999)
  [[ -f "$f" ]] || { echo "${tag}: missing ${f}"; return 1; }
  gain=$(cat "$volfile" 2>/dev/null || echo 1.00)

  pid= ; pos=0
  if [[ -f "$statef" ]] && read -r pid t0 off < "$statef" && kill -0 "$pid" 2>/dev/null; then
    ps -o command= -p "$pid" 2>/dev/null | grep -qF "$match" || pid=
  else
    pid=
  fi
  if [[ -n "$pid" ]]; then
    pos=$(( $(date +%s) - t0 + off ))
    if [[ -n "$loop" ]]; then
      (( pos < 0 )) && pos=0 || pos=$(( pos % dur ))
    else
      (( pos < 0 || pos >= dur )) && pos=0
    fi
  fi

  if [[ -n "$arg" ]]; then
    [[ "$arg" == [0-9] ]] || { echo "${tag}: volume is a single digit 0-9 (10%-100%)"; return 1; }
    gain=$(_audio_gain "$arg"); pct=$(( ($arg + 1) * 10 ))
    print -r -- "$gain" > "$volfile"
    [[ -n "$pid" ]] && kill -9 "$pid" 2>/dev/null
    play -q "$f" "${rep[@]}" trim "$pos" vol "$gain" >/dev/null 2>&1 &
    print -r -- "$! $(date +%s) $pos" > "$statef"
    disown 2>/dev/null
    if (( pos > 0 )); then echo "${label} vol ${pct}% (at ${pos}s)"
    else echo "${label} on (${len}) - vol ${pct}%"; fi
    return
  fi

  if [[ -n "$pid" ]]; then
    kill -9 "$pid" 2>/dev/null
    rm -f "$statef"
    echo "${label} off"
  else
    play -q "$f" "${rep[@]}" vol "$gain" >/dev/null 2>&1 &
    print -r -- "$! $(date +%s) 0" > "$statef"
    disown 2>/dev/null
    echo "${label} on (${len})"
  fi
}

# lenny: It Ain'"'"'t Over '"'"'Til It'"'"'s Over (Lenny Kravitz)
#   lenny       toggle on/off
#   lenny 0-9   set volume 10%-100% (resumes at current position; starts it if stopped)
lenny() {
  _track lenny "🎸 it ain'"'"'t over" \
    "$HOME/Music/tracks/Lenny Kravitz - It Ain'"'"'t Over '"'"'Til It'"'"'s Over (Official Music Video).wav" \
    245 "4:05" "Lenny Kravitz" "$1"
}

# silence: kill any active play process (bn or lenny)
silence() {
  if pgrep -f "play -q" >/dev/null 2>&1; then
    pkill -9 -f "play -q" >/dev/null 2>&1
    rm -f "$HOME"/.*-start
    echo "🔇 silence"
  else
    echo "already quiet"
  fi
}'

echo ""
echo "done. run: source ~/.zshrc"
