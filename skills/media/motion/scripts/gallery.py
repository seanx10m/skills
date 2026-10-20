#!/usr/bin/env python3
"""Build gallery.html for a folder of motion projects (each <sub>/renders/loop.mp4).

Usage: gallery.py <parent-dir> [title] [accent-hex]
Captions come from <sub>/CAPTION.txt (line 1 = name, line 2 = one-sentence description).
"""
import html
import json
import sys
from pathlib import Path

parent = Path(sys.argv[1]).resolve()
title = sys.argv[2] if len(sys.argv) > 2 else "Motion"
accent = sys.argv[3] if len(sys.argv) > 3 else "#E8E6E1"
items = []
for sub in sorted(p for p in parent.iterdir() if p.is_dir() and not p.name.startswith(("_", "."))):
    mp4 = next((m for m in [sub / "renders" / "loop.mp4", *sorted((sub / "renders").glob("*.mp4"))] if m.exists()), None) if (sub / "renders").exists() else None
    cap = (sub / "CAPTION.txt").read_text().splitlines() if (sub / "CAPTION.txt").exists() else [sub.name, ""]
    items.append({"src": str(mp4.relative_to(parent)) if mp4 else "", "name": cap[0], "desc": cap[1] if len(cap) > 1 else ""})

page = f"""<!doctype html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title><style>
:root{{--bg:#111214;--panel:#1B1C1F;--line:#3A3B40;--text:#F2F1EE;--dim:#9A9A9F;--pink:{accent}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,sans-serif;padding:32px 16px}}
h1{{font:700 32px system-ui,sans-serif;max-width:1800px;margin:0 auto 24px}}h1 span{{color:var(--pink)}}
.grid{{max-width:1800px;margin:0 auto;display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,560px),1fr));gap:20px}}
figure{{margin:0;background:var(--panel);border:1px solid var(--line);border-radius:16px;overflow:hidden;cursor:zoom-in}}
video{{display:block;width:100%;aspect-ratio:16/9;background:#000}}figcaption{{padding:14px 18px}}
.n{{font:600 18px system-ui,sans-serif}}.d{{color:var(--dim);font-size:14px;margin-top:4px;line-height:1.45}}
.missing{{aspect-ratio:16/9;display:flex;align-items:center;justify-content:center;color:var(--dim)}}
.full{{position:fixed;inset:0;background:rgba(10,11,14,.96);display:none;align-items:center;justify-content:center;cursor:zoom-out}}
.full video{{width:min(96vw,170vh);height:auto;border-radius:12px}}.full.on{{display:flex}}
</style></head><body><h1>{html.escape(title)} <span>options</span></h1><div class="grid" id="g"></div>
<div class="full" id="f"><video id="fv" muted loop playsinline controls></video></div>
<script>
const ITEMS={json.dumps(items)};const g=document.getElementById("g"),f=document.getElementById("f"),fv=document.getElementById("fv");
for(const it of ITEMS){{const el=document.createElement("figure");
el.innerHTML=(it.src?`<video src="${{it.src}}" muted loop autoplay playsinline></video>`:`<div class="missing">Still rendering</div>`)+`<figcaption><div class="n"></div><div class="d"></div></figcaption>`;
el.querySelector(".n").textContent=it.name;el.querySelector(".d").textContent=it.desc;
if(it.src)el.onclick=()=>{{fv.src=it.src;f.classList.add("on");fv.play()}};g.appendChild(el)}}
f.onclick=e=>{{if(e.target===f){{f.classList.remove("on");fv.pause()}}}};addEventListener("keydown",e=>{{if(e.key==="Escape"){{f.classList.remove("on");fv.pause()}}}});
</script></body></html>"""
(parent / "gallery.html").write_text(page)
print(parent / "gallery.html")
