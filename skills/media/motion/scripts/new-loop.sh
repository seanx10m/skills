#!/bin/sh
# Scaffold a self-contained motion project: three.js (pinned), starter loop, optional brand folder.
# Usage: new-loop.sh <project-dir> [title] [brand-dir]
set -eu
DIR="${1:?usage: new-loop.sh <project-dir> [title] [brand-dir]}"
TITLE="${2:-Motion}"
BRAND="${3:-}"
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
THREE_VER=0.181.2
CACHE="$HOME/.cache/motion/three-$THREE_VER"

# three.js is 16MB, so it is cached once per machine instead of shipped in the skill
if [ ! -f "$CACHE/three.module.js" ]; then
  mkdir -p "$CACHE"
  TMP="$(mktemp -d)"
  (cd "$TMP" && npm pack "three@$THREE_VER" --silent >/dev/null && tar xzf "three-$THREE_VER.tgz")
  cp "$TMP/package/build/three.module.js" "$TMP/package/build/three.core.js" "$CACHE/"
  cp -R "$TMP/package/examples/jsm" "$CACHE/addons"
  rm -rf "${TMP:?}"
fi

mkdir -p "$DIR/assets" "$DIR/renders" "$DIR/frames"
cp -R "$CACHE" "$DIR/assets/three"
if [ -n "$BRAND" ]; then
  mkdir -p "$DIR/assets/brand"
  cp -R "${BRAND%/}/." "$DIR/assets/brand/"
  # GIFs are never played live: split each into frames stepped by time
  for g in "$DIR/assets/brand/"*.gif; do
    [ -f "$g" ] || continue
    n="$(basename "$g" .gif)"
    [ -d "$DIR/assets/brand/$n-frames" ] && continue
    mkdir -p "$DIR/assets/brand/$n-frames"
    ffmpeg -loglevel error -i "$g" -vsync 0 "$DIR/assets/brand/$n-frames/f%03d.png"
  done
fi
[ -f "$DIR/index.html" ] || sed "s/__TITLE__/$TITLE/" "$SKILL/assets/loop-template.html" > "$DIR/index.html"
echo "scaffolded $DIR (three r$THREE_VER${BRAND:+, brand from $BRAND}, index.html)"
