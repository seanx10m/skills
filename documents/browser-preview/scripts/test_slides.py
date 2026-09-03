#!/usr/bin/env python3
"""Self-check for deck splitting. Run: python3 test_slides.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mdview import split_slides, strip_frontmatter

# hr splits; directives peel off
sl = split_slides("# A\nface a\n\n:::details\ndeep a\n:::\n\n:::notes\nsay a\n:::\n\n---\n\n# B\nface b\n")
assert len(sl) == 2, sl
assert sl[0]["title"] == "A" and sl[1]["title"] == "B"
assert sl[0]["face"] == "# A\nface a", repr(sl[0]["face"])
assert sl[0]["details"] == "deep a" and sl[0]["notes"] == "say a"
assert sl[1]["details"] == "" and sl[1]["notes"] == ""

# a setext H2 underline must NOT split the deck
sl = split_slides("intro\n\nTitle\n---\nbody\n")
assert len(sl) == 1, sl

# no hr anywhere -> split on top-level ## headings
sl = split_slides("# Doc\nlead\n\n## One\na\n\n## Two\nb\n")
assert [x["title"] for x in sl] == ["Doc", "One", "Two"], sl

# no hr, no ## -> one slide, untitled falls back
sl = split_slides("just a paragraph\n")
assert len(sl) == 1 and sl[0]["title"] == "Slide 1"

# faceLines cut: details start strictly after the face's last line
face = sl[0]["face"]
assert face.count("\n") + 1 == 1

# frontmatter: title comes out, table is suppressed for decks
t, body = strip_frontmatter("---\ntitle: Deck\n---\n\n# H\nx\n", "f.md", emit_table=False)
assert t == "Deck" and body.lstrip().startswith("# H"), (t, body)
t2, body2 = strip_frontmatter("---\ntitle: Deck\n---\n\n# H\nx\n", "f.md")
assert "title" in body2  # default still emits the metadata table

print("test_slides: ok")
