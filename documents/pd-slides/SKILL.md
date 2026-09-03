---
name: pd-slides
description: Build a split-screen deck - slides on the left, the full source document
  ("the paper") on the right, with browser-preview's select-to-comment margin rail over
  the paper. Every slide owns a distinct section of the paper, which lights up as you
  move. Optionally the deck reads itself aloud - one Gemini TTS clip per paragraph of the
  paper, word for word, so the caption, the highlighted block and the slide advance
  together and nothing can drift. Ships a component vocabulary (:::cards, :::cols,
  :::stats, :::deep, :::note) so a dense slide costs a fraction of hand-styled markup.
  Use when the user says "/pd-slides", "pd slides", "make this a deck", "turn this spec
  into slides", "slideshow this", "deck with the paper under it", "narrate the deck",
  "read the paper aloud", "add subtitles", "audio summary of these slides", or wants to
  review a long document headline-first with the evidence one keystroke away.

---

# pd-slides

A deck compresses. A paper argues. Split the screen and you keep both.

**PD is progressive disclosure.** The deck is the headline layer, the paper is the evidence layer, and the pane is the disclosure: you read at whichever altitude the claim needs, one keystroke apart.

```bash
bash   ~/.claude/skills/pd-slides/scripts/pdslides.sh  <deck.md> [paper.md]   # silent
python3 ~/.claude/skills/pd-slides/scripts/pdnarrate.py <deck.md> [paper.md]  # + narration
```

Renders to `<repo-root>/scratch/.previews/<flat-name>.deck.html` and opens it. One-shot;
browser-preview's eyeball toggle is untouched.

- **Left** - the slide stage. Full-bleed, animated, keyboard-driven.
- **Right** - `paper.md`, rendered exactly as `browser-preview` would render it.
- **Both panes are commentable**, and neither reflows. Comments collapse behind a count
  pill in that pane's bottom-right corner and float over the content as an overlay when
  you open it. Selecting text opens it for you. (Plain `browser-preview` keeps its
  always-visible reserved-margin rail - this is deck behaviour only.)

The pane is **sticky**: it stays open as you move through the deck, and only the grip on
the divider (or `p`) closes it. Every slide owns a **distinct section** of the paper -
changing slides scrolls to it and lights it up, with the rest of the document dimmed
behind. `pdnarrate.py` reads the paper aloud on top of that - one clip per paragraph, captioned,
with the paragraph lit and the slides advancing themselves.

## See it first

```bash
python3 ~/.claude/skills/pd-slides/scripts/pdnarrate.py \
  ~/.claude/skills/pd-slides/demo/deck.md ~/.claude/skills/pd-slides/demo/paper.md
```

Eight slides, two diagrams, cards, cols, stats, tables and three bridge lines, narrated.
It is the skill arguing for its own four decisions, so it doubles as the worked example of every feature below.
First run speaks ~40 clips (a few minutes); after that it is cached and instant.

## House style

**Read `style.md` before authoring a deck.**
It is the opinionated part - what belongs on a slide, how the paper should be written given it will be read aloud, when each component earns its place, diagram rules, voice.
It ships with a foundation; personalize it and it holds across every deck.

Its YAML frontmatter also sets the narration defaults (`voice`, `style`, `seed`, `from`, `subs`, `autoplay`, `turn`, `turn_volume`), which `pdnarrate.py` reads.
Precedence, nearest wins: **CLI flag → `pd-style.md` beside the deck → the skill's `style.md` → built-in.**
Drop a `pd-style.md` next to a project's `deck.md` to override a field or two without touching the global one.

## Authoring

`deck.md` is plain Markdown split on `---`. Everything else is optional.

### Free, no markup

| You write | You get |
|---|---|
| a paragraph **above** the heading | the uppercase eyebrow label |
| a paragraph **after** the heading | the serif lede |
| a Markdown table | mono, tabular-aligned numerics, hairline rules |
| `:::notes` … `:::` | that slide's speaker notes (`n`), and its narration script unless `:::say` overrides |
| `:::say` … `:::` | the spoken line for this slide, when it should differ from the note |
| `:::paper` … `:::` | the paper heading this slide pins to, when the titles deliberately differ |

