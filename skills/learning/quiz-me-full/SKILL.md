---
name: quiz-me-full
description: Spaced-repetition quizzing over a topic, Anki-style, with progress kept as plain Markdown on the Desktop so a later session can pick it up. Adds SM-2 scheduling, an adaptive 1-5 difficulty ladder, leech detection, and a confidence-weighted grade that punishes confidently-wrong hardest. Also emits a narration-ready review brief of what you keep missing, for a text-to-speech tool or a scheduled reminder. Use when the user says "quiz-me-full", "/quiz-me-full", "keep quizzing me on X", "spaced repetition", "what am I still getting wrong", "continue my quiz", "review my misses", or asks to resume a previous quiz session. For a one-shot quiz with nothing saved, use quiz-me.
disable-model-invocation: true
---

# quiz-me-full

Spaced repetition quizzing. Standalone: it bundles the deck parser and renderer
(`scripts/deck.py`, `scripts/render.py`, `scripts/template.html`), the same ones used by
the one-shot `quiz-me` skill. This skill adds the scheduler, the progress file, and the review brief.

All commands: `python3 ~/.claude/skills/quiz-me-full/scripts/quizctl.py <cmd>`

## The loop

```bash
quizctl.py status <deck-id>        # read this FIRST when resuming
quizctl.py start  <deck.md>        # picks due cards, opens the browser
#   ... user answers, clicks Download on the result screen ...
quizctl.py sync                    # folds the result into progress.md
quizctl.py brief  <deck-id>        # narration-ready review of the misses
```

`sync` reads `~/Downloads/*.quizresult.json` and deletes each after folding it in.
If the download is blocked, the user can click Copy instead and paste the blob -
then `echo '<blob>' | quizctl.py record` does the same thing.

## Resuming a session (the main reason this skill exists)

**Run `status` before anything else.** It is the whole handoff:

```
Storage Layers  (storage-layers)
  level    2 - Mechanics: Which store answers which read
  due now  4   new 7   total 15
  leeches  1  -> #3 A skill's scripts/ and references/ files
  next due 2026-08-16
  progress ~/Desktop/quiz-progress/storage-layers.md
  recent:
    2026-08-13 22:31 · #3 L1 · CONFIDENTLY WRONG · 21d -> today · ease 1.35
```

That tells you where they are, what is due, and what is fighting them. Open the
progress file itself only when you need the per-card history.

## Progress file

`~/Desktop/quiz-progress/<deck-id>.md` - one per deck. **The Markdown table in it
IS the database.** It is parsed back on every read, so hand-editing a row works
(bump a due date, force a level via the `level:` line, reset a card's `cw` to 0).
A row that cannot be parsed is skipped, never fatal. The file is regenerated on
write, so columns stay aligned and the prose sections stay current.

Columns: `id · card · L · reps · lapses · cw · ease · ivl · due · last · state`

`cw` is the count of **confidently wrong** answers - the column that matters most.
`L` is the question's difficulty from the deck, not a measure of your performance
on it; that is what `ease` is for, and conflating them is the classic mistake.

Below the table is an append-only log with timestamps - every miss, every lucky
guess, every level change, every session total.

## The scheduling, and how it differs from Anki

SM-2, the classic Anki algorithm, with one change to where the grade comes from.
Anki asks how hard recall felt **after** showing you the answer, which cannot
distinguish "knew it" from "guessed right". This asks for confidence **before**
the explanation is revealed, so it can:

| | Sure | Think so | Guess |
|---|---|---|---|
| **Correct** | grade 5 - interval grows fastest | 4 - solid | 3 - lucky, ease drops, back soon |
| **Wrong** | **0 - confidently wrong**, relearn today, extra ease hit | 1 - wrong | 2 - honest miss, gentlest reset |

The bottom-left cell is the point of the whole skill. A confident wrong model is
more expensive than an admitted gap, because it is the one that gets designed
against - so it is scheduled as more urgent than an honest "I don't know".

A card becomes a **leech** at 2 confidently-wrong answers or 8 lapses. Leeches are
surfaced everywhere and sorted to the front of the next session. They are never
suspended - hiding what you most need is the wrong default.

## The difficulty ladder

Five levels, fixed per question in the deck: **1 Purpose · 2 Mechanism ·
3 Factors · 4 Consequence · 5 Design**. Shown as `●●●○○` in the UI.

The rungs climb from *why does this exist* to *what is wrong with this proposed
change*, and deliberately never include "where does this live". Location is the
one thing a reader recovers in seconds with grep, so a card testing it measures
lookup speed rather than understanding. See the optional `quiz-me` skill for the full authoring rule.

You sit at one level per deck. New cards are only introduced within one rung of
where you are, so the deck feeds you harder material as you earn it.

- **Promote** at ≥80% accuracy on cards at or above your level, with ≥2 of them
  answered confidently.
- **Demote** below 40%.
- Cards *below* your level do not count toward promotion - otherwise the ladder
  just measures deck composition.

## The review brief

```bash
quizctl.py brief <deck-id> [--out PATH]
```

Writes `~/Desktop/quiz-progress/<deck-id>-review.md`: prose, not a table, covering
the six questions fighting you hardest - what you got wrong, how many times, the
right answer, why, and the citation.

It is written to be **spoken**: backticks stripped, no bare "1 cards", no table.
That makes it a direct input to any text-to-speech tool, and worth scheduling:

```bash
quizctl.py brief storage-layers        # then hand the path to your TTS tool
```

Pair with `/schedule` for a recurring reminder of what you keep missing.

## Flags worth knowing

| Flag | On | Effect |
|---|---|---|
| `--new N` | `start` | Cap never-seen cards (default 4). New material is the tiring part. |
| `--max N` | `start` | Cap the whole session (default 12). |
| `--all` | `start` | Ignore due dates and the level band - every card, for a cram or a demo. |
| `--no-open` | `start` | Render without opening; the path is printed. |

## Building a deck

Deck format: one Markdown file (`# Deck: Title`, `id: slug`, then `## Question [difficulty 1-5]`,
`- [ ]`/`- [x]` options, `>` explanation lines, `@` citation). See the docstring in
`scripts/deck.py`. Question-writing guidance is in the optional `quiz-me` skill. Decks live in
`~/Desktop/quiz-progress/decks/`.

Write your own deck and keep it in `~/Desktop/quiz-progress/decks/`.

## Failure modes to expect

- **`sync` says it cannot find the deck.** It resolves through the `source:` line
  in the progress file. If the deck moved, edit that line.
- **Nothing due.** `status` prints the next due date; `--all` overrides.
- **The user answered but never clicked Download.** The blob is in the textarea on
  the result screen - have them paste it, then `quizctl.py record`.
