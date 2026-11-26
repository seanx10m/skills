#!/bin/sh
# todos: one always-on-top panel that stacks every goal file in a folder.
# usage:
#   todos.sh start [dir] [corner]          show the panel for <dir>/*.json (default ~/.todos/current), corner br|bl|tr|tl
#   todos.sh stop  [dir]                   close it (PID recorded at start; no pattern kills)
#   todos.sh new   <name> "<title>" ["<id>:<label>" ...] [--percent N] [--dir dir]   write <dir>/<name>.json
#   todos.sh step  <name> <id> <todo|active|done> [dir]   update one step; animates within 1 s
#   todos.sh percent <name> <0-100> [dir]  for a goal with no steps yet
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
BIN="$HERE/todos"
DEF=$HOME/.todos/current
build() { [ "$BIN" -nt "$HERE/Todos.swift" ] 2>/dev/null || swiftc -parse-as-library -O "$HERE/Todos.swift" -o "$BIN" 2>&1 | grep -v warning || true; }
edit() { python3 -I "$HERE/edit.py" "$@"; }
cmd=${1:-}; shift || true
case "$cmd" in
  start) D=${1:-$DEF}; C=${2:-br}; mkdir -p "$D"; build
    [ -f "$D/.pid" ] && kill -0 "$(cat "$D/.pid")" 2>/dev/null && { echo "already running pid $(cat "$D/.pid")"; exit 0; }
    GOAL_FLOATER_CORNER="$C" nohup "$BIN" "$D" >"$D/.floater.log" 2>&1 &
    echo $! > "$D/.pid"; echo "started pid $(cat "$D/.pid") for $D" ;;
  stop) D=${1:-$DEF}; [ -f "$D/.pid" ] && kill "$(cat "$D/.pid")" 2>/dev/null && rm -f "${D:?}/.pid" && echo stopped || echo "not running" ;;
  new) edit new "$DEF" "$@" ;;
  step) edit step "${4:-$DEF}" "$1" "$2" "$3" ;;
  percent) edit percent "${3:-$DEF}" "$1" "$2" ;;
  *) sed -n '2,9p' "$0"; exit 2 ;;
esac
