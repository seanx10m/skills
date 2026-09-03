#!/bin/sh
# lorax - speaks for the trees. Prunes finished worktrees, and refuses to touch
# work that exists nowhere else.
#
# THE ONE CRITERION: prune a worktree only when its work is recoverable without
# it. Not age, not cleanliness - recoverability.
#
# Deliberately conservative. Everything it will not decide, it reports.
#   removes  : worktree whose PR is MERGED, no tracked edits, older than a day
#   reports  : open PRs, closed-unmerged PRs, unpushed branches, dirty merged
#              worktrees, phantom directories
#   never    : deletes a branch, or any worktree with commits only on this disk
#
# NOTE ancestry lies here: many repos squash-merge, so branch commits never become
# ancestors of main and `git branch --merged` catches ~3 of 38 landed branches.
# PR state is the only truth. That is why this needs `gh` and a throttle.
#
# Usage: lorax.sh [--report]     --report never removes anything
#        lorax.sh --anim [on|off] toggle or print the truffula animation
set -u

hooks=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
self="$hooks/$(basename -- "$0")"
anim_flag="$HOME/.claude/lorax-anim-on"     # sentinel, matching ~/.claude/sound-on
anim_tmpl="$hooks/lorax-anim.html"

# --- toggle and internal modes. Both exit before any pruning can happen.
case "${1:-}" in
  --anim)
    case "${2:-}" in
      on)  mkdir -p "$HOME/.claude" && : > "$anim_flag"; echo "LORAX: animation on" ;;
      off) rm -f "$anim_flag"; echo "LORAX: animation off" ;;
      "")  if [ -f "$anim_flag" ]; then echo "on"; else echo "off"; fi ;;
      *)   echo "usage: $(basename -- "$0") --anim [on|off]" >&2; exit 2 ;;
    esac
    exit 0 ;;
  --anim-prep)
    # Internal: stdin is "<1|0>\t<name>\t<reason>" per line, 1 = doomed. Writes $3
    # from template $2. Split out so the test can exercise it without a browser.
    # python3, not sed: the names carry quotes and slashes that only a real JSON
    # encoder gets right. Program is -c so stdin stays free for the feed.
    [ -f "${2:-}" ] || exit 3
    python3 -c '
import json, os, re, sys
tmpl, out = sys.argv[1], sys.argv[2]
trees = []
for line in sys.stdin:
    line = line.rstrip("\n")
    if not line:
        continue
    if "\t" in line:
        parts = line.split("\t", 2)      # split(,2) so a reason may hold tabs
        flag = parts[0]
        name = parts[1] if len(parts) > 1 else ""
        reason = parts[2] if len(parts) > 2 else ""
    else:
        flag, _, name = line.partition(" ")   # legacy 2-field form, no reason
        reason = ""
    if name:
        trees.append({"name": name, "doomed": flag == "1", "reason": reason})
doomed = [t for t in trees if t["doomed"]]
held = [t for t in trees if not t["doomed"]]
sel = doomed + held[: max(0, 14 - len(doomed))]   # short animation beats a full census
src = open(tmpl).read()
# ponytail: assumes the default value at the marker holds no ";". Ceiling is a
# template edit, not user data - injected JSON never round-trips through this.
new, n = re.subn(r"(/\*__TREES__\*/)[^;]*;",
                 lambda m: m.group(1) + " " + json.dumps(sel) + ";", src, count=1)
if not n:
    sys.exit(3)          # marker gone: caller skips the animation, never fails
# The repo name. Optional by design: an older template has no marker and the
# page falls back on its own, so this must never be able to fail the run.
new = re.sub(r"(/\*__REPO__\*/)[^;]*;",
             lambda m: m.group(1) + " " + json.dumps(os.environ.get("LORAX_REPO", "")) + ";",
             new, count=1)
open(out, "w").write(new)
' "$2" "${3:-}" || exit 3
    exit 0 ;;
esac

# --- global build: the repo comes from the working directory, not from where
# this script lives (it lives in ~/.claude/hooks and serves every repo).
# --repo <dir> aims it at a checkout explicitly; the skill uses that.
[ "${1:-}" = "--repo" ] && { cd -- "${2:-.}" 2>/dev/null || exit 0; shift 2; }

