---
name: pd-slides-plus
description: pd-slides, served from a local web server instead of opened as a file - which
  makes four things possible that a file cannot do. Diagrams are live Excalidraw canvases
  that autosave as real .excalidraw files in the repo. A running dev server can be framed
  inside a slide, so the deck shows the product instead of a screenshot of it. A docked
  agent pane lets the reader talk to Claude from the page and Claude answer back. And
  comments, speaker notes and preferences survive a reload. Binds to the LAN so someone on
  another device can open the deck, with a token gating anything that writes to disk. Use
  when the user says "/pd-slides-plus", "pd slides plus", "serve the deck", "editable
  diagrams in the deck", "excalidraw in the slides", "embed the app in a slide", "chat with
  the agent from the deck", or wants a deck that can be edited and answered rather than
  only read.
---

# pd-slides-plus

Everything pd-slides cannot do traces to one fact: a `file://` page has no origin, so it
has no storage, no `fetch`, and no cross-frame access.

Put the same deck behind a local server and four things become possible at once.

```bash
python3 ~/.claude/skills/pd-slides-plus/scripts/pdplus.py serve <deck.md> [paper.md]
```

**The renderer is not forked.** This is `--plus` on the same `mdview.py` pd-slides uses, so
every fix to the slide stage, the paper pairing, the comment rail or the narration lands in
both skills at once. What is forked is the skill: pd-slides stays a file you can email.

**Requires two sibling skills to be installed**, because it runs their code, not copies of
it: `pd-slides` (narration, via `scripts/pdnarrate.py`) and `browser-preview` (the renderer
itself, via `scripts/mdview.py`). Without both under `~/.claude/skills/`, `pdplus.py` fails
on import.

Read the [pd-slides SKILL](../pd-slides/SKILL.md) first - the deck format, the paper
contract, the component vocabulary, the narration and the presenter window are all
unchanged and are documented there. This file covers only what the server adds.

## Editable diagrams

A fenced `draw` block becomes a live Excalidraw canvas, in either pane.

````markdown
```draw pipeline
```
````

Edits autosave 700ms after you stop drawing, to `diagrams/pipeline.excalidraw` - a real
file that opens in excalidraw.com like any other. **The file is the source of truth and the
deck is one editor for it**, which is the opposite of a diagram exported into a slide and
stale by the time anyone argues with it.

`--scenes <dir>` moves where they live. Excalidraw and React are vendored in `assets/`
(4.3MB), not loaded from a CDN, so this works on a plane.

## The app in the slide

````markdown
```app http://localhost:3000 520
```
````

Frames a URL - your running dev server, a dashboard, anything - with a Reload button for
when you have just rebuilt it, and an open-in-a-tab link. The trailing number is the height
in pixels, default 520.

This is the one feature that is *impossible* in pd-slides rather than merely awkward: a
`file://` page cannot frame `http://localhost` at all.

## The agent pane

`g` docks a chat panel on the right. You type; it lands in `.pdplus/chat.jsonl` with the
slide you were on. Claude reads it and answers back into the page.

```bash
pdplus.py poll                    # blocks until the reader says something unread
pdplus.py say "on it - one sec"   # replies into the page
```

`poll` reads the log, not the socket, so it survives the server restarting, and its read
position is a **cursor on disk** rather than "everything from now" - a message sent between
two polls is never dropped. `--since 0` replays the whole thread.

The messages carry which slide the reader was on, so "this one is too dense" is a complete
sentence.

## What now persists

`http://localhost` is a secure context and a real origin, so on top of the above:

- **Speaker notes write back to `deck.md`** as `:::notes` blocks when the tab closes. No
  more copy-out. The file is reassembled byte-identical apart from the note blocks.
- The clipboard API works properly instead of falling back to `execCommand`.
- `localStorage` is available, so preferences survive a reload.

## On the network

The server binds to `0.0.0.0` and prints two URLs - `localhost` and your LAN address - so
someone on another device can open the deck, comment on it, and talk to the agent.

Reads are open to the network. **Anything that writes to the filesystem** - saving a scene,
writing notes back to `deck.md` - **requires the token in the URL**, so being on the wifi is
not the same as being allowed to edit the repo. The token is fresh per run and printed once.

## Demo

```bash
cd ~/.claude/skills/pd-slides-plus/demo
python3 ~/.claude/skills/pd-slides-plus/scripts/pdplus.py serve deck.md paper.md
```

Ten slides: the eight from pd-slides plus a live Excalidraw canvas and an app frame - which
frames the deck's own server, the cheapest possible proof that it works.

Add `--narrate` to build the audio track too (first run speaks ~44 clips, then caches).

## Not built

- No auth beyond the write token, no TLS. This is a tool for your own machine and your own
  network, not a deployment.
- The agent side is a CLI the agent drives. There is no daemon watching for you.
- Scenes are per-name, not per-slide. Two `draw pipeline` fences are the same canvas, which
  is a feature when you want the diagram in both panes and a surprise otherwise.
- No conflict handling: two people drawing on one scene, last write wins.
