---
name: quiz-me
description: Turn anything just discussed - a codebase subsystem, a doc, an architecture decision, a set of notes - into an interactive multiple-choice quiz that opens in the browser and gauges intuition rather than recall. Each question carries a 1-5 difficulty and asks how confident you were BEFORE revealing the answer, so the result separates "knew it" from "guessed right" and calls out confidently-wrong specifically. Use when the user says "quiz me", "/quiz-me", "test my intuition", "do I actually understand this", "make a quiz on X", "check if I got that". For spaced repetition across sessions with progress kept on disk, use quiz-me-full instead.
---

# quiz-me

One-shot quiz. Write a deck, render it, open it. Nothing is saved.

`quiz-me-full` is the sibling that adds spaced repetition, a progress file, and
an adaptive difficulty ladder - it calls the exact scripts in this skill to do
the rendering, so improve the UI here and both get it.

## The two steps

**1. Write a deck file.** Markdown, one file, no scaffolding:

```markdown
# Deck: HTTP Caching
id: http-caching

## Why does `Cache-Control: no-store` exist when `no-cache` already does? [2]
- [ ] They are synonyms
- [ ] `no-cache` forbids storage; `no-store` forbids reuse
- [x] `no-cache` allows storage but forces revalidation; `no-store` forbids storage
> `no-cache` is a revalidation rule, not a storage ban - the response may sit on
> disk as long as it is re-checked before reuse. `no-store` is the one that keeps
> it off disk, which is what you want for anything sensitive.
@ RFC 9111 §5.2.2
```

`[2]` is difficulty 1-5 (default 3). `- [x]` is the correct option. `>` lines are
the explanation shown after answering. `@` is the citation. That is the format.

**2. Render it.**

```bash
python3 ~/.claude/skills/quiz-me/scripts/render.py <deck.md>
python3 ~/.claude/skills/quiz-me/scripts/render.py <deck.md> --cards 3,7,9
```

It writes a self-contained HTML file and opens it. No server, no dependencies.

## Writing questions that actually gauge intuition

### The one rule that matters most: never test what grep answers

**Do not ask where something lives.** "Which file holds the `Skill` model?", "which
module imports this?", "what is this function called?" - all worthless. A reader
recovers any of that in seconds, so testing it measures lookup speed, not
understanding, and knowing it confers nothing.

Ask instead what a person **cannot** recover by grepping:

| Weak card | Strong card |
|---|---|
| Where does the ORM model live? | What is `core/` for, as distinct from `data/`? |
| Which function is in this module? | Why does this module exist at all? |
| What is this file called? | What is this doc for - who reads it and when? |
| Which line sets this flag? | How does the mirror actually work, end to end? |
| What is the default value? | What factors feed the recommendation ranking? |

If a card can be answered by someone who has never thought about the system but is
fast with a search box, cut it.

### The five rungs

1. **Purpose** - why does this exist at all; what would be worse without it
2. **Mechanism** - how does it work end to end; what calls what, in order
3. **Factors** - what feeds a decision, and what deliberately does not
4. **Consequence** - what breaks, and what the trade-off buys
5. **Design** - a concrete proposed change, and what is wrong with it

The best single question to build a deck around is **"how does X actually work?"**
for each major subsystem. The second best is **"what is the point of Y?"** - and Y
can be a doc, a convention, or a process, not only code.

### What to mine for

- **Where the plausible answer fails.** "Which store loses the bytes on unpublish?"
  Everyone says all of them. Only one does.
- **The reason behind a rule**, not the rule. Anyone can read the rule.
- **Blast radius.** "You delete X tomorrow - what breaks?" This separates knowing the
  diagram from understanding it.
- **Duplication and drift.** Anything stored twice, and which copy wins on read.
- **Absences that carry meaning** - a gate that is deliberately soft, a table that was
  dropped, a check that is deliberately missing. Not "this column does not exist", but
  "why was it removed".

### Rules that keep a deck honest

- **Every explanation carries a citation** (`@ file.py:120`, an ADR, a doc section).
  A wrong answer has to be falsifiable, or the quiz is just your opinion.
- **Cite from the code you actually read**, not from the docs alone. Docs go stale;
  a `file:line` is checkable in seconds.
- **Distractors must be things a reasonable person would believe.** Four options where
  three are obviously silly tests nothing.
- **The explanation must teach**, not just confirm. A reader who missed the card should
  come away with the model, not just the answer.
- **Spread the difficulty.** All-hard is demoralizing, all-easy is flattering.
- **12-16 cards per deck** unless it is a reference deck built for repetition.

## What the result screen reports

- Score, and accuracy broken out **by stated confidence**.
- A calibration read - the interesting output. Confidently-wrong answers are named
  separately because they are the expensive ones: a confident wrong model is what
  gets designed against. Lucky guesses are named too, in the other direction.
- Every missed question repeated with its explanation and citation.

## Where things go

Rendered HTML lands in `~/Desktop/quiz-progress/.rendered/`. Decks are conventionally
kept in `~/Desktop/quiz-progress/decks/`, but `render.py` takes any path.

## Files

| Path | What |
|---|---|
| `scripts/deck.py` | Deck parser + the 5-level ladder. Run it directly for a self-check. |
| `scripts/render.py` | Deck -> self-contained HTML, opens it. The only entry point. |
| `scripts/template.html` | The UI. Placeholders: `__CONFIG__`, `__CARDS__`, `__LEVELS__`. |

The template renders both modes. `quiz-me-full` passes `scheduled: true` plus
per-card interval previews; without those it is a plain quiz. **The scheduler is
never implemented in JavaScript** - Python ships six pre-computed outcome strings
per card so the two cannot drift.
