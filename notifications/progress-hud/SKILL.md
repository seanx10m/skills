---
name: progress-hud
description: A toggleable floating always-on-top macOS progress HUD (green percent bar + effort title + phase/detail) that appears automatically whenever long-running work starts - a Workflow, /goal, /loop, a serial-workflow-loop, a big refactor, or any multi-step build the model classifies as long-running. Toggle on/off like /notify. When ON, the model raises and updates the HUD via the `progress-hud` CLI; when OFF, nothing spawns. Use when the user says "/progress-hud", "progress hud on/off", "show a progress bar", "floating progress", "HUD for this run", "track this workflow visually", or asks to see live progress of a long effort.
---

# 📊 Progress HUD

A floating, always-on-top card (rides above windows/tabs and across Spaces) that
renders a **generic progress feed** for whatever long-running effort is running.
It is a dumb renderer: it polls `~/.progress-hud/current.json` and draws it. Producers
write that feed through the `progress-hud` CLI - one file, many producers, one HUD.

- green rounded percent bar + `done/total · %`
- effort **title**, plus a **phase · detail** line (this is the "expand for more" detail)
- states: `running` (green), `stalled` (amber, auto after 90s no update), `done` (✓, lingers ~5s then closes)
- gear → **settings panel with a transparency dial** (sets the default alpha for next launch)
- optional animated mascot at `~/.progress-hud/mascot.gif` (square-cropped, rounded)
- `–` compact pill (just %) · drag anywhere · `×` quit · singleton (one HUD at a time)

CLI: `~/.claude/skills/progress-hud/scripts/progress-hud` (builds the Swift binary
with `swiftc` on first run into `~/.progress-hud/ProgressHUD`).

## Toggle (persisted, like /notify)

When the user invokes `/progress-hud …` or says "progress hud …":

- `progress-hud on`  → global ON. Long-running work raises the HUD.
- `progress-hud off` → global OFF. Nothing spawns; kills a live HUD.
- `progress-hud session on|off|reset` → this-session override (beats global).
- `progress-hud status` → resolved state + whether the HUD is running + the feed.

Resolution: session `.off` → OFF; session file → ON; else global `~/.progress-hud/enabled`.

After changing, confirm the mode in one sentence.

## When it auto-activates (the "any time X" behavior)

When the toggle is ON, a UserPromptSubmit hook injects a one-line reminder each turn.
**Acting on that reminder is the mechanism** - the harness can't classify "long-running"
for you, so you do:

> If you are starting work you'd classify as **long-running** (a Workflow, `/goal`,
> `/loop`, a serial-workflow-loop, or a multi-step build/refactor), raise the HUD.
> Skip it for quick one-off tasks.

Raise + drive it:

```
scripts/progress-hud start "config → settings rename" --total 8 --phase "U1 · Scout"
scripts/progress-hud update --done 1 --phase "U2 · Dev" --detail "committed U1"
scripts/progress-hud update --done 2 --phase "U3 · Review"
scripts/progress-hud done          # ✓, closes itself
```

Only spawns if the toggle is ON, so calling `start` unconditionally is safe - OFF
makes it a no-op. Producers that are *always* long-running (serial-workflow-loop,
/loop, /goal handlers) should call `start`/`update`/`done` directly so the bar moves
without relying on the model remembering.

## Feed schema (`~/.progress-hud/current.json`)

```json
{ "title": "…", "done": 3, "total": 8,
  "phase": "U3 · Dev", "detail": "scouting edit sites",
  "state": "running", "updatedAt": 1720000000 }
```

## Self-check

`bash ~/.claude/skills/progress-hud/scripts/demo.sh` - forces the toggle on, walks a
fake 5-step effort so you can watch the bar move, then closes. Restores prior toggle.

## Notes

- **Singleton**: pidfile `~/.progress-hud/pid`; the CLI won't spawn a second HUD; the HUD
  removes its pid on exit (also on SIGTERM/SIGINT).
- **Lifecycle**: `done` lingers ~5s then quits; `stop` kills it and clears the feed;
  turning the toggle off kills a live HUD.
- **Transparency default** persists in `~/.progress-hud/config.json` (`{"alpha":0.35..1.0}`).
- **Mascot**: drop an animated `~/.progress-hud/mascot.gif`; absent = no mascot, HUD still works.
- **Rebuild** after editing the Swift: delete `~/.progress-hud/ProgressHUD` (the CLI
  rebuilds when the source is newer).
- macOS only (AppKit + `swiftc`).
