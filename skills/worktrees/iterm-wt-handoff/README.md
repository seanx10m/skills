# iterm-wt-handoff

Hands off in-progress dev work to a fresh agent AND launches that agent in a new iTerm2 pane below the current one (or a tab, window, or right split), already in the worktree and already reading the handoff doc.
The outgoing agent commits outstanding work, records the worktree path and branch, writes a terse handoff doc to `/tmp/wt-handoff-<branch>-<date>.md`, then runs `scripts/iterm-spawn`.

Standalone: the full handoff procedure is in this skill's `SKILL.md`, no other skill needed.

## Requirements

- macOS, [iTerm2](https://iterm2.com).
- `git`.
- An agent CLI. Default is `claude` (Claude Code); any command can go after `--`.
- First run may prompt for macOS Automation permission. Approve it once.

## Install

```sh
cp -r skills/worktrees/iterm-wt-handoff ~/.claude/skills/
chmod +x ~/.claude/skills/worktrees/iterm-wt-handoff/scripts/iterm-spawn
```

The script also works on its own:

```sh
scripts/iterm-spawn --cwd ~/code/my-app --title "handoff · my-app" -- claude "Read /tmp/wt-handoff-main-2026-01-01.md and execute the Next steps in it, in order."
```
