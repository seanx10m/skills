# browser-preview

Render Markdown (Mermaid diagrams, tables, code) to a self-contained HTML page and open it in your browser.

- Single file or whole folder (file-explorer sidebar).
- Select text to comment; threads live in a margin rail. Copy notes / Copy md / Copy md + notes.
- Collapsible `<details>` toggles, light/dark theme, one-word-at-a-time speed reader (key `r`).
- Optional global MODE: every `.md` Claude writes auto-opens (via a PostToolUse hook).

## Requirements

- macOS (uses `open`; the renderer itself is plain Python 3, stdlib only)
- `python3`, `git` (for the repo/branch badges), `jq` (hook only)
- Internet for the Mermaid / marked / highlight.js CDN scripts
- Optional: `node` + `jsdom` to run the `scripts/test_*.mjs` self-checks (`npm i jsdom`)

## Install

```bash
cp -r skills/agent-ui/browser-preview ~/.claude/skills/
```

No build step. Usage and the optional hook / statusline setup are in `SKILL.md`.

```bash
bash ~/.claude/skills/agent-ui/browser-preview/scripts/browserpreview.sh open notes.md
bash ~/.claude/skills/agent-ui/browser-preview/scripts/browserpreview.sh open ./docs
```

`live` / `listen` (editable diagrams, comment streaming) need a separate live-server script via `BP_LIVE_SERVER`; they are not bundled.
