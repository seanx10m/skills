#!/bin/sh
# PreToolUse guard (Bash): refuse `git checkout` / `git switch` in the SHARED
# ROOT checkout. Moving the root branch moves it for every concurrent session.
# File-path checkouts (`git checkout -- <path>`, `git checkout <ref> -- <path>`)
# are fine: they touch the tree, not HEAD.
set -u

payload=$(cat)
cmd=$(printf '%s' "$payload" | jq -r '.tool_input.command // empty')
[ -n "$cmd" ] || exit 0

gd=$(git rev-parse --git-dir 2>/dev/null) || exit 0
case "$gd" in */worktrees/*) exit 0 ;; esac

printf '%s' "$cmd" | grep -qE '(^|[^[:alnum:]_])git[[:space:]]+(checkout|switch)([[:space:]]|$)' || exit 0
printf '%s' "$cmd" | grep -qE 'git[[:space:]]+(checkout|switch)[[:space:]].*--' && exit 0

root=$(git rev-parse --show-toplevel 2>/dev/null || pwd -P)
jq -n --arg repo "$(basename "$root")" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: ("BLOCKED: this is the shared ROOT checkout of \($repo), used by multiple agent sessions. git checkout/switch here moves the branch for ALL of them. Work in your own worktree instead: call the EnterWorktree tool, or git worktree add .claude/worktrees/<name> -b <name> <default-branch> then EnterWorktree with that path. The root stays pinned. Disable via /hooks to override.")
  }
}'
