#!/usr/bin/env bash
# Compile the personal-say Personal Voice engine (embeds Info.plist so macOS
# will grant Personal Voice authorization to a plain CLI binary).
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SKILL_DIR/scripts"
swiftc personal-say.swift -o personal-say \
  -framework AVFoundation -framework Foundation \
  -Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist -Xlinker Info.plist
echo "built $SKILL_DIR/scripts/personal-say"

swiftc talk-reader-live.swift -o talk-reader-live \
  -framework Cocoa -framework AVFoundation -framework Foundation \
  -Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist -Xlinker Info.plist
echo "built $SKILL_DIR/scripts/talk-reader-live"
