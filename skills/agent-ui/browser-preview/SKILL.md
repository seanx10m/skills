---
name: browser-preview
description: Render Markdown docs (with Mermaid diagrams + tables) to a self-contained HTML preview and open it in the browser. Folder mode adds a file-explorer sidebar. Pages support select-to-comment in a margin rail (Copy notes / Copy md / Copy md + notes), toggles, and a one-word-at-a-time speed reader (key r). An optional global MODE auto-opens every .md Claude writes via a PostToolUse hook. Use when the user invokes /browser-preview, says "browser preview on/off", "auto preview on", or for a one-off says "preview this", "open this in browser", "preview this folder", "speed read this", "set my reading speed".
---

# browser-preview

Renders Markdown to a self-contained HTML preview and opens it in the browser -
the place graphical Mermaid + full Markdown (tables, code, headings) render properly
while you stay in the terminal chat.

Two distinct actions:

| Action | What | Sticky? |
|---|---|---|
| **MODE** (auto) | ON -> every `.md` Claude writes auto-opens in the browser (needs the optional hook below) | yes, global until off |
| **ONE-OFF** ("preview this") | render+open a single doc or folder now, mode unchanged | no, fires once |

```
browser-preview/
├── SKILL.md
├── README.md
├── references/
│   └── rsvp-research.md    why every speed-reader number is what it is
├── scripts/
│   ├── mdview.py            the renderer (Python 3, stdlib only)
│   ├── browserpreview.sh    control: on | off | toggle | status | wpm | open | live | listen
│   ├── post-write-hook.sh   optional PostToolUse hook: render + open-once when MODE on
│   ├── prune-old.sh         rolling 2-day cleanup of old previews / markers
│   └── test_*.mjs, test_slides.py   self-checks (jsdom needed for the .mjs ones)
└── state/                   created on first use
    ├── preview-on           global flag (presence = MODE ON)
    ├── speedread-wpm        the user's default reading speed (absent = 250)
    └── opened/              per-file markers so each file opens once
```

