#!/usr/bin/env python3
"""write_notes rewrites the whole deck, so the separators it puts back have to be the
ones SLIDE_HR took out. A separator that loses its blank line still LOOKS fine and
still renders — as one slide holding the whole deck. Assert the slide count survives
the round-trip, and that a deck whose notes did not change is not rewritten at all."""
import pathlib, sys, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from pdplus import write_notes, SLIDE_HR

DECK = """---
title: T
---

# One

text

---

# Two

:::notes
old note
:::

---

# Three
"""
# a separator written loosely: extra blank line above, trailing spaces after
LOOSE = "# A\n\ntext\n\n\n---   \n\n# B\n"


def roundtrip(src, notes):
    with tempfile.TemporaryDirectory() as d:
        f = pathlib.Path(d) / "deck.md"
        f.write_text(src, encoding="utf-8")
        ok, msg = write_notes(f, notes)
        return ok, msg, f.read_text(encoding="utf-8")


def slides(text):
    return len(SLIDE_HR.split(text))


def main():
    ok, msg, out = roundtrip(DECK, ["", "old note", ""])
    assert ok, msg
    # THE property: the file that comes out splits into the same slides that went in
    assert slides(out) == slides(DECK) == 3, f"{slides(out)} slides out, {slides(DECK)} in"
    # unchanged notes must not rewrite anything
    assert out == DECK, "unchanged notes did not round-trip byte-identically:\n%r" % out

    # a new note lands, and the separators still hold
    ok, msg, out = roundtrip(DECK, ["fresh", "", "last"])
    assert ok, msg
    assert slides(out) == 3, f"{slides(out)} slides after editing notes"
    assert ":::notes\nfresh\n:::" in out and "old note" not in out

    # a loosely written separator may be tidied, but never past what SLIDE_HR matches
    ok, msg, out = roundtrip(LOOSE, ["", ""])
    assert ok, msg
    assert slides(out) == 2, f"{slides(out)} slides out of the loose deck"
    assert "---   \n" in out, "trailing spaces on the separator were rewritten"

    print("ok  write_notes  3 decks, separators intact")
    return 0


if __name__ == "__main__":
    sys.exit(main())
