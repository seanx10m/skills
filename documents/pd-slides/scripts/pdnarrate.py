#!/usr/bin/env python3
"""Render a pd-slides deck WITH a narration track.

Two modes, one output shape. Both emit a list of *cues* — one clip plus where it
belongs — so the player in mdview.py was written once and neither mode branches it.

  --from paper  (default when a paper is given)
      One clip per BLOCK of paper.md, read word for word. The paper is the script;
      nothing is authored twice. The clip boundary IS the block boundary, so the
      caption, the highlight and the slide can never drift out of sync with the
      audio — no timestamps, no forced alignment, no SRT.
      A block that cannot be spoken (table, code, diagram, image) is skipped unless
      an HTML comment stands in for it:  <!-- say: the table breaks that down ... -->

  --from deck
      One clip per slide, scripted from each slide's :::say (or its :::notes).
      A presenter talking over the deck rather than the document read aloud.

Render and embed are one atomic step on purpose: the player lives in the generated
HTML, not in the markdown, so a later plain `pdslides.sh` run silently wipes the
track. Same trap rich-artifact exists to close, deck-shaped.

  pdnarrate.py deck.md paper.md                  # read the paper, deck follows
  pdnarrate.py deck.md paper.md --autoplay
  pdnarrate.py deck.md --from deck -v Sulafat
"""
import argparse, base64, hashlib, json, os, pathlib, re, shutil, subprocess, sys, tempfile

HOME = pathlib.Path.home()
SKILL = HOME / ".claude/skills/pd-slides"
MDVIEW = HOME / ".claude/skills/browser-preview/scripts/mdview.py"
TTS = HOME / ".claude/skills/gemini-tts/scripts/tts.py"
CACHE = SKILL / "scratch/audio"
STYLE = SKILL / "style.md"
TURN = SKILL / "assets/pageturn.mp3"
SLOT = "/*PD_AUDIO_SLOT*/"
# ponytail: 32k mono AAC, matching rich-artifact. Speech at 24kHz, ~3x smaller with no
# audible loss, and it matters because every byte gets base64'd into the page (+33%).
BITRATE, CHANNELS, RATE = "32k", "1", "24000"

sys.path.insert(0, str(MDVIEW.parent))
from mdview import split_slides, strip_frontmatter  # noqa: E402

SAY_RE = re.compile(r"<!--\s*say:\s*(.*?)-->", re.S)
FENCE_RE = re.compile(r"^\s*(```|~~~)")
HEAD_RE = re.compile(r"^(#{1,6})\s+\S")
TABLE_RULE = re.compile(r"^\s*\|?[\s:|-]*-{2,}[\s:|-]*$")
ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\S")


def load_style(near):
    """Narration defaults from style.md — the skill's, or a `pd-style.md` beside the
    deck. Nearest wins field by field; a CLI flag still beats both.

    ponytail: a six-line frontmatter reader, not a YAML dependency. The file's body is
    prose for whoever authors the deck; only these keys are machine-read."""
    out = {}
    for path in (STYLE, pathlib.Path(near) / "pd-style.md"):
        if not path.exists():
            continue
        txt = path.read_text(encoding="utf-8")
        if not txt.startswith("---"):
            continue
        fm = txt.split("---", 2)[1]
        for line in fm.splitlines():
            if line.strip().startswith("#") or ":" not in line:
                continue
            k, v = line.split(":", 1)
            v = v.strip()
            if v in ("true", "false"):
                v = v == "true"
            elif v.isdigit():
                v = int(v)
            out[k.strip()] = v
    return out


def run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], check=True, text=True, capture_output=True, **kw)


def note(m):
    print(m, file=sys.stderr)


def plain(md):
    """Inline markdown -> the words a person actually hears and reads in the caption.

    One string does three jobs (spoken, captioned, cache key), which is the only
    reason the caption can be trusted to match the audio."""
    t = md
    # `:::cards` and friends are SLIDE components; in a paper they render as literal
    # text, and reading the fence aloud is the tell that one wandered in.
    t = re.sub(r"(?m)^\s*:{3,}[ \t]*\w*[ \t]*$", "", t)
    t = re.sub(r"^\s{0,3}#{1,6}\s+", "", t)
    t = re.sub(r"^\s*>\s?", "", t, flags=re.M)
    t = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", t)
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"(\*\*|__|\*|_|~~)", "", t)
    return re.sub(r"\s+", " ", t).strip()


