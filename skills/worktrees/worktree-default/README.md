# worktree-default

Installs (or removes) a "worktrees by default" hook set in a repo, so concurrent Claude Code sessions never move the shared root checkout under each other.

- **SessionStart**: fast-forwards the root to `origin/<default>` and tells the agent to call `EnterWorktree` before its first edit.
- **PreToolUse (Edit/Write/NotebookEdit)**: denies file writes under the root checkout.
- **PreToolUse (Bash)**: denies `git checkout` / `git switch` in the root (path-form checkouts still pass).

A per-session pass file (`~/.claude/wt-root-ok/<repo>/<session_id>`) lifts the guard when the user explicitly wants the root.

## Requirements

- POSIX `sh`, `git`, `jq`, `python3`. macOS or Linux.

## Install

```sh
cp -r skills/worktrees/worktree-default ~/.claude/skills/
sh ~/.claude/skills/worktrees/worktree-default/install.sh /path/to/repo          # install hooks into a repo
sh /path/to/repo/.claude/hooks/test_worktree_guard.sh                  # verify
sh ~/.claude/skills/worktrees/worktree-default/install.sh --uninstall /path/to/repo
```

The installer is idempotent, only touches its own entries in `.claude/settings.json`, refuses to run inside a worktree, and adds `.claude/worktrees/` to `.gitignore`.
