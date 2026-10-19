#!/bin/bash
# Deletes files older than N days (default 2) from a directory. Rolling window,
# no state of its own - reuses mtime the filesystem already tracks. Called from
# browser-preview's hook so its scratch/.previews and state/opened dirs don't grow forever.
set -uo pipefail
DIR="${1:?usage: prune-old.sh <dir> [days=2]}"
DAYS="${2:-2}"
[ -d "$DIR" ] || exit 0
find "$DIR" -type f -mtime "+$DAYS" -delete 2>/dev/null
exit 0
