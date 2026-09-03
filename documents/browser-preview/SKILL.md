---
name: browser-preview
description: Render Markdown docs (with Mermaid diagrams + tables) to a branded HTML
  preview in the browser. Two ways - a sticky global MODE (eyeball statusline toggle,
  every .md Claude writes auto-opens) and a ONE-OFF "preview this" verb (render+open
  a doc, or - the default for anything multi-file like a skill or a docs dir - a whole
  folder with a file-explorer sidebar, mode unchanged). Pages support select-to-comment
  in a Google-Docs-style right margin rail (cards always visible, quoting the highlighted
  text, Cmd/Ctrl+Enter to post, with Copy notes / Copy md / Copy md + notes buttons
  and c/m/b shortcuts) and, in folder mode, a sidebar to explore multiple files. Use
  when the user invokes /browser-preview, says "browser preview on/off", "auto preview
  on", "turn on the eyeball", OR for a one-off says "preview this", "open this in
  browser", "show that doc in the browser", "preview that file", "preview this folder",
  "explore this folder in browser".

---

# browser-preview

Renders Markdown to a self-contained, branded HTML preview and opens it in the browser —
the only place graphical Mermaid + full Markdown (tables, code, headings) render properly
while you stay in the terminal chat (the Claude Code TUI strips inline images).

Two distinct actions, mirroring talk-to-me's toggle + one-off `say`:

| Action | What | Sticky? | Analogy |
|---|---|---|---|
| **MODE** (auto) | ON → every `.md` Claude writes auto-opens in browser | yes, global until off | talk-to-me / caveman toggle |
| **ONE-OFF** ("preview this") | render+open a single doc now, mode unchanged | no, fires once | talk-to-me's `say <text>` |

Surfaced as an eyeball (👁) on/off badge in the statusline (next to the talk-to-me and caveman badges).

```
browser-preview/
├── SKILL.md
├── assets/                 all header/badge art, so an install is self-contained
│   ├── panel-icon.png      Claude mark (header, left)
│   ├── brand-logo.png      brand mark (header, right)
│   └── badge-icon.png        the bottom-right signature badge
├── scripts/
│   ├── browserpreview.sh    control: on | off | toggle | status | open <file.md>
│   └── post-write-hook.sh   PostToolUse(Write|Edit|MultiEdit) — render + open-once when MODE on
└── state/
    ├── preview-on           global flag (presence = MODE ON)
    └── opened/              per-file markers so each file opens once per run
```

Renderer: `~/.claude/scripts/mdview.py` — self-contained HTML (Markdown embedded, NO
server, NO file:// fetch), strips YAML frontmatter, Mermaid/marked/highlight.js from CDN.
Header: real Claude mark (`talk-to-me/assets/panel-icon.png`, left) + "CLAUDE CODE" kicker
+ doc title; right side has repo/branch badges + brand logo. brand light theme.

## Handling requests

```bash
bash ~/.claude/skills/browser-preview/scripts/browserpreview.sh <command>
```

| User says | Command |
|---|---|
| "browser preview on" / "auto preview on" / "eyeball on" | `on` |
| "browser preview off" / "stop auto preview" | `off` |
| "toggle browser preview" | `toggle` |
| "is it on?" | `status` |
| **"preview this"** / "open this in browser" / "preview X.md" (ONE-OFF) | `open <file.md>` |
| **"preview this folder"** / "explore this folder in browser" (ONE-OFF) | `open <folder>` |

**Default to folder mode for anything multi-file.** When the target has sibling or
child `.md` files - a **skill** (a `SKILL.md` with a `references/` folder), a docs
directory, an ADR set, any `.md` that sits next to related `.md`s - `open` the
**containing folder**, not the single file, so the sidebar shows the whole set. A
lone `.md` with no `.md` siblings opens single-file. "preview this skill",
"show me the setup-shortcuts skill", "read this doc" over a folder-resident file → folder mode
by default. Only open the bare file when the user explicitly wants just that one file.

For a one-off "preview this" with no filename, render the **most recent `.md` Claude
just wrote/edited** in this conversation (apply the folder-default rule: if it lives
among sibling `.md`s, open its folder). Report the one-line status back; the badge
updates on the next statusline repaint.

## In-page features

- **Margin comments (Google Docs layout):** select text (drag, or double-click a word) inside
  any rendered block and a comment card opens in the **right margin rail** on mouse-up. Every
  thread stays visible as a card in that rail — no pins, nothing to click open. The commented
  text is highlighted amber; clicking a highlight focuses its card, clicking a card highlights
  its text, and cards stack downward when their anchors collide.
  The highlight covers **exactly the words you selected**, not the block they sit in.
  Threads anchor to `{file, line, lineEnd}` for card placement — the source line(s) the selection
  touched — plus per-block character offsets for the highlight itself, and each one **also stores the selected text**,
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
  Comments live only in the open page (no localStorage) — copy them out before closing the tab.
- **Three copy buttons** (header) + single-key shortcuts, all clipboard:
  - **Copy notes** (`c`) — the pointer list of all comments, across every file in folder mode.
  - **Copy md** (`m`) — the raw source of the *current* doc (active file in folder mode).
  - **Copy md + notes** (`b`, "both") — the current doc's source with a `## Notes` section of
    its comments appended. This is the paste-back-to-Claude workhorse: doc + your anchored edits
    in one shot. Shortcuts are ignored while typing in a comment card.
- **Signature badge:** a fixed pill in the bottom-right corner - "Made with the
  browser preview skill", linking out to this skill's record. The icon is embedded as a
  data URI from this skill's own `assets/`, so it survives being republished as a Claude
  Artifact (where a strict CSP blocks every external host). Replaced the old
  `Claude · design-doc preview` footer.
- **Folder mode:** `mdview.py <folder>` (or `open <folder>` above) walks the folder for
  every `.md`/`.markdown`/`.mdx` file (skips `.git`, `node_modules`, `.previews`, dotdirs),
  embeds them all in one page, and adds a left sidebar to switch files without re-running
  the tool. Single-file runs are unchanged (no sidebar shown). Output path mirrors single-file
  naming: `<folder path> + .preview.html`, written as a sibling of the folder, never inside it.

## Mechanics

- **MODE trigger:** PostToolUse hook matching `Write|Edit|MultiEdit`. Bails unless the flag
  exists and the file is `*.md|*.markdown|*.mdx`. Renders to `<repo-root>/scratch/.previews/`
  (NOT next to the source), opens the browser once per path (marker in `state/opened/`);
  later edits re-render silently (manual Cmd-R — "render once" model).
- **Output location:** preview HTML always lands in `<repo-root>/scratch/.previews/`, named by
  the source's path relative to the repo root with `/` → `__` so same-named files in different
  dirs don't collide (`docs/adr/x.md` → `docs__adr__x.preview.html`). Repo root is the git
  toplevel of the source file, falling back to the file's own dir when not in a repo. This
  keeps build artifacts out of the source tree entirely.
- **ONE-OFF:** `browserpreview.sh open <file.md>` (or `python3 ~/.claude/scripts/mdview.py
  <file.md>`) renders + opens immediately, regardless of MODE, without flipping it. Same
  `scratch/.previews/` output location as the hook.

## Notes

- Previews live under `scratch/.previews/`; gitignore that one path instead of scattering
  `*.preview.html` across the tree (the old behavior).
- The hook ignores its own outputs, but skill/system `.md` writes under `~/.claude` will
  still trigger MODE if left on; that's expected.
- Needs internet for CDN scripts; doc text + branding always render (embedded), only
  diagram/table styling needs the CDN.
