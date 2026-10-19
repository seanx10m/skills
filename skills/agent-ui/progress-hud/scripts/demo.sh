#!/usr/bin/env bash
# demo.sh - self-check: force the HUD on, walk a fake 5-step effort so you can
# watch the bar move, then close. Restores the prior global toggle.
set -euo pipefail
unset CLAUDE_CODE_SESSION_ID   # force the shared singleton feed path for a deterministic self-check
CLI="$(cd "$(dirname "$0")" && pwd)/progress-hud"
had_global=0; [ -f "$HOME/.progress-hud/enabled" ] && had_global=1

"$CLI" on >/dev/null
"$CLI" start "progress-hud demo" --total 5 --phase "step 1" --detail "starting up"
for i in 1 2 3 4 5; do
  sleep 1.2
  "$CLI" update --done "$i" --phase "step $i" --detail "did unit $i"
done
"$CLI" done
sleep 1

# restore toggle
if [ "$had_global" -eq 0 ]; then "$CLI" off >/dev/null; fi
echo "demo complete."

# sanity: feed reached done=5/total=5
python3 - "$HOME/.progress-hud/current.json" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    assert d.get("done") == 5 and d.get("total") == 5, d
    print("OK: feed reached 5/5, state=%s" % d.get("state"))
except FileNotFoundError:
    print("OK: feed cleared (HUD closed on done)")
PY
