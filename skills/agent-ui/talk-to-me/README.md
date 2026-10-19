# talk-to-me

Speaks Claude Code's replies aloud in your own macOS Personal Voice, with a floating karaoke panel that highlights each word as it is spoken and echoes your prompt in your voice.

## Requirements

- macOS 14+ (Personal Voice), Xcode command line tools (`xcode-select --install`), `jq`.
- Create a Personal Voice in System Settings > Accessibility > Personal Voice (optional: without one it uses the system voice).
- The voice is your choice: `/talk-to-me voice <name>` or `/talk-to-me auto`. Nothing is hardcoded.
- Optional: set `state/me-voice` to your Personal Voice name so your own prompts are read back in it.

## Install

```bash
cp -r skills/agent-ui/talk-to-me ~/.claude/skills/
bash ~/.claude/skills/agent-ui/talk-to-me/scripts/install.sh
```

`install.sh` compiles `personal-say`, `personal-say-tofile` and `talk-reader-live` from their `.swift` sources via `scripts/build.sh` (binaries are not shipped), registers the hooks in `~/.claude/settings.json`, and installs three Quick Actions to `~/Library/Services` (they use `$HOME/.claude/skills/talk-to-me`, no absolute paths).
Then assign hotkeys in System Settings > Keyboard > Keyboard Shortcuts > Services and restart Claude Code.

See `SKILL.md` for commands and behavior.
