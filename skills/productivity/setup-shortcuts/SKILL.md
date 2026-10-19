---
name: setup-shortcuts
description: Installs zsh shell shortcuts for launching Claude Code with a chosen model and effort level (c/cc/ccc plus l/m/h/xh/mx effort suffixes) and for jumping to projects by fuzzy name (cg, and ccg to jump and launch Claude there), plus a caf display-awake toggle on macOS. Use when the user wants to install, update, or remove these shell shortcuts.
disable-model-invocation: true
---

# setup-shortcuts

This skill changes the user's shell config (`~/.zshrc`), so confirm before installing.

## Install

1. Check the shell is zsh (`echo $SHELL`). The shortcuts are zsh-only; stop and say so otherwise.
2. Tell the user, plainly, that by default every shortcut launches Claude with `--dangerously-skip-permissions`, which runs tools (shell commands, file edits) without asking first.
   Ask whether they want that, or `CLAUDE_SHORTCUT_FLAGS=""` to keep normal permission prompts.
   If they want prompts, add `export CLAUDE_SHORTCUT_FLAGS=""` to `~/.zshrc` above the block the installer adds (or tell them to).
3. Ask where their projects live if not `~/code`; if different, add `export CG_ROOT="<path>"` to `~/.zshrc`.
4. Run the installer from this skill's directory:
   ```bash
   bash "<skill-dir>/install.sh"
   ```
   It copies `shortcuts.zsh` to `~/.config/claude-shortcuts/shortcuts.zsh` and adds one delimited `source` block to `~/.zshrc` (only if absent - safe to re-run; re-running also updates the copied file).
5. Tell the user to run `source ~/.zshrc` or open a new terminal.

## Uninstall

```bash
bash "<skill-dir>/install.sh" --uninstall
```

## What gets installed

| Shortcut | Does |
|---|---|
| `c` / `cc` / `ccc` | `claude --model sonnet` / `opus` / `fable` |
| suffix `l` `m` `h` `xh` `mx` | adds `--effort low/medium/high/xhigh/max` (e.g. `cch`, `cccmx`, `cl`) |
| `ccu` | opus + `--effort xhigh` |
| `cg <name words>` | cd to the best-matching project dir under `$CG_ROOT` (default `~/code`) |
| `ccg <name words> [-- args]` | `cg`, then `cc` with the remaining args |
| `caf` / `caf off` | macOS: keep the display awake for 24h / stop |

Every Claude shortcut passes `$CLAUDE_SHORTCUT_FLAGS` and then any extra arguments through.

`cg` matching: words are joined, lowercased, and stripped to letters and digits (`cg my app` = `myapp`).
`PROJECT_DIRS` (an assoc array of normalized name -> path) is checked first; otherwise an exact directory name beats a partial one, and the shortest path wins within a tier.
To pin a name, the user defines `PROJECT_DIRS` in `~/.zshrc` before the source block, or adds `PROJECT_DIRS[myapp]="$HOME/code/work/my-app"` after it.
