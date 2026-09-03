#!/usr/bin/env python3
"""pd-slides-plus - the deck, served, so it can write to disk and talk back.

pd-slides opens a finished file. Everything it cannot do traces to one fact: a
`file://` page has no origin, so it has no storage, no fetch, and no cross-frame
access. Put the same deck behind a local server and four things become possible at
once - diagrams you edit and that save as real files, a live app framed inside a
slide, an agent you can talk to from the page, and comments that survive a reload.

The renderer is NOT forked. This is `--plus` on the same mdview.py that pd-slides
uses, so every fix to the deck, the paper pairing or the narration lands in both.

  pdplus.py serve deck.md paper.md      # render, serve, open
  pdplus.py poll                        # agent side: block until the user says something
  pdplus.py say "on it - one sec"       # agent side: reply into the page
  pdplus.py stop
"""
import argparse, http.server, json, os, pathlib, re, secrets, socket, subprocess, sys, \
    threading, time, urllib.parse, webbrowser

HOME = pathlib.Path.home()
SKILL = HOME / ".claude/skills/pd-slides-plus"
MDVIEW = HOME / ".claude/skills/browser-preview/scripts/mdview.py"
NARRATE = HOME / ".claude/skills/pd-slides/scripts/pdnarrate.py"
ASSETS = SKILL / "assets"

sys.path.insert(0, str(MDVIEW.parent))
from mdview import split_slides, strip_frontmatter, SLIDE_HR  # noqa: E402

STATE = {}          # filled by serve()
CHAT = []           # [{n, from, text, ts, slide?, title?}]
CHAT_EV = threading.Condition()


def workdir(deck):
    d = deck.parent / ".pdplus"
    d.mkdir(exist_ok=True)
    return d


