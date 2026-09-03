#!/bin/sh
# Runnable check for the worktree-default guards.
#   sh .claude/hooks/test_worktree_guard.sh
set -eu

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
guard="$here/worktree-guard.sh"
bguard="$here/worktree-branch-guard.sh"
root=$(CDPATH= cd -- "$here/../.." && pwd -P)
repo=$(basename "$root")
fail=0

# This is the template copy until install.sh puts it in <repo>/.claude/hooks/.
case "$here" in */.claude/hooks) ;; *)
  echo "skip: run the installed copy - sh <repo>/.claude/hooks/$(basename "$0")"; exit 0 ;;
esac

check() { # name expected(deny|allow) script payload
  # hooks run with cwd = the project dir; reproduce that
  out=$(cd "$root" && printf '%s' "$4" | sh "$3" 2>&1 || true)
  got=allow
  printf '%s' "$out" | grep -q '"deny"' && got=deny
  if [ "$got" = "$2" ]; then echo "ok   $1"
  else echo "FAIL $1 - expected $2, got $got"; fail=1; fi
}

check "in-repo write is denied" deny "$guard" \
  "{\"session_id\":\"t1\",\"tool_input\":{\"file_path\":\"$root/src/foo.py\"}}"
check "write outside the repo is allowed" allow "$guard" \
  '{"session_id":"t1","tool_input":{"file_path":"/tmp/scratch/note.md"}}'
check "no file_path is allowed" allow "$guard" \
  '{"session_id":"t1","tool_input":{"command":"ls"}}'
check "worktree path is allowed" allow "$guard" \
  "{\"session_id\":\"t1\",\"tool_input\":{\"file_path\":\"$root/.claude/worktrees/x/src/foo.py\"}}"

mkdir -p "$HOME/.claude/wt-root-ok/$repo"
touch "$HOME/.claude/wt-root-ok/$repo/pass-test"
check "session with a root pass is allowed" allow "$guard" \
  "{\"session_id\":\"pass-test\",\"tool_input\":{\"file_path\":\"$root/src/foo.py\"}}"
check "another session is still denied" deny "$guard" \
  "{\"session_id\":\"other\",\"tool_input\":{\"file_path\":\"$root/src/foo.py\"}}"
rm -f "$HOME/.claude/wt-root-ok/$repo/pass-test"

check "git checkout in root is denied" deny "$bguard" \
  '{"tool_input":{"command":"git checkout -b feature"}}'
check "git switch in root is denied" deny "$bguard" \
  '{"tool_input":{"command":"git switch main"}}'
check "path checkout is allowed" allow "$bguard" \
  '{"tool_input":{"command":"git checkout origin/main -- README.md"}}'
check "unrelated bash is allowed" allow "$bguard" \
  '{"tool_input":{"command":"git status"}}'

[ "$fail" -eq 0 ] && echo "all pass" || echo "FAILURES"
exit "$fail"