Renderer: `scripts/mdview.py` - self-contained HTML (Markdown embedded, NO server,
NO file:// fetch), strips YAML frontmatter, Mermaid/marked/highlight.js from CDN.
Header: Claude mark + "CLAUDE CODE" kicker + doc title; right side has repo/branch badges.
Light/dark theme follows the OS.

## Handling requests

```bash
bash ~/.claude/skills/browser-preview/scripts/browserpreview.sh <command>
```

| User says | Command |
|---|---|
| "browser preview on" / "auto preview on" | `on` |
| "browser preview off" / "stop auto preview" | `off` |
| "toggle browser preview" | `toggle` |
| "is it on?" | `status` |
| **"preview this"** / "open this in browser" / "preview X.md" (ONE-OFF) | `open <file.md>` |
| **"preview this folder"** / "explore this folder in browser" (ONE-OFF) | `open <folder>` |
| **"live"** / "editable diagrams" / "excalidraw this doc" | `live <file.md\|folder>` |
| **any preview opened to collect feedback** - a test list, a review, "comment on this" | `live <file.md>` in the background + Monitor `listen <file.md>` (see below) |
| "set my reading speed to 500" / "speed reader default" | `wpm 500` (or `wpm rec` to go back to 250) |

**Default to folder mode for anything multi-file.** When the target has sibling or
child `.md` files - a **skill** (a `SKILL.md` with a `references/` folder), a docs
directory, an ADR set, any `.md` that sits next to related `.md`s - `open` the
**containing folder**, not the single file, so the sidebar shows the whole set. A
lone `.md` with no `.md` siblings opens single-file. "preview this skill",
"show me this skill", "read this doc" over a folder-resident file -> folder mode
by default. Only open the bare file when the user explicitly wants just that one file.

For a one-off "preview this" with no filename, render the **most recent `.md` Claude
just wrote/edited** in this conversation (apply the folder-default rule: if it lives
among sibling `.md`s, open its folder). Report the one-line status back.

## Collecting feedback - live mode + listen (optional)

**Optional - needs a live-server script that is not bundled.** Set `BP_LIVE_SERVER=/path/to/server.py` (it must accept `serve <file> --doc` and `listen <file>`); without it `live` and `listen` exit with a message and `open` is the only path.

When a preview is opened so the user can give feedback on it - a test list, a review - and a live server is configured, prefer live mode over `open`.
Live mode is served over http, so every comment is written to disk the moment it is posted and the agent can hear it.

```bash
bash ~/.claude/skills/browser-preview/scripts/browserpreview.sh live notes.md     # run_in_background - it blocks
bash ~/.claude/skills/browser-preview/scripts/browserpreview.sh listen notes.md   # Monitor this: one line per comment
```

- **On disk, as the user comments**, next to the doc:
  - `notes.notes.md` - the doc plus a `## Notes` section, exactly what Copy md + notes gives. The file to read when they say they are done.
  - `notes.notes.jsonl` - append-only, one event per comment, reply or delete (`{ts, type, file, label, line, quote, text, files}`).
  - A folder's go beside the folder (`docs.notes.md`), never inside it.
- **`listen`** follows the jsonl and prints one line per event, e.g. `comment L42 "the sentence" > fix this wording`, plus ` [attached: /abs/path]` per file.
  Start it under the **Monitor** tool so each comment wakes you, and act on (or acknowledge) feedback while they are still testing.
  It reads the file, not the server, so it can start first and survives a server restart; `--all` replays existing comments.
- The header badge reads **Live** while the server takes every change, **Not streaming** in red if it stops (the notes are still in the browser).
- Notes also come back from the server on reload, so a new port (new origin, empty localStorage) loses nothing.
- Use `open` (file://) only for read-only previews, or when the user explicitly asks for it.

## Live mode - editable diagrams (optional)

`live` serves the same page over http instead of opening it from `file://`. That one
change is what makes every ```` ```mermaid ```` fence an **editable Excalidraw canvas**
instead of a rendered image - the page has an origin, so it can write to disk.

```bash
bash ~/.claude/skills/browser-preview/scripts/browserpreview.sh live notes.md
```

Scenes autosave 700ms after you stop drawing to `./diagrams/<doc>-d<n>.excalidraw` -
real files that open in excalidraw.com. `Reseed` rebuilds one from the doc's mermaid,
discarding edits. Blocks the shell; run it in the background and hand over the URL.

**Getting edits back out - same three buttons as comments:**

| In the page | Gives you |
|---|---|
| **Copy** on a canvas header | just that diagram, as a ```` ```mermaid ```` fence |
| **Copy md** (`m`) | the whole doc, every canvas swapped for how it looks **now** |
| **Copy md + notes** (`b`) | that, plus the margin comments - one paste, whole review |

The fence keeps its scene name (```` ```mermaid architecture-d1 ````), so pasting it
back into the source and re-serving lands on the same canvas instead of a new one.

**From the terminal instead**, don't read the `.excalidraw` JSON (it is ~1KB per shape);
summarize it with a script of your own or ask the user to paste the diagram back.

The live server is the same renderer served over http, not a fork.

## Speed reader

Every page carries a classic RSVP speed reader - one word at a time, fixed at the pivot
letter so the eye never moves. **Speed read** in the header, or `r`.

**Speed.** The slider defaults to *the user's own preference*: whatever they last
dragged it to in this browser, else the saved default in `state/speedread-wpm`
(`browserpreview.sh wpm <n>`, `wpm rec` to clear), else **250 wpm**.
Two presets sit under the slider: **250 reading** and **400 fast pass**.
250 is where the evidence sits - average adult silent reading is 238-260 wpm
(Brysbaert 2019, n=18,573), Spritz's own SDK shipped 250, and given a pause button
readers self-selected 209 (Benedetto 2015).
400 is roughly 1.6x a natural rate, which is a fast pass over a document rather than
primary reading, and it is labelled as such.
Do not put a speed-with-comprehension claim in this UI: every vendor claim in this space
that has been tested has failed.

**Timing follows Spritz's own patent** (US 8,903,174 B2), not the open-source clones.
Word time is length only - 1-7 characters 1x, 8-13 1.3x, over 13 1.6x, punctuation not
counted. Pauses are real blank frames between words. The good idea nobody copied is
FIG. 5b: the pause after a sentence scales with how long that sentence was (1.1x under
12 words, 2.2x to 22, 3.3x beyond), so a long sentence buys real recovery. `Mr.`, `3.14`
and a `1.` list marker do not count as sentence ends. Words over 13 characters split at
a hyphen, else into `ceil(len/8)` parts with a `-` continuation mark.

**The pivot letter** is the ORP, at 1 -> 0, 2-5 -> 1, 6-9 -> 2, 10-13 -> 3, 14+ -> 4 on
the punctuation-stripped word - Spritz's TABLE I, which OpenSpritz, jetzt and speedread
all independently guessed right. It is red (`#CC0001`), cool blue on dark the way jetzt
swaps it. The pivot column sits at **30% of the frame, not centre**, because a word hangs
mostly to the right of its ORP. A zero-width centre cell with the glyph centred over it is
what stops the column jittering, so the font can be proportional rather than monospace.

**Diagrams pause the stream.** A mermaid diagram, table, image or code block is a picture,
not a sentence - streaming it one token at a time is nonsense. The reader stops, shows the
whole thing scaled to fit, runs a dwell bar sized to how much is in it (2.6s to 14s), then
resumes. Space skips ahead immediately. **No other RSVP reader does this** - they either
exclude non-prose from the DOM walk or stream a table's cells as if they were a sentence.

**The continue line.** The exact word being read is underlined in the document itself, so
you can look away from the stream, find your place and read on with your eyes. Click any
word in the page and the stream jumps there. Pause and the line goes dashed; close and
reopen with `r` and it resumes from that word. The context strip under the word fades
while playing, because anything legible there pulls the eye off the pivot column.

| Control | Key |
|---|---|
| Play / pause | `space` |
| Step one word | `←` `→` |
| Back to the start of the sentence | `shift`+`←` |
| Speed ±25 wpm | `↑` `↓` |
| Full screen ↔ half screen | `f` |
| Move the half panel - bottom / right / left / top | `d` |
| Close | `esc` |

**Full screen** takes the viewport. **Half screen** takes half of it and docks to any
edge, so the rendered doc stays visible next to the stream. Both the mode and the dock
edge are remembered per browser.

## In-page features

- **Toggles (progressive disclosure):** write a raw `<details><summary>The claim</summary>` line, a blank line, the Markdown body (tables, lists, mermaid, nested toggles all render), a blank line, then `</details>`.
  The blank lines are what let the inner Markdown render; without them marked swallows the body as raw HTML.
  They draw Notion-style: a small chevron in a fixed gutter turns 90 degrees on open, the summary text is the row, hover tints it, and an open toggle's body hangs off one quiet left rule.
  An **Open toggles / Close toggles** header button appears when the doc has any.
  Comments work inside an opened toggle, and clicking a card anchored inside a closed one opens it.
  Mermaid inside a closed toggle renders the first time it opens (it cannot measure a hidden node), and the speed reader reads a closed toggle as its summary line only.
  Summaries are raw HTML, so write `<code>x</code>` there, not backticks.
  Guarded by `scripts/test_toggles.mjs`.

- **Margin comments (Google Docs layout):** select text (drag, or double-click a word) inside
  any rendered block and a comment card opens in the **right margin rail** on mouse-up. Every
  thread stays visible as a card in that rail - no pins, nothing to click open. The commented
  text is highlighted amber; clicking a highlight focuses its card, clicking a card highlights
  its text, and cards stack downward when their anchors collide.
  The highlight covers **exactly the words you selected**, not the block they sit in.
  Threads anchor to `{file, line, lineEnd}` for card placement - the source line(s) the selection
  touched - plus per-block character offsets for the highlight itself, and each one **also stores the selected text**,
  shown as a quote on the card. So **Copy Notes** (header button) reads:

  ```
  L42 "the sentence you highlighted"
    > fix this wording
  ```

  Quote + note, not a bare line pointer and not a context dump. Line position is an
  approximation (mapped from the selection's on-screen position within its block), good enough
  to relocate a comment, not a byte-exact source pointer.
  Each selection is its own comment, the way Google Docs works: two highlights in the same
  paragraph are two cards, ordered by where their words sit. Only re-selecting text that
  overlaps an existing highlight opens that thread to reply. The reply box only appears on the card you're working in; **Cmd/Ctrl+Enter posts**,
  Esc discards a draft, `×` deletes a comment (or the whole thread from the card header).
- **Comments survive a crash, a closed tab and a browser restart.**
  Every change (add, reply, delete, collapse) autosaves to `localStorage` at once, and the page restores it on load.
  The key is `bp.notes:<absolute source path>`, because Chrome gives every file:// page one shared origin and the path is all that keeps two docs apart.
  Folder mode keys each file as `<folder>/<relpath>`, which is the same absolute path, so a single-file render and a folder render of one file share notes.
  On load each thread re-anchors from its stored block offsets while the doc is unchanged (a per-thread fingerprint of the source says so).
  When the doc changed, the thread re-finds its stored quote, whitespace-insensitive, nearest its old line.
  A quote that is gone stays as an **orphan** card pinned at the top of the rail (dashed border), and Copy notes marks it `[text not found in current version]`.
  Nothing is ever dropped.
  - **The disk copy**, so clearing the browser can't lose them either, is `bp-notes-<doc>.json` (threads, for Restore) plus `bp-notes-<doc>.md` (the doc + `## Notes`, what Copy md + notes gives - the recovery file an agent can just read).
    In live mode the server writes `<doc>.notes.md` instead, on every comment (see Collecting feedback):
    - **Default:** a download into the same folder as attachments (`~/Downloads` unless Chrome's Default profile says otherwise), when the tab hides or closes and every 30s while there are unsaved changes.
      Chrome never overwrites a download, so a repeat lands as `bp-notes-<doc> (1).json` - the highest number is newest.
      That cost is why it does not fire on every change.
    - **Better, one click:** click **Saved** in the header and pick a folder.
      The File System Access API works on file:// in Chrome (it counts as a secure context), so the page then rewrites the two files in that folder in place about 3s after each change, silently, no copies.
      The folder handle lives in IndexedDB; after a reload Chrome re-asks for write access on your first click unless you chose "Allow on every visit".
  - **Saved** in the header confirms the autosave; hover it for the save time and the disk path.
    It reads **Not saved** in red if the browser blocks storage (copy notes out then).
  - **Saved** and **Restore** (the circular arrow) share one pill in the header.
  - **Restore** loads any `bp-notes-*.json` back in.
    It merges and skips threads already present, so restoring twice is harmless; notes from a doc that moved still land when the file holds one doc or the relative path matches.
- **Collapse a comment:** the chevron at the left of a card's header folds that one thread to a
  single line showing a snippet of its first comment. Click the chevron again, or anywhere on the
  folded card, to expand it. Folding is view-only - collapsed threads still go out with Copy notes.
  **Collapse all** (`x`, header, shown once a thread exists) folds every thread; with all folded it
  reads **Expand all** and opens them back up.
- **Attachments on comments:** paste (Cmd+V) or drop any file - screenshot, PDF, anything - into a
  comment or reply box, or drop it on the card.
  The page downloads it at once to Chrome's download folder as `bp-<stamp>-<n>-<name>` (folder read
  from Chrome's Default profile prefs at render time, else `~/Downloads`), and the note carries the
  absolute path, so Copy notes / Copy md + notes emit `[attached: /abs/path]` under the comment.
  One paste hands Claude every file by reference; the clipboard can't carry the bytes alongside text.
  Click an image chip to copy the image itself, any other chip to copy its path.
  Several files in one paste/drop trips Chrome's one-time "download multiple files" prompt - Allow it
  once (all file:// previews share that permission). Headless Chrome silently denies all but the first.
- **Three copy buttons** (header) + single-key shortcuts, all clipboard:
  - **Copy notes** (`c`) - the pointer list of all comments, across every file in folder mode.
  - **Copy md** (`m`) - the raw source of the *current* doc (active file in folder mode).
  - **Copy md + notes** (`b`, "both") - the current doc's source with a `## Notes` section of
    its comments appended. This is the paste-back-to-Claude workhorse: doc + your anchored edits
    in one shot. Shortcuts are ignored while typing in a comment card.
- **Header at any width:** the title always keeps room and ellipsizes; the button cluster keeps its natural size and scrolls sideways (no bar) when the window is narrow.
  Below 1500px, Collapse all, Speed read and Reader mode go icon-only (tooltips keep their names and keys).
- **Folder mode:** `mdview.py <folder>` (or `open <folder>` above) walks the folder for
  every `.md`/`.markdown`/`.mdx` file (skips `.git`, `node_modules`, `.previews`, dotdirs),
  embeds them all in one page, and adds a left sidebar to switch files without re-running
  the tool. Single-file runs are unchanged (no sidebar shown). Output path mirrors single-file
  naming: `<folder path> + .preview.html`, written as a sibling of the folder, never inside it.

## Mechanics

- **MODE trigger:** PostToolUse hook matching `Write|Edit|MultiEdit`. Bails unless the flag
  exists and the file is `*.md|*.markdown|*.mdx`. Renders to `<repo-root>/scratch/.previews/`
  (NOT next to the source), opens the browser once per path (marker in `state/opened/`);
  later edits re-render silently (manual Cmd-R - "render once" model).
- **Output location:** preview HTML always lands in `<repo-root>/scratch/.previews/`, named by
  the source's path relative to the repo root with `/` -> `__` so same-named files in different
  dirs don't collide (`docs/adr/x.md` -> `docs__adr__x.preview.html`). Repo root is the git
  toplevel of the source file, falling back to the file's own dir when not in a repo. This
  keeps build artifacts out of the source tree entirely.
- **ONE-OFF:** `browserpreview.sh open <file.md>` (or `python3 scripts/mdview.py
  <file.md>`) renders + opens immediately, regardless of MODE, without flipping it. Same
  `scratch/.previews/` output location as the hook.

## Notes

- Previews live under `scratch/.previews/`; gitignore that one path instead of scattering
  `*.preview.html` across the tree (the old behavior).
- The hook ignores its own outputs, but skill/system `.md` writes under `~/.claude` will
  still trigger MODE if left on; that's expected.
- Needs internet for CDN scripts; doc text always renders (embedded), only
  diagram/table styling needs the CDN.

## Optional: install the auto-open MODE hook

MODE does nothing until `scripts/post-write-hook.sh` is registered as a PostToolUse hook.
Add this to `~/.claude/settings.json` (merge into any existing `hooks` block; requires `jq`):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          { "type": "command", "command": "bash ~/.claude/skills/browser-preview/scripts/post-write-hook.sh" }
        ]
      }
    ]
  }
}
```

Then `browserpreview.sh on` / `off` flips it.

## Optional: statusline badge

To show MODE in a custom statusline, have the statusline script run
`bash ~/.claude/skills/browser-preview/scripts/browserpreview.sh status` (prints `on` or `off`)
and render a badge when it prints `on`.
