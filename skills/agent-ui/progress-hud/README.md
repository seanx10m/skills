# progress-hud

A floating always-on-top macOS progress card (percent bar, title, phase/detail) driven by a small CLI, so Claude Code can show live progress for long-running work.

## Requirements

macOS with Xcode command line tools (`swiftc`).

## Install

```bash
cp -r skills/agent-ui/progress-hud ~/.claude/skills/
```

No build step to run by hand: the CLI compiles `assets/ProgressHUD.swift` into `~/.progress-hud/ProgressHUD` on first use.
Try it with `bash ~/.claude/skills/agent-ui/progress-hud/scripts/demo.sh`.

See `SKILL.md` for the toggle and CLI.
