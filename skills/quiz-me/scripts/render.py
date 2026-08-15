#!/usr/bin/env python3
"""Deck -> one self-contained HTML file, opened in the browser.

This is the whole of `quiz-me`. `quiz-me-full` calls the same entry point with
a scheduled subset and per-card interval previews, so there is exactly ONE
renderer and the plain and spaced-repetition modes cannot drift apart.

    render.py deck.md                      # everything, no scheduling
    render.py deck.md --cards 3,7,9        # a subset, in that order
    render.py deck.md --config cfg.json    # scheduled mode (quiz-me-full)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from deck import LEVELS, DeckError, parse  # noqa: E402

HERE = Path(__file__).parent
TEMPLATE = HERE / "template.html"
OUT_DIR = Path.home() / "Desktop" / "quiz-progress" / ".rendered"

# Inline `code` in deck text is authored as markdown; the template expects HTML.
_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")


def _fmt(text: str) -> str:
    """Minimal inline markdown -> HTML. Deliberately not a markdown parser:
    a deck is one question and a paragraph, and pulling in a dependency to
    render two inline forms would be the wrong trade."""
    out = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    out = _CODE.sub(r"<code>\1</code>", out)
    return _BOLD.sub(r"<b>\1</b>", out)


def build(deck: dict, cards: list[dict], config: dict) -> str:
    tpl = TEMPLATE.read_text(encoding="utf-8")
    payload = []
    for c in cards:
        payload.append({
            "id": c["id"], "d": c["d"], "a": c["a"],
            "q": _fmt(c["q"]),
            "opts": [_fmt(o) for o in c["opts"]],
            "exp": _fmt(c["exp"]),
            "cite": c.get("cite", ""),
            "tag": c.get("tag", ""),
            "sched": c.get("sched"),
        })
    cfg = {
        "deck": deck["id"], "deckTitle": deck["title"],
        "scheduled": False, "session": "", "level": 0, "syncCmd": "",
        **config,
    }
    sub = {
        "__TITLE__": deck["title"],
        "__KICKER__": cfg.get("kicker", "Quiz"),
        "__SUBTITLE__": cfg.get("subtitle",
            f"{len(cards)} cards. Answer, then say how sure you were - "
            "the score grades calibration, not just hits."),
        "__CONFIG__": json.dumps(cfg),
        "__CARDS__": json.dumps(payload),
        "__LEVELS__": json.dumps({str(k): v[0] for k, v in LEVELS.items()}),
    }
    for k, v in sub.items():
        tpl = tpl.replace(k, v)
    return tpl


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck")
    ap.add_argument("--cards", default="", help="comma-separated card ids, in order")
    ap.add_argument("--config", default="", help="JSON string or path to a JSON file")
    ap.add_argument("--out", default="")
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args()

    try:
        d = parse(a.deck)
    except DeckError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    by_id = {c["id"]: c for c in d["cards"]}
    if a.cards:
        try:
            ids = [int(x) for x in a.cards.split(",") if x.strip()]
        except ValueError:
            print("error: --cards must be comma-separated integers", file=sys.stderr)
            return 1
        missing = [i for i in ids if i not in by_id]
        if missing:
            print(f"error: no card {missing} in deck (has 1..{len(d['cards'])})",
                  file=sys.stderr)
            return 1
        cards = [by_id[i] for i in ids]
    else:
        cards = d["cards"]

    cfg = {}
    if a.config:
        raw = Path(a.config)
        cfg = json.loads(raw.read_text()) if raw.is_file() else json.loads(a.config)

    # `sched` previews arrive keyed by card id; attach them here so the
    # scheduler never has to know the render payload shape.
    sched = cfg.pop("sched", {}) or {}
    for c in cards:
        c["sched"] = sched.get(str(c["id"]))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = Path(a.out) if a.out else OUT_DIR / f"{d['id']}.html"
    out.write_text(build(d, cards, cfg), encoding="utf-8")
    print(out)
    if not a.no_open:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.run([opener, str(out)], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
