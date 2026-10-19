---
name: progress-hud
description: A toggleable floating always-on-top macOS progress HUD (green percent bar + effort title + phase/detail) shown while long-running work runs - a /loop, a /goal, a big refactor, or any multi-step build. When ON, the model raises and updates the HUD via the `progress-hud` CLI; when OFF, nothing spawns. Use when the user says "/progress-hud", "progress hud on/off", "show a progress bar", "floating progress", or asks to see live progress of a long effort.
---

# Progress HUD

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
- **bundle mode**: merge every concurrent session's HUD into one window, one row per effort, instead of a stack of separate cards

CLI: `~/.claude/skills/progress-hud/scripts/progress-hud` (builds the Swift binary
with `swiftc` on first run into `~/.progress-hud/ProgressHUD`).

## Toggle (persisted)

When the user invokes `/progress-hud …` or says "progress hud …":

- `progress-hud on`  → global ON. Long-running work raises the HUD.
- `progress-hud off` → global OFF. Nothing spawns; kills a live HUD.
- `progress-hud session on|off|reset` → this-session override (beats global).
- `progress-hud bundle on|off|status` → merge concurrent HUDs into one window (one row
  per effort) instead of a separate floating card per session. Off by default.
- `progress-hud status` → resolved state + whether the HUD is running + the feed.

Resolution: session `.off` → OFF; session file → ON; else global `~/.progress-hud/enabled`.

After changing, confirm the mode in one sentence.

## When it auto-activates (the "any time X" behavior)

When the toggle is ON, the model should raise the HUD itself. Optionally add a
UserPromptSubmit hook that prints a one-line reminder each turn while the toggle is on
(e.g. a command that runs `progress-hud status` and echoes "progress-hud is ON: raise the
HUD for long-running work" when it reports ON). **Acting on that reminder is the mechanism** - the harness can't classify "long-running"
for you, so you do:

> If you are starting work you'd classify as **long-running** (a long agent workflow,
> `/goal`, `/loop`, or a multi-step build/refactor), raise the HUD.
> Skip it for quick one-off tasks.

Raise + drive it:

```
scripts/progress-hud start "my-app rename" --total 8 --phase "U1 · Scout"
scripts/progress-hud update --done 1 --phase "U2 · Dev" --detail "committed U1"
scripts/progress-hud update --done 2 --phase "U3 · Review"
scripts/progress-hud done          # ✓, closes itself
```

Only spawns if the toggle is ON, so calling `start` unconditionally is safe - OFF
makes it a no-op. Producers that are *always* long-running (loop or goal handlers) should call `start`/`update`/`done` directly so the bar moves
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

- **Bundle mode**: `progress-hud bundle on` merges all concurrent sessions' HUDs into
  one window - a header ("N running") plus one compact row per active feed, sorted by
  session id, resized to fit. Backed by one shared `--bundle` renderer process
  (pidfile `~/.progress-hud/bundle.pid`) that polls every `sessions/*.json` feed
  instead of a single file; `start`/`update` are unchanged, they still just write that
  session's feed - toggling bundle only changes which renderer reads it. A row lingers
  ~5s after `done` like the single card, then drops out; the shared window auto-quits
  once no rows remain. No per-row settings/compact/close in bundle mode, one shared `×`
  quits the viewer (the underlying sessions keep running regardless).
- **Singleton**: pidfile `~/.progress-hud/pid`; the CLI won't spawn a second HUD; the HUD
  removes its pid on exit (also on SIGTERM/SIGINT). In bundle mode this is
  `~/.progress-hud/bundle.pid` instead.
- **Lifecycle**: `done` lingers ~5s then quits; `stop` kills it and clears the feed;
  turning the toggle off kills a live HUD.
- **Transparency default** persists in `~/.progress-hud/config.json` (`{"alpha":0.35..1.0}`).
- **Mascot**: drop an animated `~/.progress-hud/mascot.gif`; absent = no mascot, HUD still works.
- **Rebuild** after editing the Swift: delete `~/.progress-hud/ProgressHUD` (the CLI
  rebuilds when the source is newer).
- macOS only (AppKit + `swiftc`).
