---
name: notify
description: End-of-turn alerts for Claude Code, as one 4-way mode over sound + native macOS banner - off / sound / banner / both. Both fire at the same moment (end of turn, or when Claude needs you), so they stay in sync. The banner shows the repo (org/repo) and session title with a robot icon; clicking it brings the originating terminal (iTerm/Warp) to the front. Use when the user says "/notify", "notify off/sound/banner/both", "notifications on/off", "ping me when done", "mac notifications", "sound only", "banner only", "/notify p", "mark this session priority/important", "louder sound for this session".
---

# ⚡️ Notify

One master switch over two end-of-turn alerts. Both fire on the same events, so
they're always in sync:

- **sound** - `afplay` the `/sound`-selected file (the existing sound skill picks *which*).
- **banner** - a native macOS notification via the signed helper `Claude Notify.app`:
  - title = **repo** (`org/repo` from the git remote)
  - subtitle = **session title** (Claude's own `aiTitle`)
  - body = empty on done / the ask on needs-you
  - icon = robot; **click it -> the originating terminal (iTerm/Warp) comes forward**

Events: **Stop** (turn finished) and **Notification** (needs permission / waiting).

## Modes

| mode     | sound | banner |
|----------|:-----:|:------:|
| `off`    |   -   |   -    |
| `sound`  |   ✓   |   -    |
| `banner` |   -   |   ✓    |
| `both`   |   ✓   |   ✓    |

Backed by two global flags: `~/.claude/sound-on` (sound) and `~/.claude/notify-on`
(banner). The mode just sets both together - no hook changes, and plain `/sound`
still works independently.

## Instructions

When the user invokes `/notify <mode>` or says "notify …":

**Set the mode (global):**
- `/notify off`    -> `rm -f ~/.claude/sound-on ~/.claude/notify-on`
- `/notify sound`  -> `touch ~/.claude/sound-on && rm -f ~/.claude/notify-on`
- `/notify banner` -> `rm -f ~/.claude/sound-on && touch ~/.claude/notify-on`
- `/notify both`   -> `touch ~/.claude/sound-on ~/.claude/notify-on`

Aliases: "sounds only" = `sound`, "banner only" = `banner`, "on" = `both`.

**Priority session** (distinct alert sound - marks this session as important):
- `/notify p`     -> `mkdir -p ~/.claude/sounds/sessions && echo ~/.claude/sounds/notify4.mp3 > ~/.claude/sounds/sessions/$CLAUDE_CODE_SESSION_ID` then reply "🔴 Priority session - sound 4 set."
- `/notify p off` -> `rm -f ~/.claude/sounds/sessions/$CLAUDE_CODE_SESSION_ID` then reply "Priority cleared - back to global/default sound."
- Reuses the existing `/sound` per-session override file (`~/.claude/sounds/sessions/$CLAUDE_CODE_SESSION_ID`) - both the Stop and Notification sound hooks already read it first, so no hook changes needed. Sound must still be globally on (`/notify sound` or `/notify both`) for anything to play.

**Per-session banner override** (session beats global; sound stays global):
- `/notify session on`  -> `mkdir -p ~/.claude/notify/sessions && rm -f ~/.claude/notify/sessions/$CLAUDE_CODE_SESSION_ID.off && touch ~/.claude/notify/sessions/$CLAUDE_CODE_SESSION_ID`
- `/notify session off` -> `mkdir -p ~/.claude/notify/sessions && rm -f ~/.claude/notify/sessions/$CLAUDE_CODE_SESSION_ID && touch ~/.claude/notify/sessions/$CLAUDE_CODE_SESSION_ID.off`
- `/notify session reset` -> `rm -f ~/.claude/notify/sessions/$CLAUDE_CODE_SESSION_ID ~/.claude/notify/sessions/$CLAUDE_CODE_SESSION_ID.off`

**Status / test:**
- `/notify` or `/notify status` -> report the resolved mode:
  - `test -f ~/.claude/sound-on && echo "sound: on" || echo "sound: off"`
  - `test -f ~/.claude/notify-on && echo "banner: on" || echo "banner: off"`
- `/notify test` -> `bash ~/.claude/skills/notify/scripts/notify.sh --test` (fires a sample banner, ignoring the gate)

After changing, confirm the mode in one sentence.

## Notes

- **Banner delivery** = signed Swift helper `~/Applications/Claude Notify.app` (source +
  `build.sh` in `notify/app/`), bundle id `com.example.claude-notify-robot`, carrying the
  robot bundle icon. On macOS Tahoe this is the ONLY reliable custom-icon path
  (`osascript` can't attach an image; `terminal-notifier` is silently dropped). See
  `[[spend-alert-furnace-icon]]`. `notify.sh` falls back to `osascript` (generic icon, no
  click action) if the app is missing/unauthorized.
- **Rebuild** after editing the Swift: `bash ~/.claude/skills/notify/app/build.sh`.
- **First-run permission**: the helper needs a one-time notification grant. NEVER run the
  binary directly with args to "test" from a plain shell - `requestAuthorization` returns
  *denied* with no GUI and persists it. Grant via System Settings -> Notifications -> Claude Notify.
- **Click-to-focus** = app-level only (activates iTerm/Warp via `TERM_PROGRAM`); the exact
  pane isn't addressable from a hook (no tty, env session id doesn't map to a live pane).
- **Stop fires every turn end** - same cadence as `/sound`. Turn it on when you step away.
- Session markers pruned after 7 days (SessionStart cleanup).
