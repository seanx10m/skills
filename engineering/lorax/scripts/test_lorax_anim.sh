#!/bin/sh
# Runnable check for the lorax animation wiring. sh .claude/hooks/test_lorax_anim.sh
# Opens no browser and removes no worktrees: --anim* modes exit before pruning,
# and --report is a dry run.
set -u

lorax=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)/lorax.sh
flag="$HOME/.claude/lorax-anim-on"
tmp="${TMPDIR:-/tmp}/lorax-anim-test-$$"
fail=0

# Whatever state the user left the toggle in is theirs, not ours.
had_flag=0; [ -f "$flag" ] && had_flag=1
restore() {
  if [ "$had_flag" -eq 1 ]; then mkdir -p "$HOME/.claude" && : > "$flag"; else rm -f "$flag"; fi
  rm -rf "$tmp"
}
trap restore EXIT INT TERM

check() { # name expected actual
  if [ "$2" = "$3" ]; then
    echo "ok   $1"
  else
    echo "FAIL $1 - expected [$2], got [$3]"
    fail=1
  fi
}

mkdir -p "$tmp"

# --- the sticky toggle
sh "$lorax" --anim on >/dev/null 2>&1
got=absent; [ -f "$flag" ] && got=present
check "--anim on creates the sentinel" present "$got"
check "--anim reports on" on "$(sh "$lorax" --anim 2>&1)"

sh "$lorax" --anim off >/dev/null 2>&1
got=absent; [ -f "$flag" ] && got=present
check "--anim off removes the sentinel" absent "$got"
check "--anim reports off" off "$(sh "$lorax" --anim 2>&1)"

# --- substitution into a template carrying the marker
tmpl="$tmp/tmpl.html"
out="$tmp/out.html"
{
  echo '<html><script>'
  echo '  const TREES = /*__TREES__*/ [{"name":"default","doomed":true}];'
  echo '</script></html>'
} > "$tmpl"

# Names deliberately carry a quote, a backslash and a slash - sed bait. Reasons
# carry spaces and a "#", which is why the feed is tab-separated. The last line
# is the legacy 2-field form, which must still parse.
{
  printf '1\t%s\t%s\n' 'feat/anim-doomed' 'PR #42 merged - work is in main'
  printf '1\t%s\t%s\n' 'quote"name'      'PR merged - work is in main'
  printf '0\t%s\t%s\n' 'feat/held-open'   'PR #7 still open'
  printf '0\t%s\t%s\n' 'back\slash'      'merged, but has uncommitted tracked edits'
  printf '0 %s\n'      'legacy-no-tabs'
} | sh "$lorax" --anim-prep "$tmpl" "$out"
check "--anim-prep exits clean" 0 "$?"

line=$(grep 'const TREES' "$out" 2>/dev/null || true)
json=$(printf '%s' "$line" | sed -e 's/^.*\/\*__TREES__\*\///' -e 's/;[^;]*$//')

# one field off one tree, by name - assertions read as the data, not as greps
field() {
  printf '%s' "$json" | python3 -c "
import json, sys
hit = [t for t in json.load(sys.stdin) if t['name'] == sys.argv[1]]
print(hit[0][sys.argv[2]] if hit else '<missing>')" "$1" "$2"
}

got=no;  printf '%s' "$json" | python3 -m json.tool >/dev/null 2>&1 && got=yes
check "injected TREES is valid JSON" yes "$got"

got=no; printf '%s' "$line" | grep -q 'feat/anim-doomed' && got=yes
check "doomed name is injected" yes "$got"
got=no; printf '%s' "$line" | grep -q 'feat/held-open' && got=yes
check "held name is injected too" yes "$got"
got=no; printf '%s' "$line" | grep -q 'default' && got=yes
check "template default is replaced" no "$got"
check "template itself is untouched" 1 \
  "$(grep -c 'default' "$tmpl" | tr -d ' ')"

# --- the reason field
check "reason with spaces survives intact" \
  "PR #42 merged - work is in main" "$(field 'feat/anim-doomed' reason)"
check "a held tree carries its reason too" \
  "PR #7 still open" "$(field 'feat/held-open' reason)"
check "a reason with a comma survives" \
  "merged, but has uncommitted tracked edits" "$(field 'back\slash' reason)"
check "numberless PR degrades to the bare noun" \
  "PR merged - work is in main" "$(field 'quote"name' reason)"
check "legacy tab-less line still parses" "legacy-no-tabs" "$(field 'legacy-no-tabs' name)"
check "legacy line gets an empty reason" "" "$(field 'legacy-no-tabs' reason)"
check "legacy flag still read" "False" "$(field 'legacy-no-tabs' doomed)"

# doomed first, then held - the animation cuts before it spares
got=$(printf '%s' "$json" | python3 -c 'import json,sys; print(",".join(str(t["doomed"]) for t in json.load(sys.stdin)))')
check "doomed sort first, all five kept" "True,True,False,False,False" "$got"

# --- a missing marker is a skip, not a failure
plain="$tmp/plain.html"; echo '<html>no marker</html>' > "$plain"
printf '1 x\n' | sh "$lorax" --anim-prep "$plain" "$tmp/never.html" >/dev/null 2>&1
check "missing marker exits 3" 3 "$?"
got=absent; [ -f "$tmp/never.html" ] && got=present
check "missing marker writes nothing" absent "$got"

# --- a missing template is a skip too
printf '1 x\n' | sh "$lorax" --anim-prep "$tmp/nope.html" "$tmp/never2.html" >/dev/null 2>&1
check "missing template exits 3" 3 "$?"

# --- the dry run never animates, even with the toggle on
sh "$lorax" --anim on >/dev/null 2>&1
before=$(ls "${TMPDIR:-/tmp}"/lorax-run-*.html 2>/dev/null | wc -l | tr -d ' ')
rep=$(sh "$lorax" --report 2>&1)
# Empty is legal: no gh, offline, or no worktrees at all. Anything else must be the report.
got=no
[ -z "$rep" ] && got=yes
printf '%s' "$rep" | grep -q '^LORAX: Would prune' && got=yes
check "--report prints its one-line report (or nothing without gh)" yes "$got"
after=$(ls "${TMPDIR:-/tmp}"/lorax-run-*.html 2>/dev/null | wc -l | tr -d ' ')
check "--report wrote no run file" "$before" "$after"

exit $fail