def paper_blocks(md):
    """paper.md -> [{line, kind, text}] in document order, mirroring how the page
    renders it.

    Line numbers, not indexes, are the join to the DOM: `tagLines` in mdview already
    stamps every rendered block with its line in this file, so both halves agree
    without a second markdown parser and they degrade independently — a block the
    two disagree about is skipped, not mismatched.
    """
    lines = md.split("\n")
    blocks, buf, start, fence = [], [], 0, None

    def flush():
        nonlocal buf, start
        if not buf:
            return
        raw = "\n".join(buf).strip("\n")
        if raw.strip():
            blocks.append({"line": start + 1, "raw": raw})
        buf = []

    for i, ln in enumerate(lines):
        m = FENCE_RE.match(ln)
        if fence:
            buf.append(ln)
            if m and ln.strip().startswith(fence):
                fence = None
                flush()
            continue
        if m:
            flush(); fence = ln.strip()[:3]; start = i; buf = [ln]; continue
        if not ln.strip():
            flush(); continue
        # a heading or a list item starts its own block — that is exactly what the
        # renderer tags, so the line numbers land on real elements
        if (HEAD_RE.match(ln) or ITEM_RE.match(ln)) and buf:
            flush()
        if not buf:
            start = i
        buf.append(ln)
    flush()

    out = []
    for b in blocks:
        raw, line = b["raw"], b["line"]
        rows = raw.split("\n")
        first = rows[0].lstrip()
        says = SAY_RE.findall(raw)
        body = SAY_RE.sub("", raw).strip()
        hm = HEAD_RE.match(first)
        depth = len(hm.group(1)) if hm else 0
        if FENCE_RE.match(first):
            kind = "code"
        elif len(rows) > 1 and "|" in first and TABLE_RULE.match(rows[1]):
            kind = "table"
        elif re.match(r"^!\[", first):
            kind = "image"
        elif first.startswith("<"):
            kind = "html"
        elif hm:
            kind = "heading"
        else:
            kind = "text"
        # a block whose content is a table, a diagram, code or an image has no words to
        # read. It is skipped, and a `<!-- say: -->` beside it is how you give it some.
        speakable = kind not in ("code", "table", "image", "html")
        if body:
            out.append({"line": line, "kind": kind, "depth": depth,
                        "text": plain(body) if speakable else ""})
        # A bridge line rides at the position it was written, and lights the block above
        # it — the table or diagram it is standing in for.
        for sy in says:
            out.append({"line": line, "kind": "say", "depth": 0, "text": plain(sy)})
    return out


def clip_for(text, voice, style, seed, tmp):
    """One cached clip per (text, voice, style, seed). Editing one paragraph re-speaks
    that paragraph and nothing else — the whole reason clips are per-block on disk."""
    key = hashlib.sha256("\x00".join([text, voice, style, str(seed)]).encode()).hexdigest()[:16]
    dest = CACHE / f"{key}.m4a"
    if dest.exists() and dest.stat().st_size > 0:
        return dest, True
    CACHE.mkdir(parents=True, exist_ok=True)
    raw = tmp / f"{key}-raw.m4a"
    cmd = [sys.executable, TTS, "-o", raw, "-v", voice, "--seed", str(seed)]
    if style:
        cmd += ["-s", style]
    # captured, not streamed: stdout is the output path contract for `$(pdnarrate.py …)`
    r = subprocess.run([str(c) for c in cmd], input=text, text=True, capture_output=True)
    if r.returncode:
        sys.exit((r.stderr or r.stdout).strip() or "tts failed")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw,
         "-c:a", "aac", "-b:a", BITRATE, "-ac", CHANNELS, "-ar", RATE, dest])
    return dest, False


def duration(path):
    try:
        return round(float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "default=nw=1:nk=1", path]).stdout.strip()), 2)
    except Exception:
        return 0.0


def render(deck, paper, out, plus=False):
    cmd = [sys.executable, MDVIEW, deck, "--deck", "--no-open", "-o", out]
    if plus:
        cmd.append("--plus")
    if paper:
        cmd += ["--paper", paper]
    r = subprocess.run([str(c) for c in cmd], text=True, capture_output=True)
    if r.returncode:
        sys.exit(r.stderr.strip() or "mdview failed")
    if r.stderr.strip():
        note(r.stderr.strip())
    return out


def inject(page, blob):
    """Idempotent: the slot is a fixed one-liner mdview always emits, so a re-run
    replaces the track rather than stacking a second one."""
    s = page.read_text(encoding="utf-8")
    if SLOT not in s:
        sys.exit(f"error: no {SLOT} in {page} — mdview.py is out of date for this skill")
    line = re.compile(r"<script>window\.PD_AUDIO=.*?" + re.escape(SLOT) + r"</script>", re.S)
    page.write_text(line.sub("<script>window.PD_AUDIO=" + blob + SLOT + "</script>", s, count=1),
                    encoding="utf-8")


def out_path(deck):
    r = subprocess.run(["git", "-C", str(deck.parent), "rev-parse", "--show-toplevel"],
                       text=True, capture_output=True)
    root = pathlib.Path(r.stdout.strip()) if r.returncode == 0 else deck.parent
    try:
        flat = str(deck.relative_to(root).with_suffix("")).replace("/", "__")
    except ValueError:
        flat = deck.stem
    d = root / "scratch/.previews"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{flat}.deck.html"


