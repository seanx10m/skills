#!/usr/bin/env python3
"""Terminal tap: run a command in a pty we own, mirror it to the real terminal,
and extract assistant prose as it is painted so it can be spoken mid-turn.

Anchor is the message bullet at column 0 plus its indented continuation lines,
not a whole-screen diff - the surrounding chrome redraws, a message block does not.
"""
import os, sys, pty, select, signal, fcntl, termios, struct, time, re, unicodedata

import pyte

BULLET = ("●", "⏺")          # the message markers the TUI paints
SPINNER = re.compile(r"^[\s✶✹✳✴✵✷·…]*$")
STATUS  = re.compile(r" · |/effort|tokens\)|^\w+ ·")   # status chrome also paints a bullet
CHROME  = re.compile(r"[─-╿]")   # box drawing: any panel line

def term_size(fd):
    try:
        h, w, _, _ = struct.unpack("HHHH", fcntl.ioctl(fd, termios.TIOCGWINSZ, b"\0"*8))
        return (h or 40), (w or 100)
    except Exception:
        return 40, 100

class Extractor:
    """Feeds bytes to a screen model and yields message text once it stops changing."""
    def __init__(self, cols, rows, on_text, settle=0.45):
        self.screen = pyte.HistoryScreen(cols, rows, history=4000)
        self.stream = pyte.Stream(self.screen)
        self.on_text = on_text
        self.settle = settle
        self.blocks = {}      # first line of a block -> [text, last_change, emitted_len]
        self.spoken = set()

    def feed(self, data):
        self.stream.feed(data)

    def _lines(self):
        hist = ["".join(c.data for c in row.values()).rstrip()
                for row in self.screen.history.top]
        return hist + [l.rstrip() for l in self.screen.display]

    def scan(self):
        lines, now = self._lines(), time.time()
        i, seen = 0, set()
        while i < len(lines):
            ln = lines[i]
            if ln[:1] in BULLET:
                body = [ln[1:].strip()]
                j = i + 1
                while j < len(lines):
                    nxt = lines[j]
                    if not nxt.strip():
                        body.append("")
                    elif nxt.startswith("  ") and nxt[:1] not in BULLET and not CHROME.search(nxt):
                        body.append(nxt.strip())
                    else:
                        break
                    j += 1
                text = "\n".join(body).strip()
                text = re.sub(r"\n{3,}", "\n\n", text)
                if text and not CHROME.search(text.splitlines()[0]):
                    key = text.splitlines()[0][:60]
                    seen.add(key)
                    prev = self.blocks.get(key)
                    if prev is None or prev[0] != text:
                        self.blocks[key] = [text, now, prev[2] if prev else 0]
                i = j
            else:
                i += 1
        # Release COMPLETE SENTENCES as they finish, keyed by CONTENT not position -
        # the block reflows as the pane scrolls, so a character offset into it drifts.
        for key, st in list(self.blocks.items()):
            text, changed, _ = st
            if STATUS.search(text.splitlines()[0]):
                continue
            parts = re.findall(r".+?[.!?](?=[\s\n]|$)|.+$", text, flags=re.S)
            for idx, raw in enumerate(parts):
                sent = " ".join(raw.split()).lstrip("\u25cf\u23fa ").strip()
                # chrome can also land INSIDE a block as an indented line, so filter
                # every sentence, not just the block's first line
                if not sent or SPINNER.match(sent) or len(sent) < 2 or STATUS.search(sent):
                    continue
                closed = sent[-1] in ".!?"
                # an unterminated tail only goes out once the block stops growing
                if not closed and now - changed < self.settle:
                    continue
                if sent in self.spoken:
                    continue
                self.spoken.add(sent)
                self.on_text(sent)

def main():
    argv = sys.argv[1:]
    if not argv:
        print("usage: tap.py <command> [args...]", file=sys.stderr); sys.exit(2)
    sink = os.environ.get("TALKTOME_TAP_OUT", "")
    rows, cols = term_size(sys.stdin.fileno())

    spool = os.environ.get("TALKTOME_TAP_SPOOL", "")
    if spool:
        os.makedirs(spool, exist_ok=True)
    beat = os.path.join(spool, ".beat") if spool else ""
    out = open(sink, "a", buffering=1) if sink else None
    seq = [0]
    def emit(text):
        line = text.replace("\n", " ")
        if out:
            out.write(line + "\n")
        if spool:
            seq[0] += 1
            tmp = os.path.join(spool, ".w%d" % seq[0])
            with open(tmp, "w") as f:
                f.write(line)
            os.rename(tmp, os.path.join(spool, "%019d-%04d.txt" % (time.time_ns(), seq[0])))

    pid, fd = pty.fork()
    if pid == 0:
        if spool:
            os.environ["TALKTOME_TAP_SPOOL"] = spool
        os.execvp(argv[0], argv)

    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    ex = Extractor(cols, rows, emit)

    try:
        mode = termios.tcgetattr(sys.stdin.fileno()); tty_ok = True
        import tty as _tty; _tty.setraw(sys.stdin.fileno())
    except Exception:
        tty_ok = False

    def winch(*_):
        r, c = term_size(sys.stdin.fileno())
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", r, c, 0, 0))
        ex.screen.resize(r, c)
    signal.signal(signal.SIGWINCH, winch)

    try:
        while True:
            try:
                r, _, _ = select.select([fd, sys.stdin.fileno()], [], [], 0.15)
            except InterruptedError:
                continue
            if fd in r:
                try:
                    data = os.read(fd, 65536)
                except OSError:
                    break
                if not data:
                    break
                os.write(sys.stdout.fileno(), data)          # the real terminal, untouched
                ex.feed(data.decode("utf8", "replace"))
            if sys.stdin.fileno() in r:
                d = os.read(sys.stdin.fileno(), 65536)
                if d:
                    os.write(fd, d)
            ex.scan()
            if beat:
                try:
                    open(beat, "w").close()
                except OSError:
                    pass
    finally:
        if tty_ok:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSAFLUSH, mode)
        if out:
            out.close()

if __name__ == "__main__":
    main()
