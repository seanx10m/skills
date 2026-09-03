---
name: setup-shortcuts
description: Installs a personal set of shell aliases/functions (Claude Code launcher shortcuts, cloud/tool auth, project-jump, caffeinate toggle, dev-tool CLIs, and two sound toggles) into ~/.zshrc, bundling the audio files the sound toggles need. Use when the user says "set up shortcuts", "setup shortcuts", "/setup-shortcuts", or wants these shell shortcuts installed/reinstalled on a machine.
---

# Setup Shortcuts

Idempotently installs shell shortcuts into `~/.zshrc` and drops the bundled
audio assets in place. Safe to re-run — each block checks its own marker
and skips if already present.

## Run it

```
zsh scripts/install.sh
```

Then `source ~/.zshrc` (the script prints this reminder).

## What it installs

- **claude-code-launchers** — `c`/`cc`/`ccc` (sonnet/opus/fable) plus the
  full model x effort grid (`cl`, `cm`, `ch`, `cxh`, `cmx`, `ccl`...`cccmx`, `ccu`).
- **cloud-auth** — `g` (gcloud auth login), `a` (ant auth login), `ga`
  (gcloud application-default login), `sl` (slack login).
- **cg** — jump to a project dir via a `PROJECT_DIRS` map, falling back to
  a fuzzy find under `~/code`. Edit the map in the installed block for a
  new machine's paths.
- **caf** — `caffeinate -d` toggle with a 24h cap; `caf off` stops it.
- **dev-tool-aliases** — `ca` (cursor-agent, composer-2.5), `cx` (codex),
  `s` (sf org login, my-org-prod).
- **sound-toggles** — `bn` (brown noise, 20s fade in / 1s fade out),
  `lenny` (Lenny Kravitz — It Ain't Over 'Til It's Over, resumable), the
  shared `_track`/`_audio_gain` helpers `lenny` depends on, and `silence`
  (kill whatever's playing). Audio files ship in `assets/` and get copied
  to `~/.brownnoise.wav`, `~/.bn-tail.wav`, and
  `~/Music/tracks/Lenny Kravitz - It Ain't Over 'Til It's Over (Official Music Video).wav`
  if not already there.

## Requirements

`install.sh` preflight-checks these and prints what's missing (it still
installs the aliases/functions either way — they just won't run until the
binary exists):

| binary | needed by | install |
|---|---|---|
| `claude` | claude-code-launchers | official installer, see claude.com/code |
| `gcloud` | `g`, `ga` | `brew install --cask google-cloud-sdk` |
| `slack` | `sl` | `brew install slack-cli` |
| `cursor-agent` | `ca` | official installer, see cursor.com |
| `codex` | `cx` | `npm install -g @openai/codex` |
| `sf` | `s` | `npm install -g @salesforce/cli` |
| `sox` (provides `play`) | `bn`, `lenny` | `brew install sox` |
| `caffeinate` | `caf` | built into macOS, nothing to install |

Not checked: `ant`, needed by `a`. On this machine `ant` on `$PATH`
resolves to Apache Ant (the Java build tool), not an Anthropic CLI —
`a="ant auth login"` hangs rather than authenticating. Needs the real
Anthropic Platform CLI installed and ahead of Apache Ant on `PATH` before
`a` is usable; left unfixed here since the right binary/install path
wasn't confirmed.

## Notes

- Known broken and deliberately left out: `mmd` (mermaid→PNG) — `mmdc`
  needs Puppeteer's headless Chrome, which isn't installed, so it fails
  before it ever gets to rendering.
- Re-running only fills in missing blocks; it never touches ones already
  present, so hand edits to an installed block survive.
