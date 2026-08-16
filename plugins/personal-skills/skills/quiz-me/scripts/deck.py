"""Deck parsing + the difficulty ladder. Shared by quiz-me and quiz-me-full.

A deck is ONE markdown file. It is the only authoring surface: the agent
writes it, a human can edit it, and nothing else needs to be generated.

    # Deck: Rex Storage Substrate
    id: rex-storage

    ## Where does a Skill's SKILL.md body live? [2]
    - [ ] Cloud SQL only
    - [ ] GCS and the mirror
    - [x] All three
    > All three. Postgres has `skills.body`, GCS has the object, the mirror
    > has the file. The one genuine three-way duplicate.
    @ core/profile/models.py:200

`[2]` is the difficulty, 1-5, default 3. `- [x]` marks the correct option.
`>` lines are the explanation, `@` is the citation. That's the whole format.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# The five rungs. Difficulty is a property of the QUESTION, not of your
# performance on it - a card does not get harder because you keep missing it.
# That is what the SM-2 ease factor is for, and conflating the two is the
# classic mistake (Anki keeps them separate for the same reason).
#
# The rungs climb from PURPOSE to DESIGN, and deliberately never include
# "where does this live". Location is the one thing a reader can always
# recover in seconds with grep, so testing it measures nothing and teaches
# nothing - while "why does this exist" is exactly what a newcomer cannot
# recover from the code and most needs in week one.
LEVELS = {
    1: ("Purpose", "Why this exists at all"),
    2: ("Mechanism", "How it actually works, end to end"),
    3: ("Factors", "What goes into the decision, and what does not"),
    4: ("Consequence", "What breaks, and what the trade-off buys"),
    5: ("Design", "Here is a change - what is wrong with it"),
}

DOTS = {n: "●" * n + "○" * (5 - n) for n in LEVELS}


class DeckError(Exception):
    pass


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48] or "deck"


def parse(path: str | Path) -> dict:
    """Markdown deck file -> {id, title, cards:[...]}. Raises DeckError."""
    p = Path(path)
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise DeckError(f"cannot read deck {p}: {exc}") from exc

    title, deck_id = p.stem.replace("-", " ").title(), ""
    cards: list[dict] = []
    cur: dict | None = None

    def close() -> None:
        if cur is None:
            return
        if len(cur["opts"]) < 2:
            raise DeckError(f"card {cur['n']} ({cur['q'][:40]!r}) has < 2 options")
        if cur["a"] is None:
            raise DeckError(f"card {cur['n']} ({cur['q'][:40]!r}) marks no `- [x]` answer")
        cur["exp"] = " ".join(cur["exp"]).strip()
        cards.append(cur)

    for raw in lines:
        line = raw.rstrip()
        s = line.strip()

        if s.startswith("# Deck:"):
            title = s[len("# Deck:"):].strip()
            continue
        m = re.match(r"^id:\s*(\S+)", s)
        if m and cur is None:
            deck_id = m.group(1)
            continue

        if s.startswith("## "):
            close()
            q = s[3:].strip()
            diff = 3
            m = re.search(r"\s*\[([1-5])\]\s*$", q)
            if m:
                diff = int(m.group(1))
                q = q[: m.start()].strip()
            cur = {"n": len(cards) + 1, "q": q, "opts": [], "a": None,
                   "exp": [], "cite": "", "d": diff}
            continue

        if cur is None:
            continue

        m = re.match(r"^-\s*\[([ xX])\]\s*(.+)$", s)
        if m:
            if m.group(1).lower() == "x":
                cur["a"] = len(cur["opts"])
            cur["opts"].append(m.group(2).strip())
            continue

        if s.startswith(">"):
            cur["exp"].append(s[1:].strip())
            continue

        if s.startswith("@ "):
            cur["cite"] = s[2:].strip()
            continue

        # A bare line right after the heading continues the question text.
        if s and not cur["opts"]:
            cur["q"] += " " + s

    close()
    if not cards:
        raise DeckError(f"{p}: no cards found (need `## question` headings)")
    for i, c in enumerate(cards, 1):
        c["id"] = i
    return {"id": deck_id or _slug(title), "title": title,
            "path": str(p.resolve()), "cards": cards}


def next_level(level: int, results: list[dict]) -> tuple[int, str]:
    """The adaptive ladder: climb on confident correctness, fall on misses.

    `results` is this session's rows, each {ok, conf, d} where conf is
    0=sure / 1=think / 2=guess. Only cards AT or ABOVE the current level
    count toward climbing - clearing easy cards you have already mastered
    should not promote you, or the ladder just measures deck composition.
    """
    at = [r for r in results if r["d"] >= level]
    if not at:
        return level, "no cards at your level this session - held"
    hits = sum(1 for r in at if r["ok"])
    solid = sum(1 for r in at if r["ok"] and r["conf"] == 0)
    acc = hits / len(at)

    if level < 5 and acc >= 0.8 and solid >= 2:
        return level + 1, f"{hits}/{len(at)} at L{level}, {solid} of them confident - promoted"
    if level > 1 and acc < 0.4:
        return level - 1, f"{hits}/{len(at)} at L{level} - dropped back to rebuild"
    return level, f"{hits}/{len(at)} at L{level} - holding"


if __name__ == "__main__":  # smallest thing that fails if parsing breaks
    src = """# Deck: T
id: t

## easy one [1]
- [ ] a
- [x] b
> because b
@ file.py:1

## harder
- [x] c
- [ ] d
"""
    tmp = Path("/tmp/_deck_selfcheck.md")
    tmp.write_text(src)
    d = parse(tmp)
    assert d["id"] == "t" and len(d["cards"]) == 2, d
    assert d["cards"][0]["d"] == 1 and d["cards"][1]["d"] == 3
    assert d["cards"][0]["a"] == 1 and d["cards"][0]["exp"] == "because b"
    assert d["cards"][0]["cite"] == "file.py:1"
    assert next_level(1, [{"ok": True, "conf": 0, "d": 1}] * 3)[0] == 2
    assert next_level(3, [{"ok": False, "conf": 1, "d": 3}] * 3)[0] == 2
    assert next_level(2, [{"ok": True, "conf": 0, "d": 1}] * 5)[0] == 2  # below level
    tmp.unlink()
    print("deck.py self-check OK", file=sys.stderr)
