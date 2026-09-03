#!/bin/sh
# Wire lorax into ~/.claude/settings.json as a SessionStart hook. Idempotent.
# Usage: sh install.sh            (install)
#        sh install.sh --uninstall
set -eu

src=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)/scripts/lorax.sh
[ -f "$src" ] || { echo "missing $src" >&2; exit 1; }
chmod +x "$(dirname "$src")"/*.sh

mode=install
case "${1:-}" in --uninstall) mode=uninstall ;; esac

cfg="$HOME/.claude/settings.json"
[ -f "$cfg" ] || { mkdir -p "$(dirname "$cfg")"; echo '{}' > "$cfg"; }

tmp=$(mktemp)
MODE=$mode SRC=$src python3 - "$cfg" > "$tmp" <<'PY'
import json, os, sys
cfg = sys.argv[1]
d = json.load(open(cfg))
hooks = d.setdefault("hooks", {})

# Drop any existing lorax entry, wherever it points, so this never doubles up.
out = []
for e in hooks.get("SessionStart", []):
    e = dict(e)
    e["hooks"] = [h for h in e.get("hooks", []) if "lorax.sh" not in h.get("command", "")]
    if e["hooks"]:
        out.append(e)
if out:
    hooks["SessionStart"] = out
else:
    hooks.pop("SessionStart", None)

if os.environ["MODE"] == "install":
    hooks.setdefault("SessionStart", []).append({
        "matcher": "",
        "hooks": [{"type": "command",
                   "command": 'sh "%s"' % os.environ["SRC"],
                   "timeout": 20}],
    })

json.dump(d, sys.stdout, indent=2)
sys.stdout.write("\n")
PY
mv "$tmp" "$cfg"

echo "$mode complete: $cfg"
[ "$mode" = install ] && echo "check: sh $src --report"
exit 0
