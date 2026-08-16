---
name: lorax
description: Prune finished git worktrees in the current repo, or report what is safe to prune and what is being held. Speaks for the trees - removes a worktree only when its work exists somewhere else. Use when the user says "/lorax", "lorax", "prune worktrees", "clean up worktrees", "what worktrees can I delete", "worktree status", or asks to turn the truffula animation on or off.
---

# Lorax

Prunes finished git worktrees under `.claude/worktrees/`, and refuses to touch work
that exists nowhere else.

Script: `~/.claude/hooks/lorax.sh`. It also runs automatically at every session
start, self-throttled to one PR pass per hour per repo. This skill is the manual
trigger, and `--report` here ignores that throttle.

## The one criterion

Remove a worktree only when its work is **recoverable without it**. Not age, not
cleanliness - recoverability. It removes only when the PR is **MERGED**, there are
no *tracked* edits, and the last commit is over a day old. Capped at 10 per run.
**It never deletes a branch.**

Ancestry lies here: squash-merged branch commits never become ancestors of the
default branch, so `git branch --merged` misses almost everything. Merged-PR state
from `gh` is the only truth, which is why it needs the network.

## Verbs

Always run from inside the target repo, or aim it with `--repo <dir>`.

| The user wants | Run |
|---|---|
| See what would go, change nothing | `sh ~/.claude/hooks/lorax.sh --report` |
| Actually prune | `sh ~/.claude/hooks/lorax.sh` |
| Another checkout | `sh ~/.claude/hooks/lorax.sh --repo /path/to/repo --report` |
| Animation on / off / status | `sh ~/.claude/hooks/lorax.sh --anim on` \| `off` \| (no arg) |

**Default to `--report` first.** Show the user what it holds and why, and only run
the real prune if they confirm or clearly asked to prune outright.

## Reading the output

One line. `Would prune`/`Pruned` names what is going, then every hold category with
its reason. The interesting half is what it **refuses** to cut:

- `HELD ... no merged PR` - may hold commits on no other disk. **Push before removing.**
- `Kept ... merged-but-dirty` - tracked edits. Look before deleting.
- `Kept ... open PR` / `closed unmerged` - your call, never automatic.
- `Not registered as worktrees` - phantom directories git does not know about.
  Never auto-deleted; inspect by hand.

Relay these to the user rather than only the prune count - a held branch with
unpushed commits is the one thing that actually needs a human.

## Scope and safety

- Skips any repo with no `.claude/worktrees/` directory.
- **Defers to a repo-local `.claude/hooks/lorax.sh`** if one exists, so a repo with
  its own tuned copy is never pruned twice. `pendo-io/rex` has one.
- Exits silently with no `gh`, no `origin` remote, or no network - no PR truth means
  nothing safe to decide, so it holds everything.
- Never runs from inside a worktree.

## Animation

An opt-in truffula animation plays in a small native panel when a run actually
removes something. Gated on `~/.claude/lorax-anim-on`; off by default. A `--report`
never animates, because it cut nothing.

To demo it without waiting for a real prune, feed `--anim-prep` tab-separated
`<1|0>\t<name>\t<reason>` lines (1 = doomed) and open the result:

```sh
printf '1\tsome-branch\tPR #123 merged - work is in main\n0\tother\tPR still open\n' \
  | sh ~/.claude/hooks/lorax.sh --anim-prep ~/.claude/hooks/lorax-anim.html /tmp/lorax-demo.html
sh ~/.claude/hooks/lorax-open.sh /tmp/lorax-demo.html 220 130
```
