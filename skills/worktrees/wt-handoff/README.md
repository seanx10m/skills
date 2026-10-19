# wt-handoff

Hands off in-progress dev work to a fresh agent session on the right git worktree.
The outgoing agent commits outstanding work, records the exact worktree path and branch, resolves anything ambiguous, and writes a terse handoff doc to `/tmp/wt-handoff-<branch>-<date>.md`.
The doc carries what does not survive on disk: decisions, dead ends, gotchas, and what the user asked for.

Doc only - it does not open a terminal. For a variant that also launches the next agent, see `ghostty-wt-handoff`, `iterm-wt-handoff`, or `warp-wt-handoff` (each is standalone).

## Requirements

- `git`. Any platform.

## Install

```sh
cp -r skills/worktrees/wt-handoff ~/.claude/skills/
```

Invoke with `/wt-handoff [what the next session should focus on]`.
