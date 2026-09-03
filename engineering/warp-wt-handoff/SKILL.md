---
name: warp-wt-handoff
description: Hand off active dev work to a fresh agent AND launch that agent in a new Warp terminal, already cd'd to the worktree and already reading the handoff doc. Use when the user says "/warp-wt-handoff", "handoff and spawn", "hand this off and open it in Warp", or wants the next session started for them rather than described to them.
argument-hint: "What will the next agent session focus on?"
---

`$WARP` below means the `scripts/` directory next to this file.

This is `/wt-handoff` plus a launch. Do the handoff exactly as that skill defines it, then start the incoming agent.

## Step 1 — Run the handoff

Follow the `wt-handoff` skill start to finish: commit outstanding work, identify the worktree, resolve ambiguity, write the doc to `/tmp/wt-handoff-<branch-slug>-<date>.md`.

Do not abbreviate it because a spawn is coming. The doc is the entire payload the new agent gets — it starts with an empty context and this file.

## Step 2 — Launch the incoming agent

```bash
"$WARP"/warp-spawn \
  --cwd "<absolute worktree path>" \
  --title "handoff · <repo name>" \
  -- cc "Read <handoff doc path> and execute the Next steps in it, in order."
```

- `--cwd` is the worktree path from the handoff doc's `Worktree > Path`, verbatim and absolute.
- The prompt stays short and points AT the doc. Never inline the handoff content into the command — it is a shell argument.
- Default is a new **tab in the active window**, opened with a Warp tab config. Nothing is typed into a prompt, so nothing can land in the wrong terminal.
- `--title` is the handoff label Warp paints above the tab, in yellow. Name it for the repo and the theme — `handoff · Dining Out AI`, `handoff · kode`. It is not the tab's own name: Warp keeps naming the tab after its command and cwd, and two tabs sharing a title stay two labels rather than one group.
- `--color` overrides the yellow (`black red green yellow blue magenta cyan white`). Leave it unless the user asks.
- Pass `--window` for a separate window instead — also required for `--pane`/`--split`.
- The script prints the tab-config (or launch-config) path. Report it, so a failed launch is debuggable.

## Step 3 — Confirm

Tell the user, in two lines: the doc path, and that the agent is running in Warp on `<branch>`.

Do not follow the incoming agent's work. This session's job ends at the launch.
