#!/usr/bin/env python3
"""
mdview — render a Markdown design doc (with embedded ```mermaid) into a single
self-contained HTML file and open it in the browser. No server, no file:// fetch:
the Markdown and the brand/Claude branding are embedded directly, so it opens with
plain file://. Mermaid + marked + highlight.js load from CDN (needs internet).

Usage:
    mdview.py /path/to/doc.md            # render + open a single file
    mdview.py /path/to/folder            # render + open every .md under folder,
                                          # with a file sidebar to explore them
    mdview.py deck.md --deck             # deck mode: slides from one .md
    mdview.py deck.md --paper paper.md   # deck + split-screen paper pane
                                          # (both via the pd-slides skill)
    mdview.py /path/to/doc.md --no-open  # just write the .html next to it
    mdview.py /path/to/doc.md -o /tmp/out.html

Features baked into the rendered page:
    - Select text to comment. Threads live as cards in a Google-Docs-style right
      rail (always visible, no pins to click open), each quoting the text it was
      left on so "Copy notes" reads as quote + note, not a bare line number.
    - Folder mode adds a left sidebar to switch between files without re-running
      the tool.

Branding/header shows: Claude glyph, brand logo, doc title, repo + git branch.
Styled to echo the talk-to-me panel (light, rounded, brand-flavored).
"""
import base64, html, json, os, re, subprocess, sys, webbrowser

SKILL_URL = ""
DECK_SKILL_URL = ""
# Vendored, not CDN: plus mode is a local server and has to work on a plane. The asset
# path tells Excalidraw where to find its own fonts and worker chunk.
PLUS_HEAD = """<script>window.EXCALIDRAW_ASSET_PATH="/assets/";</script>
<script src="/assets/react.js"></script>
<script src="/assets/react-dom.js"></script>
<script src="/assets/excalidraw.js"></script>
<script src="/assets/mermaid-to-excalidraw.js"></script>"""
ASSET_DIR = os.path.expanduser("~/.claude/skills/talk-to-me/assets")
# This skill's own assets take precedence, so an install carries them.
SKILL_ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
IGNORE_DIRS = {".git", "node_modules", ".previews", "__pycache__", ".venv", "venv"}
MAX_BYTES = 1_000_000  # ponytail: per-file cap in folder mode so one huge asset can't bloat the page

MD_EXT = {".md", ".markdown", ".mdx"}
IMG_EXT = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
           ".gif": "image/gif", ".svg": "image/svg+xml", ".webp": "image/webp"}
NAME_LANG = {"Dockerfile": "dockerfile", "Makefile": "makefile", "Procfile": "bash"}
EXT_LANG = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript", ".ts": "typescript", ".tsx": "typescript",
    ".sh": "bash", ".bash": "bash", ".zsh": "bash", ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".toml": "ini", ".go": "go", ".rs": "rust", ".java": "java", ".rb": "ruby", ".css": "css", ".scss": "scss",
    ".html": "xml", ".sql": "sql", ".c": "c", ".cpp": "cpp", ".h": "c", ".hpp": "cpp", ".swift": "swift",
    ".kt": "kotlin", ".php": "php", ".lua": "lua", ".xml": "xml", ".ps1": "powershell",
    ".txt": None, ".env": "bash", ".cfg": "ini", ".ini": "ini",
}

def b64_asset(name):
    for d in (SKILL_ASSET_DIR, ASSET_DIR):
        try:
            with open(os.path.join(d, name), "rb") as f:
                return base64.b64encode(f.read()).decode()
        except Exception:
            continue
    return ""

def git_info(path):
    d = path if os.path.isdir(path) else os.path.dirname(os.path.abspath(path))
    def run(args):
        try:
            return subprocess.check_output(args, cwd=d, stderr=subprocess.DEVNULL).decode().strip()
        except Exception:
            return ""
    branch = run(["git", "branch", "--show-current"]) or run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    root = run(["git", "rev-parse", "--show-toplevel"])
    repo = os.path.basename(root) if root else ""
    return repo, branch

def _fm_cell(v):
    if isinstance(v, dict):
        v = ", ".join(f"{k}: {_fm_cell(x)}" for k, x in v.items())
    elif isinstance(v, (list, tuple)):
        v = ", ".join(_fm_cell(x) for x in v)
    elif isinstance(v, bool) or v is None:
        v = {True: "true", False: "false", None: ""}[v]
    return " ".join(str(v).split()).replace("|", "\\|")

def fm_table(fm):
    """YAML frontmatter -> a markdown table, so long values wrap instead of scrolling."""
    try:
        import yaml
        data = yaml.safe_load(fm)
    except Exception:
        return None
    if not isinstance(data, dict) or not data:
        return None
    rows = "\n".join(f"| {_fm_cell(k)} | {_fm_cell(v)} |" for k, v in data.items())
    return f"| Field | Value |\n| --- | --- |\n{rows}\n"

def strip_frontmatter(md, fallback_name, emit_table=True):
    """Pulls YAML frontmatter name:/title: (else first H1, else filename).

    The frontmatter is re-emitted as a table at the top of the body so it stays
    visible in the render (skill metadata is content, not noise).
    """
    fm_title = None
    if md.lstrip().startswith("---"):
        s = md.lstrip()
        end = s.find("\n---", 3)
        if end != -1:
            fm = s[3:end]
            for line in fm.splitlines():
                ls = line.strip()
                if ls.lower().startswith(("name:", "title:")):
                    fm_title = ls.split(":", 1)[1].strip().strip('"\'')
            nl = s.find("\n", end + 1)
            md = s[nl + 1:] if nl != -1 else ""
            if emit_table:
                block = fm_table(fm) or ("```yaml\n" + fm.strip("\n") + "\n```\n")
                md = block + "\n" + md
    title = fm_title or fallback_name
    if not fm_title:
        for line in md.splitlines():
            if line.startswith("# "):
                title = line[2:].strip(); break
    return title, md

# A thematic break only splits slides when a blank line sits above it — otherwise
# `Title\n---` (a setext H2) would silently cut the deck in half.
SLIDE_HR = re.compile(r"\n[ \t]*\n[ \t]*(?:-{3,}|\*{3,}|_{3,})[ \t]*\n")
DIRECTIVE = re.compile(r"(?ms)^:{3,}[ \t]*(notes|details|say|paper)[ \t]*$\r?\n(.*?)^:{3,}[ \t]*$\r?\n?")
# The same four directives written on ONE line: `:::paper What shipped` (a closing
# `:::` optional). A one-word anchor on its own line is the natural way to write it,
# and the block-only form silently rendered it onto the slide as text instead.
DIRECTIVE_1L = re.compile(r"(?m)^:{3,}[ \t]*(notes|details|say|paper)[ \t]+(.+?)[ \t]*(?::{3,})?[ \t]*$\r?\n?")


def split_slides(md):
    """One markdown file -> [{title, face, details, notes}].

    Slides split on a thematic break (---). A doc with none splits on top-level
    '## ' headings instead, so an existing spec becomes a deck with zero markup.
    Inside a slide, `:::notes` / `:::details` / `:::say` / `:::paper` fenced
    directives peel off the speaker notes, the progressive-disclosure section, the
    narration script and the explicit paper-section anchor; what remains is the face.
    """
    if SLIDE_HR.search(md):
        chunks = SLIDE_HR.split(md)
    else:
        parts = re.split(r"(?m)^(?=## )", md)
        chunks = parts if len(parts) > 1 else [md]
    slides = []
    for chunk in chunks:
        parts = {"details": [], "notes": [], "say": [], "paper": []}
        def grab(m):
            parts[m.group(1)].append(m.group(2).strip("\n"))
            return ""
        face = DIRECTIVE_1L.sub(grab, DIRECTIVE.sub(grab, chunk)).strip("\n")
        if not (face or any(parts.values())):
            continue
        title = next((l.lstrip("#").strip() for l in face.splitlines() if l.startswith("#")), "")
        slides.append({"title": title or "Slide %d" % (len(slides) + 1), "face": face,
                       "details": "\n\n".join(parts["details"]),
                       "notes": "\n\n".join(parts["notes"]),
                       # narration falls back to the speaker notes: the notes ARE the script
                       # for most decks, and asking for the same prose twice is how the two
                       # drift apart.
                       "say": "\n\n".join(parts["say"]) or "\n\n".join(parts["notes"]),
                       "paper": " ".join(parts["paper"]).strip()})
    return slides or [{"title": "Slide 1", "face": md, "details": "", "notes": "",
                       "say": "", "paper": ""}]