All four take a **one-line form** too - `:::say The line for this slide` or `:::paper What shipped` - with a trailing `:::` optional. A fence that matches nothing is dropped rather than printed at the reader, and a fence written inside a ``` code block is left alone, since that is someone documenting the syntax rather than using it.

### Components

Five blocks. They exist to cut agent output cost, not for tidiness - a hand-styled deck
measured **28% inline `style=` attributes by bytes**, and every one of those is a token.

````markdown
:::cards
### Opportunity 1 | strong
No module owns a finished Record
2 hydrators · 72 stamp sites · 12 card builders
### Opportunity 3 | worth exploring
The data/ interface is 117 names wide
50% single-caller · 19 exported and never called
:::

:::cols
### Scope walked
any markdown, one column per ###
### The deletion test
any markdown
:::

:::stats
56,475 | src/core/ | LOC
21,888 | src/api/ | LOC
:::

:::deep
the one sentence this slide exists to deliver
:::

:::note
a left-ruled aside
:::
````

`### Eyebrow | status` - the status word picks its own pill colour: `strong`/`good`/`solid`
are green, `warn`/`worth exploring`/`maybe` amber, `weak`/`bad`/`leak`/`risk` red.

**Raw HTML passes straight through.** The vocabulary is a floor on effort, not a ceiling
on layout.

### The paper

`paper.md` is an ordinary document - it renders exactly as `browser-preview` renders it, and reads standalone.

**Every slide owns a distinct section of it.**
The pane cuts the rendered paper at its `#`/`##`/`###` headings into sections, then allocates those sections across the deck once, up front.
Opening the pane is therefore never "somewhere in the paper" - it is always *this slide's* evidence.

That section also wears a **focus layer**: it lifts into a tinted card carrying a `Slide 4 / 12 · <title>` tag, and every other section dims back behind it.
Press `o` to drop the layer and read the paper as a plain document; the pairing and the scroll stay.

So: **write `paper.md` with one section per slide, in the deck's order.**
That is the contract the split screen is built on, and it is what you should generate when you write both files.
mdview prints a build-time warning when the paper has fewer sections than the deck has slides, because no matcher can make that one-to-one.

Pairing runs in three passes:

1. **`:::paper <heading>`** on a slide pins it to that heading outright, wherever it sits. Use it when a slide's title deliberately differs from its section's.
2. **Title matching**, three tiers most-confident-first - exact text, prefix either way, then significant-word containment (so "The vocabulary" finds "The component vocabulary") - scanned forward from the last section taken, over unclaimed sections only. A deck follows its paper's order, so order is a stronger signal than any single fuzzy hit judged alone.
3. **Gap fill** for whatever is left, in document order, wrapping to the earliest unclaimed section if a pin jumped ahead.

The result is total and collision-free: no two slides share a section while one is free, and no slide opens the pane onto nothing.
Only a paper with fewer sections than slides forces sharing, and then the tail shares the last one.

The old behaviour - per-slide fuzzy lookup, no match meaning no scroll - is gone.
Deciding slide 4's section in isolation is exactly what let two slides land on the same heading and a third land nowhere.
It is an allocation, so it is allocated.

Horizontal keys drive the deck, vertical keys read: `↓`/`↑` scroll the paper the moment it's open, with no click to focus it first.

Omit `paper.md` and the deck still works - the grip hides itself.

### Narration

A deck can read itself aloud. Two modes, one player.

```bash
python3 ~/.claude/skills/pd-slides/scripts/pdnarrate.py <deck.md> [paper.md] [--autoplay]
```

Use `pdnarrate.py` **instead of** `pdslides.sh` when the deck has audio.
Render and embed are one atomic step on purpose: the player lives in the generated HTML, not in the markdown, so a later plain `pdslides.sh` run silently wipes the track.
Same trap `rich-artifact` exists to close, deck-shaped.

**`--from paper` (the default when a paper is given) reads `paper.md` word for word.**
The paper is the script. Nothing is authored twice, and the narration cannot say something the document does not.

**Why verbatim is the cheap design, not the expensive one.**
Identical words mean there is nothing to align. One clip per *block* of the paper, and the clip boundary **is** the block boundary - so which clip is playing *is* the highlighted paragraph, *is* the caption, *is* which slide is up. No timestamps, no SRT, no forced alignment, and nothing that can drift out of sync however the deck is driven.

