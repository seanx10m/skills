#!/bin/sh
# lorax-open - show an HTML animation in a small native panel.
# Builds the Swift binary on first run (and whenever the source is newer),
# exactly as progress-hud does. Falls back to a browser if anything goes wrong.
#
# Usage: lorax-open.sh <html> [w] [h]
#        lorax-open.sh --check     build only, report, open nothing
set -u

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
src="$here/lorax-window.swift"
bin="$HOME/.lorax/LoraxWindow"

build() {
  [ -f "$src" ] || return 1
  command -v swiftc >/dev/null 2>&1 || return 1
  [ -f "$bin" ] && [ ! "$src" -nt "$bin" ] && return 0
  mkdir -p "$(dirname "$bin")" || return 1
  swiftc -O -o "$bin" "$src" >/dev/null 2>&1 || return 1
}

if [ "${1:-}" = "--check" ]; then
  if build && [ -x "$bin" ]; then echo "lorax-open: native panel ready at $bin"; exit 0; fi
  echo "lorax-open: native panel unavailable, would fall back to a browser"; exit 0
fi

html=${1:-}
w=${2:-220}
h=${3:-130}
[ -f "$html" ] || exit 0        # nothing to show is not a failure

# ponytail: a failed build falls back rather than retrying. Ceiling is one
# stale-source rebuild attempt per call, which is what the mtime check gives.
if build && [ -x "$bin" ]; then
  "$bin" "$html" "$w" "$h" >/dev/null 2>&1 &
else
  open -na "Google Chrome" --args --app="file://$html" --window-size="$w,$h" >/dev/null 2>&1 \
    || open "$html" >/dev/null 2>&1 || true
fi
exit 0
