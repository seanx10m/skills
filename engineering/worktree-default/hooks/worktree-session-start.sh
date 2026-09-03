#!/bin/sh
# SessionStart: tell the session to open its own worktree, fast-forward the
# pinned root, and (if lorax.sh is installed alongside) let it prune what has
# finished. Session start IS the schedule - lorax self-throttles.
set -u

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
root=$(CDPATH= cd -- "$here/../.." && pwd -P)
case "$root" in
  */.claude/worktrees/*) exit 0 ;;   # this session is already in a worktree
esac

# Default branch, from the remote rather than hardcoded.
def=$(git -C "$root" symbolic-ref -q --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')
[ -n "${def:-}" ] || def=$(git -C "$root" config --get init.defaultBranch 2>/dev/null)
[ -n "${def:-}" ] || def=main

sync=""
if git -C "$root" fetch origin "$def" -q 2>/dev/null; then
  behind=$(git -C "$root" rev-list --count "HEAD..origin/$def" 2>/dev/null || echo 0)
  if [ "${behind:-0}" -gt 0 ] 2>/dev/null; then
    if git -C "$root" checkout -q "origin/$def" -- 2>/dev/null; then
      sync=" Root checkout was $behind commit(s) behind origin/$def - fast-forwarded to origin/$def."
    else
      sync=" Root checkout is $behind commit(s) behind origin/$def and could not be fast-forwarded automatically (local changes?) - check by hand."
    fi
  fi
fi

msg="WORKTREE DEFAULT: this session is in the shared ROOT checkout.$sync Before your first file edit in this repo, call the EnterWorktree tool with a short task name - it branches off fresh origin/$def. If the user named an existing branch, git worktree add .claude/worktrees/<name> <branch> and EnterWorktree with that path instead. A PreToolUse hook denies writes under the root until you do. Read-only sessions (questions, reviews, log reads) need no worktree."

if [ -f "$here/lorax.sh" ]; then
  lorax=$(sh "$here/lorax.sh" 2>/dev/null)
  [ -n "$lorax" ] && msg="$msg

$lorax"
fi

jq -n --arg m "$msg" '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$m}}'