def paper_cues(paper):
    """[{line, sec, text}] — every speakable block of the paper, in reading order."""
    _, body = strip_frontmatter(paper.read_text(encoding="utf-8"), paper.name)
    cues, sec, started = [], -1, False
    for b in paper_blocks(body):
        # mirrors sectionizePaper(): a .pp-sec opens at every H1/H2/H3, and at the very
        # first block whatever it is. Deeper headings sit inside their section.
        if not started or (b["kind"] == "heading" and b["depth"] <= 3):
            sec += 1
        started = True
        if b["text"]:
            cues.append({"line": b["line"], "sec": sec, "text": b["text"]})
    return cues


def deck_cues(deck_body):
    cues = []
    for i, sl in enumerate(split_slides(deck_body)):
        text = plain((sl.get("say") or "").strip())
        if text:
            cues.append({"slide": i, "text": text, "title": sl["title"]})
    return cues


def main():
    a = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("deck")
    a.add_argument("paper", nargs="?")
    a.add_argument("--from", dest="src", choices=("paper", "deck"), default=None,
                   help="narrate the paper word for word (default when a paper is given), "
                        "or the deck's own :::say / :::notes scripts")
    a.add_argument("-o", "--out")
    a.add_argument("-v", "--voice", default=None)
    a.add_argument("-s", "--style", default=None)
    a.add_argument("--seed", type=int, default=None)
    a.add_argument("--autoplay", action="store_true", default=None,
                   help="start on load (browsers block sound until the first click)")
    a.add_argument("--no-subs", action="store_true", help="captions off by default")
    a.add_argument("--plus", action="store_true",
                   help="pd-slides-plus build (served, editable diagrams, agent pane)")
    a.add_argument("--no-open", action="store_true")
    args = a.parse_args()

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            sys.exit(f"error: {tool} not on PATH")
    deck = pathlib.Path(args.deck).resolve()
    if not deck.exists():
        sys.exit(f"not found: {deck}")
    st = load_style(deck.parent)
    voice = args.voice or st.get("voice", "Charon")
    style = args.style if args.style is not None else \
        st.get("style", "an unhurried, confident reading voice")
    seed = args.seed if args.seed is not None else int(st.get("seed", 42))
    autoplay = args.autoplay if args.autoplay is not None else bool(st.get("autoplay", False))
    subs = False if args.no_subs else bool(st.get("subs", True))
    paper = pathlib.Path(args.paper).resolve() if args.paper else None
    if paper and not paper.exists():
        sys.exit(f"paper not found: {paper}")

    mode = args.src or st.get("from") or ("paper" if paper else "deck")
    if mode == "paper" and not paper:
        # style.md defaulting to `paper` must not hard-fail a paperless deck — only an
        # explicit --from paper is a request the caller got wrong.
        if args.src == "paper":
            sys.exit("--from paper needs a paper.md")
        mode = "deck"

    if mode == "paper":
        cues = paper_cues(paper)
        if not cues:
            sys.exit("nothing speakable in the paper")
    else:
        _, body = strip_frontmatter(deck.read_text(encoding="utf-8"), deck.name, emit_table=False)
        cues = deck_cues(body)
        if not cues:
            sys.exit("no narration: give a slide a :::say block, or speaker notes in :::notes")

    fresh = cached = 0
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        for i, c in enumerate(cues):
            path, hit = clip_for(c["text"], voice, style, seed, tmp)
            cached += hit
            fresh += not hit
            c["dur"] = duration(path)
            c["src"] = "data:audio/mp4;base64," + base64.b64encode(path.read_bytes()).decode()
            note(f"  {i+1:>3}. {'cached' if hit else 'spoken '} {c['dur']:>5.1f}s  "
                 f"{c['text'][:60]}")

    out = pathlib.Path(args.out).resolve() if args.out else out_path(deck)
    render(deck, paper, out, args.plus)
    FONTS = {"hand": 1, "virgil": 1, "normal": 2, "helvetica": 2, "sans": 2,
             "code": 3, "mono": 3, "cascadia": 3}
    payload = {"autoplay": autoplay, "subs": subs, "mode": mode, "cues": cues,
               "diagramFont": FONTS.get(str(st.get("diagram_font", "normal")).lower(), 2)}
    # The page turn rides in the same blob as the narration because it is part of the
    # narration: it only ever sounds while a clip is playing.
    want = str(st.get("turn", "default")).strip().lower()
    turn = TURN if want in ("", "default", "true") else pathlib.Path(st["turn"]).expanduser()
    vol = float(st.get("turn_volume", 0.32))
    if want not in ("off", "none", "false") and turn.exists() and vol > 0:
        payload["turn"] = "data:audio/mpeg;base64," + \
            base64.b64encode(turn.read_bytes()).decode()
        payload["turnVolume"] = vol
    blob = json.dumps(payload).replace("</", "<\\/")
    inject(out, blob)
    total = sum(c["dur"] for c in cues)
    note(f"{mode} / {voice}: {len(cues)} cues, {fresh} spoken, {cached} cached, "
         f"{int(total // 60)}:{int(total % 60):02d}, {out.stat().st_size / 1e6:.1f}MB page")
    print(out)
    if not args.no_open:
        subprocess.run(["open", f"file://{out}"])


if __name__ == "__main__":
    sys.exit(main())
