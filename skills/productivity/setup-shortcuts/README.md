# setup-shortcuts

Short zsh commands for launching Claude Code with a chosen model and effort, and for jumping to projects by name.

- `c` / `cc` / `ccc` launch `claude` with sonnet / opus / fable.
  Add an effort suffix `l` `m` `h` `xh` `mx` (low/medium/high/xhigh/max): `cch`, `cccmx`, `cl`. `ccu` = opus + xhigh.
  Extra args pass through: `cc --resume`.
- `cg <name words>` cds to a project under `$CG_ROOT` (default `~/code`). Words are joined and normalized, so `cg my app` finds `My-App`.
  The `PROJECT_DIRS` map is checked first, then an exact directory name beats a partial one, then the shortest path wins.
- `ccg <name words> [-flags | -- args]` = `cg` then `cc` there: `ccg my app --resume`, `ccg my app -- "fix the tests"`.
- `caf` / `caf off` (macOS) keeps the display awake for 24h via `caffeinate -d`. It tracks its own PID in `~/.cache/claude-shortcuts/caf.pid` and only kills that.

## WARNING: permission prompts are OFF by default

Every Claude shortcut passes `$CLAUDE_SHORTCUT_FLAGS`, which defaults to `--dangerously-skip-permissions`.
That flag makes Claude run tools - shell commands, file edits and deletes, network calls - **without asking you first**.
Only use it if you understand and accept that risk (ideally in a sandbox, container, or VM).

To keep Claude's normal permission prompts, set it to empty in `~/.zshrc` (above the installed block, or anywhere - it is read on every call):

```zsh
export CLAUDE_SHORTCUT_FLAGS=""
```

You can also put other flags there, e.g. `CLAUDE_SHORTCUT_FLAGS="--permission-mode acceptEdits"`.

## Requirements

- zsh (the shortcuts use zsh-only syntax).
- [Claude Code](https://docs.claude.com/en/docs/claude-code) (`claude` on your `PATH`).
- `caf` needs macOS (`caffeinate`, BSD `date`). Everything else works on any zsh.
- Note: `cc` shadows the system C compiler command in interactive shells (`command cc` still reaches it).

## Install

As a skill (then run `/setup-shortcuts` in Claude Code):

```bash
cp -r skills/productivity/setup-shortcuts ~/.claude/skills/
```

Or directly:

```bash
bash skills/productivity/setup-shortcuts/install.sh            # install / update
bash skills/productivity/setup-shortcuts/install.sh --uninstall
```

The installer copies `shortcuts.zsh` to `~/.config/claude-shortcuts/shortcuts.zsh` and appends one delimited block to `~/.zshrc` that sources it, only if the block is not already there.
`--uninstall` removes the block and the copied file.

## Configure

Set these in `~/.zshrc` before the installed block:

```zsh
export CG_ROOT="$HOME/projects"          # where cg searches (default ~/code)
typeset -A PROJECT_DIRS=(                # exact overrides, normalized keys (a-z0-9)
  myapp "$HOME/code/work/my-app"
)
```
