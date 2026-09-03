---
# Machine defaults. pdnarrate.py reads these; a CLI flag still wins.
voice: Charon
style: an unhurried, confident reading voice - a colleague walking you through their own work, not an announcer
seed: 42
from: paper
subs: true
autoplay: false
# page-turn sound under the narration. A path, or `off`.
turn: default
turn_volume: 0.32
# converted diagrams (pd-slides-plus): normal = Helvetica, hand = Virgil, code = Cascadia
diagram_font: normal
---

# House style for pd-slides

Personalize this file. It is read before a deck is authored, and its frontmatter sets the narration defaults.
Drop a `pd-style.md` next to a `deck.md` to override it for one project - the nearest file wins, field by field.

## The division of labour

**The paper argues. The deck compresses. The narration reads the paper.**
Three artifacts, one act of writing: only the paper and the deck are authored, and the narration is the paper spoken.

Write the paper first, always.
A deck written first becomes a paper padded out to justify it, and it shows.

## The paper

One section per slide, in the deck's order. This is a contract, not a preference - it is what the split screen is built on.

Write it to be **read aloud**, because it will be.
Sentences a person can say in one breath. No sentence should need a re-read to parse.
Semicolons and parentheticals are where narration goes to die - use a full stop.

Numbers get spelled the way you would say them: "seventy-two stamp sites", not "72 stamp sites", unless the figure is the point and belongs in a table.

Every table, diagram, code block and image gets a `<!-- say: -->` bridge beneath it.
The bridge is not a caption - it says what the reader should *take* from the thing, in one sentence.
Bad: "The table shows lines saved per component."
Good: "A card row is five lines of markup instead of twenty-five - that difference is the whole reason the vocabulary exists."

## Speaker notes

**Leave them empty.** Do not write `:::notes` unless you are asked for them.

Notes are the speaker's scratchpad, not a thing to be authored on their behalf - the presenter window (`v`) opens straight into an editable pane so they can type their own, and pre-filling it with a guess at what someone wants to say is noise they then have to delete.

If they are asked for, they are prompts and not prose: what to slow down on, what to skip, what the room will push back on.

## The deck

**One claim per slide.** If a slide needs "and", it is two slides.

The heading is the claim, not the topic. "The interface is 117 names wide" beats "Interface analysis".

Use the free markup before reaching for components:
- a paragraph **above** the heading is the eyebrow - use it for the section or the stage ("Evidence", "Opportunity 3")
- a paragraph **after** the heading is the serif lede - use it for the one sentence that carries the slide

Then components, in rough order of how often they earn their place:

| Want | Use |
|---|---|
| three or four parallel findings, each with a verdict | `:::cards` with `### Label \| strong` |
| a two-up comparison, before/after, ours/theirs | `:::cols` |
| the two or three numbers that anchor the argument | `:::stats` |
| the single sentence the slide exists to deliver | `:::deep` |
| an aside that would break the flow inline | `:::note` |

**Six lines of body text is the ceiling.** Past that it is a document, and the document is already on the right.

Never put a code block or a diagram inside a `:::` block - the expansion flattens line breaks. Diagrams go at slide level.

## Diagrams

`graph TD`, always. Never `graph LR` - subgraphs must stack vertically.
Ten boxes is the cap. An eleventh means the diagram is doing two jobs; split it.
Label the edges. An unlabelled arrow is a claim you did not make.

## Voice

Plain declaratives. Say the thing, then say why it is true.
Name the tradeoff you took and what it cost - a deck with no cost in it reads as a sales pitch.
No "leverage", "robust", "seamless", "unlock". No em dashes; use a plain dash.

## Narration

Default voice is `Charon` - informative, low, holds up over ten minutes.
`Sulafat` for warmer material, `Kore` when the content is hard news and should sound firm.

Paragraph is the floor on clip length. Do not split sentences into their own blocks to get tighter highlighting - each clip starts cold and it sounds it.
