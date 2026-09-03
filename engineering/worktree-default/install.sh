#!/bin/sh
# Install the worktree-default hooks into a repo. Idempotent.
# Usage: sh install.sh [repo-path]   (default: cwd)
#        sh install.sh --uninstall [repo-path]
set -eu

src=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)/hooks
mode=install
case "${1:-}" in --uninstall) mode=uninstall; shift ;; esac
repo=${1:-$(pwd -P)}
repo=$(CDPATH= cd -- "$repo" && git rev-parse --show-toplevel)
case "$repo" in */.claude/worktrees/*) echo "refusing: $repo is a worktree, install into the root checkout" >&2; exit 1 ;; esac

dst="$repo/.claude/hooks"
cfg="$repo/.claude/settings.json"

if [ "$mode" = uninstall ]; then
  rm -f "$dst/worktree-guard.sh" "$dst/worktree-branch-guard.sh" "$dst/worktree-session-start.sh" "$dst/test_worktree_guard.sh"
else
  mkdir -p "$dst"
  for f in worktree-guard.sh worktree-branch-guard.sh worktree-session-start.sh; do
    cp "$src/$f" "$dst/$f"; chmod +x "$dst/$f"
  done
  cp "$src/../test_worktree_guard.sh" "$dst/test_worktree_guard.sh"
fi

[ -f "$cfg" ] || { mkdir -p "$(dirname "$cfg")"; echo '{}' > "$cfg"; }

# Merge (or strip) our three entries without disturbing anything else.
tmp=$(mktemp)
MODE=$mode python3 - "$cfg" > "$tmp" <<'PY'
import json, os, sys
p = sys.argv[1]
d = json.load(open(p))
hooks = d.setdefault("hooks", {})
P = '"${CLAUDE_PROJECT_DIR:-.}"/.claude/hooks'
MARK = "worktree-guard.sh", "worktree-branch-guard.sh", "worktree-session-start.sh"

def strip(event):
    out = []
    for e in hooks.get(event, []):
        e = dict(e)
        e["hooks"] = [h for h in e.get("hooks", [])
                      if not any(m in h.get("command", "") for m in MARK)]
        if e["hooks"]:
            out.append(e)
    if out:
        hooks[event] = out
    else:
        hooks.pop(event, None)

for ev in ("PreToolUse", "SessionStart"):
    strip(ev)

if os.environ["MODE"] == "install":
    hooks.setdefault("PreToolUse", []).extend([
        {"matcher": "Edit|Write|NotebookEdit",
         "hooks": [{"type": "command", "command": f'sh {P}/worktree-guard.sh', "timeout": 10}]},
        {"matcher": "Bash",
         "hooks": [{"type": "command", "command": f'sh {P}/worktree-branch-guard.sh', "timeout": 10}]},
    ])
    hooks.setdefault("SessionStart", []).append(
        {"matcher": "",
         "hooks": [{"type": "command", "command": f'sh {P}/worktree-session-start.sh', "timeout": 20}]})

json.dump(d, sys.stdout, indent=2)
sys.stdout.write("\n")
PY
mv "$tmp" "$cfg"

# Worktrees live inside the repo - keep them out of git.
ign="$repo/.claude/worktrees/"
if [ "$mode" = install ] && ! grep -qxF '.claude/worktrees/' "$repo/.gitignore" 2>/dev/null; then
  printf '.claude/worktrees/\n' >> "$repo/.gitignore"
fi

echo "$mode complete: $repo"
[ "$mode" = install ] && echo "check: sh $dst/test_worktree_guard.sh"
exit 0
