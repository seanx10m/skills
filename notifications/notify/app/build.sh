#!/usr/bin/env bash
# Build + bundle + sign Claude Notify.app (the ⚡️ /notify banner helper).
# Idempotent: rerun after editing ClaudeNotify.swift. Signed helper is the ONLY
# reliable custom-icon notification path on macOS Tahoe (see [[spend-alert-furnace-icon]]).
set -euo pipefail

HERE="$HOME/.claude/skills/notify/app"
APP="$HOME/Applications/Claude Notify.app"
IDENT="YOUR_CODESIGN_IDENTITY_SHA1"   # Apple Development: <your identity>
ICNS="$HOME/.claude/skills/notify/assets/robot.icns"

echo "compiling…"
swiftc -O -target arm64-apple-macos13.0 -o "$HERE/ClaudeNotify" "$HERE/ClaudeNotify.swift"

echo "bundling -> $APP"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$HERE/ClaudeNotify" "$APP/Contents/MacOS/ClaudeNotify"
cp "$ICNS" "$APP/Contents/Resources/AppIcon.icns"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Claude Notify</string>
  <key>CFBundleDisplayName</key><string>Claude Notify</string>
  <key>CFBundleIdentifier</key><string>com.example.claude-notify-robot</string>
  <key>CFBundleExecutable</key><string>ClaudeNotify</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>LSUIElement</key><true/>
</dict>
</plist>
PLIST

echo "signing…"
codesign --force --options runtime --sign "$IDENT" "$APP"
codesign --verify --strict "$APP" && echo "signature OK"

# register so LaunchServices picks up the icon + bundle id for notification perms
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP"
echo "built: $APP"