root=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || exit 0
root=$(CDPATH= cd -- "$root/.." && pwd -P)   # git-common-dir is <main>/.git even from a worktree
case "$root" in */.claude/worktrees/*) exit 0 ;; esac

# A repo that does not use .claude/worktrees is none of lorax's business, and a
# repo carrying its own tuned copy owns itself - defer, never run twice.
[ -d "$root/.claude/worktrees" ] || exit 0
[ -f "$root/.claude/hooks/lorax.sh" ] && exit 0

wt_dir="$root/.claude/worktrees"
stamp="$root/.claude/.lorax-stamp"
report="$root/.claude/.lorax-report"
THROTTLE_HOURS=1         # the ~5s gh call, at most once an hour per checkout
MAX_REMOVALS=10          # a bug cannot wipe the board in one run
MIN_AGE_HOURS=24         # never touch something you were using this morning

dry=0
[ "${1:-}" = "--report" ] && dry=1

# --- tier 1: free, local, no judgment. Only drops registry entries whose
# directory is already gone, so there is nothing to lose. Always runs.
git -C "$root" worktree prune >/dev/null 2>&1

[ -d "$wt_dir" ] || exit 0

# --- tier 2: throttled PR pass.
if [ "$dry" -eq 0 ] && [ -f "$stamp" ]; then
  cutoff=$(( THROTTLE_HOURS * 60 ))
  if [ -n "$(find "$stamp" -mmin -"$cutoff" 2>/dev/null)" ]; then
    [ -s "$report" ] && cat "$report"
    exit 0
  fi
fi

command -v gh >/dev/null 2>&1 || exit 0
# The repo is whatever $root's origin points at - resolved, not assumed, so one
# copy serves every checkout. No remote means no PR truth, so there is nothing
# safe to decide: hold everything by exiting.
slug=$(git -C "$root" config --get remote.origin.url 2>/dev/null) || exit 0
slug=${slug#*github.com[:/]}; slug=${slug%.git}
case "$slug" in ""|*" "*|/*) exit 0 ;; esac

# 3000 > every PR a repo of this size has. A capped list is not a missing PR: a
# branch whose PR fell outside the window reads as "no PR" and gets HELD
# forever. Costs ~5s, once per THROTTLE_HOURS.
prs=$(gh pr list --repo "$slug" --state all --limit 3000 \
        --json headRefName,state,number --jq '.[] | [.headRefName,.state,.number] | @tsv' 2>/dev/null) || exit 0
[ -n "$prs" ] || exit 0        # offline or rate-limited: do nothing, try later

# main vs master vs anything else - read it, never assume.
defbranch=$(git -C "$root" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null)
defbranch=${defbranch#origin/}
[ -n "$defbranch" ] || defbranch=main

removed=0 kept_open=0 kept_local=0 kept_dirty=0 kept_closed=0 kept_fresh=0 kept_cap=0 phantom=""
names=""

# Animation feed, one "<1|0>\t<name>\t<reason>" line each. Held names are collected
# too, with their reason: what lorax refuses to cut is the interesting half.
# Tab-separated because every reason contains spaces.
TAB=$(printf '\t')
doom_feed="" held_feed=""
hold() { held_feed="${held_feed}0$TAB$1$TAB$2
"; }

for wt in "$wt_dir"/*; do
  [ -d "$wt" ] || continue
  name=$(basename -- "$wt")

  # A directory git does not know about is not a worktree. Report, never delete:
  # it may hold files nothing else has.
  if ! git -C "$root" worktree list --porcelain | grep -qx "worktree $wt"; then
    phantom="$phantom $name"
    continue
  fi

  branch=$(git -C "$wt" rev-parse --abbrev-ref HEAD 2>/dev/null) || continue
  [ "$branch" = "HEAD" ] && { kept_local=$((kept_local + 1)); hold "$name" "detached HEAD - not a feature branch"; continue; }
  [ "$branch" = "$defbranch" ] && { kept_local=$((kept_local + 1)); hold "$name" "on $defbranch - not a feature branch"; continue; }

  hit=$(printf '%s\n' "$prs" | awk -F'\t' -v b="$branch" '$1==b{print $2" "$3; exit}')
  state=${hit%% *}
  num=""; case "$hit" in *" "*) num=${hit#* } ;; esac
  # A reason must never read "PR #" with nothing after it, so anything that is
  # not a plain number degrades to the bare noun.
  case "$num" in ''|*[!0-9]*) num="" ;; esac
  pr="PR"; [ -n "$num" ] && pr="PR #$num"

  case "$state" in
    MERGED) ;;
    OPEN)   kept_open=$((kept_open + 1));   hold "$name" "$pr still open"; continue ;;
    CLOSED) kept_closed=$((kept_closed + 1)); hold "$name" "$pr closed unmerged - your call"; continue ;;
    *)      kept_local=$((kept_local + 1)); hold "$name" "no PR - commits may exist only on this disk"; continue ;;
  esac

  # Merged, but hold anything with tracked edits - untracked build junk is fine.
  if [ -n "$(git -C "$wt" status --porcelain --untracked-files=no 2>/dev/null)" ]; then
    kept_dirty=$((kept_dirty + 1))
    hold "$name" "merged, but has uncommitted tracked edits"
    continue
  fi

  # Age by last commit, not directory mtime - a build or a git op touches the
  # directory without meaning you were working in it.
  last=$(git -C "$wt" log -1 --format=%ct 2>/dev/null || echo 0)
  now=$(date +%s)
  if [ "$last" -gt 0 ] && [ $(( (now - last) / 3600 )) -lt "$MIN_AGE_HOURS" ]; then
    kept_fresh=$((kept_fresh + 1)); hold "$name" "merged, but committed to in the last 24h"; continue
  fi
  if [ "$removed" -ge "$MAX_REMOVALS" ]; then
    kept_cap=$((kept_cap + 1)); hold "$name" "ready, but over the per-run cap of $MAX_REMOVALS"; continue
  fi

  if [ "$dry" -eq 1 ]; then
    removed=$((removed + 1)); names="$names $name"
  elif git -C "$root" worktree remove "$wt" >/dev/null 2>&1; then
    removed=$((removed + 1)); names="$names $name"   # branch deliberately left alone
    doom_feed="${doom_feed}1$TAB$name$TAB$pr merged - work is in main
"
  fi
done

verb="Pruned"; [ "$dry" -eq 1 ] && verb="Would prune"
out="LORAX: $verb $removed finished worktree(s) (PR merged, no tracked edits)."
[ -n "$names" ] && out="$out$names."
[ "$kept_open" -gt 0 ]   && out="$out Kept $kept_open with an open PR."
[ "$kept_dirty" -gt 0 ]  && out="$out Kept $kept_dirty merged-but-dirty - has tracked edits, look before deleting."
[ "$kept_closed" -gt 0 ] && out="$out Kept $kept_closed whose PR was closed unmerged."
[ "$kept_local" -gt 0 ]  && out="$out HELD $kept_local with no merged PR - these may hold commits that exist on no other disk; push the branch before removing."
[ "$kept_fresh" -gt 0 ]  && out="$out Kept $kept_fresh merged but committed to in the last day."
[ "$kept_cap" -gt 0 ]    && out="$out $kept_cap more are ready but over the per-run cap of $MAX_REMOVALS - next run takes them."
[ -n "$phantom" ]        && out="$out Not registered as worktrees (inspect by hand, never auto-deleted):$phantom."

if [ "$dry" -eq 0 ]; then
  printf '%s\n' "$out" > "$report"
  : > "$stamp"
fi
printf '%s\n' "$out"

# --- the truffula animation. Opt-in, backgrounded, and every failure swallowed:
# it is a view of a decision already made, so it must never shape or delay one.
# A dry run has cut nothing and a throttled run already exited, so neither lands here.
if [ "$dry" -eq 0 ] && [ -n "$doom_feed" ] && [ -f "$anim_flag" ] && [ -f "$anim_tmpl" ]; then
  (
    run="${TMPDIR:-/tmp}/lorax-run-$$.html"
    printf '%s' "$doom_feed$held_feed" \
      | LORAX_REPO="$(basename -- "$root")" sh "$self" --anim-prep "$anim_tmpl" "$run" || exit 0
    # A small native AppKit panel, like progress-hud. lorax-open degrades to a
    # browser on its own, so this line cannot fail.
    sh "$hooks/lorax-open.sh" "$run" 220 130 >/dev/null 2>&1 || true
  ) >/dev/null 2>&1 &
fi
