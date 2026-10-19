# shortcuts.zsh - Claude Code launch shortcuts + project jumpers (zsh only).
#
# Source this from ~/.zshrc (install.sh does that for you):
#   source ~/.config/claude-shortcuts/shortcuts.zsh
#
# Settings (set them BEFORE sourcing, or any time after - the functions read them on every call):
#   CLAUDE_SHORTCUT_FLAGS  extra flags passed to every Claude launch.
#                          Default: --dangerously-skip-permissions (NO permission prompts).
#                          Set CLAUDE_SHORTCUT_FLAGS="" to keep Claude's normal permission prompts.
#   CG_ROOT                where cg searches for projects. Default: $HOME/code
#   PROJECT_DIRS           assoc array of exact name -> path overrides for cg (see below).

[[ -n $ZSH_VERSION ]] || { echo "shortcuts.zsh: requires zsh" >&2; return 1 2>/dev/null || exit 1; }

# `=` (not `:=`) so an explicit empty value is kept.
: ${CLAUDE_SHORTCUT_FLAGS=--dangerously-skip-permissions}

# ---------------------------------------------------------------------------
# Claude alias grid
#   c = sonnet, cc = opus, ccc = fable
#   suffix l/m/h/xh/mx = --effort low/medium/high/xhigh/max
#   ccu = opus + xhigh
# All extra arguments pass straight through, e.g. `cch --resume`.
# Note: `cc` shadows the system C compiler command in interactive shells.
# ---------------------------------------------------------------------------

# _claude_shortcut <model> [effort] -- [args...]
_claude_shortcut() {
  local model=$1 effort=$2
  shift 2
  local -a cmd
  cmd=(claude ${=CLAUDE_SHORTCUT_FLAGS} --model "$model")
  [[ -n $effort ]] && cmd+=(--effort "$effort")
  command "${cmd[@]}" "$@"
}

# Drop any same-named aliases first so the function definitions below win.
unalias c cl cm ch cxh cmx cc ccl ccm cch ccxh ccmx ccu ccc cccl cccm ccch cccxh cccmx 2>/dev/null

# Sonnet
c()     { _claude_shortcut sonnet ""     "$@"; }
cl()    { _claude_shortcut sonnet low    "$@"; }
cm()    { _claude_shortcut sonnet medium "$@"; }
ch()    { _claude_shortcut sonnet high   "$@"; }
cxh()   { _claude_shortcut sonnet xhigh  "$@"; }
cmx()   { _claude_shortcut sonnet max    "$@"; }
# Opus
cc()    { _claude_shortcut opus   ""     "$@"; }
ccl()   { _claude_shortcut opus   low    "$@"; }
ccm()   { _claude_shortcut opus   medium "$@"; }
cch()   { _claude_shortcut opus   high   "$@"; }
ccxh()  { _claude_shortcut opus   xhigh  "$@"; }
ccmx()  { _claude_shortcut opus   max    "$@"; }
ccu()   { _claude_shortcut opus   xhigh  "$@"; }
# Fable
ccc()   { _claude_shortcut fable  ""     "$@"; }
cccl()  { _claude_shortcut fable  low    "$@"; }
cccm()  { _claude_shortcut fable  medium "$@"; }
ccch()  { _claude_shortcut fable  high   "$@"; }
cccxh() { _claude_shortcut fable  xhigh  "$@"; }
cccmx() { _claude_shortcut fable  max    "$@"; }

# ---------------------------------------------------------------------------
# cg <name words> = cd to a project.
# Checks PROJECT_DIRS first (exact, no guessing), then falls back to a live
# `find` under $CG_ROOT (skips .git, node_modules, archive, build dirs, ...).
#
# Define your own overrides before sourcing this file (or add to it after):
#   typeset -A PROJECT_DIRS=(
#     myapp "$HOME/code/work/my-app"
#   )
# Keys are normalized names: lowercase letters and digits only.
# ---------------------------------------------------------------------------
(( ${+PROJECT_DIRS} )) || typeset -gA PROJECT_DIRS=(
  # myapp "$HOME/code/work/my-app"
)

cg() {
  emulate -L zsh
  local root=${CG_ROOT:-$HOME/code}
  [[ -z "$1" ]] && { cd "$root"; return }

  # normalize: join all words, lowercase, drop everything that is not a letter or
  # digit, so "my app" -> "myapp", "myapp" matches "My App" and
  # "my-app" matches "MyApp Server".
  local q=${${${(j::)@}:l}//[^a-z0-9]/}
  if [[ -n "${PROJECT_DIRS[$q]}" ]]; then cd "${PROJECT_DIRS[$q]}"; return; fi
  local -a exact partial
  local d n
  while IFS= read -r d; do
    n=${${${d:t}:l}//[^a-z0-9]/}
    if [[ $n == $q ]]; then exact+=("$d")
    elif [[ $n == *$q* ]]; then partial+=("$d"); fi
  done < <(find "$root" -maxdepth 5 \
             \( -name .git -o -name node_modules -o -name archive -o -name .venv \
                -o -name dist -o -name build -o -name __pycache__ \) -prune -o \
             -type d -print 2>/dev/null)

  # exact name beats partial, always; within a tier the shortest path wins
  # (that is the project root rather than a nested subdir of the same name).
  local -a hits
  if (( ${#exact} )); then hits=("${exact[@]}"); else hits=("${partial[@]}"); fi
  (( ${#hits} )) || { echo "cg: no match for '$*'"; return 1 }
  (( ${#hits} > 1 )) && hits=("${(@f)$(printf '%s\n' "${hits[@]}" | awk '{print length, $0}' | sort -n | cut -d' ' -f2-)}")

  print -u2 "cg: '$*' -> ${hits[1]}${${(M)$(( ${#hits} > 1 )):#1}:+ (+$(( ${#hits} - 1 )) more)}"
  cd "${hits[1]}"
}

# ccg <name words> [-flags | -- args] = cg to the project, then launch cc there.
# Name is every word up to the first -flag or a bare "--" (dropped); the rest goes
# to cc, so "ccg my app --resume" and "ccg my app -- 'fix the tests'" both work.
ccg() {
  local -a name
  while (( $# )) && [[ $1 != -* ]]; do name+=("$1"); shift; done
  [[ $1 == -- ]] && shift
  cg "${name[@]}" || return
  cc "$@"
}

# ---------------------------------------------------------------------------
# caf = keep the display awake (macOS caffeinate -d), 24h cap.
#   caf      start, or restart the 24h timer if already running
#   caf off  stop
# Tracks its own process in a PID file and only ever kills that PID.
# ---------------------------------------------------------------------------
caf() {
  local dir=${XDG_CACHE_HOME:-$HOME/.cache}/claude-shortcuts
  local pidfile=$dir/caf.pid pid
  if [[ -r $pidfile ]]; then
    pid=$(<"$pidfile")
    # only kill it if that PID is still a caffeinate process (PIDs get reused)
    if [[ $pid == <-> ]] && [[ $(ps -p "$pid" -o comm= 2>/dev/null) == *caffeinate ]]; then
      kill "$pid" 2>/dev/null
    fi
    rm -f "$pidfile"
  fi
  [[ "$1" == off ]] && { echo "caf off"; return; }
  command -v caffeinate >/dev/null || { echo "caf: caffeinate not found (macOS only)" >&2; return 1; }
  mkdir -p "$dir"
  nohup caffeinate -d -t 86400 >/dev/null 2>&1 &!
  print -r -- $! >| "$pidfile"
  echo "caf on - display awake until $(date -v+24H '+%a %H:%M')"
}
alias cafd=caf