def collect_files(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
        for fn in filenames:
            out.append(os.path.join(dirpath, fn))
    out.sort()
    return out

def classify(fp):
    """kind in {"markdown","image","code",None}; meta = mimetype (image) or hljs lang (code, may be None)."""
    name = os.path.basename(fp)
    ext = os.path.splitext(name)[1].lower()
    if ext in MD_EXT: return "markdown", None
    if ext in IMG_EXT: return "image", IMG_EXT[ext]
    if name in NAME_LANG: return "code", NAME_LANG[name]
    if ext in EXT_LANG: return "code", EXT_LANG[ext]
    return None, None

TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/github-markdown-css@5/github-markdown.min.css">
<link rel="stylesheet" media="(prefers-color-scheme: light)" href="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11/build/styles/github.min.css">
<link rel="stylesheet" media="(prefers-color-scheme: dark)" href="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11/build/styles/github-dark.min.css">
<script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11/build/highlight.min.js"></script>
<style>
  :root{ color-scheme:light dark;
         --brand:#0E7C86; --brand-soft:#E9F2F3; --ink:#202832; --ink-2:#3a3a44; --muted:#8a8f98;
         --line:#ececf0; --bg:#FBFBF9; --surface:#fff; --surface-2:#f6f7f9; --surface-3:#ebebef;
         --surface-4:#eceef1; --input-bg:#fbfbfc; --header-bg:rgba(255,255,255,.86);
         --toast-bg:#16161d; --toast-ink:#fff; }
  @media (prefers-color-scheme: dark){
    :root{ --brand:#3ab6c0; --brand-soft:rgba(58,182,192,.16); --ink:#e4e4ea; --ink-2:#c3c3cd; --muted:#8b8b99;
           --line:#2c2c37; --bg:#131319; --surface:#1b1b23; --surface-2:#23232d; --surface-3:#2a2a35;
           --surface-4:#2f2f3b; --input-bg:#20202a; --header-bg:rgba(19,19,25,.86);
           --toast-bg:#e4e4ea; --toast-ink:#16161d; }
  }
  *{ box-sizing:border-box; }
  body{ margin:0; background:var(--bg); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:var(--ink); }
  header{ position:sticky; top:0; z-index:10; display:flex; align-items:center; gap:13px;
          padding:10px 22px; background:var(--header-bg); backdrop-filter:saturate(180%) blur(14px);
          border-bottom:1px solid var(--line); }
  /* left cluster: Claude mark + doc name */
  .brand{ display:flex; align-items:center; gap:11px; min-width:0; }
  .brand .claude{ height:26px; width:auto; flex:none; object-fit:contain; display:block; }
  .titlewrap{ display:flex; flex-direction:column; gap:1px; min-width:0; }
  .title{ font-weight:680; font-size:15px; letter-spacing:-.012em; color:var(--ink);
          white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:46vw; }
  .kicker{ font-size:10.5px; font-weight:600; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); }
  /* right cluster: badges + brand brand mark */
  .badges{ margin-left:auto; display:flex; align-items:center; gap:8px; }
  .badge{ display:inline-flex; align-items:center; gap:6px; font-size:12px; color:var(--ink-2);
          background:var(--surface); border:1px solid var(--line); border-radius:999px; padding:4px 11px; }
  .badge svg{ width:13px; height:13px; opacity:.7; }
  .badge.branch{ color:var(--brand); background:var(--brand-soft); border-color:transparent; font-weight:600; }
  .badge.branch svg{ opacity:.95; fill:var(--brand); }
  button.badge{ font:inherit; cursor:pointer; }
  button.badge:hover{ background:var(--surface-2); }
  .badge .btxt{ display:inline-flex; flex-direction:column; align-items:flex-start; line-height:1.1; }
  .badge .blabel{ white-space:nowrap; }
  .badge .bkey{ font-size:9px; opacity:.5; letter-spacing:.4px; text-transform:uppercase; margin-top:1px; }
  .brand-mark{ height:18px; width:auto; object-fit:contain; display:block; opacity:.9; margin-left:4px; }
  .vsep{ width:1px; height:20px; background:var(--line); margin:0 2px; }
  .shell{ display:flex; align-items:flex-start; }
  .sidebar{ width:240px; flex:none; position:sticky; top:64px; max-height:calc(100vh - 64px);
            min-height:calc(100vh - 64px); overflow:auto; padding:16px 12px 16px 16px;
            background:var(--surface); border-right:1px solid var(--line); }
  .sidebar.hidden{ display:none; }
  .sidebar details{ margin:0; }
  .sidebar summary{ cursor:pointer; list-style:none; display:flex; align-items:center; gap:5px;
                     padding:6px 8px; border-radius:6px; font-size:13px; font-weight:600; color:var(--ink-2); }
  .sidebar summary::-webkit-details-marker{ display:none; }
  .sidebar .chevron{ flex:none; width:16px; height:16px; color:var(--muted); transition:transform .12s; }
  .sidebar details[open] > summary > .chevron{ transform:rotate(90deg); }
  .sidebar summary:hover{ background:var(--surface-3); }
  .sidebar details details, .sidebar details > a{ margin-left:15px; }
  .sidebar a{ display:flex; align-items:center; gap:6px; padding:5px 8px; border-radius:6px; font-size:13px;
              color:var(--ink-2); text-decoration:none; white-space:nowrap; }
  .sidebar a:hover{ background:var(--surface-3); }
  .sidebar a.active{ background:var(--brand-soft); color:var(--brand); font-weight:600; }
  .sidebar .ico, .sidebar .dir-ico{ flex:none; width:16px; height:16px; display:block; }
  .sidebar a span:last-child{ overflow:hidden; text-overflow:ellipsis; }
  /* the rail lives in main's right padding, so the doc never reflows when a comment lands */
  main{ flex:1; min-width:0; position:relative; --rail-w:272px;
        padding-right:calc(var(--rail-w) + 28px); padding-left:calc(var(--rail-w) + 28px); }
  /* the doc is centered in the viewport, not in the leftover space beside the rail — that
     costs a mirrored gutter on the left, and centering wins. Below the width where both
     gutters + the 780px measure fit, drop the left one and let the rail overlay instead. */
  @media (max-width:1400px){ main{ padding-left:0; } }
  @media (max-width:1100px){ main{ padding-right:0; } #rail{ display:none; } }
  .markdown-body{ max-width:780px; margin:40px auto 96px; background:transparent; border:none;
                  border-radius:0; padding:24px 32px; box-shadow:none; }
  /* reading smoothness: serif body text at a comfortable measure (header/sidebar stay sans) */
  .markdown-body, .markdown-body p, .markdown-body li, .markdown-body blockquote{
    font-family:Charter,Georgia,"Times New Roman",serif; font-size:17px; line-height:1.55; }
  .markdown-body h1, .markdown-body h2, .markdown-body h3, .markdown-body h4{
    font-family:Charter,Georgia,"Times New Roman",serif; letter-spacing:-.01em; }
  .markdown-body table, .markdown-body th, .markdown-body td{
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; font-size:15px; }
  .markdown-body code, .markdown-body pre{ font-size:.86em; }
  .markdown-body .mermaid{ background:var(--surface); text-align:center; margin:20px 0; cursor:zoom-in; border-radius:8px; transition:box-shadow .15s; }
  .markdown-body .mermaid:hover{ box-shadow:0 0 0 2px rgba(14,124,134,.3); }
  .markdown-body h1:first-child{ margin-top:0; }
  .sig-badge{ position:fixed; right:18px; bottom:18px; z-index:9999; display:inline-flex;
    align-items:center; gap:8px; padding:8px 14px 8px 10px; border-radius:999px;
    background:var(--card,#fff); border:1px solid var(--line,#dadce1);
    box-shadow:0 2px 10px rgba(16,24,40,.10); font-size:12.5px; font-weight:600;
    line-height:1; color:var(--fg,#2a2c35); text-decoration:none;
    transition:box-shadow .15s ease, transform .15s ease, border-color .15s ease; }
  .sig-badge:hover{ box-shadow:0 4px 16px rgba(16,24,40,.16); transform:translateY(-1px); }
  .sig-badge img{ width:22px; height:22px; display:block; border-radius:4px; }
  .sig-badge .arrow{ opacity:.45; font-weight:400; }
  /* the plain preview signature, bottom-right, with a dismiss to its right.
     ponytail: per-tab only, same as #pdsig - file:// has no localStorage. */
  #docsig{ position:fixed; right:18px; bottom:18px; z-index:9999;
    display:inline-flex; align-items:center; gap:6px; }
  #docsig.gone, body.deck #docsig{ display:none; }
  #docsig .sig-badge{ position:static; }
  @media (max-width:640px){ #docsig{ right:10px; bottom:10px; } }
  /* mermaid click-to-zoom lightbox */
  .mzoom-overlay{ position:fixed; inset:0; z-index:1000; display:none; background:rgba(16,16,29,.74); backdrop-filter:blur(3px); }
  .mzoom-overlay.show{ display:block; }
  .mzoom-stage{ position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
                touch-action:none; cursor:grab; overflow:hidden; }
  .mzoom-stage:active{ cursor:grabbing; }
  .mzoom-stage svg, .mzoom-stage img{ transform-origin:center center; max-width:none !important; max-height:none !important; will-change:transform; }
  .mzoom-controls{ position:fixed; bottom:20px; left:50%; transform:translateX(-50%); display:flex; gap:8px; z-index:1001; }
  .mzoom-controls button{ font:700 15px/1 -apple-system,sans-serif; min-width:40px; height:36px; padding:0 13px;
                          border-radius:9px; border:1px solid rgba(255,255,255,.28); background:rgba(255,255,255,.94);
                          color:#16161d; cursor:pointer; box-shadow:0 2px 8px rgba(0,0,0,.25); }
  .mzoom-controls button:hover{ background:var(--surface); }
  .mzoom-hint{ position:fixed; top:16px; left:50%; transform:translateX(-50%); color:#fff; opacity:.85;
               font:500 12px -apple-system,sans-serif; z-index:1001; letter-spacing:.01em; }
  /* line comments — Google-Docs-style right rail: highlight in the text, card in the margin */
  .mline{ position:relative; }
  /* the highlight wraps only the selected words, not the whole block */
  .mhl{ background:rgba(255,212,59,.32); border-radius:3px;
        box-shadow:0 0 0 1.5px rgba(255,212,59,.32); cursor:pointer; transition:background .15s, box-shadow .15s; }
  .mhl:hover{ background:rgba(255,199,0,.44); box-shadow:0 0 0 1.5px rgba(255,199,0,.44); }
  .mhl.active{ background:rgba(255,186,0,.58); box-shadow:0 0 0 1.5px rgba(255,186,0,.58); }
  #rail{ position:absolute; top:0; right:14px; width:var(--rail-w); }
  .rail-card{ position:absolute; left:0; width:var(--rail-w); background:var(--surface); border:1px solid var(--line);
              border-radius:12px; padding:9px 11px 10px; cursor:pointer;
              box-shadow:0 1px 3px rgba(16,16,29,.09);
              transition:top .18s cubic-bezier(.3,.8,.4,1), box-shadow .15s, border-color .15s; }
  .rail-card:hover{ box-shadow:0 3px 12px rgba(16,16,29,.13); }
  .rail-card.active, .rail-card.draft{ border-color:var(--brand); box-shadow:0 6px 20px rgba(14,124,134,.18); }
  .rail-card.draft{ animation:cardin .26s cubic-bezier(.22,1,.36,1); }
  @keyframes cardin{ from{ opacity:0; transform:translateY(-6px) } to{ opacity:1; transform:none } }
  #notesCount{ display:inline-block; min-width:9px; padding:0 5px; border-radius:999px; background:var(--surface-4);
               color:var(--muted); font-weight:700; font-size:10.5px; text-align:center; transition:background .2s, color .2s; }
  #notesCount.has{ background:var(--brand); color:#fff; }
  #notesCount.bump{ animation:countpop .34s cubic-bezier(.34,1.56,.64,1); }
  @keyframes countpop{ 0%{ transform:scale(1) } 40%{ transform:scale(1.45) } 100%{ transform:scale(1) } }
  .cb-head{ display:flex; align-items:center; gap:6px; margin:1px 0 8px; }
  .cb-head-icon{ display:flex; color:var(--brand); flex:none; }
  .cb-head-icon svg{ width:13px; height:13px; }
  .cb-head-title{ font:700 11.5px -apple-system,sans-serif; color:var(--ink); letter-spacing:-.01em; }
  .cb-head-line{ font:600 10px -apple-system,sans-serif; color:var(--muted); letter-spacing:.03em; }
  /* composer only in the card you're working in — inactive cards stay compact */
  .rail-card textarea{ display:none; }
  .rail-card.active textarea, .rail-card.draft textarea{ display:block; }
  .rail-card textarea{ width:100%; height:32px; min-height:32px; resize:none; border:1px solid var(--line); border-radius:9px;
                       padding:7px 9px; font:13px -apple-system,sans-serif; background:var(--input-bg);
                       transition:height .15s, border-color .15s, box-shadow .15s; }
  .rail-card textarea:focus{ outline:none; height:58px; border-color:var(--brand); background:var(--surface);
                             box-shadow:0 0 0 3px rgba(14,124,134,.14); }
  .cb-close{ margin-left:auto; border:none; background:none; font-size:16px; line-height:1;
             cursor:pointer; color:var(--muted); padding:2px 6px; border-radius:6px; transition:background .15s, color .15s; }
  .cb-close:hover{ color:var(--ink); background:var(--surface-3); }
  .cb-quote{ font:italic 12px/1.45 Charter,Georgia,serif; color:var(--muted); border-left:3px solid rgba(255,199,0,.85);
             padding:1px 0 1px 8px; margin:0 0 8px; overflow:hidden;
             display:-webkit-box; -webkit-box-orient:vertical; -webkit-line-clamp:3; }
  #rail[data-kind="code"] .cb-quote{ font:11.5px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace; white-space:pre-wrap; }
  .cb-thread{ display:flex; flex-direction:column; gap:6px; margin-bottom:8px; max-height:220px; overflow:auto; }
  .rail-card:not(.active):not(.draft) .cb-thread{ margin-bottom:0; }
  .cb-comment{ display:flex; justify-content:space-between; align-items:flex-start; gap:8px;
               background:var(--surface-2); border-radius:9px; padding:7px 9px; font-size:12.5px; line-height:1.4; }
  .cb-comment-del{ border:none; background:none; color:var(--muted); cursor:pointer; font-size:13px; line-height:1; flex:none; }
  .cb-comment-del:hover{ color:#c62828; }
  /* action row only shows on the card you're actually working in */
  .cb-row{ display:none; gap:6px; margin-top:8px; justify-content:flex-end; }
  .rail-card.active .cb-row, .rail-card.draft .cb-row{ display:flex; }
  .cb-row button{ font:600 12px -apple-system,sans-serif; padding:6px 12px; border-radius:8px; border:1px solid var(--line);
                   background:var(--surface-2); cursor:pointer; transition:transform .1s, box-shadow .1s, background .15s; }
  .cb-row button:hover{ background:var(--surface-4); }
  .cb-save{ background:linear-gradient(180deg, #12969f, var(--brand)) !important; color:#fff !important;
             border-color:transparent !important; box-shadow:0 2px 6px rgba(14,124,134,.35); }
  .cb-save:hover{ transform:translateY(-1px); box-shadow:0 4px 10px rgba(14,124,134,.4); }
  .toast{ position:fixed; bottom:20px; left:50%; transform:translateX(-50%); background:var(--toast-bg); color:var(--toast-ink);
          padding:8px 16px; border-radius:999px; font:600 12px -apple-system,sans-serif; z-index:2000; opacity:0;
          transition:opacity .2s; pointer-events:none; }
  .toast.show{ opacity:1; }
  /* ── deck mode (pd-slides) ─────────────────────────────────────────────
     Split screen. Left = the deck stage. Right = `main`, which is the ordinary
     browser-preview document pane holding paper.md — so the comment engine,
     the rail and the copy buttons are untouched code. The split is sticky
     across slides; the grip on the divider collapses it. */
  #stage, #pdgrip{ display:none; }
  body.deck{ --hdr:47px; overflow:hidden; }
  body.deck .shell{ height:calc(100vh - var(--hdr)); align-items:stretch; }
  body.deck #stage{ display:block; position:relative; flex:1 1 0px; min-width:0; overflow:hidden;
                    transition:flex-grow .36s cubic-bezier(.22,1,.36,1), opacity .26s ease; }
  /* The pane is always laid out; opening it animates its flex-basis from 0. The document
     inside keeps a FIXED width the whole time, so the pane reveals it rather than
     reflowing the text on every frame — a reflowing wall of prose is the "pop". */
  body.deck main{ display:block; --paper-w:clamp(560px, 52vw, 1000px); --pw:0px; --rail-w:252px;
                  flex:0 0 var(--pw); height:calc(100vh - var(--hdr)); overflow:hidden;
                  opacity:0; position:relative; padding:0;
                  transition:flex-basis .36s cubic-bezier(.22,1,.36,1), opacity .3s ease; }
  body.deck.split main{ --pw:var(--paper-w); opacity:1; overflow:auto; }
  body.deck main > .markdown-body{ width:calc(var(--paper-w) - 52px); }
  body.deck #rail{ right:18px; }
  /* the paper rail overlays too — the paper's measure never changes because of a comment */
  body.deck #rail{ right:18px; pointer-events:none; z-index:6; opacity:0; visibility:hidden;
                   transform:translateX(10px);
                   transition:opacity .24s ease, transform .3s cubic-bezier(.22,1,.36,1),
                              visibility 0s linear .24s; }
  body.deck main.cx #rail{ opacity:1; visibility:visible; transform:none; transition-delay:0s, 0s, 0s; }
  body.deck #rail .rail-card{ pointer-events:auto;
                              box-shadow:0 6px 22px rgba(0,0,0,.13), 0 1px 3px rgba(0,0,0,.08); }
  @media (prefers-color-scheme: dark){
    body.deck #rail .rail-card{ box-shadow:0 6px 24px rgba(0,0,0,.5), 0 1px 3px rgba(0,0,0,.4); }
  }
  body.deck .shell{ position:relative; }
  body.deck .markdown-body{ margin:26px auto 90px; padding:0; max-width:none; }
  body.deck.split.full #stage{ flex-grow:0; opacity:0; pointer-events:none; }
  body.deck.split.full main{ --pw:100%; }
  body.deck.split.full main > .markdown-body{ width:auto; max-width:780px; }
  /* the grip: always there, says what is behind it, collapses the split */
  /* ── paper sections ────────────────────────────────────────────────────
     Every slide owns a section of the paper. The pane cuts the rendered paper into
     .pp-sec blocks at one per heading, the pairing is allocated once, and the section
     belonging to the slide you are on wears the focus layer: a tinted card carrying
     that slide's number, with every other section dimmed back. Opening the pane is
     therefore never "somewhere in the paper" — it is *this slide's* evidence. */
  .pp-sec{ position:relative; padding:12px 16px 14px; margin:0 -16px; border-radius:10px;
    border:1px solid transparent; scroll-margin-top:26px;
    transition:opacity .3s ease, background .3s ease, border-color .3s ease; }
  body.deck.focus main .pp-sec{ opacity:.32; }
  body.deck.focus main .pp-sec.pp-on{ opacity:1; background:var(--brand-soft);
    border-color:color-mix(in srgb, var(--brand) 34%, transparent); }
  .pp-sec .pp-tag{ position:absolute; top:-9px; left:14px; display:none; align-items:center;
    gap:5px; max-width:calc(100% - 28px); overflow:hidden; text-overflow:ellipsis;
    white-space:nowrap; font:700 10.5px/1 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    letter-spacing:.07em; text-transform:uppercase; color:var(--surface);
    background:var(--brand); padding:6px 11px; border-radius:999px;
    box-shadow:0 2px 8px rgba(0,0,0,.22); }
  .pp-sec .pp-tag b{ font-weight:700; opacity:.72; letter-spacing:.09em; }
  body.deck main .pp-sec.pp-on .pp-tag{ display:inline-flex; }
  body.deck .pp-sec > :first-child:not(.pp-tag){ margin-top:0; }

  /* ── narration transport ───────────────────────────────────────────────
     One clip per slide, so the audio cannot drift out of sync with the deck: the
     slide change IS the seam. `auto` plays the whole deck straight through and
     advances the slides itself. */
  .deckbar .pdaudio{ display:none; align-items:center; gap:3px; }
  body.deck.hasaudio .deckbar .pdaudio{ display:inline-flex; }
  .deckbar .pdtime{ font:11px/1 ui-monospace,SFMono-Regular,Menlo,monospace;
    color:var(--muted); min-width:36px; text-align:center; }
  #pdPlayBtn.playing{ background:var(--brand); border-color:transparent; color:#fff; }
  #pdPlayBtn.blocked{ animation:pdpulse 1.7s ease-in-out infinite; }
  @keyframes pdpulse{ 0%,100%{ box-shadow:0 0 0 0 rgba(14,124,134,.5) }
                      50%{ box-shadow:0 0 0 6px rgba(14,124,134,0) } }
  /* the block being read. A left rule rather than a fill: the focus card already
     tints the section, and a second wash inside it reads as two states, not one. */
  #doc .pp-reading{ position:relative; }
  #doc .pp-reading::before{ content:""; position:absolute; left:-14px; top:-3px; bottom:-3px;
    width:3px; border-radius:2px; background:var(--brand); }
  #doc .pp-reading{ background:color-mix(in srgb, var(--brand) 7%, transparent);
    box-shadow:0 0 0 6px color-mix(in srgb, var(--brand) 7%, transparent); border-radius:2px; }
  body.deck.focus main .pp-sec .pp-reading{ transition:background .2s ease; }

  /* captions. Words are spans HERE and nowhere else — see showCue(). */
  #pdsubs{ display:none; position:fixed; left:50%; bottom:22px; transform:translateX(-50%);
    z-index:44; max-width:min(860px, 78vw); padding:13px 20px; border-radius:12px;
    background:color-mix(in srgb, var(--surface) 88%, transparent);
    backdrop-filter:blur(14px); -webkit-backdrop-filter:blur(14px);
    border:1px solid var(--line); box-shadow:0 10px 34px rgba(0,0,0,.16);
    font-family:Charter,"Iowan Old Style",Georgia,serif; font-size:17px; line-height:1.55;
    color:var(--muted); text-align:center; pointer-events:none; }
  body.deck.hasaudio #pdsubs.on{ display:block; }
  #pdsubs .pdw{ transition:color .12s ease; }
  #pdsubs .pdw.said{ color:var(--ink-2); }
  #pdsubs .pdw.saying{ color:var(--brand); font-weight:600; }
  /* ── plus: editable diagrams, live app frames, the agent pane ──────────── */
  .pd-draw{ border:1px solid var(--line); border-radius:10px; overflow:hidden;
    margin:16px 0; background:var(--surface); }
  .pd-draw-head, .pd-app-head{ display:flex; align-items:center; gap:10px;
    padding:7px 12px; border-bottom:1px solid var(--line); background:var(--surface-2);
    font:600 11px/1 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    letter-spacing:.06em; text-transform:uppercase; color:var(--ink-2); }
  .pd-draw-state{ margin-left:auto; font-weight:500; text-transform:none;
    letter-spacing:0; font-size:11.5px; color:var(--muted); }
  .pd-draw-state.dirty{ color:var(--brand); }
  .pd-draw-reseed, .pd-draw-done{ font:inherit; font-size:10px; cursor:pointer;
    background:none; border:none; color:var(--brand); padding:0; }
  .pd-draw-hint{ margin-left:auto; font-weight:500; text-transform:none; letter-spacing:0;
    font-size:11px; color:var(--muted); }
  .pd-draw .pd-draw-done, .pd-draw.editing .pd-draw-hint{ display:none; }
  .pd-draw.editing .pd-draw-done{ display:inline; margin-left:auto; }
  .pd-draw.editing{ border-color:var(--brand); }
  /* viewModeEnabled drops the toolbar but keeps the footer, the zoom pill and — in a
     pane this narrow, where Excalidraw switches to its MOBILE layout — `App-bottom-bar`,
     which lives outside `layer-ui__wrapper` and so survived the first attempt. In view
     mode the canvas is a picture, so every chrome container goes; they all come back
     the moment you click in. */
  .pd-draw:not(.editing) .excalidraw .layer-ui__wrapper,
  .pd-draw:not(.editing) .excalidraw .App-bottom-bar,
  .pd-draw:not(.editing) .excalidraw .App-toolbar-container,
  .pd-draw:not(.editing) .excalidraw .App-menu_bottom,
  .pd-draw:not(.editing) .excalidraw .App-menu,
  .pd-draw:not(.editing) .excalidraw .mobile-misc-tools-container,
  .pd-draw:not(.editing) .excalidraw .main-menu-trigger,
  .pd-draw:not(.editing) .excalidraw .zoom-actions,
  .pd-draw:not(.editing) .excalidraw .Island,
  .pd-draw:not(.editing) .excalidraw .excalidraw-contextMenu{ display:none !important; }
  .pd-draw:not(.editing) .excalidraw{ cursor:pointer; }
  .pd-draw-full{ font:inherit; font-size:14px; line-height:1; cursor:pointer;
    background:none; border:none; color:var(--muted); padding:0 2px;
    transform:rotate(90deg); }
  .pd-draw-full:hover{ color:var(--brand); }
  /* Full screen is a real diagram surface, not a bigger thumbnail — so it goes to
     edit mode on the way in. A diagram you bothered to enlarge is one you are about
     to work on. */
  .pd-draw.fs{ position:fixed; inset:14px; z-index:120; margin:0; display:flex;
    flex-direction:column; box-shadow:0 24px 80px rgba(0,0,0,.5); }
  .pd-draw.fs .pd-draw-host{ flex:1; height:auto; }
  #pdscrim{ display:none; position:fixed; inset:0; z-index:119;
    background:rgba(10,12,16,.62); backdrop-filter:blur(2px); }
  body.drawfs #pdscrim{ display:block; }
  .pd-draw-state{ margin-left:12px; }
  .pd-draw-host{ height:440px; }
  .slide .pd-draw-host{ height:min(52vh, 480px); }
  /* Excalidraw ships its own dark theme; let it own the box it is in */
  .pd-draw-host .excalidraw{ --ui-font:inherit; }
  .pd-app{ border:1px solid var(--line); border-radius:10px; overflow:hidden;
    margin:16px 0; background:var(--surface); display:flex; flex-direction:column; }
  .pd-app-url{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; text-transform:none;
    letter-spacing:0; font-size:11.5px; color:var(--muted); }
  .pd-app-head button, .pd-app-head a{ margin-left:auto; font:inherit; font-size:10.5px;
    cursor:pointer; background:none; border:none; color:var(--brand); text-decoration:none;
    padding:0; }
  .pd-app-head a{ margin-left:12px; }
  .pd-app iframe{ flex:1; width:100%; border:0; background:#fff; }

  /* the agent pane docks right, over the paper, and never reflows either pane */
  #pdchat{ display:none; position:fixed; right:0; top:var(--hdr,47px); bottom:0; width:360px;
    z-index:46; flex-direction:column; background:var(--surface);
    border-left:1px solid var(--line); box-shadow:-12px 0 34px rgba(0,0,0,.13); }
  body.plus.chat #pdchat{ display:flex; }
  #pdchat .ch-head{ display:flex; align-items:center; gap:8px; padding:11px 14px;
    border-bottom:1px solid var(--line); font:600 12px/1 -apple-system,BlinkMacSystemFont,
    "Segoe UI",sans-serif; letter-spacing:.05em; text-transform:uppercase; color:var(--ink-2); }
  #pdchat .ch-dot{ width:7px; height:7px; border-radius:50%; background:var(--muted); }
  #pdchat .ch-dot.live{ background:#3fbf7f; }
  #pdchat .ch-x{ margin-left:auto; cursor:pointer; border:none; background:none;
    color:var(--muted); font-size:17px; line-height:1; padding:0 2px; }
  #pdchat .ch-log{ flex:1; overflow:auto; padding:14px; display:flex; flex-direction:column;
    gap:10px; }
  #pdchat .msg{ max-width:88%; padding:9px 12px; border-radius:12px; font-size:13.5px;
    line-height:1.5; white-space:pre-wrap; word-wrap:break-word; }
  #pdchat .msg.me{ align-self:flex-end; background:var(--brand); color:var(--surface); }
  #pdchat .msg.agent{ align-self:flex-start; background:var(--surface-2);
    border:1px solid var(--line); color:var(--ink); }
  #pdchat .msg .who{ display:block; font-size:9.5px; letter-spacing:.09em;
    text-transform:uppercase; opacity:.6; margin-bottom:3px; }
  #pdchat .ch-foot{ border-top:1px solid var(--line); padding:10px; }
  #pdchat textarea{ width:100%; box-sizing:border-box; resize:none; height:66px;
    background:var(--surface-2); color:var(--ink); border:1px solid var(--line);
    border-radius:9px; padding:9px 11px; font:14px/1.5 inherit; }
  #pdchat textarea:focus{ outline:none; border-color:var(--brand); }
  #pdchat .ch-hint{ margin-top:6px; font-size:11px; color:var(--muted); }
  body.plus.chat main{ padding-right:360px; }
  body.plus.chat #rail{ right:378px; }
  .deckbar .pdplus{ display:none; align-items:center; gap:3px; }
  body.plus .deckbar .pdplus{ display:inline-flex; }
  #pdChatBtn .n{ margin-left:4px; font-size:10px; font-weight:700; }
  .deckbar button.mute{ opacity:.4; }
  /* the current clip's progress, hairline under the deck's own progress bar */
  #pdabar{ display:none; position:fixed; top:calc(var(--hdr, 47px) + 2px); left:0; height:2px;
    width:0; background:var(--brand); opacity:.42; z-index:15; }
  body.deck.hasaudio #pdabar{ display:block; }
  body.deck #pdgrip{ display:flex; flex:none; width:34px; align-items:center; justify-content:center;
                     gap:9px; cursor:pointer; border:none; border-left:1px solid var(--line);
                     background:var(--surface); color:var(--muted); padding:0;
                     writing-mode:vertical-rl; font:inherit; font-size:10.5px; font-weight:700;
                     letter-spacing:.13em; text-transform:uppercase; }
  body.deck #pdgrip{ transition:background .2s ease, color .2s ease; }
  body.deck #pdgrip:hover{ background:var(--brand-soft); color:var(--brand); }
  body.deck.split #pdgrip{ background:var(--surface-2); color:var(--ink-2); }
  body.deck #pdgrip svg{ width:13px; height:13px; transform:rotate(90deg); transition:transform .2s; }
  body.deck.split #pdgrip svg{ transform:rotate(-90deg); }
  body.deck #pdgrip.empty{ display:none; }
  /* ── slides ───────────────────────────────────────────────────────────── */
  /* Slides travel, they do not crossfade. Two full slides dissolving through each other
     reads as a flicker; the incoming one entering from the direction you moved reads as
     a deck. Start offsets are set imperatively in goSlide so both directions work off one
     pair of rules. */
  .slide{ position:absolute; inset:0; overflow-y:auto; opacity:0; pointer-events:none;
          transition:opacity .26s ease, transform .52s cubic-bezier(.16,.84,.28,1); }
  .slide.on{ opacity:1; transform:none; pointer-events:auto; z-index:2;
             transition:opacity .42s ease, transform .62s cubic-bezier(.16,.84,.28,1); }
  .slide .pad{ max-width:1120px; margin:0 auto; padding:44px 54px 88px; }
  /* Slide comments never reflow the slide. The rail is an OVERLAY inside the active
     slide (so cards still scroll with their text), collapsed behind a corner pill until
     you open it. The paper pane keeps the classic reserved-margin rail. */
  body.deck #stage{ --srail-w:252px; }
  #srail{ position:absolute; top:0; right:18px; width:var(--srail-w);
          pointer-events:none; z-index:6; opacity:0; visibility:hidden;
          transform:translateX(10px);
          transition:opacity .24s ease, transform .3s cubic-bezier(.22,1,.36,1),
                     visibility 0s linear .24s; }
  #stage.cx #srail{ opacity:1; visibility:visible; transform:none; transition-delay:0s, 0s, 0s; }
  #srail .rail-card{ width:var(--srail-w); pointer-events:auto;
                     box-shadow:0 6px 22px rgba(0,0,0,.13), 0 1px 3px rgba(0,0,0,.08); }
  @media (prefers-color-scheme: dark){
    #srail .rail-card{ box-shadow:0 6px 24px rgba(0,0,0,.5), 0 1px 3px rgba(0,0,0,.4); }
  }
  #pdcbtn, #pdcbtn2{ position:absolute; right:18px; bottom:18px; z-index:22;
           opacity:0; visibility:hidden; transform:translateY(8px) scale(.96);
           transition:opacity .22s ease, transform .3s cubic-bezier(.22,1,.36,1),
                      visibility 0s linear .22s, background .15s, color .15s;
           align-items:center; gap:7px; cursor:pointer; font:inherit; font-size:12px;
           font-weight:600; color:var(--ink-2); background:var(--surface);
           border:1px solid var(--line); border-radius:999px; padding:7px 13px;
           box-shadow:0 4px 16px rgba(0,0,0,.10); }
  #pdcbtn, #pdcbtn2{ display:inline-flex; }
  #pdcbtn.show, #pdcbtn2.show{ opacity:1; visibility:visible; transform:none;
                               transition-delay:0s, 0s, 0s, 0s, 0s; }
  #pdcbtn:hover, #pdcbtn2:hover{ background:var(--surface-2); }
  #stage.cx #pdcbtn, main.cx ~ #pdcbtn2{ background:var(--brand-soft); border-color:transparent; color:var(--brand); }
  #pdcbtn svg, #pdcbtn2 svg{ width:13px; height:13px; opacity:.75; }
  #pdcbtn .n, #pdcbtn2 .n{ font-variant-numeric:tabular-nums; background:var(--surface-3);
              border-radius:999px; padding:0 6px; font-size:11px; }
  #stage.cx #pdcbtn .n, main.cx ~ #pdcbtn2 .n{ background:rgba(255,255,255,.55); }
  /* pinned to the shell's bottom-right, which is the paper pane's corner in both
     split and full — inside `main` it would scroll away with the document */
  #pdcbtn2{ bottom:18px; }
  body.deck:not(.split) #pdcbtn2{ opacity:0 !important; visibility:hidden !important; }
  body.deck.split .slide .pad{ padding:34px 38px 80px; }
  @media (prefers-reduced-motion: no-preference){
    /* the stagger is capped in goSlide: past ~8 blocks the cascade outlives the
       slide change and reads as lag rather than as arrival */
    .slide.on > .pad > *{ animation:pdrise .62s cubic-bezier(.16,.84,.28,1) both;
                          animation-delay:calc(var(--i,0) * 42ms); }
  }
  @keyframes pdrise{ from{ opacity:0; transform:translateY(11px); } to{ opacity:1; transform:none; } }
  /* display type: serif headline, sans furniture — the eyebrow is just the first
     paragraph when it sits above the heading, so a cover costs no extra markup */
  .slide .pad > p:first-child{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
                               font-size:10.5px; letter-spacing:.14em; text-transform:uppercase;
                               font-weight:700; color:var(--muted); margin:0 0 14px; }
  .slide h1{ font-family:Charter,"Iowan Old Style",Georgia,serif; font-weight:700;
             font-size:clamp(32px,3.9vw,56px); line-height:1.04; letter-spacing:-.023em;
             margin:0 0 18px; border:none; padding:0; }
  .slide h2{ font-family:Charter,"Iowan Old Style",Georgia,serif; font-weight:700;
             font-size:clamp(24px,2.5vw,35px); line-height:1.14; letter-spacing:-.016em;
             margin:0 0 14px; border:none; padding:0; }
  .slide h3{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
             font-size:10.5px; letter-spacing:.14em; text-transform:uppercase;
             font-weight:700; color:var(--muted); margin:26px 0 10px; }
  .slide h1 + p, .slide h2 + p{ font-family:Charter,Georgia,serif; font-size:20px; line-height:1.5;
                                color:var(--ink-2); max-width:74ch; margin:0 0 16px; }
  .slide p, .slide li{ font-size:16px; line-height:1.6; color:var(--ink-2); }
  .slide ul, .slide ol{ max-width:82ch; }
  .slide li{ margin:7px 0; }
  .slide strong{ color:var(--ink); }
  .slide code{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.88em;
               background:var(--surface-3); padding:1px 5px; border-radius:4px; }
  .slide table{ border-collapse:collapse; width:100%; font-size:13.5px;
                font-variant-numeric:tabular-nums; }
  .slide table th{ text-align:left; font-size:10px; letter-spacing:.1em; text-transform:uppercase;
                   color:var(--muted); font-weight:700; padding:0 0 7px; border-bottom:1px solid var(--line); }
  .slide table td{ padding:6px 0; border-bottom:1px solid var(--line); }
  .slide table td:not(:first-child){ text-align:right; font-family:ui-monospace,Menlo,monospace; }
  .slide .mermaid{ display:flex; justify-content:center; margin:18px 0; }
  /* ── component vocabulary (the ::: blocks) ────────────────────────────── */
  .pd-card{ background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:16px 17px; }
  .pd-lbl{ font-size:10px; letter-spacing:.13em; text-transform:uppercase; font-weight:700;
           color:var(--muted); margin:0 0 6px; display:flex; align-items:center; gap:8px; }
  .pd-pill{ font-size:9.5px; letter-spacing:.09em; text-transform:uppercase; font-weight:800;
            padding:2px 8px; border-radius:99px; background:var(--surface-3); color:var(--ink-2); }
  .pd-pill[data-s="good"]{ background:rgba(4,120,87,.12); color:#047857; }
  .pd-pill[data-s="warn"]{ background:rgba(180,83,9,.13); color:#b45309; }
  .pd-pill[data-s="bad"]{ background:rgba(220,38,38,.12); color:#dc2626; }
  @media (prefers-color-scheme: dark){
    .pd-pill[data-s="good"]{ color:#34d399; } .pd-pill[data-s="warn"]{ color:#fbbf24; }
    .pd-pill[data-s="bad"]{ color:#f87171; }
  }
  .pd-title{ font-family:Charter,Georgia,serif; font-size:18.5px; line-height:1.28;
             color:var(--ink); margin:0; font-weight:600; }
  .pd-meta{ font-size:12px; line-height:1.45; color:var(--muted); margin:8px 0 0; }
  .pd-cards{ display:grid; gap:13px; margin:22px 0;
             grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); }
  .pd-cols{ display:grid; gap:20px; margin:22px 0; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); }
  .pd-cols > .pd-card > :is(p,ul,ol){ font-size:13.5px; line-height:1.55; }
  .pd-cols > .pd-card > :is(p,ul,ol):last-child{ margin-bottom:0; }
  .pd-stats{ display:grid; gap:0; margin:20px 0; max-width:640px; }
  .pd-stat{ display:flex; align-items:baseline; gap:12px; padding:7px 0; border-bottom:1px solid var(--line); }
  .pd-stat .v{ font-family:ui-monospace,Menlo,monospace; font-variant-numeric:tabular-nums;
               font-size:15px; font-weight:600; color:var(--ink); min-width:5.5ch; text-align:right; }
  .pd-stat .k{ font-size:13px; color:var(--ink-2); flex:1; }
  .pd-stat .u{ font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.08em; }
  .pd-deep{ background:linear-gradient(135deg,#0f172a,#1e293b); color:#e2e8f0; border-radius:12px;
            padding:22px 24px; margin:22px 0; }
  .pd-deep :is(p,li){ color:#cbd5e1; font-size:14.5px; }
  .pd-deep :is(h1,h2,h3,strong){ color:#f8fafc; }
  .pd-deep code{ background:rgba(255,255,255,.1); color:#e2e8f0; }
  .pd-note{ border-left:3px solid var(--brand); padding:2px 0 2px 15px; margin:20px 0; }
  .pd-note :is(p,li){ font-size:14.5px; }
  .pd-note > :last-child{ margin-bottom:0; }
  /* ── chrome ───────────────────────────────────────────────────────────── */
  #pdbar{ display:none; position:fixed; top:var(--hdr); left:0; height:2px; width:0;
          background:var(--brand); z-index:15; transition:width .3s cubic-bezier(.22,1,.36,1); }
  body.deck #pdbar{ display:block; }
  .deckbar{ display:none; align-items:center; gap:3px; }
  body.deck .deckbar{ display:inline-flex; }
  .deckbar button{ font:inherit; cursor:pointer; background:var(--surface); border:1px solid var(--line);
                   color:var(--ink-2); width:27px; height:27px; border-radius:8px;
                   display:grid; place-items:center; padding:0; }
  .deckbar button:hover:not(:disabled){ background:var(--surface-2); }
  .deckbar button:disabled{ opacity:.32; cursor:default; }
  .deckbar button.on{ background:var(--brand-soft); border-color:transparent; color:var(--brand); }
  .deckbar button svg{ width:14px; height:14px; }
  .deckbar .count{ font-size:12px; color:var(--ink-2); min-width:50px; text-align:center;
                   font-variant-numeric:tabular-nums; }
  body.deck #copyNotesBtn .blabel, body.deck #copyMdBtn .blabel,
  body.deck #copyMdNotesBtn .blabel{ display:none; }
  body.deck #copyNotesBtn, body.deck #copyMdBtn, body.deck #copyMdNotesBtn{ padding:5px 8px; }
  body.deck #copyNotesBtn .btxt, body.deck #copyMdBtn .btxt,
  body.deck #copyMdNotesBtn .btxt{ gap:0; }
  body.deck .sidebar{ display:none; }
  body.deck.nav .sidebar{ display:block; height:calc(100vh - var(--hdr)); min-height:0; top:0; }
  .sidebar a .sl-n{ flex:none; width:17px; text-align:right; color:var(--muted);
                    font-variant-numeric:tabular-nums; font-size:11px; }
  .sidebar a.active .sl-n{ color:var(--brand); }
  #pdnotes{ position:fixed; left:0; right:0; bottom:0; z-index:30; max-height:42vh; overflow:auto;
            background:var(--surface); border-top:1px solid var(--line);
            box-shadow:0 -10px 30px rgba(0,0,0,.11); padding:14px 26px 22px;
            transform:translateY(101%); transition:transform .22s cubic-bezier(.22,1,.36,1); }
  #pdnotes.open{ transform:none; }
  #pdnotes .nhead{ font-size:10.5px; font-weight:700; letter-spacing:.08em; text-transform:uppercase;
                   color:var(--muted); margin-bottom:9px; }
  #pdnotes .nbody{ max-width:840px; font-family:Charter,Georgia,serif; font-size:15.5px;
                   line-height:1.55; color:var(--ink-2); }
  #pdnotes .nbody p{ margin:0 0 9px; }
  #pdnotes .nbody ul, #pdnotes .nbody ol{ margin:0 0 9px; padding-left:20px; }
  body.deck .sig-badge{ display:none; }
  /* the deck's own signature, bottom-left, with a dismiss to its left — it sits over
     the slide and a reader who has seen it once should be able to put it away.
     ponytail: per-tab only. file:// has no localStorage to remember the choice in. */
  #pdsig{ display:none; position:fixed; left:18px; bottom:18px; z-index:25;
    align-items:center; gap:6px; }
  body.deck #pdsig{ display:inline-flex; }
  body.deck #pdsig.gone{ display:none; }
  #pdsig .sig-badge.pd{ display:inline-flex; position:static; }
  #pdsigX, #docsigX{ flex:none; width:24px; height:24px; padding:0; display:flex; align-items:center;
    justify-content:center; border-radius:999px; cursor:pointer; font:400 15px/1 -apple-system,
    BlinkMacSystemFont,"Segoe UI",sans-serif; color:var(--muted);
    background:var(--card,#fff); border:1px solid var(--line,#dadce1);
    box-shadow:0 2px 10px rgba(16,24,40,.10);
    transition:color .15s ease, border-color .15s ease, opacity .15s ease; opacity:.55; }
  #pdsig:hover #pdsigX, #docsig:hover #docsigX{ opacity:1; }
  #pdsigX:hover, #docsigX:hover{ color:var(--ink); border-color:var(--muted); }
  @media (max-width:640px){ #pdsig{ left:10px; bottom:10px; } }
  @media (prefers-reduced-motion: reduce){
    body.deck #stage, body.deck main, #srail, body.deck #rail, #pdcbtn, #pdcbtn2,
    .slide, #pdnotes, .rail-card, .pp-sec, #pdsubs .pdw{ transition-duration:.01ms !important; }
    #pdPlayBtn.blocked{ animation:none !important; }
    .rail-card.draft{ animation:none; }
  }
  /* code file view */
  .markdown-body pre.code-view{ margin:0; padding:0; background:transparent; overflow:visible; }
  .code-lines{ font:12.5px/1.6 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }
  .code-line{ display:flex; border-radius:5px; }
  .code-line .ln{ flex:none; width:38px; text-align:right; margin-right:14px; color:var(--muted); user-select:none; }
  .code-line .lc{ white-space:pre; overflow-x:auto; }
  .code-line:hover{ background:var(--surface-2); }
</style></head>
<body>
<header>
  <div class="brand">
    __CLAUDE_IMG__
    <div class="titlewrap">
      <div class="kicker">Claude Code</div>
      <div class="title">__TITLE__</div>
    </div>
  </div>
  <div class="badges">
    <div class="deckbar">
      <button id="pdPrev" type="button" title="Previous slide (←)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg></button>
      <span class="count" id="pdCount">1 / 1</span>
      <button id="pdNext" type="button" title="Next slide (→)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18l6-6-6-6"/></svg></button>
      <button id="pdPaperBtn" type="button" title="Paper pane (p)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h9l7 7v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z"/><path d="M13 4v7h7"/></svg></button>
      <button id="pdFullBtn" type="button" title="Paper full width (f)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3H5a2 2 0 0 0-2 2v3M16 3h3a2 2 0 0 1 2 2v3M8 21H5a2 2 0 0 1-2-2v-3M16 21h3a2 2 0 0 0 2-2v-3"/></svg></button>
      <button id="pdNavBtn" type="button" title="Slide list (s)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h4M4 12h4M4 18h4M11 6h9M11 12h9M11 18h9"/></svg></button>
      <button id="pdNotesBtn" type="button" title="Speaker notes (n)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M4 12h16M4 17h9"/></svg></button>
      <button id="pdPresentBtn" type="button" title="Presenter window (v)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="14" height="11" rx="1.5"/><path d="M6 20h6"/><path d="M19 8h3v12h-9v-3"/></svg></button>
      <button id="pdFocusBtn" type="button" title="Focus the paper on this slide's section (o)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/></svg></button>
      <div class="pdplus">
        <div class="vsep"></div>
        <button id="pdChatBtn" type="button" title="Agent pane (g)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7A8.4 8.4 0 0 1 4 11.5 8.5 8.5 0 0 1 12.5 3 8.5 8.5 0 0 1 21 11.5z"/></svg><span class="n"></span></button>
      </div>
      <div class="pdaudio">
        <div class="vsep"></div>
        <button id="pdPlayBtn" type="button" title="Play this slide's narration (a)"><svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M8 5.5v13l11-6.5z"/></svg></button>
        <button id="pdAutoBtn" type="button" title="Play the whole deck, advancing slides (shift+A)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h11M4 12h11M4 18h7"/><path d="M17 15l3 3-3 3"/><path d="M20 18h-6"/></svg></button>
        <button id="pdSubsBtn" type="button" title="Captions (t)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M7 14h3M13 14h4"/></svg></button>
        <span class="pdtime" id="pdTime">0:00</span>
      </div>
      <div class="vsep"></div>
    </div>
    <button id="copyNotesBtn" class="badge" type="button">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
      </svg>
      <span class="btxt"><span class="blabel">Copy notes <span id="notesCount">0</span></span><span class="bkey">c</span></span>
    </button>
    <button id="copyMdBtn" class="badge" type="button">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
      </svg>
      <span class="btxt"><span class="blabel">Copy md</span><span class="bkey">m</span></span>
    </button>
    <button id="copyMdNotesBtn" class="badge" type="button">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
      </svg>
      <span class="btxt"><span class="blabel">Copy md + notes</span><span class="bkey">b</span></span>
    </button>
    __REPO_BADGE__
    __BRANCH_BADGE__
    <div class="vsep"></div>
    __BRAND_IMG__
  </div>
</header>
<div class="shell">
  <nav class="sidebar hidden" id="sidebar"></nav>
  <section id="stage"><button id="pdcbtn" type="button" title="Slide comments"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7A8.4 8.4 0 0 1 4 11.5 8.5 8.5 0 0 1 12.5 3 8.5 8.5 0 0 1 21 11.5z"/></svg><span class="lbl">Comments</span><span class="n">0</span></button></section>
  <div id="srail"></div>
  <button id="pdgrip" type="button" title="Paper pane (p)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18l6-6-6-6"/></svg><span id="pdgripLbl">Paper</span></button>
  <main><article class="markdown-body" id="doc">rendering…</article><div id="rail"></div></main>
  <button id="pdcbtn2" type="button" title="Paper comments"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7A8.4 8.4 0 0 1 4 11.5 8.5 8.5 0 0 1 12.5 3 8.5 8.5 0 0 1 21 11.5z"/></svg><span class="lbl">Comments</span><span class="n">0</span></button>
</div>
<div id="pdbar"></div>
<div id="pdabar"></div>
<audio id="pdAudio" preload="auto"></audio>
<audio id="pdTurn" preload="auto"></audio>
<div id="pdsubs"></div>
<div id="pdscrim"></div>
<aside id="pdchat">
  <div class="ch-head"><span class="ch-dot" id="chDot"></span><span>Agent</span>
    <button class="ch-x" id="chX" type="button" title="Close (g)">&#215;</button></div>
  <div class="ch-log" id="chLog"></div>
  <div class="ch-foot"><textarea id="chIn" placeholder="Ask the agent&#8230;"></textarea>
    <div class="ch-hint">Enter to send &#183; Shift+Enter for a new line</div></div>
</aside>
<div id="pdnotes"><div class="nhead">Speaker notes</div><div class="nbody" id="pdnotesBody"></div></div>
<div id="docsig">__SIG_BADGE__<button id="docsigX" type="button" title="Hide">&#215;</button></div>
<script>document.getElementById("docsigX").addEventListener("click",()=>document.getElementById("docsig").classList.add("gone"));</script>
<div id="pdsig"><button id="pdsigX" type="button" title="Hide">&#215;</button>__PD_BADGE__</div>
__PLUS_HEAD__
<script>window.PD_AUDIO=null;/*PD_AUDIO_SLOT*/</script>
<script>
  const DOCS = __DOCS_JSON__;
  const state = { current: DOCS[0].path, annots: {} };
  let annotSeq = 1;
  // Deck mode: `main`/#doc holds paper.md and stays an ordinary browser-preview
  // document (comment engine untouched). The slides are their own pane beside it.
  const DECK = __DECK__;
  const PLUS = __PLUS__;
  const SLIDES = __SLIDES_JSON__;
  const DECK_TITLE = __DECK_TITLE__;
  const HAS_PAPER = __HAS_PAPER__;
  const deckState = { i:0, split:false, full:false, notesOpen:false, navOpen:false, focus:true };
  // Injected by pdnarrate.py, absent otherwise. { autoplay, clips:[{src,dur}|null,...] }
  const AUDIO = (window.PD_AUDIO && Array.isArray(window.PD_AUDIO.cues)) ? window.PD_AUDIO : null;
  if(DECK){
    document.body.classList.add('deck');
    // the stage is exactly the viewport minus the header — measure it, since badge
    // text metrics move the header height by a few px per platform
    const syncHdr = () => document.body.style.setProperty(
      '--hdr', document.querySelector('header').offsetHeight + 'px');
    syncHdr();
    addEventListener('resize', () => { syncHdr(); try{ layoutRail(); }catch(e){} });
  }
  // ── surfaces ─────────────────────────────────────────────────────────────
  // A "surface" is one commentable pane: an element holding line-tagged blocks plus
  // the rail its comment cards live in. Normal mode has exactly one (#doc + #rail).
  // Deck mode adds a second for the slide stage, so both panes comment identically.
  // Threads are already keyed by an arbitrary string in state.annots, so a surface's
  // key IS that string — slides need no new storage, just their own key.
  const SURFACES = [];
  function addSurface(key, doc, rail){
    const sf = { key, doc, rail };
    SURFACES.push(sf);
    return sf;
  }
  function sfOfNode(n){
    const el = n && (n.nodeType === 1 ? n : n.parentElement);
    return el && SURFACES.find(s => s.doc.contains(el) || s.rail.contains(el));
  }
  function sfOfKey(k){ return SURFACES.find(s => s.key === k); }
  // Anchors are measured in the rail parent's unscrolled coordinate space: when that
  // parent scrolls itself (the paper pane, a slide) the cards track their text.
  function originTop(sf){
    const par = sf.rail.parentElement;
    return par.getBoundingClientRect().top - par.scrollTop;
  }

  const prefersDark = matchMedia('(prefers-color-scheme: dark)').matches;
  mermaid.initialize({ startOnLoad:false, theme: prefersDark ? 'dark' : 'default', securityLevel:'loose' });
  const renderer = new marked.Renderer();
  const origCode = renderer.code.bind(renderer);
  renderer.code = (code, lang) => {
    const text = (typeof code === 'object') ? code.text : code;
    const language = (typeof code === 'object') ? code.lang : lang;
    const lw = (language||'').trim().split(/\s+/);
    const kind = (lw[0] || '').toLowerCase();
    // In plus mode a mermaid fence on a SLIDE becomes an editable Excalidraw canvas
    // seeded from that same mermaid, while the paper keeps the rendered diagram.
    // That split is the point: the paper is the uneditable source of truth and the
    // slide is the working surface, so a scene is a DERIVED view of the paper's
    // mermaid — which is what makes "reseed" a safe action rather than a loss.
    if(kind === 'mermaid'){
      if(!PLUS || !RENDER_SLIDE) return `<pre class="mermaid">${text}</pre>`;
      return drawBox(nameFor(lw[1], text), text);
    }
    if(PLUS && kind === 'draw'){
      return drawBox(nameFor(lw[1], text), '');
    }
    if(PLUS && lw[0] === 'app'){
      const url = (lw[1] || text.trim().split('\n')[0] || '').replace(/["'<>]/g, '');
      const h = (lw[2] || '').match(/^\d+$/) ? lw[2] : '520';
      return `<div class="pd-app" style="height:${h}px"><div class="pd-app-head">` +
             `<span class="pd-app-url">${escapeHtml(url)}</span>` +
             `<button class="pd-app-reload" data-url="${escapeHtml(url)}">Reload</button>` +
             `<a href="${escapeHtml(url)}" target="_blank" rel="noopener">Open \u2197</a></div>` +
             `<iframe src="${escapeHtml(url)}" loading="lazy"></iframe></div>`;
    }
    return origCode(code, lang);
  };
  marked.setOptions({ renderer, gfm:true });

  function setupZoom(root){
    const ov = document.createElement('div');
    ov.className = 'mzoom-overlay';
    ov.innerHTML = '<div class="mzoom-stage"></div>'
      + '<div class="mzoom-hint">scroll to zoom · drag to pan · Esc to close</div>'
      + '<div class="mzoom-controls">'
      + '<button data-z="copy">Copy image</button>'
      + '<button data-z="out">−</button><button data-z="reset">Reset</button>'
      + '<button data-z="in">+</button><button data-z="close">✕</button></div>';
    document.body.appendChild(ov);
    const stage = ov.querySelector('.mzoom-stage');
    // cur is the pannable clone shown on the stage; curSrc is the original, already-
    // rendered element still in the doc — copying reads from curSrc so it never races
    // the clone's own (re)load of an <img src>.
    let cur=null, curSrc=null, scale=1, tx=0, ty=0, dragging=false, sx=0, sy=0;
    const apply = () => { if(cur) cur.style.transform = `translate(${tx}px,${ty}px) scale(${scale})`; };
    const open = (srcEl) => {
      stage.innerHTML=''; curSrc = srcEl; cur = srcEl.cloneNode(true);
      stage.appendChild(cur); scale=1; tx=0; ty=0; apply(); ov.classList.add('show');
    };
    const close = () => ov.classList.remove('show');
    ov.addEventListener('wheel', e => { e.preventDefault();
      const f = e.deltaY<0 ? 1.12 : 1/1.12; scale = Math.min(10, Math.max(.15, scale*f)); apply();
    }, {passive:false});
    stage.addEventListener('pointerdown', e => { dragging=true; sx=e.clientX-tx; sy=e.clientY-ty; stage.setPointerCapture(e.pointerId); });
    stage.addEventListener('pointermove', e => { if(dragging){ tx=e.clientX-sx; ty=e.clientY-sy; apply(); } });
    stage.addEventListener('pointerup', () => dragging=false);
    ov.addEventListener('click', e => { if(e.target===ov || e.target===stage) close(); });
    ov.querySelector('.mzoom-controls').addEventListener('click', e => {
      const z = e.target.getAttribute('data-z'); if(!z) return;
      if(z==='copy'){ if(curSrc) copyImageEl(curSrc); return; }
      else if(z==='in') scale=Math.min(10, scale*1.25);
      else if(z==='out') scale=Math.max(.15, scale/1.25);
      else if(z==='reset'){ scale=1; tx=0; ty=0; }
      else if(z==='close'){ close(); return; }
      apply();
    });
    document.addEventListener('keydown', e => { if(e.key==='Escape') close(); });
    root.querySelectorAll('.mermaid').forEach(m => {
      m.addEventListener('click', () => { const svg=m.querySelector('svg'); if(svg) open(svg); });
    });
    // Plain markdown images (`![]()`) get the same zoom+copy lightbox as diagrams —
    // previously they had no click behavior and no way to get the actual pixels out.
    root.querySelectorAll('img').forEach(img => {
      img.style.cursor = 'zoom-in';
      img.addEventListener('click', () => open(img));
    });
  }

  // ponytail: line = the containing block's start line in source (paragraph/heading/
  // list/table/code-fence granularity, not per rendered visual line — a full source
  // map through marked would need per-inline-token tracking). char = offset within
  // that block's *rendered* text, not raw markdown (formatting chars are stripped by
  // render). Good enough to relocate a comment; not a byte-exact source pointer.
  function tagLines(root, src){
    let tokens;
    try { tokens = marked.lexer(src, {gfm:true}); } catch(e){ return; }
    const lineOf = idx => src.slice(0, idx).split('\n').length;
    let cursor = 0;
    // Tokens and rendered children are NOT 1:1 — marked emits `space` tokens for blank
    // lines, which render nothing. Walking both with one index (the old bug) shifted every
    // block's line number by however many blank lines preceded it, so comments anchored to
    // the wrong source lines. Advance the element index only for tokens that produced one.
    const els = Array.from(root.children);
    let ei = 0;
    tokens.forEach(tok => {
      if(!tok || !tok.raw) return;
      const idx = src.indexOf(tok.raw, cursor);
      if(idx === -1) return;
      cursor = idx + tok.raw.length;
      if(tok.type === 'space') return;
      // An HTML block that renders to nothing but comments produces no element child,
      // so consuming an element for it shifts every block below onto the wrong source
      // line — and comments are how a paper carries `<!-- say: -->` bridge lines.
      if(tok.type === 'html' && !/<[a-zA-Z]/.test(tok.raw)) return;
      const el = els[ei++];
      if(!el) return;
      // raw swallows the blank line after a block; trim it so lineEnd is the last line
      // that actually holds text.
      const rawEnd = idx + Math.max(1, tok.raw.replace(/\s+$/, '').length) - 1;
      // Lists render as one <ul>/<ol> per token but should highlight/anchor per bullet,
      // not the whole list — tag each <li> with its own line span and skip the wrapper
      // so blockForLine()/closest('.mline') resolve to the specific item, not the group.
      if(tok.type === 'list' && Array.isArray(tok.items)){
        const items = el.querySelectorAll(':scope > li');
        let itemCursor = idx;
        tok.items.forEach((item, j) => {
          const li = items[j];
          if(!li || !item.raw) return;
          const iidx = src.indexOf(item.raw, itemCursor);
          if(iidx === -1) return;
          itemCursor = iidx + item.raw.length;
          li.classList.add('mline');
          li.dataset.mlineStart = lineOf(iidx);
          li.dataset.mlineEnd = lineOf(iidx + Math.max(1, item.raw.replace(/\s+$/, '').length) - 1);
        });
        return;
      }
      el.classList.add('mline');
      el.dataset.mlineStart = lineOf(idx);
      el.dataset.mlineEnd = lineOf(rawEnd);
    });
  }

  // Maps a Y coordinate to a source line within a block by position (block spans
  // dataset.mlineStart..mlineEnd from tagLines). Approximation, same ceiling as the old
  // char-offset approach: good enough to land a comment on the right line, not exact for
  // blocks with wrapped/variable-height inline content.
  function lineAtY(block, clientY){
    const start = Number(block.dataset.mlineStart), end = Number(block.dataset.mlineEnd);
    if(start === end) return start;
    const rect = block.getBoundingClientRect();
    const frac = Math.min(1, Math.max(0, (clientY - rect.top) / rect.height));
    return start + Math.round(frac * (end - start));
  }
  function blockForLine(line, sf){
    return Array.from(sf.doc.querySelectorAll('.mline'))
      .find(el => line >= Number(el.dataset.mlineStart) && line <= Number(el.dataset.mlineEnd));
  }

  // Highlights cover the SELECTED WORDS, not the block the selection landed in. A selection
  // is stored as character offsets into each touched block's text ({line, start, end}) rather
  // than a live Range, so it survives re-render/reflow and re-paints from state like the cards do.
  function textNodesOf(el){
    const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    const out = []; let n;
    while((n = w.nextNode())) out.push(n);
    return out;
  }
  function rangeSpans(range, sf){
    const out = [];
    sf.doc.querySelectorAll('.mline').forEach(block => {
      if(!range.intersectsNode(block)) return;
      let acc = 0, start = null, end = null;
      textNodesOf(block).forEach(n => {
        const len = n.nodeValue.length;
        if(range.intersectsNode(n)){
          const s = (n === range.startContainer) ? range.startOffset : 0;
          const e = (n === range.endContainer) ? range.endOffset : len;
          if(e > s){ if(start === null) start = acc + s; end = acc + e; }
        }
        acc += len;
      });
      if(start !== null && end > start) out.push({ line: Number(block.dataset.mlineStart), start, end });
    });
    return out;
  }
  function clearHighlights(sf){
    sf.doc.querySelectorAll('.mhl').forEach(s => {
      const p = s.parentNode;
      while(s.firstChild) p.insertBefore(s.firstChild, s);
      p.removeChild(s); p.normalize();
    });
  }
  // overlapping spans in one block would nest one .mhl inside another (double-darkened
  // background), so coalesce them first.
  function mergeSpans(spans){
    const out = [];
    (spans || []).slice().sort((a, b) => a.line - b.line || a.start - b.start).forEach(s => {
      const p = out[out.length - 1];
      if(p && p.line === s.line && s.start <= p.end) p.end = Math.max(p.end, s.end);
      else out.push({ line: s.line, start: s.start, end: s.end });
    });
    return out;
  }
  function paintSpans(spans, threadId, active, sf){
    mergeSpans(spans).forEach(sp => {
      const block = blockForLine(sp.line, sf);
      if(!block) return;
      let acc = 0;
      // snapshot first: extractContents() splits nodes, but the originals keep their
      // pre-split text before `start`, so the untouched later nodes stay correctly offset.
      textNodesOf(block).forEach(n => {
        const len = n.nodeValue.length;
        const s = Math.max(sp.start - acc, 0), e = Math.min(sp.end - acc, len);
        acc += len;
        if(s >= e) return;
        const r = document.createRange(); r.setStart(n, s); r.setEnd(n, e);
        const el = document.createElement('span');
        el.className = 'mhl' + (active ? ' active' : '');
        el.dataset.threadId = threadId;
        el.appendChild(r.extractContents());
        r.insertNode(el);
      });
    });
  }

  function copyText(text){
    // file:// pages aren't a secure context, so navigator.clipboard is often undefined —
    // fall back to the deprecated-but-still-working execCommand path.
    if(navigator.clipboard && navigator.clipboard.writeText){
      navigator.clipboard.writeText(text).catch(() => fallbackCopy(text));
    } else fallbackCopy(text);
  }
  function fallbackCopy(text){
    const ta = document.createElement('textarea');
    ta.value = text; ta.style.position='fixed'; ta.style.opacity='0';
    document.body.appendChild(ta); ta.focus(); ta.select();
    try{ document.execCommand('copy'); }catch(e){}
    document.body.removeChild(ta);
  }
  // Rasterize a live <svg> (already on-screen, so guaranteed sized) to a PNG data URL.
  // Mermaid diagrams are inline SVG, not a fetchable resource, so this is the only way
  // to get pixels for them — and a data: URL is never treated as cross-origin, so
  // (unlike a plain <img>, see below) it's safe to draw into a canvas.
  function svgToPngDataUrl(svg){
    return new Promise((resolve, reject) => {
      const rect = svg.getBoundingClientRect();
      const w = Math.max(1, Math.round((rect.width || 800) * 2));
      const h = Math.max(1, Math.round((rect.height || 600) * 2));
      const xml = new XMLSerializer().serializeToString(svg);
      const svg64 = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(xml)));
      const img = new Image();
      img.onload = () => {
        const c = document.createElement('canvas'); c.width = w; c.height = h;
        const ctx = c.getContext('2d');
        ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, w, h); // mermaid svgs are transparent
        ctx.drawImage(img, 0, 0, w, h);
        resolve(c.toDataURL('image/png'));
      };
      img.onerror = reject;
      img.src = svg64;
    });
  }
  // Select `src` (loaded fresh into a hidden <img>) inside a contenteditable and run
  // the deprecated execCommand('copy') — the scripted equivalent of "right-click > Copy
  // Image". Unlike canvas or fetch(), this isn't blocked by file://'s same-origin rules
  // (it's a native browser action, not script pixel/byte access), which is what makes
  // it the fallback that actually works for a plain markdown image opened from disk.
  function execCommandCopyImg(src){
    return new Promise(resolve => {
      const host = document.createElement('div');
      host.contentEditable = 'true';
      host.style.cssText = 'position:fixed;left:-9999px;top:0;opacity:0;';
      const img = document.createElement('img');
      const finish = ok => { try{ document.body.removeChild(host); }catch(e){} resolve(ok); };
      img.onload = () => {
        try{
          const range = document.createRange(); range.selectNode(img);
          const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(range);
          const ok = document.execCommand('copy');
          sel.removeAllRanges(); finish(ok);
        }catch(e){ finish(false); }
      };
      img.onerror = () => finish(false);
      host.appendChild(img); document.body.appendChild(host);
      img.src = src;
    });
  }
  async function writeImageToClipboard(src){
    try{
      if(navigator.clipboard && navigator.clipboard.write && window.ClipboardItem){
        const blob = await (await fetch(src)).blob();
        await navigator.clipboard.write([new ClipboardItem({[blob.type || 'image/png']: blob})]);
        return true;
      }
    }catch(e){}
    // The async path above needs a secure context AND a fetchable src — file:// is
    // neither secure nor (per Chrome) willing to fetch() a sibling file:// resource, so
    // a plain <img> pointing at disk falls straight through to execCommandCopyImg.
    return execCommandCopyImg(src);
  }
  async function copyImageEl(el){
    try{
      // <img>: copy its real source bytes directly — no canvas detour, since a plain
      // <img> loaded from file:// taints any canvas it's drawn into (toDataURL throws),
      // even for an image sitting right next to the doc.
      // <svg>: mermaid diagrams have no source file at all, so rasterize the live DOM.
      const src = el.tagName === 'IMG' ? el.src : await svgToPngDataUrl(el);
      const ok = await writeImageToClipboard(src);
      showToast(ok ? 'Copied image' : 'Copy failed — try right-click the image');
    }catch(e){
      showToast('Copy failed — try right-click the image');
    }
  }
  function showToast(msg){
    let t = document.getElementById('toast');
    if(!t){ t = document.createElement('div'); t.id='toast'; t.className='toast'; document.body.appendChild(t); }
    t.textContent = msg; t.classList.add('show');
    clearTimeout(showToast._h); showToast._h = setTimeout(() => t.classList.remove('show'), 1600);
  }

  // Comments are threads, not flat notes: {id, line, lineEnd, quote, comments:[{id,text}]},
  // anchored to the whole source line(s) the selection touched (not a char offset), and
  // carrying the selected text itself so a note reads as "this bit, this comment" instead of
  // a bare line number. Every thread is a permanently visible card in the right rail (Google
  // Docs style) — no pins, nothing to click open. Selecting again on an overlapping line
  // range replies into the existing thread instead of starting a disconnected second one.
  // Google Docs semantics: a thread owns the exact TEXT it was left on, not the line. Two
  // separate selections in one paragraph are two comments; only re-selecting text that
  // overlaps an existing highlight lands you back in that thread (to reply).
  function spansOverlap(a, b){
    return (a || []).some(x => (b || []).some(y => y.line === x.line && x.start < y.end && y.start < x.end));
  }
  function findThreadAtSpans(file, spans){
    return (state.annots[file] || []).find(t => spansOverlap(spans, t.spans));
  }
  function addThread(file, line, lineEnd, quote, text, spans){
    const t = { id: annotSeq++, line, lineEnd, quote, spans: spans || [], comments: [{ id: annotSeq++, text }] };
    (state.annots[file] = state.annots[file] || []).push(t);
    return t;
  }
  function addReply(file, threadId, text){
    const t = (state.annots[file] || []).find(t => t.id === threadId);
    if(t) t.comments.push({ id: annotSeq++, text });
  }
  function deleteComment(file, threadId, commentId){
    const list = state.annots[file] || [];
    const t = list.find(t => t.id === threadId);
    if(!t) return;
    t.comments = t.comments.filter(c => c.id !== commentId);
    if(!t.comments.length) state.annots[file] = list.filter(x => x !== t);
  }
  // Speech-bubble icon for card heads — stroke style matches the header copy buttons (no emoji).
  const CHAT_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" '
    + 'stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7'
    + 'A8.4 8.4 0 0 1 4 11.5 8.5 8.5 0 0 1 12.5 3 8.5 8.5 0 0 1 21 11.5z"/></svg>';

  function updateNotesBadge(){
    const el = document.getElementById('notesCount');
    const total = Object.values(state.annots).reduce((n, threads) => n + threads.reduce((m, t) => m + t.comments.length, 0), 0);
    const prev = Number(el.textContent) || 0;
    el.textContent = total;
    el.classList.toggle('has', total > 0);
    if(total !== prev){ el.classList.remove('bump'); void el.offsetWidth; el.classList.add('bump'); }
  }

  function lineLabel(t){ return 'L' + t.line + (t.lineEnd > t.line ? '-' + t.lineEnd : ''); }
  function clipQuote(s, n){
    s = (s || '').replace(/\s+/g, ' ').trim();
    return s.length > n ? s.slice(0, n - 1).trimEnd() + '…' : s;
  }

  // Where a card wants to sit: the top of the commented line, in main's coordinate space.
  // Derived from the block each render (not cached) so resize/reflow re-anchors for free.
  function anchorFor(line, sf){
    const block = blockForLine(line, sf);
    if(!block) return null;
    const mainTop = originTop(sf);
    const bs = Number(block.dataset.mlineStart), be = Number(block.dataset.mlineEnd);
    const r = block.getBoundingClientRect();
    const off = be > bs ? (line - bs) / (be - bs) * Math.max(0, r.height - 18) : 0;
    return { block, top: Math.round(r.top - mainTop + off) };
  }
  // Classic margin-notes sweep: every card at its anchor, pushed down only as far as the
  // card above it forces. ponytail: no re-centering on the active card, the stack is enough.
  function layoutRail(sf){
    if(!sf || !sf.rail) return SURFACES.forEach(s => layoutRail(s));
    const cards = Array.from(sf.rail.children)
      .sort((a, b) => Number(a.dataset.anchor) - Number(b.dataset.anchor));
    let y = 0;
    cards.forEach(c => {
      const top = Math.max(Number(c.dataset.anchor) || 0, y);
      c.style.top = top + 'px';
      y = top + c.offsetHeight + 8;
    });
  }
  function setActiveCard(card){
    document.querySelectorAll('.rail-card.active').forEach(c => c.classList.remove('active'));
    document.querySelectorAll('.mhl.active').forEach(el => el.classList.remove('active'));
    if(!card) return;
    const sf = sfOfNode(card);
    card.classList.add('active');
    const id = card.dataset.threadId || 'draft';
    if(sf) sf.doc.querySelectorAll('.mhl[data-thread-id="' + id + '"]').forEach(el => el.classList.add('active'));
    layoutRail(sf);
  }

  function cardHead(title, sub, onDelete){
    const head = document.createElement('div'); head.className = 'cb-head';
    const icon = document.createElement('span'); icon.className = 'cb-head-icon'; icon.innerHTML = CHAT_SVG;
    const t = document.createElement('span'); t.className = 'cb-head-title'; t.textContent = title;
    head.appendChild(icon); head.appendChild(t);
    if(sub){ const s = document.createElement('span'); s.className = 'cb-head-line'; s.textContent = sub; head.appendChild(s); }
    if(onDelete){
      const x = document.createElement('button'); x.className = 'cb-close'; x.textContent = '×';
      x.title = 'Delete thread';
      x.addEventListener('click', e => { e.stopPropagation(); onDelete(); });
      head.appendChild(x);
    }
    return head;
  }
  // The quoted text is the point of the card: it shows WHAT was highlighted, so the note
  // stands on its own without scrolling back to the line it points at.
  function quoteEl(text){
    const q = document.createElement('div'); q.className = 'cb-quote';
    q.textContent = clipQuote(text, 160);
    return q;
  }
  function composer(placeholder, label, onSubmit){
    const ta = document.createElement('textarea'); ta.placeholder = placeholder;
    const row = document.createElement('div'); row.className = 'cb-row';
    const save = document.createElement('button'); save.className = 'cb-save'; save.textContent = label;
    save.addEventListener('click', e => {
      e.stopPropagation();
      const text = ta.value.trim();
      if(text) onSubmit(text);
    });
    ta.addEventListener('keydown', e => {
      if((e.metaKey || e.ctrlKey) && e.key === 'Enter'){ e.preventDefault(); save.click(); }
    });
    ta.addEventListener('input', () => layoutRail(sfOfNode(ta)));
    row.appendChild(save);
    return { ta, row };
  }

  function buildThreadCard(t, file){
    const card = document.createElement('div'); card.className = 'rail-card';
    card.dataset.line = t.line;
    card.appendChild(cardHead(t.comments.length > 1 ? `Thread · ${t.comments.length}` : 'Comment', lineLabel(t), () => {
      state.annots[file] = (state.annots[file] || []).filter(x => x !== t);
      renderRail();
    }));
    if(t.quote) card.appendChild(quoteEl(t.quote));
    const list = document.createElement('div'); list.className = 'cb-thread';
    t.comments.forEach(c => {
      const row = document.createElement('div'); row.className = 'cb-comment';
      const txt = document.createElement('span'); txt.textContent = c.text;
      const del = document.createElement('button'); del.textContent = '×'; del.className = 'cb-comment-del';
      del.title = 'Delete comment';
      del.addEventListener('click', e => {
        e.stopPropagation();
        deleteComment(file, t.id, c.id);
        renderRail();
      });
      row.appendChild(txt); row.appendChild(del);
      list.appendChild(row);
    });
    card.appendChild(list);
    const { ta, row } = composer('Reply…', 'Reply', text => {
      addReply(file, t.id, text);
      renderRail();
      focusThread(t.id);
    });
    card.appendChild(ta); card.appendChild(row);
    card.addEventListener('click', () => setActiveCard(card));
    card.addEventListener('focusin', () => setActiveCard(card));
    return card;
  }

  function focusThread(threadId, sf){
    const card = Array.from(sf.rail.children).find(c => Number(c.dataset.threadId) === threadId);
    if(card) setActiveCard(card);
  }

  let draft = null;  // { line, lineEnd, quote, el } — not in state until posted
  function discardDraft(){
    if(!draft) return;
    const sf = draft.sf;
    draft.el.remove(); draft = null;
    clearHighlights(sf); renderRail(sf);
  }
  function openDraft(file, line, lineEnd, quote, spans){
    const sf = sfOfKey(file);
    if(!sf) return;
    discardDraft();
    const card = document.createElement('div'); card.className = 'rail-card draft';
    card.dataset.line = line;
    card.appendChild(cardHead('New comment', 'L' + line + (lineEnd > line ? '-' + lineEnd : ''), discardDraft));
    if(quote) card.appendChild(quoteEl(quote));
    const { ta, row } = composer('Add a comment…', 'Comment', text => {
      const t = addThread(file, line, lineEnd, quote, text, spans);
      discardDraft();
      renderRail(sf);
      focusThread(t.id, sf);
    });
    card.appendChild(ta); card.appendChild(row);
    sf.rail.appendChild(card);
    setCx(sf, true);
    draft = { line, lineEnd, quote, spans, el: card, sf };
    paintSpans(spans, 'draft', true, sf);
    card.dataset.anchor = anchorForThread('draft', line, sf) || 0;
    layoutRail(sf);
    ta.focus();
  }

  // A card sits beside its own highlight, so two comments on one paragraph stack in the
  // order their words appear — line-only anchoring put them at the same y.
  function anchorForThread(id, line, sf){
    const hl = sf.doc.querySelector('.mhl[data-thread-id="' + id + '"]');
    if(hl) return Math.round(hl.getBoundingClientRect().top - originTop(sf));
    const a = anchorFor(line, sf);
    return a ? a.top : null;
  }

  function renderRail(sf){
    if(!sf || !sf.rail) return SURFACES.forEach(s => renderRail(s));
    const rail = sf.rail;
    Array.from(rail.children).forEach(c => { if(!draft || c !== draft.el) c.remove(); });
    clearHighlights(sf);
    const threads = (state.annots[sf.key] || []).slice();
    threads.forEach(t => paintSpans(t.spans, t.id, false, sf));
    if(draft && draft.sf === sf) paintSpans(draft.spans, 'draft', true, sf);
    threads.map(t => ({ t, top: anchorForThread(t.id, t.line, sf) }))
      .filter(x => x.top !== null)
      .sort((a, b) => a.top - b.top)
      .forEach(({ t, top }) => {
        const card = buildThreadCard(t, sf.key);
        card.dataset.threadId = t.id;
        card.dataset.anchor = top;
        rail.appendChild(card);
      });
    if(draft && draft.sf === sf){
      const top = anchorForThread('draft', draft.line, sf);
      if(top !== null) draft.el.dataset.anchor = top;
    }
    updateCommentPill(sf, rail.children.length);
    layoutRail(sf);
    updateNotesBadge();
  }
  // Clicking highlighted text focuses its card, the way clicking a Google Docs highlight does.
  document.addEventListener('click', e => {
    const hl = e.target.closest && e.target.closest('.mhl');
    if(!hl) return;
    const sf = sfOfNode(hl);
    if(!sf) return;
    const card = Array.from(sf.rail.children)
      .find(c => (c.dataset.threadId || 'draft') === hl.dataset.threadId);
    if(card) setActiveCard(card);
  });
  document.addEventListener('keydown', e => { if(e.key === 'Escape') discardDraft(); });
  let relayoutTimer = null;
  window.addEventListener('resize', () => { clearTimeout(relayoutTimer); relayoutTimer = setTimeout(() => renderRail(), 120); });

  // ponytail: sidebar is a real nested tree via native <details>/<summary> — no tree-view
  // library, the platform already does collapse/expand. First two levels auto-open so a
  // small skill folder (SKILL.md, scripts/, state/) reads at a glance; deeper folders stay
  // collapsed until clicked.
  function buildTree(docs){
    const root = { dirs: {}, files: [] };
    docs.forEach(d => {
      const parts = d.path.split('/');
      let node = root;
      for(let i = 0; i < parts.length - 1; i++){
        const p = parts[i];
        node.dirs[p] = node.dirs[p] || { dirs: {}, files: [] };
        node = node.dirs[p];
      }
      node.files.push(d);
    });
    return root;
  }
  // Real vscode-icons SVGs (same set the VS Code file explorer ships), loaded from
  // jsdelivr — CDN already required for marked/mermaid/hljs, so this adds no new
  // category of dependency, just one more asset off the same pipe.
  const ICON_BASE = 'https://cdn.jsdelivr.net/gh/vscode-icons/vscode-icons@master/icons/';
  const EXT_ICON = {
    py:'python', js:'js', jsx:'js', ts:'typescript', tsx:'typescript',
    sh:'shell', bash:'shell', zsh:'shell',
    json:'json', yaml:'yaml', yml:'yaml', toml:'toml',
    go:'go', rs:'rust', java:'java', rb:'ruby',
    css:'css', scss:'scss', html:'html', sql:'sql',
    c:'c', cpp:'cpp', h:'c', hpp:'cpp',
    swift:'swift', kt:'kotlin', php:'php', lua:'lua',
    xml:'xml', ps1:'powershell', ini:'ini', cfg:'ini',
  };
  function iconUrlFor(d){
    if(d.kind === 'markdown') return ICON_BASE + 'file_type_markdown.svg';
    if(d.kind === 'image') return ICON_BASE + 'file_type_svg.svg';
    const ext = d.path.split('.').pop().toLowerCase();
    const name = EXT_ICON[ext];
    return ICON_BASE + (name ? `file_type_${name}.svg` : 'default_file.svg');
  }
  const CHEVRON_SVG = '<svg class="chevron" viewBox="0 0 16 16"><path d="M6 4l4 4-4 4" fill="none" '
    + 'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  function fileLink(d){
    const a = document.createElement('a');
    a.href = '#'; a.dataset.path = d.path;
    const ico = document.createElement('img'); ico.className = 'ico'; ico.src = iconUrlFor(d); ico.alt = '';
    const label = document.createElement('span'); label.textContent = d.path.split('/').pop();
    a.appendChild(ico); a.appendChild(label);
    if(d.path === state.current) a.classList.add('active');
    a.addEventListener('click', e => { e.preventDefault(); selectDoc(d.path); });
    return a;
  }
  function renderTreeNode(node, container, depth){
    Object.keys(node.dirs).sort().forEach(dname => {
      const details = document.createElement('details');
      details.open = depth < 2;
      const summary = document.createElement('summary');
      summary.insertAdjacentHTML('beforeend', CHEVRON_SVG);
      const dirIco = document.createElement('img'); dirIco.className = 'dir-ico'; dirIco.alt = '';
      dirIco.src = ICON_BASE + (details.open ? 'default_folder_opened.svg' : 'default_folder.svg');
      summary.appendChild(dirIco);
      summary.appendChild(document.createTextNode(dname));
      details.addEventListener('toggle', () => {
        dirIco.src = ICON_BASE + (details.open ? 'default_folder_opened.svg' : 'default_folder.svg');
      });
      details.appendChild(summary);
      renderTreeNode(node.dirs[dname], details, depth + 1);
      container.appendChild(details);
    });
    node.files.slice().sort((a, b) => a.path.localeCompare(b.path)).forEach(d => container.appendChild(fileLink(d)));
  }
  function renderSidebar(){
    const nav = document.getElementById('sidebar');
    nav.innerHTML = '';
    if(DOCS.length <= 1){ nav.classList.add('hidden'); return; }
    nav.classList.remove('hidden');
    renderTreeNode(buildTree(DOCS), nav, 0);
  }
  // ── deck ────────────────────────────────────────────────────────────────
  // Component vocabulary. Each `:::name` block is expanded to finished HTML BEFORE
  // the slide's markdown is parsed; marked passes an HTML block through untouched.
  // This is what keeps slide markup terse — a three-up card row is 5 lines, not 25
  // divs of inline style.
  const STATUS = { strong:'good', good:'good', solid:'good', warn:'warn', 'worth exploring':'warn',
                   maybe:'warn', weak:'bad', bad:'bad', leak:'bad', risk:'bad' };
  function pill(txt){
    const k = (txt || '').trim().toLowerCase();
    if(!k) return '';
    return '<span class="pd-pill" data-s="' + (STATUS[k] || '') + '">' + escapeHtml(txt.trim()) + '</span>';
  }
  // splits an inner block on '### ' headers -> [{head, body}]
  function sections(inner){
    const out = [];
    inner.split(/^###[ \t]+/m).forEach((chunk, i) => {
      if(i === 0 && !chunk.trim()) return;
      const nl = chunk.indexOf('\n');
      out.push({ head: (nl === -1 ? chunk : chunk.slice(0, nl)).trim(),
                 body: (nl === -1 ? '' : chunk.slice(nl + 1)).trim() });
    });
    return out;
  }
  const COMPONENTS = {
    // ### Eyebrow | status  /  first line = title  /  rest = meta
    cards(inner){
      return '<div class="pd-cards">' + sections(inner).map(sec => {
        const [lbl, st] = sec.head.split('|');
        const lines = sec.body.split('\n').filter(l => l.trim());
        const title = lines.shift() || '';
        return '<div class="pd-card"><p class="pd-lbl">' + escapeHtml((lbl||'').trim()) + pill(st||'') + '</p>'
             + '<p class="pd-title">' + marked.parseInline(title) + '</p>'
             + (lines.length ? '<p class="pd-meta">' + marked.parseInline(lines.join(' ')) + '</p>' : '')
             + '</div>';
      }).join('') + '</div>';
    },
    // ### Heading  /  arbitrary markdown, laid out in columns
    cols(inner){
      return '<div class="pd-cols">' + sections(inner).map(sec =>
        '<div class="pd-card"><p class="pd-lbl">' + escapeHtml(sec.head) + '</p>'
        + marked.parse(sec.body) + '</div>').join('') + '</div>';
    },
    // value | label | unit
    stats(inner){
      return '<div class="pd-stats">' + inner.split('\n').filter(l => l.trim()).map(l => {
        const c = l.split('|').map(x => x.trim());
        return '<div class="pd-stat"><span class="v">' + escapeHtml(c[0] || '') + '</span>'
             + '<span class="k">' + marked.parseInline(c[1] || '') + '</span>'
             + '<span class="u">' + escapeHtml(c[2] || '') + '</span></div>';
      }).join('') + '</div>';
    },
    deep(inner){ return '<div class="pd-deep">' + marked.parse(inner) + '</div>'; },
    note(inner){ return '<div class="pd-note">' + marked.parse(inner) + '</div>'; },
  };
  // A fence that survived every expansion is a mistake, not content — a typo, or a
  // one-line `:::paper` the server already consumed. Drop the line rather than print
  // `:::paper` at the reader. Emptied, not deleted, so slide comment line numbers stay
  // true to deck.md — and skipped inside code fences, where `:::cards` is someone
  // documenting the syntax rather than using it.
  const FENCE_LINE = /^[ \t]*:{3,}[ \t]*\w*[ \t]*:{0,}[ \t]*$/;
  const BLOCK_RE = /^:::[ \t]*([a-z]+)[ \t]*\r?\n([\s\S]*?)^:::[ \t]*$/gm;
  // The expansion is padded back to the line count it replaced, so a comment left on a
  // component still reports the line it occupies in deck.md.
  // ponytail: newlines inside the generated HTML are flattened to keep that count exact —
  // a <pre> authored inside a ::: block would lose its line breaks. Put code outside them.
  function expandBlocks(src){
    // Everything inside a ``` fence is someone SHOWING the syntax, not using it.
    // Neither the component expansion nor the stray-fence drop may touch it — a deck
    // documenting `:::cards` was rendering a real card row instead of the code.
    const out = [];
    let buf = [], code = null;
    const flush = () => { if(buf.length){ out.push(expandRegion(buf.join('\n'))); buf = []; } };
    src.split('\n').forEach(ln => {
      const m = ln.match(/^\s*(```|~~~)/);
      if(code){ out.push(ln); if(m && ln.trim().startsWith(code)) code = null; return; }
      if(m){ flush(); code = ln.trim().slice(0, 3); out.push(ln); return; }
      buf.push(ln);
    });
    flush();
    return out.join('\n');
  }
  function expandRegion(src){
    const done = src.replace(BLOCK_RE, (m, name, inner) => {
      if(!COMPONENTS[name]) return m;
      const lines = m.split('\n').length;
      const html = COMPONENTS[name](inner).replace(/\n+/g, ' ');
      return html + '\n'.repeat(Math.max(0, lines - 1));
    });
    return done.split('\n').map(ln => FENCE_LINE.test(ln) ? '' : ln).join('\n');
  }

  function buildSlides(){
    const stage = document.getElementById('stage');
    SLIDES.forEach((sl, n) => {
      const sec = document.createElement('div');
      sec.className = 'slide';
      const pad = document.createElement('div');
      pad.className = 'pad';
      const src = expandBlocks(sl.content);
      RENDER_SLIDE = true; NAME_SLIDE = n; NAME_N = 0;
      pad.innerHTML = marked.parse(src);
      RENDER_SLIDE = false;
      Array.from(pad.children).forEach((c, i) => c.style.setProperty('--i', Math.min(i, 8)));
      try { tagLines(pad, src); } catch(e){}
      try { setupZoom(pad); } catch(e){}
      sec.appendChild(pad);
      stage.appendChild(sec);
    });
    stage.querySelectorAll('pre code').forEach(b => { try{ hljs.highlightElement(b); }catch(e){} });
    try { mermaid.run({ nodes: stage.querySelectorAll('.mermaid') }); } catch(e){}
  }

  // ── the paper, sectioned ────────────────────────────────────────────────
  // Every slide owns a DISTINCT section of the paper. Two halves, and the split is
  // the point: sectionizePaper() cuts the rendered paper into .pp-sec blocks (one per
  // heading), and pairSlides() *allocates* them across the deck once, up front.
  // Deciding slide 4's section in isolation — the old per-slide fuzzy lookup — is
  // exactly what let two slides land on the same heading and a third land nowhere.
  const STOP = new Set(['the','a','an','of','and','or','with','is','are','it','its','to',
                        'in','on','for','that','this','what','how','why','be','as','at','by']);
  function words(str){
    return (str || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()
      .split(' ').filter(w => w && !STOP.has(w));
  }
  function norm(s){ return (s || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim(); }
  let PAIR = [];
  function sectionizePaper(){
    const doc = document.getElementById('doc');
    if(!doc || !HAS_PAPER) return [];
    // after tagLines: the comment engine's line tags live on these same elements and
    // are carried into the wrapper untouched. Anchors are rect-based, not offsetTop-
    // based, so an unpositioned wrapper costs the rail nothing.
    const kids = Array.from(doc.children);
    const secs = [];
    let cur = null;
    kids.forEach(el => {
      if(!cur || el.tagName === 'H1' || el.tagName === 'H2' || el.tagName === 'H3'){
        cur = document.createElement('div');
        cur.className = 'pp-sec';
        cur.dataset.sec = secs.length;
        const tag = document.createElement('span');
        tag.className = 'pp-tag';
        cur.appendChild(tag);
        doc.insertBefore(cur, el);
        secs.push(cur);
      }
      cur.appendChild(el);
    });
    return secs;
  }
  function headText(sec){
    const h = sec.querySelector('h1,h2,h3');
    return h ? h.textContent : '';
  }
  // Three tiers, most confident first: exact text, prefix either way, then significant-
  // word containment ("The vocabulary" scores against "The component vocabulary").
  function scoreMatch(slideTitle, secTitle){
    const a = norm(slideTitle), b = norm(secTitle);
    if(!a || !b) return 0;
    if(a === b) return 3;
    if(a.startsWith(b) || b.startsWith(a)) return 2;
    const tw = words(a), hw = words(b);
    if(!tw.length || !hw.length) return 0;
    const A = new Set(hw), B = new Set(tw);
    return (tw.every(w => A.has(w)) || hw.every(w => B.has(w))) ? 1 : 0;
  }
  // Allocation, in three passes. `:::paper <heading>` pins outright. Then the fuzzy
  // tiers, scanned FORWARD from the last section taken and only over unclaimed ones —
  // a deck follows its paper's order, so order is a stronger signal than any single
  // fuzzy hit in isolation. Then the leftovers fill the gaps their pinned neighbours
  // left, which is what makes the mapping TOTAL: no slide opens the pane onto nothing.
  // Index pairing is still not the primary rule (a deck and a paper rarely have the
  // same section count) — it is the tie-break underneath the matching, not a substitute.
  function pairSlides(secs){
    const n = SLIDES.length, taken = new Array(secs.length).fill(false);
    const pair = new Array(n).fill(-1);
    SLIDES.forEach((sl, i) => {
      const want = norm(sl.paper);
      if(!want) return;
      const k = secs.findIndex((sec, j) => !taken[j] &&
        (norm(headText(sec)) === want || norm(headText(sec)).startsWith(want)));
      if(k >= 0){ pair[i] = k; taken[k] = true; }
    });
    let from = 0;
    for(let i = 0; i < n; i++){
      if(pair[i] >= 0){ from = Math.max(from, pair[i] + 1); continue; }
      let best = -1, bestScore = 0;
      for(let k = from; k < secs.length; k++){
        if(taken[k]) continue;
        const sc = scoreMatch(SLIDES[i].title, headText(secs[k]));
        if(sc > bestScore){ bestScore = sc; best = k; if(sc === 3) break; }
      }
      if(best >= 0){ pair[i] = best; taken[best] = true; from = best + 1; }
    }
    let next = 0, last = -1;
    for(let i = 0; i < n; i++){
      if(pair[i] >= 0){ last = pair[i]; next = Math.max(next, pair[i] + 1); continue; }
      let j = Math.max(next, last + 1);
      while(j < secs.length && taken[j]) j++;
      // Forward first, then wrap to the earliest unclaimed section anywhere. Without the
      // wrap an explicit `:::paper` pin that jumps ahead strands every slide behind it on
      // the pinned section, which is the exact collision this allocator exists to prevent.
      if(j >= secs.length) j = taken.indexOf(false);
      // a paper with fewer sections than the deck has slides: share the last one rather
      // than leave the pane blank. mdview warns about this at build time.
      if(j >= 0 && j < secs.length){ pair[i] = j; taken[j] = true; last = j; next = j + 1; }
      else pair[i] = last;
    }
    return pair;
  }
  // Opening the pane, or moving a slide, does two things: scrolls to that slide's
  // section and dresses it — the tinted card plus the slide-numbered tag — so the
  // paper reads as this slide's evidence rather than as a document you happen to be
  // scrolled into. `o` drops the dressing and leaves a plain document.
  function syncPaper(){
    if(!HAS_PAPER) return;
    const secs = document.querySelectorAll('#doc .pp-sec');
    if(!secs.length) return;
    const k = PAIR[deckState.i];
    secs.forEach(sec => sec.classList.remove('pp-on'));
    const sec = (k >= 0 && k < secs.length) ? secs[k] : null;
    if(sec){
      sec.classList.add('pp-on');
      const tag = sec.querySelector('.pp-tag');
      // "7 of 8", not "7 / 8" — a slash inside an uppercase pill reads as punctuation
      // noise, and the question it has to answer is which slide of how many.
      if(tag) tag.innerHTML = '<b>Slide ' + (deckState.i + 1) + ' of ' + SLIDES.length +
        '</b>' + (SLIDES[deckState.i].title
          ? ' \u00b7 ' + SLIDES[deckState.i].title.replace(/[<&]/g, '') : '');
    }
    if(!deckState.split || !sec) return;
    document.querySelector('main').scrollTo({ top: Math.max(0, sec.offsetTop - 26),
                                             behavior:'smooth' });
  }
  function setFocus(on){
    deckState.focus = !!on;
    document.body.classList.toggle('focus', deckState.focus);
    const b = document.getElementById('pdFocusBtn');
    if(b) b.classList.toggle('on', deckState.focus);
  }

  // ── narration ───────────────────────────────────────────────────────────
  // The player is CUE-driven, not slide-driven. A cue is one clip plus where it
  // belongs: which slide, optionally which block of the paper, and the text it
  // speaks. That one shape carries both narration modes without branching here —
  // `--from deck` emits a cue per slide, `--from paper` a cue per paper block —
  // so the transport, the auto-advance and the captions were written once.
  //
  // Nothing is time-aligned. The clip boundary IS the block boundary, so the
  // highlight, the caption and the slide can never drift out of sync with the
  // audio however the deck is driven.
  const CUES = AUDIO ? AUDIO.cues : [];
  const audioState = { playing:false, auto:true, cue:0, subs:true };
  let CUE_START = [], CUE_TOTAL = 0;
  let SEC2SLIDE = [];
  function pdAudio(){ return document.getElementById('pdAudio'); }
  // A page turn under a read-through. It fires only while the narration is playing —
  // a keyboard-driven pass through the deck should stay silent, because there the
  // slide change was the user's own action and does not need announcing.
  // ponytail: one element, rewound. Overlapping turns would need Web Audio buffers;
  // slides do not change fast enough for that to matter.
  function pageTurn(){
    if(!AUDIO || !AUDIO.turn || !audioState.playing) return;
    const t = document.getElementById('pdTurn');
    if(!t.src) t.src = AUDIO.turn;
    t.volume = AUDIO.turnVolume != null ? AUDIO.turnVolume : 0.32;
    try { t.currentTime = 0; t.play().catch(() => {}); } catch(e){}
  }
  function fmtTime(t){
    if(!isFinite(t) || t < 0) t = 0;
    return Math.floor(t / 60) + ':' + String(Math.floor(t % 60)).padStart(2, '0');
  }
  // Which slide a cue belongs to. Paper cues carry a paper SECTION, and the slide
  // is whichever one the allocator gave that section — the same PAIR, read backwards.
  // Reading the paper therefore drives the deck for free.
  function cueSlide(c){
    if(c.slide != null) return c.slide;
    if(c.sec != null && SEC2SLIDE[c.sec] != null) return SEC2SLIDE[c.sec];
    return null;
  }
  // The block a cue reads. Source line, not index: `tagLines` already stamps every
  // rendered block with its line in paper.md, so the two halves agree without a
  // second parser. A bridge line (a `<!-- say: -->` standing in for a table) has no
  // block of its own, so it lights the nearest one above it — the thing it describes.
  function cueEl(c){
    if(c.line == null) return null;
    const doc = document.getElementById('doc');
    if(!doc) return null;
    const exact = doc.querySelector('[data-mline-start="' + c.line + '"]');
    if(exact) return exact;
    let best = null;
    doc.querySelectorAll('[data-mline-start]').forEach(el => {
      const l = Number(el.dataset.mlineStart);
      if(l <= c.line && (!best || l > Number(best.dataset.mlineStart))) best = el;
    });
    return best;
  }
  function cueAt(n){ return (n >= 0 && n < CUES.length) ? CUES[n] : null; }
  // Jump the read-head to wherever the deck just went, so driving the deck by hand
  // and driving it by listening stay the same cursor.
  function cueForSlide(n){
    const k = CUES.findIndex(c => cueSlide(c) === n);
    return k >= 0 ? k : audioState.cue;
  }
  function clearReading(){
    document.querySelectorAll('.pp-reading').forEach(el => el.classList.remove('pp-reading'));
  }
  function showCue(c){
    clearReading();
    const el = c ? cueEl(c) : null;
    if(el){
      el.classList.add('pp-reading');
      if(deckState.split && !isVisibleIn(el, document.querySelector('main')))
        el.scrollIntoView({ block:'center', behavior:'smooth' });
    }
    const bar = document.getElementById('pdsubs');
    bar.innerHTML = '';
    if(!c || !c.text){ bar.classList.remove('on'); return; }
    // Words are spans HERE, in the caption bar, and never in the paper: the paper is a
    // commentable surface and the comment engine walks its text nodes. ponytail: the
    // ceiling is that the paper highlights per block, not per word. Wrapping words in
    // #doc is the upgrade path, and it needs the selection code audited first.
    c.text.split(/(\s+)/).forEach(tok => {
      if(!tok.trim()){ bar.appendChild(document.createTextNode(tok)); return; }
      const w = document.createElement('span');
      w.className = 'pdw'; w.textContent = tok;
      bar.appendChild(w);
    });
    bar.classList.toggle('on', audioState.subs);
  }
  // ponytail: the word cursor is ESTIMATED — duration spread across the caption by
  // character count. Gemini TTS returns no word timings, and real forced alignment is a
  // whole extra dependency for a moving underline. It drifts a little inside a long
  // paragraph and re-syncs hard at every clip boundary, which is often enough to read as
  // correct. Upgrade path if it ever isn't: word offsets from a timestamping ASR pass.
  function paintWords(frac){
    const ws = document.querySelectorAll('#pdsubs .pdw');
    if(!ws.length) return;
    let total = 0;
    ws.forEach(w => total += w.textContent.length + 1);
    let seen = 0, cut = frac * total;
    ws.forEach(w => {
      const len = w.textContent.length + 1;
      w.classList.toggle('said', seen + len <= cut);
      w.classList.toggle('saying', seen < cut && seen + len > cut);
      seen += len;
    });
  }
  function isVisibleIn(el, pane){
    if(!pane) return true;
    const r = el.getBoundingClientRect(), p = pane.getBoundingClientRect();
    return r.top >= p.top + 8 && r.bottom <= p.bottom - 8;
  }
  function loadCue(n){
    const el = pdAudio(), c = cueAt(n);
    if(!c){ el.pause(); el.removeAttribute('src'); el.dataset.n = ''; return false; }
    if(el.dataset.n !== String(n)){ el.src = c.src; el.dataset.n = String(n); }
    try { el.currentTime = 0; } catch(e){}
    return true;
  }
  function playCue(n){
    if(!AUDIO) return;
    audioState.cue = Math.max(0, Math.min(n, CUES.length - 1));
    const c = cueAt(audioState.cue);
    if(!c){ audioState.playing = false; updateAudioChrome(); return; }
    const want = cueSlide(c);
    // move the deck to the cue, not the cue to the deck — a read-through leads
    if(want != null && want !== deckState.i) goSlide(want, true);
    // a paper cue lights a paragraph, which is nothing to look at behind a closed
    // pane. Reading the paper aloud opens the paper.
    if(c.line != null && !deckState.split) setSplit(true);
    loadCue(audioState.cue);
    showCue(c);
    pdAudio().play().then(() => {
      audioState.playing = true;
      document.getElementById('pdPlayBtn').classList.remove('blocked');
      updateAudioChrome();
    }).catch(() => {
      // Chrome refuses sound until the page has been interacted with. Say so on the
      // button instead of failing silently — the first click or key press retries.
      audioState.playing = false;
      document.getElementById('pdPlayBtn').classList.add('blocked');
      updateAudioChrome();
    });
  }
  function pauseCue(){ pdAudio().pause(); audioState.playing = false; updateAudioChrome(); }
  function toggleAudio(){ if(!AUDIO) return; audioState.playing ? pauseCue() : playCue(audioState.cue); }
  function toggleAuto(){
    audioState.auto = !audioState.auto;
    document.getElementById('pdAutoBtn').classList.toggle('on', audioState.auto);
  }
  function toggleSubs(force){
    audioState.subs = (force === undefined) ? !audioState.subs : force;
    const b = document.getElementById('pdSubsBtn');
    if(b) b.classList.toggle('on', audioState.subs);
    document.getElementById('pdsubs').classList.toggle('on',
      audioState.subs && !!document.querySelector('#pdsubs .pdw'));
  }
  // The deck moved on its own (a key, the sidebar). Follow it with the read-head so the
  // next play starts from what is on screen, but never yank the audio mid-sentence.
  function syncAudio(fromCue){
    if(!AUDIO || fromCue) return;
    const k = cueForSlide(deckState.i);
    if(k === audioState.cue) return;
    audioState.cue = k;
    if(audioState.playing) playCue(k);
    else { loadCue(k); showCue(cueAt(k)); updateAudioChrome(); }
  }
  function updateAudioChrome(){
    if(!AUDIO) return;
    const el = pdAudio(), c = cueAt(audioState.cue);
    const play = document.getElementById('pdPlayBtn');
    play.classList.toggle('playing', audioState.playing);
    play.title = audioState.playing ? 'Pause (a)' : 'Play (a)';
    const dur = c ? (el.duration || c.dur || 0) : 0;
    const at = Math.min(el.currentTime || 0, dur || 0);
    const elapsed = (CUE_START[audioState.cue] || 0) + at;
    document.getElementById('pdTime').textContent =
      CUE_TOTAL ? fmtTime(Math.max(0, CUE_TOTAL - elapsed)) : '—';
    document.getElementById('pdabar').style.width =
      (CUE_TOTAL ? (elapsed / CUE_TOTAL * 100) : 0) + '%';
    if(dur) paintWords(at / dur);
  }
  function initAudio(){
    if(!AUDIO || !CUES.length) return;
    document.body.classList.add('hasaudio');
    // section -> slide, the allocator read backwards. First slide wins a shared section.
    SEC2SLIDE = [];
    PAIR.forEach((sec, slide) => { if(sec >= 0 && SEC2SLIDE[sec] == null) SEC2SLIDE[sec] = slide; });
    CUE_START = []; CUE_TOTAL = 0;
    CUES.forEach(c => { CUE_START.push(CUE_TOTAL); CUE_TOTAL += (c.dur || 0); });
    const el = pdAudio();
    document.getElementById('pdPlayBtn').addEventListener('click', toggleAudio);
    document.getElementById('pdAutoBtn').addEventListener('click', toggleAuto);
    document.getElementById('pdSubsBtn').addEventListener('click', () => toggleSubs());
    document.getElementById('pdAutoBtn').classList.toggle('on', audioState.auto);
    el.addEventListener('timeupdate', updateAudioChrome);
    el.addEventListener('loadedmetadata', updateAudioChrome);
    el.addEventListener('ended', () => {
      if(audioState.auto && audioState.cue < CUES.length - 1){ playCue(audioState.cue + 1); }
      else { audioState.playing = false; paintWords(1); updateAudioChrome(); }
    });
    audioState.cue = cueForSlide(deckState.i);
    loadCue(audioState.cue);
    showCue(cueAt(audioState.cue));
    toggleSubs(AUDIO.subs !== false);
    updateAudioChrome();
    if(AUDIO.autoplay){
      playCue(audioState.cue);
      const retry = () => {
        if(!audioState.playing &&
           document.getElementById('pdPlayBtn').classList.contains('blocked'))
          playCue(audioState.cue);
        removeEventListener('pointerdown', retry); removeEventListener('keydown', retry);
      };
      addEventListener('pointerdown', retry); addEventListener('keydown', retry);
    }
  }
  function slideKey(n){ return 'Slide ' + (n + 1) + (SLIDES[n].title ? ' · ' + SLIDES[n].title : ''); }
  function goSlide(n, fromCue){
    if(n < 0 || n >= SLIDES.length || n === deckState.i) return;
    if(draft && draft.sf === SLIDE_SF) discardDraft();
    const secs = document.querySelectorAll('#stage .slide');
    const dir = n > deckState.i ? 1 : -1;
    const TRAVEL = 34;
    const prev = secs[deckState.i];
    deckState.i = n;
    const next = secs[n];
    if(prev && prev !== next){
      prev.classList.remove('on');
      prev.style.transform = 'translateX(' + (-TRAVEL * dir) + 'px)';
    }
    secs.forEach(el => { if(el !== prev && el !== next) el.classList.remove('on'); });
    // commit the entry offset with transitions off, then let the .on rule animate it home
    next.style.transition = 'none';
    next.style.transform = 'translateX(' + (TRAVEL * dir) + 'px)';
    void next.offsetWidth;
    next.style.transition = '';
    next.classList.add('on');
    next.style.transform = '';
    next.scrollTop = 0;
    // one rail, moved into whichever slide is showing — it scrolls with that slide's text
    try { mountDraws(next); } catch(e){}
    next.appendChild(SLIDE_SF.rail);
    SLIDE_SF.doc = next.querySelector('.pad');
    SLIDE_SF.key = slideKey(n);
    location.hash = 's' + (n + 1);
    if(prev && prev !== next) pageTurn();
    updateDeckChrome();
    renderRail(SLIDE_SF);
    syncPaper();
    syncAudio(fromCue);
  }
  // The split is sticky: it stays open as you move through the deck, and only the
  // grip (or `p`) closes it.
  function setSplit(on){
    deckState.split = on && HAS_PAPER;
    if(!deckState.split) deckState.full = false;
    document.body.classList.toggle('split', deckState.split);
    document.body.classList.toggle('full', deckState.full);
    document.getElementById('pdPaperBtn').classList.toggle('on', deckState.split);
    document.getElementById('pdgripLbl').textContent = deckState.split ? 'Hide paper' : 'Paper';
    setTimeout(() => { try{ layoutRail(); }catch(e){} syncPaper(); }, 220);
  }
  function setFull(on){
    if(!deckState.split && on) return setSplit(true), setFull(true);
    deckState.full = on && deckState.split;
    document.body.classList.toggle('full', deckState.full);
    document.getElementById('pdFullBtn').classList.toggle('on', deckState.full);
    setTimeout(() => { try{ layoutRail(); }catch(e){} }, 220);
  }
  function toggleNav(){
    deckState.navOpen = !deckState.navOpen;
    document.body.classList.toggle('nav', deckState.navOpen);
    document.getElementById('pdNavBtn').classList.toggle('on', deckState.navOpen);
    setTimeout(() => { try{ layoutRail(); }catch(e){} }, 60);
  }
  function toggleNotes(force){
    deckState.notesOpen = (force === undefined) ? !deckState.notesOpen : force;
    document.getElementById('pdnotes').classList.toggle('open', deckState.notesOpen);
    document.getElementById('pdNotesBtn').classList.toggle('on', deckState.notesOpen);
  }
  function updateDeckChrome(){
    const n = deckState.i;
    document.getElementById('pdCount').textContent = (n + 1) + ' / ' + SLIDES.length;
    document.getElementById('pdPrev').disabled = n === 0;
    document.getElementById('pdNext').disabled = n === SLIDES.length - 1;
    document.getElementById('pdbar').style.width = ((n + 1) / SLIDES.length * 100) + '%';
    document.querySelectorAll('#sidebar a').forEach((a, k) => a.classList.toggle('active', k === n));
    const nb = document.getElementById('pdnotesBody');
    nb.innerHTML = SLIDES[n].notes ? marked.parse(SLIDES[n].notes)
                                   : '<p style="color:var(--muted)">No notes for this slide.</p>';
    try { presPaint(); } catch(e){}
  }
  function renderDeckNav(){
    const nav = document.getElementById('sidebar');
    nav.innerHTML = '';
    nav.classList.remove('hidden');
    SLIDES.forEach((sl, i) => {
      const a = document.createElement('a');
      a.href = '#s' + (i + 1);
      const num = document.createElement('span'); num.className = 'sl-n'; num.textContent = i + 1;
      const t = document.createElement('span'); t.textContent = sl.title || ('Slide ' + (i + 1));
      a.appendChild(num); a.appendChild(t);
      a.addEventListener('click', e => { e.preventDefault(); goSlide(i); });
      nav.appendChild(a);
    });
  }
  // A pill is the collapsed state of a surface's rail: it sits in that pane's corner,
  // shows the count, and opening it floats the cards OVER the content instead of
  // reserving margin for them. Drafting a comment opens it for you. Surfaces without a
  // pill (plain browser-preview) keep the always-visible reserved-margin rail.
  function attachPill(sf, pill, host){ sf.pill = pill; sf.host = host; }
  function updateCommentPill(sf, n){
    if(!sf.pill) return;
    sf.pill.querySelector('.n').textContent = n;
    sf.pill.classList.toggle('show', n > 0);
    if(!n) setCx(sf, false);
  }
  function setCx(sf, on){
    if(!sf || !sf.host) return;
    sf.host.classList.toggle('cx', !!on);
    if(on) setTimeout(() => { try{ layoutRail(sf); }catch(e){} }, 0);
  }
  // ── presenter window ────────────────────────────────────────────────────
  // A second window holding what the room must not see: this slide's notes, what is
  // coming next, and how long you have been talking. The deck stays in the shared
  // window, unchanged, so screen-sharing one window is the whole setup.
  //
  // ponytail: opened BLANK and written into, never navigated to a file:// URL. A blank
  // window inherits its opener's origin, so the parent can hold the handle and mutate
  // the child's DOM directly — no postMessage, no BroadcastChannel, no localStorage,
  // all three of which are dead or unreliable on file:// in Chrome.
  let PRES = null, PRES_T0 = 0, PRES_TIMER = null;
  const PRES_CSS = `
    :root{ color-scheme:dark; }
    body{ margin:0; background:#14161c; color:#e6e6ee; font:15px/1.6 -apple-system,
      BlinkMacSystemFont,"Segoe UI",sans-serif; padding:22px 26px 26px; }
    .top{ display:flex; align-items:baseline; gap:14px; border-bottom:1px solid #2a2d38;
      padding-bottom:12px; margin-bottom:18px; }
    .n{ font:700 12px/1 ui-monospace,SFMono-Regular,Menlo,monospace; letter-spacing:.1em;
      text-transform:uppercase; color:#3ab6c0; }
    h1{ font:700 21px/1.25 Charter,"Iowan Old Style",Georgia,serif; margin:0; flex:1; }
    .clock{ font:600 15px/1 ui-monospace,SFMono-Regular,Menlo,monospace; color:#8b8b99; }
    textarea{ display:block; width:100%; box-sizing:border-box; min-height:44vh;
      resize:vertical; background:#181a22; color:#e6e6ee; border:1px solid #2a2d38;
      border-radius:10px; padding:16px 18px; font:17px/1.62 -apple-system,
      BlinkMacSystemFont,"Segoe UI",sans-serif; }
    textarea:focus{ outline:none; border-color:#3ab6c0; background:#1b1e27; }
    textarea::placeholder{ color:#5c5f6b; }
    .hint{ margin-top:8px; font-size:12px; color:#6a6c78; }
    .next{ margin-top:26px; padding-top:14px; border-top:1px solid #2a2d38; color:#8b8b99;
      font-size:13.5px; }
    .next b{ color:#c3c3cd; font-weight:600; }
    .bar{ position:fixed; left:0; right:0; bottom:0; display:flex; gap:8px; padding:12px 26px;
      background:#181a22; border-top:1px solid #2a2d38; }
    button{ font:inherit; font-size:13px; cursor:pointer; background:#22252f; color:#e6e6ee;
      border:1px solid #343846; border-radius:8px; padding:7px 14px; }
    button:hover{ background:#2b2f3b; }
    .sp{ flex:1 }`;
  // file:// is not a secure context, so navigator.clipboard is usually undefined —
  // same fallback the deck uses, run inside the child so the selection is its own.
  function presCopy(w, text){
    const d = w.document;
    const ta = d.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    d.body.appendChild(ta); ta.select();
    try { d.execCommand('copy'); } catch(e){}
    ta.remove();
  }
  function presFmt(ms){
    const t = Math.floor(ms / 1000);
    return Math.floor(t / 60) + ':' + String(t % 60).padStart(2, '0');
  }
  function presPaint(){
    if(!PRES || PRES.closed) return;
    const d = PRES.document, n = deckState.i, sl = SLIDES[n];
    d.getElementById('pn').textContent = 'Slide ' + (n + 1) + ' of ' + SLIDES.length;
    d.getElementById('pt').textContent = sl.title || ('Slide ' + (n + 1));
    // Only ever repainted on a slide change, so it never clobbers what is being typed.
    const body = d.getElementById('pnotes');
    if(body !== d.activeElement) body.value = sl.notes || '';
    const nx = SLIDES[n + 1];
    d.getElementById('pnext').innerHTML = nx
      ? 'Next &nbsp;<b>' + (nx.title || ('Slide ' + (n + 2))).replace(/[<&]/g, '') + '</b>'
      : 'Last slide.';
  }
  function presTick(){
    if(!PRES || PRES.closed) return closePresenter();
    const c = PRES.document.getElementById('pclock');
    if(c) c.textContent = presFmt(Date.now() - PRES_T0);
  }
  function closePresenter(){
    if(PRES_TIMER){ clearInterval(PRES_TIMER); PRES_TIMER = null; }
    if(PRES && !PRES.closed) PRES.close();
    PRES = null;
    document.getElementById('pdPresentBtn').classList.remove('on');
  }
  function openPresenter(){
    if(PRES && !PRES.closed){ closePresenter(); return; }
    const w = window.open('', 'pd-presenter', 'width=820,height=640');
    if(!w){ alert('Allow pop-ups for this page to use the presenter window.'); return; }
    PRES = w; PRES_T0 = Date.now();
    w.document.open();
    w.document.write('<!doctype html><meta charset="utf-8"><title>Presenter \u00b7 ' +
      DECK_TITLE.replace(/[<&]/g, '') + '</title><style>' + PRES_CSS + '</style>' +
      '<div class="top"><span class="n" id="pn"></span><h1 id="pt"></h1>' +
      '<span class="clock" id="pclock">0:00</span></div>' +
      '<textarea id="pnotes" placeholder="Notes for this slide\u2026"></textarea>' +
      '<div class="hint">Edits live in this window only. Copy them out before you close it.</div>' +
      '<div class="next" id="pnext"></div>' +
      '<div class="bar"><button id="pb">\u2190 Prev</button>' +
      '<button id="pf">Next \u2192</button><span class="sp"></span>' +
      '<button id="pc">Copy all notes</button>' +
      '<button id="pr">Reset timer</button></div>');
    w.document.close();
    const d = w.document;
    d.getElementById('pb').onclick = () => goSlide(deckState.i - 1);
    d.getElementById('pf').onclick = () => goSlide(deckState.i + 1);
    d.getElementById('pr').onclick = () => { PRES_T0 = Date.now(); presTick(); };
    // The notes pane is the speaker's scratchpad — the one surface here that is theirs
    // to write on. Edits go straight back into SLIDES, so the `n` drawer in the deck
    // shows them too. ponytail: session-only, like the comment rail; `file://` has no
    // storage to persist to, which is exactly why Copy all notes exists.
    d.getElementById('pnotes').addEventListener('input', e => {
      SLIDES[deckState.i].notes = e.target.value;
      try { updateDeckChrome(); } catch(err){}
    });
    d.getElementById('pc').onclick = () => {
      const out = SLIDES.map((sl, i) => sl.notes && sl.notes.trim()
        ? 'Slide ' + (i + 1) + ' \u00b7 ' + (sl.title || '') + '\n\n:::notes\n' +
          sl.notes.trim() + '\n:::\n'
        : null).filter(Boolean).join('\n');
      presCopy(w, out || 'No notes yet.');
      const b = d.getElementById('pc'), was = b.textContent;
      b.textContent = 'Copied'; setTimeout(() => { b.textContent = was; }, 1200);
    };
    // the presenter window drives the deck too — you should never have to click back
    // into the shared window to advance, that is the click the room sees
    d.addEventListener('keydown', e => {
      if(e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' '){
        e.preventDefault(); goSlide(deckState.i + 1);
      } else if(e.key === 'ArrowLeft' || e.key === 'PageUp'){
        e.preventDefault(); goSlide(deckState.i - 1);
      }
    });
    w.addEventListener('pagehide', () => closePresenter());
    PRES_TIMER = setInterval(presTick, 1000);
    document.getElementById('pdPresentBtn').classList.add('on');
    presPaint(); presTick();
  }
  // an orphaned presenter window outliving its deck is worse than none
  addEventListener('pagehide', () => { if(PRES && !PRES.closed) PRES.close(); });

  // ── plus ────────────────────────────────────────────────────────────────
  // Everything here needs a server behind it, which is the whole reason plus mode
  // exists: file:// has no origin, so it has no storage, no fetch, no cross-frame.
  // On http://localhost the page can persist to disk, frame a live app, and talk to
  // the agent — and localStorage and the clipboard API start working for free.
  // Set only while a slide's markdown is being parsed — the same fence has to render
  // differently in the two panes, and marked gives the renderer no pane context.
  let RENDER_SLIDE = false;
  function slugify(s){
    return (s || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40);
  }
  // A stable name, so edits survive a rebuild AND an edit to the mermaid source. An
  // explicit label wins; otherwise it is the slide plus the diagram's position on it,
  // which only moves when you reorder the deck.
  let NAME_N = 0;
  function nameFor(label, text){
    if(label) return label.replace(/[^\w.-]/g, '');
    NAME_N++;
    const t = (SLIDES[NAME_SLIDE] && SLIDES[NAME_SLIDE].title) || ('slide-' + (NAME_SLIDE + 1));
    return (slugify(t) || 'slide') + '-d' + NAME_N;
  }
  let NAME_SLIDE = 0;
  function drawBox(name, seed){
    const enc = seed ? encodeURIComponent(seed) : '';
    return '<div class="pd-draw" data-scene="' + name + '" data-seed="' + enc + '">' +
      '<div class="pd-draw-head"><span>' + name + '</span>' +
      '<span class="pd-draw-hint">click to edit</span>' +
      '<button class="pd-draw-full" type="button" title="Full screen (or double-click)">\u2922</button>' +
      '<button class="pd-draw-done" type="button">Done</button>' +
      (seed ? '<button class="pd-draw-reseed" type="button" title="Rebuild from the paper\u2019s mermaid, discarding edits">Reseed</button>' : '') +
      '<span class="pd-draw-state">loading\u2026</span></div>' +
      '<div class="pd-draw-host"></div></div>';
  }
  const PLUS_TOKEN = (location.search.match(/[?&]k=([^&]+)/) || [])[1] || '';
  function api(path, opts){
    const j = path.indexOf('?') === -1 ? '?' : '&';
    return fetch(path + j + 'k=' + encodeURIComponent(PLUS_TOKEN), opts);
  }
  // ── editable diagrams ───────────────────────────────────────────────────
  // One Excalidraw per ```draw <name> fence, in either pane. Scenes live on disk as
  // real .excalidraw files, so they open in excalidraw.com and survive a rebuild —
  // the deck is not their storage, it is one editor for them.
  const DRAWN = new Map();
  // Mermaid is the authoring format and Excalidraw is the editor. A scene is SEEDED
  // from the paper's mermaid the first time and saved to disk from then on, so your
  // layout survives both a rebuild and an edit to the source. Reseed throws the scene
  // away and rebuilds from the mermaid — safe, because the mermaid is the source of
  // truth and the canvas was only ever a derived view of it.
  // Excalidraw ships exactly three faces: 1 Virgil (hand-drawn), 2 Helvetica,
  // 3 Cascadia (mono). Which one a converted diagram gets is taste, not correctness,
  // so it is a setting — `diagram_font: hand|normal|code` in style.md. Applied only
  // at conversion, so a font you change by hand afterwards survives.
  const DIAGRAM_FONT = (window.PD_AUDIO && window.PD_AUDIO.diagramFont) || 2;
  // ── icons in diagrams ───────────────────────────────────────────────────
  // A node written `A["@postgres Postgres"]` gets the real Postgres mark pinned to it.
  // The marker is stripped from the label, so the mermaid stays readable and the paper
  // still renders it as an ordinary diagram — the icons are a slide-side enrichment,
  // not a fork of the source.
  const ICON_RE = /@([a-z0-9][\w.-]*)\s*/i;
  const ICON_PX = 26;
  async function iconDataUrl(name){
    const c = getComputedStyle(document.body).getPropertyValue('--ink-2').trim() || '#c9ccd4';
    const r = await fetch('/icon/' + encodeURIComponent(name) + '?c=' + encodeURIComponent(c));
    if(!r.ok) return null;
    const blob = await r.blob();
    return await new Promise(res => {
      const fr = new FileReader(); fr.onload = () => res(fr.result); fr.readAsDataURL(blob);
    });
  }
  // Excalidraw images live in a side table keyed by fileId, not inline on the element,
  // so every icon is registered with addFiles() before its element can render.
  async function applyIcons(els, exapi){
    const want = [];
    els.forEach(el => {
      if(el.type !== 'text' || !el.text) return;
      const m = el.text.match(ICON_RE);
      if(!m) return;
      el.text = el.text.replace(ICON_RE, '').trim();
      if(el.originalText) el.originalText = el.originalText.replace(ICON_RE, '').trim();
      const host = el.containerId ? els.find(e => e.id === el.containerId) : el;
      if(host) want.push({ name: m[1].toLowerCase(), host });
    });
    if(!want.length) return els;
    const files = [], extra = [];
    for(const w of want){
      const url = await iconDataUrl(w.name);
      if(!url) continue;                      // unknown icon: the label just loses its @
      const id = 'ic_' + w.name + '_' + Math.random().toString(36).slice(2, 8);
      files.push({ id, dataURL: url, mimeType: url.slice(5, url.indexOf(';')),
                   created: Date.now() });
      extra.push({ type:'image', fileId:id, id: 'img_' + id,
        x: w.host.x + w.host.width / 2 - ICON_PX / 2, y: w.host.y - ICON_PX - 7,
        width: ICON_PX, height: ICON_PX, angle:0, strokeColor:'transparent',
        backgroundColor:'transparent', fillStyle:'solid', strokeWidth:1,
        strokeStyle:'solid', roughness:0, opacity:100, groupIds:[], frameId:null,
        roundness:null, seed: Math.floor(Math.random() * 1e6), version:1, versionNonce:0,
        isDeleted:false, boundElements:null, updated: Date.now(), link:null, locked:false,
        status:'saved', scale:[1, 1] });
    }
    if(files.length && exapi) exapi.addFiles(files);
    return els.concat(extra);
  }
  async function seedFrom(mermaidSrc){
    if(!window.MermaidToExcalidraw || !mermaidSrc) return null;
    // mermaid line breaks are `<br/>`; the converter passes them through as literal
    // text, so a label reads `#doc<br>right pane` on the canvas. Do it here.
    const src = mermaidSrc.replace(/<br\s*\/?>/gi, '\n');
    const { elements } = await MermaidToExcalidraw.parseMermaidToExcalidraw(
      src, { fontSize: 16 });
    const out = ExcalidrawLib.convertToExcalidrawElements(elements);
    out.forEach(el => { if(el.type === 'text') el.fontFamily = DIAGRAM_FONT; });
    return out;
  }
  async function seedWithIcons(mermaidSrc, exapi){
    const els = await seedFrom(mermaidSrc);
    return els ? await applyIcons(els, exapi) : null;
  }
  function mountDraws(root){
    if(!PLUS || !window.ExcalidrawLib) return;
    root.querySelectorAll('.pd-draw:not([data-on])').forEach(box => {
      box.dataset.on = '1';
      const name = box.dataset.scene;
      const seed = box.dataset.seed ? decodeURIComponent(box.dataset.seed) : '';
      const host = box.querySelector('.pd-draw-host');
      const state = box.querySelector('.pd-draw-state');
      const url = '/scene/' + encodeURIComponent(name) + '?k=' + encodeURIComponent(PLUS_TOKEN);
      let timer = null, exapi = null, view = true;
      const rroot = ReactDOM.createRoot(host);
      const flush = () => {
        if(!exapi) return;
        fetch(url, { method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ type:'excalidraw', version:2, source:'pd-slides-plus',
            elements: exapi.getSceneElements(),
            // without the files table the icons come back as empty frames on reload
            files: exapi.getFiles(),
            appState: { viewBackgroundColor: exapi.getAppState().viewBackgroundColor } }) })
          .then(r => { state.textContent = r.ok ? 'saved' : 'save failed';
                       state.classList.remove('dirty'); })
          .catch(() => { state.textContent = 'save failed'; });
      };
      const fit = els => {
        // twice: once now, once after Excalidraw has measured its own container, or
        // the first node sits half off the top edge
        const go = () => { try{ exapi.scrollToContent(els || exapi.getSceneElements(),
                                                      { fitToContent:true }); }catch(e){} };
        requestAnimationFrame(go); setTimeout(go, 120);
      };
      // A deck holds EVERY slide in the DOM and shows one, so a canvas on any other
      // slide mounts into a host that measures 0x0: scrollToContent has no viewport to
      // fit against and parks the drawing at a corner at a meaningless zoom, which is
      // what "the slide came up blank" actually is. So a fit is OWED until two things
      // are true — the scene has arrived AND the host has a size — and either can land
      // last. Mount order is why: mountDraws runs before the deck reveals the slide it
      // restores to, so even the slide you land on starts at 0x0, and its resize can
      // beat React's excalidrawAPI handoff. A rendezvous covers both orders; a retry
      // on one of them does not.
      // ponytail: it discharges once and disconnects, so nothing accumulates and no
      // later resize is acted on. Deliberately NOT re-fitting on those: every one is
      // either the user (pan, zoom, full screen) or a slide re-shown after they edited
      // it, and re-fitting there would throw away the viewport they chose.
      let sized = false, loaded = false;
      const fitWhenReady = els => {
        if(!sized || !loaded) return;
        ro.disconnect(); fit(els);
      };
      const ro = new ResizeObserver(() => {
        if(!host.offsetWidth || !host.offsetHeight) return;
        sized = true; fitWhenReady();
      });
      ro.observe(host);
      const put = (els, label) => {
        if(!els || !els.length) return;
        exapi.updateScene({ elements: els });
        // fitWhenReady, not fit: fitting into a 0x0 host is the bug, and Reseed still
        // gets its fit here because by then the host is on screen
        loaded = true; fitWhenReady(els); state.textContent = label;
      };
      // ponytail: view mode by default. Most of the time a diagram is read, not
      // edited, and Excalidraw's toolbars sit ON TOP of the drawing — so the UI only
      // appears once you actually click in. Excalidraw hides all of its own chrome in
      // view mode, which is why this is a prop and not a pile of CSS.
      const paint = () => rroot.render(React.createElement(ExcalidrawLib.Excalidraw, {
        excalidrawAPI: a => {
          if(exapi) return;                       // only on the first mount
          exapi = a; DRAWN.set(name, a);
          fetch(url).then(r => r.ok ? r.json() : null).then(saved => {
            if(saved && saved.elements && saved.elements.length){
              if(saved.files) a.addFiles(Object.values(saved.files));
              put(saved.elements, 'on disk'); return;
            }
            if(!seed){ state.textContent = 'empty'; return; }
            state.textContent = 'converting\u2026';
            seedWithIcons(seed, exapi).then(els => { put(els, 'ready'); flush(); })
              .catch(e => { state.textContent = 'mermaid did not convert';
                            console.warn('[pd-slides-plus]', name, e); });
          }).catch(() => { state.textContent = 'offline'; });
        },
        viewModeEnabled: view,
        onChange: () => {
          if(view || state.textContent === 'converting\u2026') return;
          state.textContent = 'editing\u2026'; state.classList.add('dirty');
          clearTimeout(timer); timer = setTimeout(flush, 700);
        },
        UIOptions: { canvasActions: { loadScene:false, saveToActiveFile:false,
                                      export:false, toggleTheme:true } },
        theme: matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light',
      }));
      const setView = v => {
        if(view === v) return;
        view = v; box.classList.toggle('editing', !v); paint();
        if(v){ clearTimeout(timer); flush(); fit(); }
      };
      // A slide is `position:absolute; z-index:2`, which makes a stacking context —
      // so a `position:fixed` child is trapped inside it and the scrim paints OVER the
      // full-screen canvas however high its z-index goes. The fix is not a bigger
      // number, it is leaving the context: park a marker and move the box to <body>.
      let slot = null;
      const setFs = on => {
        if(on && !slot){
          slot = document.createComment('pd-draw');
          box.parentNode.insertBefore(slot, box);
          document.body.appendChild(box);
        } else if(!on && slot){
          slot.parentNode.insertBefore(box, slot);
          slot.remove(); slot = null;
        }
        box.classList.toggle('fs', on);
        document.body.classList.toggle('drawfs', on);
        if(on) setView(false);
        // Excalidraw measures its container on resize; without this the canvas keeps
        // the old box and the drawing sits in a corner of the new one.
        setTimeout(() => { dispatchEvent(new Event('resize')); fit(); }, 60);
      };
      // clicking the scrim leaves full screen, the way any overlay should behave
      document.getElementById('pdscrim').addEventListener('click', () => {
        if(box.classList.contains('fs')) setFs(false);
      });
      paint();
      box.querySelector('.pd-draw-full').addEventListener('click', e => {
        e.stopPropagation(); setFs(!box.classList.contains('fs'));
      });
      host.addEventListener('dblclick', () => setFs(!box.classList.contains('fs')));
      document.addEventListener('keydown', e => {
        if(e.key === 'Escape' && box.classList.contains('fs')){
          e.stopPropagation(); setFs(false);
        }
      }, true);
      host.addEventListener('pointerdown', () => setView(false));
      box.querySelector('.pd-draw-done').addEventListener('click', e => {
        e.stopPropagation(); setView(true);
      });
      // clicking anywhere else puts it back to a picture
      document.addEventListener('pointerdown', e => {
        if(!view && !box.classList.contains('fs') && !box.contains(e.target)) setView(true);
      }, true);
      const re = box.querySelector('.pd-draw-reseed');
      if(re) re.addEventListener('click', () => {
        if(!confirm('Rebuild ' + name + ' from the mermaid in the paper?\n\nYour edits to this canvas are discarded.')) return;
        state.textContent = 'converting\u2026';
        seedWithIcons(seed, exapi).then(els => { exapi.updateScene({ elements: [] });
                                                put(els, 'ready'); flush(); })
          .catch(() => { state.textContent = 'mermaid did not convert'; });
      });
    });
    root.querySelectorAll('.pd-app-reload:not([data-on])').forEach(b => {
      b.dataset.on = '1';
      b.addEventListener('click', () => {
        const f = b.closest('.pd-app').querySelector('iframe');
        f.src = f.src;   // a dev server you just rebuilt should not need a page reload
      });
    });
  }
  // ── the agent pane ──────────────────────────────────────────────────────
  // A file both sides append to, long-polled. Same shape as lavish's poll loop, but
  // ours because the server is ours — the agent replies with `pdplus say`.
  let CHAT_N = 0, CHAT_UNREAD = 0;
  function chatAdd(m){
    const log = document.getElementById('chLog');
    const d = document.createElement('div');
    d.className = 'msg ' + (m.from === 'agent' ? 'agent' : 'me');
    const w = document.createElement('span'); w.className = 'who';
    w.textContent = m.from === 'agent' ? 'Agent' : 'You';
    d.appendChild(w); d.appendChild(document.createTextNode(m.text));
    log.appendChild(d); log.scrollTop = log.scrollHeight;
  }
  function chatBadge(){
    const n = document.querySelector('#pdChatBtn .n');
    if(n) n.textContent = CHAT_UNREAD ? String(CHAT_UNREAD) : '';
  }
  function chatPoll(){
    if(!PLUS) return;
    api('/chat?since=' + CHAT_N).then(r => r.json()).then(d => {
      document.getElementById('chDot').classList.add('live');
      (d.messages || []).forEach(m => {
        chatAdd(m); CHAT_N = m.n;
        if(m.from === 'agent' && !document.body.classList.contains('chat')){
          CHAT_UNREAD++; chatBadge();
        }
      });
      chatPoll();
    }).catch(() => {
      document.getElementById('chDot').classList.remove('live');
      setTimeout(chatPoll, 3000);   // server restarted or went away; keep trying
    });
  }
  function chatSend(text){
    if(!text.trim()) return;
    api('/chat', { method:'POST', headers:{'Content-Type':'application/json'},
                   body: JSON.stringify({ from:'user', text: text,
                                          slide: deckState.i + 1,
                                          title: SLIDES[deckState.i].title || '' }) });
  }
  function toggleChat(force){
    const on = (force === undefined) ? !document.body.classList.contains('chat') : force;
    document.body.classList.toggle('chat', on);
    document.getElementById('pdChatBtn').classList.toggle('on', on);
    if(on){ CHAT_UNREAD = 0; chatBadge(); document.getElementById('chIn').focus(); }
    setTimeout(() => { try{ layoutRail(); }catch(e){} }, 220);
  }
  function initPlus(){
    if(!PLUS) return;
    document.body.classList.add('plus');
    mountDraws(document);
    document.getElementById('pdChatBtn').addEventListener('click', () => toggleChat());
    document.getElementById('chX').addEventListener('click', () => toggleChat(false));
    const inp = document.getElementById('chIn');
    inp.addEventListener('keydown', e => {
      if(e.key === 'Enter' && !e.shiftKey){
        e.preventDefault(); chatSend(inp.value); inp.value = '';
      }
      e.stopPropagation();   // the deck's own keys must not fire while typing
    });
    chatPoll();
    // notes are the speaker's, so plus mode writes them back to deck.md rather than
    // making them a thing to copy out
    addEventListener('pagehide', () => {
      try {
        navigator.sendBeacon('/notes?k=' + encodeURIComponent(PLUS_TOKEN),
          new Blob([JSON.stringify(SLIDES.map(s => s.notes || ''))],
                   { type:'application/json' }));
      } catch(e){}
    });
  }

  let SLIDE_SF = null;
  function initDeck(){
    buildSlides();
    SLIDE_SF = addSurface('slide', document.getElementById('stage'), document.getElementById('srail'));
    renderDeckNav();
    document.getElementById('pdgrip').classList.toggle('empty', !HAS_PAPER);
    document.getElementById('pdPaperBtn').disabled = !HAS_PAPER;
    document.getElementById('pdFullBtn').disabled = !HAS_PAPER;
    document.getElementById('pdPrev').addEventListener('click', () => goSlide(deckState.i - 1));
    document.getElementById('pdNext').addEventListener('click', () => goSlide(deckState.i + 1));
    document.getElementById('pdgrip').addEventListener('click', () => setSplit(!deckState.split));
    document.getElementById('pdPaperBtn').addEventListener('click', () => setSplit(!deckState.split));
    document.getElementById('pdFullBtn').addEventListener('click', () => setFull(!deckState.full));
    document.getElementById('pdNavBtn').addEventListener('click', () => toggleNav());
    document.getElementById('pdNotesBtn').addEventListener('click', () => toggleNotes());
    document.getElementById('pdPresentBtn').addEventListener('click', () => openPresenter());
    document.getElementById('pdsigX').addEventListener('click', () =>
      document.getElementById('pdsig').classList.add('gone'));
    document.getElementById('pdFocusBtn').addEventListener('click', () => setFocus(!deckState.focus));
    document.getElementById('pdFocusBtn').disabled = !HAS_PAPER;
    PAIR = pairSlides(sectionizePaper());
    setFocus(HAS_PAPER);
    initAudio();
    initPlus();
    attachPill(SLIDE_SF, document.getElementById('pdcbtn'), document.getElementById('stage'));
    const paperSf = SURFACES.find(s => s.rail.id === 'rail');
    if(paperSf) attachPill(paperSf, document.getElementById('pdcbtn2'), document.querySelector('main'));
    [[SLIDE_SF, 'pdcbtn'], [paperSf, 'pdcbtn2']].forEach(([sf, id]) => {
      if(!sf) return;
      document.getElementById(id).addEventListener('click', () =>
        setCx(sf, !sf.host.classList.contains('cx')));
    });
    renderRail();
    const start = parseInt((location.hash.match(/^#s(\d+)$/) || [])[1] || '1', 10) - 1;
    deckState.i = -1;
    goSlide(Number.isFinite(start) && start >= 0 && start < SLIDES.length ? start : 0);
  }
  function selectDoc(path){
    state.current = path;
    // toggle active class only — rebuilding the tree would collapse whatever the user opened
    document.querySelectorAll('#sidebar a').forEach(a => a.classList.toggle('active', a.dataset.path === path));
    renderCurrentDoc();
  }

  function escapeHtml(s){ return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

  // ponytail: highlight the WHOLE file once (so multi-line strings/comments tokenize
  // correctly) then split the highlighted HTML on '\n' for per-line rows — hljs only adds
  // span markup around the original text, it never eats or inserts newlines, so the line
  // count always matches the raw source. A span can end up unclosed at a line boundary
  // (multi-line comment/string); the browser auto-closes it. Cosmetic ceiling, not a bug —
  // line numbers and comment anchors stay exact either way.
  function renderCodeBlock(d, el){
    el.innerHTML = '';
    const pre = document.createElement('pre'); pre.className = 'code-view';
    const wrap = document.createElement('div'); wrap.className = 'code-lines';
    pre.appendChild(wrap); el.appendChild(pre);
    let highlighted;
    try {
      highlighted = (d.lang && hljs.getLanguage(d.lang))
        ? hljs.highlight(d.content, { language: d.lang }).value
        : hljs.highlightAuto(d.content).value;
    } catch(e) { highlighted = escapeHtml(d.content); }
    highlighted.split('\n').forEach((lineHtml, i) => {
      const row = document.createElement('div');
      row.className = 'mline code-line';
      row.dataset.mlineStart = i + 1; row.dataset.mlineEnd = i + 1;
      const num = document.createElement('span'); num.className = 'ln'; num.textContent = i + 1;
      const code = document.createElement('span'); code.className = 'lc'; code.innerHTML = lineHtml || ' ';
      row.appendChild(num); row.appendChild(code);
      wrap.appendChild(row);
    });
  }
  function renderImage(d, el){
    el.innerHTML = '';
    const img = document.createElement('img');
    img.src = d.content; img.alt = d.path;
    img.style.maxWidth = '100%'; img.style.display = 'block'; img.style.borderRadius = '8px';
    el.appendChild(img);
  }

  async function renderCurrentDoc(){
    const d = DOCS.find(x => x.path === state.current);
    const el = document.getElementById('doc');
    if(d.kind === 'markdown'){
      el.innerHTML = marked.parse(d.content);
      el.querySelectorAll('pre code').forEach(b => { try{ hljs.highlightElement(b); }catch(e){} });
      try { await mermaid.run({ nodes: el.querySelectorAll('.mermaid') }); } catch(e){}
      try { setupZoom(el); } catch(e){}
      try { tagLines(el, d.content); } catch(e){}
    } else if(d.kind === 'code'){
      renderCodeBlock(d, el);
    } else if(d.kind === 'image'){
      renderImage(d, el);
      try { setupZoom(el); } catch(e){}
    }
    draft = null;
    document.getElementById('rail').dataset.kind = d.kind;
    if(!sfOfKey(d.path)){
      const paperSf = SURFACES[0];
      if(paperSf) paperSf.key = d.path; else addSurface(d.path, el, document.getElementById('rail'));
    }
    renderRail(sfOfKey(d.path));
    document.querySelector('.title').textContent = d.title;
    document.title = DECK ? DECK_TITLE : d.title;
    if(DECK) document.querySelector('.title').textContent = DECK_TITLE;
  }

  // Trigger is any non-collapsed selection release inside the doc — a drag-select across
  // one or more lines, or the word-selection a native double-click already produces — so
  // both gestures land on whole source line(s), never a mid-word char offset.
  document.addEventListener('mouseup', e => {
    if(e.button !== 0) return;
    const sel = window.getSelection();
    if(!sel || sel.isCollapsed || !sel.rangeCount) return;
    const range = sel.getRangeAt(0);
    const sf = sfOfNode(range.commonAncestorContainer);
    if(!sf) return;
    const rects = range.getClientRects();
    if(!rects.length) return;
    const startEl = range.startContainer.nodeType === 3 ? range.startContainer.parentElement : range.startContainer;
    const endEl = range.endContainer.nodeType === 3 ? range.endContainer.parentElement : range.endContainer;
    const startBlock = startEl && startEl.closest('.mline');
    const endBlock = endEl && endEl.closest('.mline');
    if(!startBlock || !endBlock) return;
    const first = rects[0], last = rects[rects.length - 1];
    let line = lineAtY(startBlock, first.top + first.height / 2);
    let lineEnd = lineAtY(endBlock, last.top + last.height / 2);
    if(lineEnd < line){ const tmp = line; line = lineEnd; lineEnd = tmp; }
    const quote = clipQuote(sel.toString(), 400);
    const spans = rangeSpans(range, sf);
    const existing = findThreadAtSpans(sf.key, spans);
    sel.removeAllRanges();
    if(existing){
      focusThread(existing.id, sf);
      const ta = document.querySelector('.rail-card.active textarea');
      if(ta) ta.focus();
      return;
    }
    openDraft(sf.key, line, lineEnd, quote, spans);
  });
  // Serialize the notes for `files`. Each thread carries the quoted text it was left on, so
  // the note is readable without the doc open — a line number alone doesn't say what it's
  // about, and quotes drift less than line numbers when the file is edited underneath.
  // `label` prefixes each file header when more than one file is in scope. Returns {text, count}.
  function serializeNotes(files, label){
    const out = [];
    let count = 0;
    files.forEach(f => {
      if(label) out.push(f + ':');
      (state.annots[f] || []).slice().sort((a, b) => a.line - b.line || a.lineEnd - b.lineEnd).forEach(t => {
        const pad = label ? '  ' : '';
        if(t.quote) out.push(`${pad}${lineLabel(t)} "${clipQuote(t.quote, 160)}"`);
        t.comments.forEach((c, i) => {
          const prefix = t.quote ? '  > ' : (i === 0 ? `${lineLabel(t)} - ` : '  > ');
          out.push(`${pad}${prefix}${c.text}`);
          count++;
        });
      });
    });
    return { text: out.join('\n'), count };
  }
  function currentDoc(){ return DOCS.find(d => d.path === state.current) || DOCS[0]; }

  document.getElementById('copyNotesBtn').addEventListener('click', () => {
    const files = Object.keys(state.annots).filter(f => (state.annots[f] || []).some(t => t.comments.length)).sort();
    if(!files.length){ showToast('No notes yet — select some text to comment'); return; }
    const { text, count } = serializeNotes(files, DOCS.length > 1);
    copyText(text);
    showToast(`Copied ${count} note${count===1?'':'s'}`);
  });
  document.getElementById('copyMdBtn').addEventListener('click', () => {
    copyText(currentDoc().content);
    showToast('Copied source');
  });
  document.getElementById('copyMdNotesBtn').addEventListener('click', () => {
    const doc = currentDoc();
    const { text, count } = serializeNotes([doc.path], false);
    const body = count ? `${doc.content}\n\n---\n\n## Notes\n\n${text}\n` : doc.content;
    copyText(body);
    showToast(count ? `Copied source + ${count} note${count===1?'':'s'}` : 'Copied source (no notes on this doc)');
  });

  // c = copy notes, m = copy md, b = copy md + notes ("both"). Ignore when typing into a
  // comment bubble (textarea) or when a modifier is held (leave browser combos alone).
  document.addEventListener('keydown', (e) => {
    if(e.metaKey || e.ctrlKey || e.altKey) return;
    const t = e.target;
    if(t && (t.tagName === 'TEXTAREA' || t.tagName === 'INPUT' || t.isContentEditable)) return;
    if(DECK){
      if(e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' '){ e.preventDefault(); goSlide(deckState.i + 1); return; }
      if(e.key === 'ArrowLeft'  || e.key === 'PageUp'){ e.preventDefault(); goSlide(deckState.i - 1); return; }
      if(e.key === 'ArrowDown' || e.key === 'ArrowUp'){
        const step = (e.key === 'ArrowDown' ? 1 : -1) * 110;
        const pane = deckState.split ? document.querySelector('main')
                                     : document.querySelector('#stage .slide.on');
        if(pane){ e.preventDefault(); pane.scrollTop += step; }
        return;
      }
      if(e.key === 'Home'){ e.preventDefault(); goSlide(0); return; }
      if(e.key === 'End'){ e.preventDefault(); goSlide(SLIDES.length - 1); return; }
      if(e.key === 'Escape'){
        if(draft) return;   // the engine's own handler discards it; don't also collapse panes
        if(deckState.notesOpen){ toggleNotes(false); return; }
        if(deckState.full){ setFull(false); return; }
        if(deckState.split){ setSplit(false); return; }
      }
      const k = e.key.toLowerCase();
      if(k === 'p'){ e.preventDefault(); setSplit(!deckState.split); return; }
      if(k === 'f'){ e.preventDefault(); setFull(!deckState.full); return; }
      if(k === 'n'){ e.preventDefault(); toggleNotes(); return; }
      if(k === 's'){ e.preventDefault(); toggleNav(); return; }
      if(k === 'o'){ e.preventDefault(); setFocus(!deckState.focus); return; }
      if(k === 'a'){ e.preventDefault(); e.shiftKey ? toggleAuto() : toggleAudio(); return; }
      if(k === 't'){ e.preventDefault(); toggleSubs(); return; }
      if(k === 'v'){ e.preventDefault(); openPresenter(); return; }
      if(k === 'g'){ e.preventDefault(); toggleChat(); return; }
    }
    const map = { c: 'copyNotesBtn', m: 'copyMdBtn', b: 'copyMdNotesBtn' };
    const id = map[e.key.toLowerCase()];
    if(id){ e.preventDefault(); document.getElementById(id).click(); }
  });

  if(DECK) renderCurrentDoc().then(initDeck); else { renderSidebar(); renderCurrentDoc(); }
</script>
</body></html>"""

GH_SVG = ('<svg viewBox="0 0 16 16" fill="currentColor"><path d="M1.75 2A1.75 1.75 0 000 3.75v8.5C0 13.216.784 14 '
          '1.75 14h12.5A1.75 1.75 0 0016 12.25v-7.5A1.75 1.75 0 0014.25 3H7.5L6.44 1.94A1.75 1.75 0 005.19 '
          '1.5h-3.44z"/></svg>')
BRANCH_SVG = ('<svg viewBox="0 0 16 16" fill="currentColor"><path d="M11.75 2.5a.75.75 0 100 1.5.75.75 0 000-1.5zm-2.25.75a2.25 '
              '2.25 0 113 2.122V6A2.5 2.5 0 0110 8.5H6a1 1 0 00-1 1v1.128a2.251 2.251 0 11-1.5 0V5.372a2.25 2.25 0 111.5 0v1.836A2.49 '
              '2.49 0 016 7h4a1 1 0 001-1v-.628A2.25 2.25 0 019.5 3.25zM4.25 12a.75.75 0 100 1.5.75.75 0 000-1.5zM3.5 3.25a.75.75 0 '
              '111.5 0 .75.75 0 01-1.5 0z"/></svg>')

def main():
    args = [a for a in sys.argv[1:]]
    if not args or args[0] in ("-h","--help"):
        print(__doc__); return 0
    no_open = "--no-open" in args; args = [a for a in args if a != "--no-open"]
    deck = "--deck" in args; args = [a for a in args if a != "--deck"]
    # pd-slides-plus: served over http rather than opened from file://, which is what
    # makes editable diagrams, live app frames and an agent pane possible at all.
    plus = "--plus" in args; args = [a for a in args if a != "--plus"]
    if plus: deck = True
    paper = None
    if "--paper" in args:
        i = args.index("--paper"); paper = args[i+1]; del args[i:i+2]; deck = True
    out = None
    if "-o" in args:
        i = args.index("-o"); out = args[i+1]; del args[i:i+2]
    src_path = args[0]
    if not os.path.exists(src_path):
        print(f"not found: {src_path}", file=sys.stderr); return 1

    is_dir = os.path.isdir(src_path)
    if is_dir:
        files = collect_files(src_path)
        root_for_paths = os.path.abspath(src_path)
    else:
        files = [src_path]
        root_for_paths = os.path.dirname(os.path.abspath(src_path))

    slides = []
    if deck:
        if is_dir or classify(src_path)[0] != "markdown":
            print("--deck takes a single markdown file", file=sys.stderr); return 1
        with open(src_path, encoding="utf-8") as f:
            raw = f.read()
        deck_title, body = strip_frontmatter(raw, os.path.basename(src_path), emit_table=False)
        slides = [{"title": sl["title"], "content": sl["face"], "notes": sl["notes"],
                   "say": sl["say"], "paper": sl["paper"]}
                  for sl in split_slides(body)]
        # The paper is an ordinary single-doc browser-preview page — it IS #doc, which is
        # why the comment engine needed no changes to make the split pane commentable.
        if paper:
            if not os.path.exists(paper):
                print(f"paper not found: {paper}", file=sys.stderr); return 1
            with open(paper, encoding="utf-8") as f:
                praw = f.read()
            ptitle, pbody = strip_frontmatter(praw, os.path.basename(paper))
            # Every slide is meant to own a distinct section of the paper. The pairing
            # itself happens in the page (it needs the rendered headings), but a paper
            # with fewer sections than the deck has slides CANNOT be one-to-one however
            # good the matcher is, so say it here where the author can still fix it.
            nsec = len(re.findall(r"(?m)^#{1,3} +\S", pbody))
            if nsec < len(slides):
                print(f"note: paper has {nsec} section(s) for {len(slides)} slide(s) — "
                      f"{len(slides) - nsec} slide(s) will share. Add a heading per slide.",
                      file=sys.stderr)
        else:
            ptitle, pbody = deck_title, ""
        docs = [{"path": os.path.basename(paper) if paper else "paper",
                 "title": ptitle, "kind": "markdown", "lang": None, "content": pbody}]
        page_title = deck_title
        skipped = 0
    else:
      docs = []
      skipped = 0
      for fp in files:
          kind, meta = classify(fp)
          if kind is None:
              if is_dir:
                  skipped += 1; continue  # unrecognized/binary type — not worth a preview
              kind, meta = "code", None    # explicit single-file arg: best effort, hljs auto-detects
          if is_dir and os.path.getsize(fp) > MAX_BYTES:
              skipped += 1; continue
          relpath = os.path.relpath(os.path.abspath(fp), root_for_paths) if is_dir else os.path.basename(fp)
          name = os.path.basename(fp)
          if kind == "image":
              with open(fp, "rb") as f:
                  b64 = base64.b64encode(f.read()).decode()
              docs.append({"path": relpath, "title": name, "kind": "image", "lang": None,
                           "content": f"data:{meta};base64,{b64}"})
              continue
          try:
              with open(fp, encoding="utf-8") as f:
                  raw = f.read()
          except UnicodeDecodeError:
              skipped += 1; continue  # binary file without a recognized extension
          if kind == "markdown":
              title, body = strip_frontmatter(raw, name)
              docs.append({"path": relpath, "title": title, "kind": "markdown", "lang": None, "content": body})
          else:
              docs.append({"path": relpath, "title": name, "kind": "code", "lang": meta, "content": raw})

    if not docs:
        print(f"nothing previewable under: {src_path}", file=sys.stderr); return 1
    if skipped:
        print(f"skipped {skipped} file(s) — unrecognized type, binary, or over {MAX_BYTES // 1000}KB", file=sys.stderr)

    if not deck:
        page_title = docs[0]["title"] if len(docs) == 1 else (os.path.basename(os.path.abspath(src_path).rstrip("/")) or "docs")
    repo, branch = git_info(src_path)
    claude = b64_asset("panel-icon.png")
    claude_img = (f'<img class="claude" src="data:image/png;base64,{claude}" alt="Claude Code">'
                  if claude else '<div class="claude" style="background:var(--brand);border-radius:7px"></div>')
    brand = b64_asset("brand-logo.png")
    brand_img = (f'<img class="brand-mark" src="data:image/png;base64,{brand}" alt="brand" title="brand">'
                 if brand else '<b style="color:var(--brand)">brand</b>')
    sig = b64_asset("badge-icon.png")
    sig_badge = (
        f'<a class="sig-badge" href="{SKILL_URL}" target="_blank" rel="noopener noreferrer">'
        f'<img src="data:image/png;base64,{sig}" alt="">'
        '<span>Made with the browser preview skill</span>'
        '<span class="arrow">&#8599;</span></a>'
    ) if sig else ""
    pd_badge = (
        f'<a class="sig-badge pd" href="{DECK_SKILL_URL}" target="_blank" rel="noopener noreferrer">'
        f'<img src="data:image/png;base64,{sig}" alt="">'
        # plus is a different skill, not a mode of pd-slides - the badge has to say
        # which one actually built the page, or the deck credits the wrong record.
        f'<span>Made with the pd-slides{"-plus" if plus else ""} skill</span>'
        '<span class="arrow">&#8599;</span></a>'
    ) if (sig and deck) else ""
    repo_badge = f'<span class="badge">{GH_SVG}{html.escape(repo)}</span>' if repo else ""
    branch_badge = f'<span class="badge branch">{BRANCH_SVG}{html.escape(branch)}</span>' if branch else ""
    docs_json = json.dumps(docs).replace("</script>", "<\\/script>")
    slides_json = json.dumps(slides).replace("</script>", "<\\/script>")
    doc = (TEMPLATE
           .replace("__TITLE__", html.escape(page_title))
           .replace("__CLAUDE_IMG__", claude_img)
           .replace("__BRAND_IMG__", brand_img)
           .replace("__REPO_BADGE__", repo_badge)
           .replace("__BRANCH_BADGE__", branch_badge)
           .replace("__SIG_BADGE__", sig_badge)
           .replace("__PD_BADGE__", pd_badge)
           .replace("__DECK__", "true" if deck else "false")
           .replace("__PLUS__", "true" if plus else "false")
           .replace("__PLUS_HEAD__", PLUS_HEAD if plus else "")
           .replace("__DECK_TITLE__", json.dumps(page_title))
           .replace("__HAS_PAPER__", "true" if (deck and docs[0]["content"].strip()) else "false")
           .replace("__SLIDES_JSON__", slides_json)
           .replace("__DOCS_JSON__", docs_json))
    if out is None:
        out = os.path.abspath(src_path).rstrip("/") + ".preview.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(doc)
    print(out)
    if not no_open:
        webbrowser.open("file://" + out)
    return 0

if __name__ == "__main__":
    sys.exit(main())
