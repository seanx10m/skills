#!/bin/sh
# PreToolUse guard (Edit|Write|NotebookEdit): refuse writes into the SHARED ROOT
# checkout. Every session works in its own worktree; the root stays pinned.
#
# Allowed without argument:
#   - the session is already in a worktree (this script's own checkout is one)
#   - the target file lives outside this checkout (scratchpad, ~/.claude, ~/Desktop)
#   - the session has an explicit root pass: ~/.claude/wt-root-ok/<repo>/<session_id>
#
# ponytail: file writes only. Mutating Bash (sed -i, rm) is not covered - the
# sibling branch guard already pins the branch, which is the damage that
# actually spans sessions.
set -u

payload=$(cat)
f=$(printf '%s' "$payload" | jq -r '.tool_input.file_path // empty')
[ -n "$f" ] || exit 0

# The checkout that owns this hook. In a worktree session Claude runs the
# worktree's own copy, so the path itself is the discriminator.
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
case "$root" in
  */.claude/worktrees/*) exit 0 ;;   # already in a worktree - nothing to guard
esac
repo=$(basename "$root")

sid=$(printf '%s' "$payload" | jq -r '.session_id // empty')
[ -n "$sid" ] && [ -f "$HOME/.claude/wt-root-ok/$repo/$sid" ] && exit 0

case "$f" in
  /*) abs=$f ;;
  *)  abs="$(pwd -P)/$f" ;;
esac
case "$abs" in
  "$root"/.claude/worktrees/*) exit 0 ;;  # a worktree's files, not the root branch
  "$root"/*) ;;
  *) exit 0 ;;                       # outside the repo - not our business
esac

jq -n --arg f "$abs" --arg sid "$sid" --arg repo "$repo" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: ("BLOCKED: \($f) is in the SHARED ROOT checkout of \($repo). Every session works in its own worktree so the root branch never moves under another agent.\n\nDo one of these, then retry the write:\n1. Default - call the EnterWorktree tool with a short task name (it branches off the fresh default branch).\n2. The user named an existing branch - git worktree add .claude/worktrees/<name> <branch>, then EnterWorktree with that path.\n3. The user explicitly wants the root (a one-line doc fix, a hook edit) - run: mkdir -p ~/.claude/wt-root-ok/\($repo) && touch ~/.claude/wt-root-ok/\($repo)/\($sid)  ... which lifts the guard for THIS session only. Do not do this on your own initiative.")
  }
}'
