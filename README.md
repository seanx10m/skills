# skills

[Agent Skills](https://agentskills.io) for Claude Code, grouped by category.
Every skill is self-contained: install one, some, or all.

## Install

**All skills, as a Claude Code plugin** (updates itself):

```bash
claude plugin marketplace add seanx10m/skills
claude plugin install skills@skills
```

**Pick and choose** - copy any skill folder into your skills directory:

```bash
cp -r skills/<category>/<name> ~/.claude/skills/
```

Some skills have a build or install step (Swift helpers, a Rust app, hooks, shell config).
Each skill's `README.md` lists its requirements and setup.

## Worktrees

| Skill | What it does | Platform |
|---|---|---|
| [wt-handoff](skills/worktrees/wt-handoff) | Write a handoff doc so a fresh agent picks up on the right worktree | any |
| [ghostty-wt-handoff](skills/worktrees/ghostty-wt-handoff) | Handoff + launch the next agent in a new Ghostty pane | macOS |
| [iterm-wt-handoff](skills/worktrees/iterm-wt-handoff) | Handoff + launch the next agent in a new iTerm2 pane | macOS |
| [warp-wt-handoff](skills/worktrees/warp-wt-handoff) | Handoff + launch the next agent in a new Warp tab | macOS |
| [worktree-default](skills/worktrees/worktree-default) | Install hooks that make every session work in a git worktree | any |

The three terminal handoffs each include the full `wt-handoff` procedure, so none of them needs `wt-handoff` installed.

## Agent UI

| Skill | What it does | Platform |
|---|---|---|
| [browser-preview](skills/agent-ui/browser-preview) | Render Markdown (Mermaid, tables) to an HTML page with margin comments and a speed reader | any |
| [decide-ui](skills/agent-ui/decide-ui) | Turn a list into a swipe-triage or tournament-bracket decision page | any |
| [progress-hud](skills/agent-ui/progress-hud) | Floating always-on-top progress HUD for long tasks | macOS |
| [talk-to-me](skills/agent-ui/talk-to-me) | Speak responses aloud in your macOS Personal Voice with a live karaoke panel | macOS |

## Media

| Skill | What it does | Platform |
|---|---|---|
| [image-gen](skills/media/image-gen) | Generate N image options with Gemini's image model and open them in Preview | macOS |
| [watch-video](skills/media/watch-video) | Watch a video via scene-change keyframes, OCR, and local transcription | macOS |
| [xtract](skills/media/xtract) | Turn a post, video, or article link into one Markdown file with text + transcript | any |
| [youtube-transcript](skills/media/youtube-transcript) | Fetch a YouTube video's transcript | any |
| [youtube-to-mp4](skills/media/youtube-to-mp4) | Download a YouTube video as .mp4 | any |
| [youtube-to-m4a](skills/media/youtube-to-m4a) | Download a YouTube video's audio as .m4a | any |
| [youtube-to-command](skills/media/youtube-to-command) | Bind a YouTube track to a zsh command that toggles playback | macOS |
| [stick-video](skills/media/stick-video) | Hand-drawn stick-figure explainer videos with voiceover, optional two-host dialogue | any |
| [motion](skills/media/motion) | 3D motion loops for any brand: three.js scenes rendered frame-exact, fanned out as options | any |

## Learning

| Skill | What it does | Platform |
|---|---|---|
| [quiz-me](skills/learning/quiz-me) | Interactive quiz over anything just discussed | any |
| [quiz-me-full](skills/learning/quiz-me-full) | Spaced-repetition quizzing with progress kept as Markdown | any |

## Productivity

| Skill | What it does | Platform |
|---|---|---|
| [pave](skills/productivity/pave) | Active planning while an agent builds: find problems, groom what comes next | any |
| [remind](skills/productivity/remind) | Create Reminders.app reminders from natural language | macOS |
| [setup-shortcuts](skills/productivity/setup-shortcuts) | zsh shortcuts: Claude model/effort aliases, `cg`/`ccg` project jumpers, `caf` | zsh |

## License

MIT
