import json, os, sys
op, d = sys.argv[1], sys.argv[2]; a = sys.argv[3:]
def save(p, g):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p + ".tmp", "w").write(json.dumps(g, indent=1)); os.replace(p + ".tmp", p)
if op == "new":
    name, title, rest = a[0], a[1], a[2:]; steps = []; pct = None
    i = 0
    while i < len(rest):
        if rest[i] == "--dir": d = rest[i + 1]; i += 2; continue
        if rest[i] == "--percent": pct = float(rest[i + 1]); i += 2; continue
        sid, _, lab = rest[i].partition(":"); steps.append({"id": sid, "label": lab or sid, "state": "todo"}); i += 1
    g = {"title": title, "steps": steps}
    if pct is not None: g["percent"] = pct
    save(os.path.join(d, name + ".json"), g); print("wrote", os.path.join(d, name + ".json"))
else:
    p = os.path.join(d, a[0] + ".json"); g = json.load(open(p))
    if op == "step":
        hit = [s for s in g.get("steps", []) if s["id"] == a[1]]
        if not hit: sys.exit("no step " + a[1])
        hit[0]["state"] = a[2]
    elif op == "percent": g["percent"] = float(a[1])
    save(p, g)
