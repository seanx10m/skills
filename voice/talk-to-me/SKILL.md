---
name: talk-to-me
description: Toggle spoken narration of Claude Code responses in your macOS Personal Voice, streamed into a live karaoke panel that also echoes your own prompt in your own voice. Use when the user invokes /talk-to-me or asks to "read responses aloud", "talk to me", "stop talking", "pause it", "speak that", or change the narration voice or speed.
---

# talk-to-me

Self-contained skill that narrates Claude Code responses aloud in your macOS
**Personal Voice**. Everything lives inside this skill folder:

```
talk-to-me/
├── SKILL.md
├── scripts/
│   ├── personal-say        audio-only engine (Swift + AVFoundation, embedded Info.plist)
│   ├── personal-say.swift  audio engine source
│   ├── talk-reader-live    karaoke panel: highlights + auto-scrolls, APPENDS as the turn streams
│   ├── talk-reader-live.swift  panel source (Cocoa, willSpeakRange → highlight, spool watcher)
│   ├── Info.plist          NSPersonalVoiceUsageDescription (lets a CLI use Personal Voice)
│   ├── talktome.sh         control surface (on/off/stop/voice/rate/window/say)
│   ├── speak-stream.sh     PreToolUse + Stop hook — spools each text block as it lands
│   ├── flush.sh            UserPromptSubmit hook — spools YOUR prompt, keeps the panel alive
│   ├── voice-style-hint.sh UserPromptSubmit hook — voice-friendly output when on
│   ├── statusline-badges.sh status-line wrapper — 🗣/🦴 on/off badges
│   ├── claude-talk         optional: run Claude Code under the terminal tap (per-sentence)
│   ├── tap.py              the tap's screen model
│   ├── doctor.sh           is the tap actually working?
│   ├── build.sh            rebuild both engines
│   └── install.sh          wire hooks + status line + Quick Actions to these files
├── assets/
│   ├── Talk To Me.workflow    Quick Action: read highlighted text
│   ├── Pause Talking.workflow Quick Action: pause/resume (sends SIGUSR1)
│   └── Stop Talking.workflow  Quick Action: stop speech instantly
└── state/                  shared voice|rate|window|personality|me-voice + narrate-on;
                            sessions/ (on-off), sessions-cfg/<id>/ (per-session voice|rate),
                            queue/<id>/ (the panel's spool), spoken/<id> (watermark)
```

The macOS `say` CLI cannot use Personal Voice; `personal-say` is required.

## First-time setup (do this before anything else)

1. **Get a voice.** In System Settings → Accessibility → Personal Voice, create a
   Personal Voice (it records your own voice) — or skip that and rely on **auto**,
   which uses whatever voice is available. New installs default the voice to `auto`,
   so if the user already has any Personal Voice it will be picked automatically; if
   they have none, it falls back to the standard system voice. It always speaks.
2. **Install.** Run `bash ~/.claude/skills/talk-to-me/scripts/install.sh`, then assign
   the Quick Action hotkeys in System Settings and restart Claude Code.
3. **Change the voice later (optional).** Once they know their voice's name (shown in
   the Personal Voice settings), they can pick it explicitly: `/talk-to-me voice <name>`
   (substring match is fine). `/talk-to-me auto` returns to auto-pick. List of usable
   voices = the recorded Personal Voices on that Mac.

So the onboarding order is: make/confirm a voice (or use auto) → install → optionally
change to a specific voice.

## Handling a /talk-to-me request

Run the control script with the matching command and report its one-line status back:

```bash
bash ~/.claude/skills/talk-to-me/scripts/talktome.sh <command>
```

| User says | Command |
|---|---|
| `/talk-to-me`, "toggle" | `talktome.sh` |
| "on", "read your responses" (THIS session) | `talktome.sh on` |
| "on for all sessions" | `talktome.sh on all` |
| "off", "be quiet" (this session) | `talktome.sh off` |
| "off everywhere" | `talktome.sh off all` |
| "stop", "pause it" (stop current speech, stay enabled) | `talktome.sh stop` |
| "status" | `talktome.sh status` |
| "use any voice" (THIS session) | `talktome.sh auto` |
| "use <voice>" (THIS session) | `talktome.sh voice <name>` |
| "use <voice> for all sessions" / set the shared default | `talktome.sh voice <name> all` |
| "speed 1.2" / faster / slower (THIS session) | `talktome.sh rate <multiplier>` |
| "speed 1.2 for all sessions" | `talktome.sh rate <multiplier> all` |
| "show the words" / "hide the window" / audio-only | `talktome.sh window on` / `window off` |
| "turn on personality" / "personality off" / "be wise" | `talktome.sh personality on` / `personality off` |
| "say <text>" / "read this: …" | `talktome.sh say <text>` |

## Behavior notes

- **Scope is per-session by default; the `all` verbs are an authoritative global reset.**
  `on`/`off`/`toggle` affect only the current Claude Code session (keyed on
  `$CLAUDE_CODE_SESSION_ID`; the Stop hook matches on the `session_id` it receives on
  stdin). **Resolution used by every consumer (narration, the voice-mode hint, the badge):
  an explicit per-session marker wins; only a session with NO marker falls back to the
  global default.** State: `state/sessions/<id>` = explicit ON, `state/sessions/<id>.off` =
  explicit OFF, `state/narrate-on` = global default. Add `all` to a verb to act on every
  session at once: `on all` / `off all` set or clear the global default **and wipe every
  per-session marker**, so "on/off for all sessions" genuinely takes hold everywhere — no
  explicitly-on session keeps talking through an `off all`, and no muted session stays
  silent through an `on all`. `toggle all` flips the global default and likewise clears the
  per-session markers so the result is uniform. After an `all` reset you can again override
  any single session with a plain `on`/`off`. A plain `on`/`off`/`toggle` with NO session id
  is a no-op (it tells you to use the `all` form) rather than silently going global — so a
  bare toggle can never flip the global default by accident. Stale per-session markers are
  pruned after 7 days.