The slides follow for free. Each paper block knows its section, the allocator already maps section to slide, so reading across a section boundary advances the deck itself. One play button drives everything.

**Blocks that cannot be spoken** - tables, code, diagrams, images - are skipped. Give one words with an HTML comment, invisible in the rendered paper, sitting where you want it read:

```markdown
| Block | Lines | Saved |
|---|---|---|
| cards | 5 | 25 |

<!-- say: The table puts numbers on it - a card row is five lines instead of twenty five. -->
```

A bridge line lights the block above it, which is the thing it is standing in for. It is the only prose anyone writes twice, and only where prose genuinely cannot carry the point.

**`--from deck`** is the other mode: one clip per slide, scripted from each slide's `:::say` (falling back to its `:::notes`). A presenter talking over the deck rather than the document read aloud. Both modes emit the same cue shape, so the transport, the captions and the auto-advance were written once.

**A page turn** sounds when the deck advances *under narration* only - a keyboard pass through the deck stays silent, because there the slide change was your own action and does not need announcing. Set `turn:` in `style.md` to a path of your own, or `off`, and `turn_volume:` to change how loud it sits under the voice.

**In the deck.** `a` plays and pauses, `shift+A` toggles auto (plays straight through), `t` toggles captions. The transport shows time remaining for the whole track and a hairline progress bar under the deck's own. `--autoplay` starts on load - browsers block sound until the first click, so the play button pulses until then and retries on that gesture. `--no-subs` starts with captions off.

**Captions carry the word cursor**, the paper highlights per block. That split is deliberate: the paper is a commentable surface and the comment engine walks its text nodes, so wrapping words in it risks the rail. The captions are our own DOM and are free.

Clips are cached by `(text, voice, style, seed)` in `scratch/audio/`, so editing one paragraph re-speaks one paragraph. Flags: `-v` voice (default `Charon`; `Kore` firm, `Sulafat` warm, `Puck` upbeat), `-s` style, `--seed`, `--from`, `-o`, `--no-open`.

Requires `ffmpeg`/`ffprobe` and a Gemini key (`GEMINI_API_KEY` or `~/.gemini_api_key`).
A first run on a long paper is one TTS call per paragraph - sixty-odd for a 3,000-word document, cached after that. At 32k mono AAC ten minutes of audio adds roughly 3MB to the page.

## Keys

| Key | Does |
|---|---|
| `→` `←` `space` `PageUp/Dn` `Home` `End` | move through the deck |
| `↓` `↑` | scroll the paper when it's open, else the current slide |
| `p` | paper pane (sticky) |
| `o` | focus layer on the paper's matching section |
| `a` / `shift+A` | play or pause / toggle playing straight through |
| `t` | captions |
| `f` | paper full width |
| `n` | speaker notes drawer |
| `v` | presenter window |
| `s` | slide list sidebar |
| `Esc` | close notes, then full, then the pane |
| `c` / `m` / `b` | copy notes / copy paper md / copy md + notes |

## Presenting it

Two ways to put this in front of people, and the first one is usually better.

**Send it.** The file is self-contained. They press `a` and get the same walkthrough at their own pace, with the evidence beside every claim and a comment rail to argue back in. That beats a live read, and it is what the narration is for.

**Talk over it.** `v` opens a **presenter window** - this slide's notes, what is coming next, and an elapsed timer. Share the deck window; keep the presenter one on your own screen. Arrow keys work in either window, so you never have to click back into the shared one to advance, which is the click the room sees.

**The notes pane is editable** - it is the one surface here that belongs to the speaker, so it opens as a scratchpad you type straight into. Edits write back into the deck, so the `n` drawer shows them too.

They live in the window only, like the comment rail, because `file://` has nothing to persist to. **Copy all notes** emits every slide's notes as `:::notes` blocks ready to paste back into `deck.md`. Do that before you close it.

`:::notes` seeds the pane if a slide has any. **Decks ship with none by default** - notes are the speaker's, and pre-writing them is noise someone has to delete. Ask for them explicitly.

