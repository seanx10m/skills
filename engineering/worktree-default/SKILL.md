---
name: worktree-default
description: Install (or remove) the "worktrees by default" hook set in a repo - a SessionStart nudge that fast-forwards the pinned root and tells the agent to call EnterWorktree, plus PreToolUse guards that deny file writes and `git checkout`/`git switch` in the shared root checkout. Use when the user says "/worktree-default", "worktrees by default", "install the worktree hooks", "add the worktree guard to this repo", "make this repo use worktrees", "port the worktree hooks", or asks why writes to a repo root are being blocked.
---

# Worktree Default

Makes a repo enforce one-worktree-per-session. The root checkout stays pinned to
the default branch so concurrent agent sessions never move it under each other.

Originated as repo-local hooks in `<your-org>/<your-repo>`; this skill is the portable
installer.

`$WTD` below means the directory this file is in.

## Install

```sh
sh "$WTD"/install.sh [repo-path]   # default: cwd
sh "$WTD"/install.sh --uninstall [repo-path]
```

Idempotent - re-running replaces its own three entries and leaves every other
hook in `.claude/settings.json` alone.
Refuses to install into a worktree; point it at the root checkout.
Appends `.claude/worktrees/` to `.gitignore` if it isn't there.

After installing, run the check it prints:
`sh <repo>/.claude/hooks/test_worktree_guard.sh`

## What gets installed

Three scripts into `<repo>/.claude/hooks/`, wired in `<repo>/.claude/settings.json`:

| Hook | Event | Behavior |
|---|---|---|
| `worktree-session-start.sh` | SessionStart | Fast-forwards the root to `origin/<default>`, injects the WORKTREE DEFAULT instruction. Runs `lorax.sh` too if that's installed alongside. |
| `worktree-guard.sh` | PreToolUse `Edit\|Write\|NotebookEdit` | Denies writes to files under the root checkout. |
| `worktree-branch-guard.sh` | PreToolUse `Bash` | Denies `git checkout` / `git switch` in the root. Path-form checkouts (`... -- <path>`) still pass. |

Plus `test_worktree_guard.sh`, the runnable check.

The default branch is read from `origin/HEAD`, not hardcoded.

## Escape hatches

The guards exit clean when:
- the session is already in a worktree (the hook's own path is the discriminator),
- the target file is outside the repo (scratchpad, `~/.claude`, `~/Desktop`),
- a per-session pass exists: `~/.claude/wt-root-ok/<repo>/<session_id>`.

The pass file is the deliberate override for a one-line doc or hook fix in the
root. **Only create it when the user explicitly asks for the root** - never on
your own initiative. It lifts the guard for that session only.

Read-only sessions (questions, reviews, log reads) need no worktree - nothing
fires until a write is attempted.

## Not included

`lorax.sh` (worktree pruning) is a separate concern and ships in the `lorax`
skill. If it's present in the same hooks directory, the session-start hook picks
it up and appends its report; otherwise it's silently skipped.