- **Voice and rate are also per-session.** `voice`/`auto`/`rate` set an override for the
  current session only (`state/sessions-cfg/<id>/{voice,rate}`); resolution is
  per-session override → shared global file (`state/voice`, `state/rate`) → default. So
  three parallel sessions can each narrate in a different voice without stomping each
  other. Add `all` (e.g. `voice morgan all`) to write the **shared default** instead —
  that also clears the caller's own override so it follows the shared value. `window` and
  `personality` remain global. `status` shows the effective value tagged `(session)` or
  `(shared)`. Stale overrides are pruned after 7 days.
- **Voice names match personal-first.** When a name (e.g. `lily`) exists as both a macOS
  **Personal Voice** and a built-in **system** voice, the engines (`personal-say`,
  `talk-reader-live`) only ever match against the Personal-Voice list, so the Personal Voice
  always wins; the system voice is used only as a last-resort fallback when no Personal
  Voice exists at all.
- With `window on` (default), a **floating karaoke panel** appears at the top of the
  screen, highlights each word as it's spoken, auto-scrolls, and auto-closes when the turn
  is done. It has a big centered ⏸/▶ pause-resume pill and a ✕ close button, is draggable,
  and is non-activating (won't steal focus). **Click any word to (re)start reading from
  there; scroll freely for long text.** `window off` falls back to audio-only
  (`personal-say`). The panel header shows the session's name: it prefers the name you set
  with `/rename` (stored in `~/.claude/sessions/<pid>.json` under `.name`), and only falls
  back to Claude Code's auto-generated `ai-title`, then the project dir name.
- **Narration streams; the panel appends.** `speak-stream.sh` runs on **PreToolUse and
  Stop** and drops every assistant text block into `state/queue/<sid>/` the moment it lands,
  so a tool-heavy turn starts talking at the first sentence instead of at the end. ONE
  long-lived `talk-reader-live` per session drains that spool and **appends** to the open
  panel, keeping the karaoke highlight aligned across appends. `state/spoken/<sid>` is the
  watermark (last spoken message uuid), so nothing is ever spoken twice; a cold start seeds
  it at the transcript tip rather than replaying the backlog. A `.done` file written at Stop
  is what lets the panel close once speech catches up.
- **Your own prompt is echoed in your own voice.** `flush.sh` (UserPromptSubmit) spools what
  you typed as a `*.me.txt` block. The panel renders it as an indented italic quote above the
  reply and speaks it in **your** Personal Voice, so an answer keeps its question on screen
  and a reply voice never reads your words back at you. The voice is `state/me-voice`
  (default `me`, matched personal-first); the reply keeps the session voice, and
  `talk-reader-live` splits the text at speaker boundaries to switch mid-stream. A prompt is
  truncated at 700 characters, hook-injected context blocks are stripped, and an identical
  still-unread block is treated as a double hook fire, not a repeat.
- **Voice-friendly output**: while narration is on, a `UserPromptSubmit` hook
  (`scripts/voice-style-hint.sh`) injects a reminder to write replies for the ear —
  plain conversational prose, and avoid markdown tables, code blocks, bullet lists,
  headings, symbols, and long file paths/identifiers (describe them in words). The
  spoken text already strips code/markdown, but this also keeps the *visible* reply
  spoken-style so what's read matches a natural narration.
- **Personality mode** (`personality on`, default off): the personality lives in the
  *words*, not the audio — the Personal Voice already sounds like its namesake, so this
  shapes how the reply is written. When on, the same `UserPromptSubmit` hook appends a
  `<talktome-personality>` block carrying the current voice name. If that name is a
  recognizable public figure or character, the agent subtly colors the reply with their
  speaking persona — cadence, warmth, characteristic phrasing — while keeping every fact
  accurate. It's tasteful homage, never caricature, and never invents quotes or claims
  attributed to a real person. Example: a Morgan Freeman voice reads calm, wise, measured
  and reflective. If the voice is just an ordinary person's name (or `auto`), narration
  stays neutral. State lives in `state/personality`; it's global, independent of the
  on/off narration scope.
- Pause/resume from anywhere: the "Pause Talking" Quick Action sends `SIGUSR1` to
  talk-reader-live (`pkill -SIGUSR1 -x talk-reader-live`), which toggles pause. Space/Esc work
  when the panel itself is focused. Three Quick Actions total: Talk To Me, Pause
  Talking, Stop Talking — each gets a hotkey in System Settings → Keyboard Shortcuts.
- Narration ON speaks every response until turned off. A new response **interrupts**
  the previous one (no overlapping voices); the notify chime plays first (0.8s lead).
- `stop` / `pause it` kills the currently-playing speech but leaves narration enabled.
  `off` stops speech AND disables narration.
- Default voice is "auto" (first available Personal Voice); only fully-recorded Personal Voices are usable.
- Rate is a multiplier on Apple's default (1.0 = normal; many find 1.5 too fast).
- Fenced code blocks and markdown punctuation are stripped before speaking.

## (Re)installation

`bash ~/.claude/skills/talk-to-me/scripts/install.sh` — idempotent. Builds the engines,
registers the streaming hooks (Stop + PreToolUse + prompt echo) in
`~/.claude/settings.json`, and installs both Quick Actions
to `~/Library/Services`. Then assign hotkeys in System Settings → Keyboard →
Keyboard Shortcuts → Services, and restart Claude Code so the hooks load.

The former `talk-to-me-too` skill (streaming + live panel) was folded in here on
2026-08-28; only two forwarding shims remain at the old path for sessions started before
the fold.