def lan_ip():
    """The address another device on this network can actually reach.

    Opening a UDP socket to a public address makes the OS pick the interface it would
    route through; nothing is sent. Falls back to loopback on an offline machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def free_port(preferred):
    for port in (preferred, 0):
        s = socket.socket()
        try:
            s.bind(("", port))
            return s.getsockname()[1]
        except OSError:
            continue
        finally:
            s.close()
    return preferred


# ── notes round-trip ────────────────────────────────────────────────────────
NOTES_BLOCK = re.compile(r"(?ms)\n*^:{3,}[ \t]*notes[ \t]*$\r?\n.*?^:{3,}[ \t]*$\r?\n?")
NOTES_1L = re.compile(r"(?m)^:{3,}[ \t]*notes[ \t]+.+$\r?\n?")


def write_notes(deck, notes):
    """Put edited speaker notes back into deck.md, one `:::notes` block per slide.

    Split with the separators KEPT (re.split drops them) and written back UNTOUCHED —
    SLIDE_HR requires a blank line above the `---`, so a separator that is rebuilt
    instead of replayed loses it and the whole deck silently becomes one slide.
    Reassembly is byte-identical apart from the note blocks themselves and any extra
    blank lines directly above a separator or at EOF, which collapse to the one the
    separator carries. Frontmatter and components are never touched.
    """
    raw = deck.read_text(encoding="utf-8")
    head, body = "", raw
    if raw.startswith("---"):
        end = raw.find("\n---", 3)
        if end != -1:
            nl = raw.find("\n", end + 1)
            head, body = raw[:nl + 1], raw[nl + 1:]
    parts, last = [], 0
    for m in SLIDE_HR.finditer(body):
        parts.append((body[last:m.start()], m.group(0)))
        last = m.end()
    parts.append((body[last:], ""))
    if len(parts) != len(notes):
        return False, f"deck has {len(parts)} slides, got {len(notes)}"
    out = []
    for (chunk, sep), note in zip(parts, notes):
        chunk = NOTES_1L.sub("", NOTES_BLOCK.sub("", chunk)).rstrip("\n")
        if note and note.strip():
            chunk += "\n\n:::notes\n" + note.strip() + "\n:::"
        out.append(chunk + (sep or "\n"))
    deck.write_text(head + "".join(out), encoding="utf-8")
    return True, f"{sum(1 for n in notes if n.strip())} slide(s) with notes"


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _auth(self, q):
        # The server binds to the LAN so another device can open the deck. Reads are
        # open; anything that WRITES to the filesystem needs the token from the URL,
        # so being on the wifi is not the same as being allowed to edit the repo.
        return (q.get("k", [""])[0] or "") == STATE["token"]

    def _send(self, code, body=b"", ctype="application/json", extra=None):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        path = urllib.parse.unquote(u.path)

        if path in ("/", "/index.html"):
            return self._send(200, STATE["html"].read_bytes(), "text/html; charset=utf-8")

        if path.startswith("/assets/"):
            f = (ASSETS / path[len("/assets/"):]).resolve()
            if ASSETS.resolve() not in f.parents and f != ASSETS.resolve():
                return self._send(403, b'{"error":"outside assets"}')
            if not f.is_file():
                return self._send(404, b'{"error":"no such asset"}')
            types = {".js": "application/javascript", ".css": "text/css",
                     ".woff2": "font/woff2", ".wasm": "application/wasm",
                     ".json": "application/json", ".png": "image/png"}
            return self._send(200, f.read_bytes(),
                              types.get(f.suffix, "application/octet-stream"),
                              {"Cache-Control": "public, max-age=86400"})

        if path.startswith("/scene/"):
            f = scene_path(path[len("/scene/"):])
            if not f or not f.is_file():
                return self._send(404, b'{}')
            return self._send(200, f.read_bytes())

        if path.startswith("/icon/"):
            # The skill ships a common architecture vocabulary; a project drops its OWN
            # marks in ./icons next to the deck and they win, so a diagram can carry the
            # product it is about and not just the stack under it.
            name = re.sub(r"[^\w.-]", "", path[len("/icon/"):]).lower()
            if not name:
                return self._send(404, b'{}')
            for d in (STATE["icons"], ASSETS / "icons"):
                for ext in (".svg", ".png"):
                    f = d / (name + ext)
                    if f.is_file():
                        # simple-icons ship a bare monochrome path; the deck needs it
                        # visible on either theme, so colour it at serve time
                        body = f.read_bytes()
                        if ext == ".svg":
                            txt = body.decode("utf-8", "replace")
                            if "fill=" not in txt.split(">")[0]:
                                txt = txt.replace("<svg", f'<svg fill="{q.get("c", ["#c9ccd4"])[0]}"', 1)
                            body = txt.encode()
                        return self._send(200, body,
                                          "image/svg+xml" if ext == ".svg" else "image/png",
                                          {"Cache-Control": "public, max-age=3600"})
            return self._send(404, b'{}')

        if path == "/icons":
            names = set()
            for d in (STATE["icons"], ASSETS / "icons"):
                if d.is_dir():
                    names |= {f.stem.lower() for f in d.iterdir()
                              if f.suffix in (".svg", ".png")}
            return self._send(200, json.dumps(sorted(names)))

        if path == "/chat":
            since = int(q.get("since", ["0"])[0])
            # long-poll: hold the request open until there is something to say, so the
            # page gets the agent's reply the moment it lands and never polls a loop
            with CHAT_EV:
                if not [m for m in CHAT if m["n"] > since]:
                    CHAT_EV.wait(timeout=25)
                msgs = [m for m in CHAT if m["n"] > since]
            return self._send(200, json.dumps({"messages": msgs}))

        return self._send(404, b'{"error":"not found"}')

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        path = urllib.parse.unquote(u.path)
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        if not self._auth(q):
            return self._send(403, b'{"error":"bad or missing token"}')
        try:
            data = json.loads(raw or b"{}")
        except Exception:
            return self._send(400, b'{"error":"bad json"}')

        if path.startswith("/scene/"):
            f = scene_path(path[len("/scene/"):])
            if not f:
                return self._send(400, b'{"error":"bad scene name"}')
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(data, indent=2), encoding="utf-8")
            print(f"  saved {f.relative_to(STATE['root'])}"
                  f" ({len(data.get('elements') or [])} elements)", file=sys.stderr)
            return self._send(200, b'{"ok":true}')

        if path == "/notes":
            ok, msg = write_notes(STATE["deck"], data if isinstance(data, list) else [])
            print(f"  notes -> {STATE['deck'].name}: {msg}", file=sys.stderr)
            return self._send(200 if ok else 409, json.dumps({"ok": ok, "msg": msg}))

        if path == "/chat":
            push(str(data.get("text", ""))[:8000], data.get("from", "user"),
                 slide=data.get("slide"), title=data.get("title"))
            return self._send(200, b'{"ok":true}')

        return self._send(404, b'{"error":"not found"}')


def scene_path(name):
    name = re.sub(r"[^\w.-]", "", urllib.parse.unquote(name))
    if not name or name.startswith("."):
        return None
    if not name.endswith(".excalidraw"):
        name += ".excalidraw"
    return STATE["scenes"] / name


def push(text, who="agent", **extra):
    if not text.strip():
        return
    with CHAT_EV:
        m = {"n": len(CHAT) + 1, "from": who, "text": text, "ts": time.time()}
        m.update({k: v for k, v in extra.items() if v is not None})
        CHAT.append(m)
        STATE["chatlog"].write_text(
            "\n".join(json.dumps(x) for x in CHAT) + "\n", encoding="utf-8")
        CHAT_EV.notify_all()


def load_chat():
    f = STATE["chatlog"]
    if f.is_file():
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    CHAT.append(json.loads(line))
                except Exception:
                    pass


FONTS = {"hand": 1, "virgil": 1, "normal": 2, "helvetica": 2, "sans": 2,
         "code": 3, "mono": 3, "cascadia": 3}


def seed_settings(page, near):
    """Give the page its style.md-driven settings when no narration blob exists."""
    sys.path.insert(0, str(HOME / ".claude/skills/pd-slides/scripts"))
    from pdnarrate import load_style
    st = load_style(near)
    blob = json.dumps({"cues": [],
                       "diagramFont": FONTS.get(str(st.get("diagram_font", "normal")).lower(), 2)})
    txt = page.read_text(encoding="utf-8")
    page.write_text(re.sub(r"<script>window\.PD_AUDIO=.*?/\*PD_AUDIO_SLOT\*/</script>",
                           "<script>window.PD_AUDIO=" + blob + "/*PD_AUDIO_SLOT*/</script>",
                           txt, count=1, flags=re.S), encoding="utf-8")


def render(deck, paper, out, narrate, extra):
    if narrate:
        cmd = [sys.executable, NARRATE, deck] + ([paper] if paper else []) + \
              ["--plus", "--no-open", "-o", out] + extra
    else:
        cmd = [sys.executable, MDVIEW, deck, "--deck", "--plus", "--no-open", "-o", out] + \
              (["--paper", str(paper)] if paper else [])
    r = subprocess.run([str(c) for c in cmd], text=True, capture_output=True)
    if r.returncode:
        sys.exit((r.stderr or r.stdout).strip() or "render failed")
    if r.stderr.strip():
        print(r.stderr.strip(), file=sys.stderr)


def cmd_serve(a):
    deck = pathlib.Path(a.deck).resolve()
    if not deck.exists():
        sys.exit(f"not found: {deck}")
    paper = pathlib.Path(a.paper).resolve() if a.paper else None
    wd = workdir(deck)
    root = deck.parent
    STATE.update(deck=deck, root=root, html=wd / "deck.html",
                 scenes=(pathlib.Path(a.scenes).resolve() if a.scenes else root / "diagrams"),
                 icons=(pathlib.Path(a.icons).resolve() if a.icons else root / "icons"),
                 chatlog=wd / "chat.jsonl", token=secrets.token_urlsafe(8))
    (wd / "port").unlink(missing_ok=True)
    load_chat()

    # pdnarrate shells mdview itself, so plus mode rides in through its own --plus
    render(deck, paper, STATE["html"], a.narrate, [])
    if not a.narrate:
        # without a narration pass there is no PD_AUDIO blob, but the page still reads
        # its diagram font from there — seed a minimal one
        seed_settings(STATE["html"], deck.parent)

    port = free_port(a.port)
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", port), Handler)
    srv.daemon_threads = True
    url = f"http://localhost:{port}/?k={STATE['token']}"
    lan = f"http://{lan_ip()}:{port}/?k={STATE['token']}"
    (wd / "port").write_text(json.dumps({"port": port, "token": STATE["token"],
                                         "url": url, "lan": lan,
                                         "readonly": lan.split("/?k=")[0] + "/"}))
    print(f"  deck      {url}")
    print(f"  network   {lan}")
    # The token IS write access, so the link you hand someone is a decision. Print the
    # read-only one next to it rather than making people remember to strip it.
    print(f"  read-only {lan.split('/?k=')[0]}/")
    print(f"  scenes    {STATE['scenes']}")
    print(f"  icons     {STATE['icons']}  (+ {len(list((ASSETS / 'icons').glob('*.svg')))} built in)")
    print(f"  chat      pdplus.py poll   /   pdplus.py say \"...\"")
    print("  ctrl-c to stop", flush=True)
    if not a.no_open:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped", file=sys.stderr)


# ── agent side ──────────────────────────────────────────────────────────────
def find_session(start):
    d = pathlib.Path(start).resolve()
    for p in [d, *d.parents]:
        f = p / ".pdplus" / "port"
        if f.is_file():
            return json.loads(f.read_text()), p / ".pdplus"
    sys.exit("no running deck here - start one with `pdplus.py serve deck.md`")


def cmd_say(a):
    s, _ = find_session(a.cwd)
    import urllib.request
    req = urllib.request.Request(
        f"http://127.0.0.1:{s['port']}/chat?k={s['token']}",
        data=json.dumps({"from": "agent", "text": a.text}).encode(),
        headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10).read()
    print("sent")


def cmd_poll(a):
    """Block until the user has said something the agent has not read, then print it.

    Reads the LOG, not the socket, so a poll survives the server restarting. And the
    read position is a cursor on disk rather than "everything from now" — otherwise a
    message sent between two polls is silently dropped, which is the one thing a
    feedback loop may never do.
    """
    s, wd = find_session(a.cwd)
    log, cur = wd / "chat.jsonl", wd / "poll-cursor"
    # Wait on the SERVER, not on a timer. /chat already blocks on a Condition that the
    # POST handler notifies, so the agent wakes the instant a message lands instead of
    # up to a second later. The file is still the source of truth — this call only
    # decides *when* to look, and if the server is gone we fall back to the timer.
    def wait_for_change(n_seen, budget):
        import urllib.request, urllib.error
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{s['port']}/chat?since={n_seen}&k={s['token']}",
                    timeout=min(budget, 30)) as r:
                r.read()
            return True
        except Exception:
            time.sleep(1)
            return False
    def lines():
        return [l for l in (log.read_text(encoding="utf-8").splitlines()
                            if log.is_file() else []) if l.strip()]
    if a.since >= 0:
        seen = a.since
    else:
        try:
            seen = int(cur.read_text())
        except Exception:
            seen = 0
    deadline = time.time() + a.timeout
    while True:
        ls = lines()
        new = [json.loads(l) for l in ls[seen:]]
        user = [m for m in new if m.get("from") != "agent"]
        if user:
            for m in user:
                where = f" (slide {m['slide']}: {m.get('title','')})" if m.get("slide") else ""
                print(f"[{m['n']}]{where} {m['text']}")
            cur.write_text(str(len(ls)))
            return
        if time.time() >= deadline:
            break
        wait_for_change(ls[-1] and json.loads(ls[-1])["n"] if ls else 0,
                        max(1, deadline - time.time()))
    cur.write_text(str(len(lines())))
    print("(nothing new)")


def main():
    a = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = a.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve"); s.set_defaults(fn=cmd_serve)
    s.add_argument("deck"); s.add_argument("paper", nargs="?")
    s.add_argument("--port", type=int, default=7788)
    s.add_argument("--scenes", help="where .excalidraw files live (default ./diagrams)")
    s.add_argument("--icons", help="project icon dir, overrides the built-in set (default ./icons)")
    # Narration is default-on: clips are cached by the hash of their own text, so the
    # only run that costs anything is the first. A deck that cannot be listened to is
    # missing the option, not saving time.
    s.add_argument("--no-narrate", dest="narrate", action="store_false", default=True,
                   help="skip the audio track")
    s.add_argument("--no-open", action="store_true")
    p = sub.add_parser("poll"); p.set_defaults(fn=cmd_poll)
    p.add_argument("--cwd", default="."); p.add_argument("--timeout", type=int, default=600)
    p.add_argument("--since", type=int, default=-1,
               help="read position; -1 uses the saved cursor, 0 replays everything")
    y = sub.add_parser("say"); y.set_defaults(fn=cmd_say)
    y.add_argument("text"); y.add_argument("--cwd", default=".")
    args = a.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
