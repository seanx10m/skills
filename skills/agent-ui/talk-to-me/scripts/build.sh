#!/usr/bin/env bash
# Compile the Swift engines from source. Each binary embeds Info.plist
# (NSPersonalVoiceUsageDescription) so macOS will grant Personal Voice
# authorization to a plain CLI binary. Requires Xcode command line tools (swiftc).
set -euo pipefail
command -v swiftc >/dev/null || { echo "swiftc not found - run: xcode-select --install" >&2; exit 1; }
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SKILL_DIR/scripts"

PLIST=(-Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist -Xlinker Info.plist)

swiftc personal-say.swift -o personal-say \
  -framework AVFoundation -framework Foundation "${PLIST[@]}"
echo "built $SKILL_DIR/scripts/personal-say"

swiftc personal-say-tofile.swift -o personal-say-tofile \
  -framework AVFoundation -framework Foundation "${PLIST[@]}"
echo "built $SKILL_DIR/scripts/personal-say-tofile"

swiftc talk-reader-live.swift -o talk-reader-live \
  -framework Cocoa -framework AVFoundation -framework Foundation "${PLIST[@]}"
echo "built $SKILL_DIR/scripts/talk-reader-live"
