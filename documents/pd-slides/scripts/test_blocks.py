#!/usr/bin/env python3
"""The paper splitter has to agree with how the page renders the paper, block for
block, or the captions read one paragraph while the audio speaks another. Assert the
shape it produces for a paper carrying every block kind that matters."""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from pdnarrate import paper_blocks, plain

PAPER = """# Title here

First paragraph, **bold** and a [link](http://x).

## Second section

- one item
- two item

| a | b |
|---|---|
| 1 | 2 |

<!-- say: the table shows one and two -->

```python
print("silent")
```

### Deeper heading

Last words.
"""


def main():
    got = [(b["line"], b["kind"], b["depth"], b["text"]) for b in paper_blocks(PAPER)]
    want = [
        (1, "heading", 1, "Title here"),
        (3, "text", 0, "First paragraph, bold and a link."),
        (5, "heading", 2, "Second section"),
        (7, "text", 0, "one item"),
        (8, "text", 0, "two item"),
        (10, "table", 0, ""),
        (14, "say", 0, "the table shows one and two"),
        (16, "code", 0, ""),
        (20, "heading", 3, "Deeper heading"),
        (22, "text", 0, "Last words."),
    ]
    ok = True
    for g, w in zip(got, want):
        if g != w:
            print(f"FAIL got {g}\n     want {w}"); ok = False
    if len(got) != len(want):
        print(f"FAIL {len(got)} blocks, want {len(want)}"); ok = False
    # the unspeakable kinds must carry no text — a table read aloud is pipes and dashes
    for b in paper_blocks(PAPER):
        if b["kind"] in ("code", "table", "image", "html") and b["text"]:
            print(f"FAIL {b['kind']} at L{b['line']} is speakable"); ok = False
    assert plain("## A `code` *span*") == "A code span"
    print("ok  paper_blocks  %d blocks" % len(got) if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
