# skills

Agent Skills for [Claude Code](https://claude.com/claude-code), grouped by category.

A skill is a folder with a `SKILL.md` - YAML frontmatter plus Markdown instructions,
optionally bundling scripts and assets. See the
[Agent Skills specification](https://agentskills.io/specification).

## Install

Skills live in category folders here; Claude Code expects them flat in
`~/.claude/skills`. Symlink the ones you want:

```bash
git clone https://github.com/seanx10m/skills.git
cd skills
ln -s "$PWD/engineering/wt-handoff" ~/.claude/skills/wt-handoff
```

Or take everything:

```bash
for d in */*/; do ln -sfn "$PWD/${d%/}" ~/.claude/skills/; done
```

Several need configuration before first use - see the notes under each category.

---

## `engineering/`

Git worktrees, handoffs between agent sessions, and session state.

| Skill | What it does |
|---|---|
| `wt-handoff` | Hand off in-progress work to a fresh agent on the correct worktree. Writes down what dies with the session - decisions and their reasons, approaches already rejected, gotchas found the hard way - not the code the next agent can just read. |
| `warp-wt-handoff` | `wt-handoff` plus launching the incoming agent in a new Warp terminal, already `cd`'d to the worktree and already reading the doc. |
| `handoff` | The plain version, no worktrees involved. |
| `cloud-handoff` | Push in-progress work to a Claude Code cloud session when you have to leave your machine. |
| `lorax` | Prune finished worktrees. Speaks for the trees - removes one only when its work provably exists somewhere else. |
| `worktree-default` | Hook set that makes worktrees the default: a SessionStart nudge plus PreToolUse guards that deny writes and branch switches in the shared root checkout. |
| `session-state` | Persist and restore what a session was working on. |
| `loop-pre-flight` | Checks worth running before turning an agent loose on a long loop. |

## `general/`

Response modes and everyday tooling.

| Skill | What it does |
|---|---|
| `caveman` | Ultra-compressed prose at full technical accuracy. Several intensity levels. |
| `bullet` | Short conversational turns, one idea per line, grammar intact. |
| `define` | Fast, precise definitions of terms in context. |
| `dream-outcome` | Work backwards from the outcome you actually want before planning. |
| `quiz-me` | Turn a body of knowledge into a self-contained interactive quiz deck. One markdown file in, one HTML file out, no server. Cards are graded by what you *cannot* recover with grep. |
| `setup-shortcuts` | Idempotently install shell aliases and functions into `~/.zshrc` - launcher shortcuts, auth flows, project jump, caffeinate toggle, sound toggles. |

`setup-shortcuts` ships no audio; point the sound toggles at your own files, and
edit the project-jump table to your own paths.

## `documents/`

Turning documents into something readable.

| Skill | What it does |
|---|---|
| `browser-preview` | Render Markdown (Mermaid + tables) to an HTML preview. A sticky mode auto-opens every `.md` the agent writes; a one-off verb previews a single doc, or a whole folder with a file-explorer sidebar. Select-to-comment in a Google-Docs-style margin rail, with copy-out of the notes. |
| `pd-slides` | Split-screen deck: slides on the left, the full source document on the right. Each slide owns a section of the paper, which lights up as you move. Optionally the deck reads itself aloud - one TTS clip per paragraph, word for word, so caption, highlight and slide advance together and nothing drifts. |
| `pd-slides-plus` | `pd-slides` with embedded, editable Excalidraw whiteboards. |
| `to-kindle` | Convert if needed, then email a document to your Kindle. EPUB/PDF/DOCX/TXT/HTML go as-is; Markdown, MOBI, AZW3, FB2, ODT and RST convert to EPUB first. |

`to-kindle` needs `himalaya` configured, `KINDLE_ADDR` set, and the sending address
on Amazon's Approved Personal Document E-mail List.

## `voice/`

Text to speech, in several directions.

| Skill | What it does |
|---|---|
| `talk-to-me` | Narrate agent responses aloud in your macOS Personal Voice, streamed into a live karaoke panel that also echoes your own prompt back in your own voice. |
| `gemini-tts` | Markdown or text in, `.m4a` out, via the Gemini TTS API. Chunks at paragraph boundaries so long input works. |
| `gpt-tts` | The same, against OpenAI's TTS. |
| `text-to-speech` | Thin local `say`-based narration. |
| `personal-voice-to-file` | Render text to an audio file in your macOS Personal Voice. |

Cloud ones need `GEMINI_API_KEY` / `OPENAI_API_KEY`. The Personal Voice ones need a
Personal Voice recorded under macOS Settings → Accessibility.

## `notifications/`

Knowing the turn ended without watching the terminal.

| Skill | What it does |
|---|---|
| `notify` | One master switch over end-of-turn macOS notifications. Ships a small notifier app you build and sign locally. |
| `done-sound` | Play a sound when a turn finishes. |
| `text-me` | Send a message or files to your own iMessage self-chat. Stages, sends, waits for delivery, reports per-file status. |
| `progress-hud` | A floating HUD for long multi-step runs, with phase and completion tracking. |

`text-me` needs `TEXT_ME_TO` set to your own number. `notify/app/build.sh` needs your
own codesigning identity and bundle id.

---

## Configuration

These were written for one machine and then de-identified for publication.
Anywhere you see `YOUR_*`, `<your-org>`, `example.com`, or a `${VAR:?}` that errors
when unset, that is a value you need to supply. Nothing phones home.

`documents/pd-slides-plus/assets/` vendors an Excalidraw build; that code is
Excalidraw's, under its own license.

## License

MIT - see [LICENSE](LICENSE).