Two things worth knowing. The window is opened blank and written into rather than navigated to a URL, because `file://` kills `BroadcastChannel`, `localStorage` and cross-file access - a blank child inherits its opener's origin, so the deck just mutates its DOM directly. And you will need to allow pop-ups for the page once.

Closing the deck closes the presenter window with it.

## Relationship to browser-preview

pd-slides ships **no renderer**. Deck mode is `--deck` / `--paper` on
`browser-preview/scripts/mdview.py`, so it requires that skill installed.

The decision that made this cheap: `main` / `#doc` holds the **paper**, not the slides.
The paper pane therefore *is* an ordinary browser-preview document, and the comment engine
- selection spans, line tagging, rail collision layout, the copy serialisers - needed
zero changes to work in it. The only edit was one line correcting the rail's coordinate
origin so cards stay pinned when the pane scrolls itself instead of the window.

A deck signs itself in the **bottom-left corner** - the same signature pill browser-preview
puts bottom-right, pointing at this skill's record. Deck-only; plain previews are
unchanged. The `×` beside it dismisses it for the session - `file://` has no
`localStorage` to remember the choice in, so it comes back on reload.

## Comments

Both panes are surfaces. A "surface" is one commentable pane: line-tagged blocks plus the
rail its cards live in. Normal browser-preview has exactly one; a deck has two, and the
slide surface re-homes its single rail into whichever slide is showing so cards scroll
with that slide's text.

Both rails are **overlays**, not margins: a pane's layout is identical whether it has zero
comments or ten. Collapsed, each is a pill in its pane's corner showing the count; open,
the cards float above the content at their anchors. A pill hides itself when its pane has
nothing on it, and the paper's pill is pinned to the pane rather than the document, so it
stays put as you scroll.

This is the one place deck mode diverges from `browser-preview`, which keeps its
always-visible reserved-margin rail. A full-width document can afford the margin; two
panes side by side cannot.

Threads are keyed by surface, and `Copy notes` (`c`) labels them, so a paste back to
Claude reads:

```
Slide 4 · The vocabulary:
  L12 "five block components"
    > make it four, cols and cards overlap
paper.md:
  L88 "index pairing was rejected"
    > say why in one more sentence
```

`m` and `b` copy the **paper's** source (with its notes, for `b`); slide feedback travels
via `c`, where the quote does the work.

## When not to use this

pd-slides makes a **review surface**: paced, commentable, with the source document one
keystroke away. It is not a motion-design tool.

If the ask is a rendered **video** or heavy motion graphics, route to
`/hyperframes` instead - it owns animation, and its `slideshow` skill owns presenter decks
with fragment reveals and branching. Going that way trades away the comment rail and the
paper pane, which is the whole point of this skill, so only do it when the deliverable is
genuinely a video or a performance rather than a review.

Motion here is deliberately small and structural. Slides **travel** rather than crossfade -
two full slides dissolving through each other reads as a flicker however long you make it,
so the incoming slide enters from the direction you moved and its blocks stagger up behind
it. The paper pane animates its flex-basis (you cannot transition `display`), holding the
document at a fixed width for the whole reveal so the pane uncovers it instead of
reflowing prose on every frame. `prefers-reduced-motion` collapses all of it.

That is the amount of motion a review tool should have.

## Not built

- No PDF export, no presenter window, no drag-resize on the divider (three states: closed,
  split, full).
- A `<pre>` authored **inside** a `:::` component block loses its line breaks - the
  expansion is flattened to keep slide comment line numbers true to `deck.md`. Put code
  blocks outside component blocks.
- Comments live only in the open tab - copy them out with `c` or `b` before closing.
- `style.md` frontmatter is read by a six-line parser, not a YAML library: flat `key: value` only, no nesting or lists. The body is prose for the author and is never parsed.
- Narration has no scrubber and no speed control - it is a listen-through, not an editor. Move with the slide keys.
- The caption's word cursor is **estimated** (duration spread by character count), because Gemini TTS returns no word timings. It drifts a little inside a long paragraph and re-syncs hard at every block. Real per-word timing needs a timestamping ASR pass.
- Paragraph is the floor on clip length. Sentence-by-sentence TTS sounds choppy - every clip starts cold.
- A paper with fewer sections than the deck has slides makes the tail share one; the build warns, the fix is a heading.
