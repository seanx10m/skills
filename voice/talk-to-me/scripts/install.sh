#!/usr/bin/env bash
# Wire the bundled talktome assets into macOS + Claude Code.
# Idempotent: safe to re-run. Sets up (1) the Personal Voice binary,
# (2) the Stop hook in settings.json, (3) two Quick Actions in ~/Library/Services.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS="$SKILL_DIR/scripts"
ASSETS="$SKILL_DIR/assets"
SETTINGS="$HOME/.claude/settings.json"
SERVICES="$HOME/Library/Services"

echo "talk-to-me install — skill at $SKILL_DIR"

# 1) build the engine if missing
if [ ! -x "$SCRIPTS/personal-say" ]; then
  echo "→ building personal-say…"
  bash "$SCRIPTS/build.sh"
else
  echo "→ personal-say present"
fi
chmod +x "$SCRIPTS"/*.sh

# seed defaults for a fresh install (never overwrite an existing choice)
mkdir -p "$SKILL_DIR/state"
[ -f "$SKILL_DIR/state/voice" ] || printf "auto"  > "$SKILL_DIR/state/voice"
[ -f "$SKILL_DIR/state/rate"  ] || printf "1.0"   > "$SKILL_DIR/state/rate"
[ -f "$SKILL_DIR/state/window" ] || printf "on"   > "$SKILL_DIR/state/window"

# 2) register the narration hooks. Speech streams: PreToolUse + Stop feed the panel as
#    each text block lands, and UserPromptSubmit spools the user's own prompt.
if command -v jq >/dev/null && [ -f "$SETTINGS" ]; then
  HOOKCMD="bash \"$SCRIPTS/speak-stream.sh\""
  FLUSHCMD="bash \"$SCRIPTS/flush.sh\""
  tmp=$(mktemp)
  jq --arg cmd "$HOOKCMD" --arg flush "$FLUSHCMD" '
    def strip(k; re): .hooks[k] = (((.hooks[k] // [])
        | map(.hooks |= map(select((.command // "") | test(re) | not)))
        | map(select((.hooks | length) > 0))));
    .hooks //= {}
    | strip("Stop";             "talk-to-me|talktome|speak-response|speak-stream")
    | strip("PreToolUse";       "speak-stream")
    | strip("UserPromptSubmit"; "talk-to-me.*flush|talk-to-me-too")
    | .hooks.Stop             += [{matcher:"", hooks:[{type:"command", command:$cmd, async:true}]}]
    | .hooks.PreToolUse       += [{matcher:"*", hooks:[{type:"command", command:$cmd, async:true}]}]
    | .hooks.UserPromptSubmit += [{matcher:"", hooks:[{type:"command", command:$flush}]}]
  ' "$SETTINGS" > "$tmp"
  if jq -e . "$tmp" >/dev/null; then mv "$tmp" "$SETTINGS"; echo "→ streaming hooks registered (Stop + PreToolUse + prompt echo)"; else rm -f "$tmp"; echo "!! settings.json edit skipped (invalid JSON)"; fi

  # UserPromptSubmit hook: voice-friendly output style when narration is on
  HINTCMD="bash \"$SCRIPTS/voice-style-hint.sh\""
  tmp=$(mktemp)
  jq --arg cmd "$HINTCMD" '
    .hooks //= {} |
    .hooks.UserPromptSubmit = (
      ((.hooks.UserPromptSubmit // [])
        | map(.hooks |= map(select((.command // "") | test("voice-style-hint") | not)))
        | map(select((.hooks | length) > 0)))
      + [{matcher:"", hooks:[{type:"command", command:$cmd}]}]
    )
  ' "$SETTINGS" > "$tmp"
  if jq -e . "$tmp" >/dev/null; then mv "$tmp" "$SETTINGS"; echo "→ voice-style hook registered"; else rm -f "$tmp"; echo "!! voice-style hook skipped (invalid JSON)"; fi
else
  echo "!! jq or settings.json missing — register hooks manually:"
  echo "   Stop+PreToolUse: bash \"$SCRIPTS/speak-stream.sh\"  (async)"
  echo "   UserPromptSubmit: bash \"$SCRIPTS/voice-style-hint.sh\""
fi

# 2b) point the status line at the badge wrapper (preserves any existing base statusline
#     by chaining to context-guardian inside the wrapper). Only set if not already ours.
if command -v jq >/dev/null && [ -f "$SETTINGS" ]; then
  SLCMD="bash \"$SCRIPTS/statusline-badges.sh\""
  cur=$(jq -r '.statusLine.command // ""' "$SETTINGS")
  case "$cur" in
    *statusline-badges.sh*) echo "→ status line already wired" ;;
    *) tmp=$(mktemp)
       jq --arg c "$SLCMD" '.statusLine = {type:"command", command:$c}' "$SETTINGS" > "$tmp" \
         && jq -e . "$tmp" >/dev/null && mv "$tmp" "$SETTINGS" && echo "→ status line wired (badges)" \
         || { rm -f "$tmp"; echo "!! status line not changed"; } ;;
  esac
fi

# 3) install Quick Actions
mkdir -p "$SERVICES"
for wf in "Talk To Me" "Pause Talking" "Stop Talking"; do
  rm -rf "$SERVICES/$wf.workflow"
  cp -R "$ASSETS/$wf.workflow" "$SERVICES/"
  echo "→ installed Quick Action: $wf"
done

# refresh the macOS Services cache
/System/Library/CoreServices/pbs -flush 2>/dev/null || true

echo
echo "VOICE: defaulting to 'auto' (uses any Personal Voice you have; else system voice)."
echo "  To get your own voice: System Settings → Accessibility → Personal Voice → create."
echo "  To pick a specific one later:  /talktome voice <name>   (or  /talktome auto )"
echo
echo "DONE. Last manual step (macOS won't let scripts set hotkeys):"
echo "  System Settings → Keyboard → Keyboard Shortcuts… → Services → (Text / General)"
echo "    • 'Talk To Me'    → read highlighted text"
echo "    • 'Pause Talking' → pause / resume current speech"
echo "    • 'Stop Talking'  → stop speech instantly"
echo "Restart Claude Code so the Stop hook loads."
