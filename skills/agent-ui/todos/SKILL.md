---
name: todos
description: Show a small always-on-top todo panel in a corner of the Mac that stacks every agent's checklist and animates step changes as work moves - a check pops, the row glows, the bar fills, the active step pulses. Use when the user says "/todos", "show the todos", "floating todos", "track this in the corner", or asks to see what the agents are working on, step by step, while they do something else. Needs macOS with a shell (Claude Code, Cowork).
---

# todos

A tiny native Mac panel that floats over every app and Space, never takes focus, and remembers where you drag it.
It reads every `<name>.json` in one folder and re-renders within a second of any change, with an animation for each changed step and a soft Tink.
Reduce Motion on = no animation, no pulse.

## Commands

One panel stacks every `*.json` list in a folder (default `~/.todos/current`), so several agents can each own one file.
All in `scripts/todos.sh` inside this skill:

```sh
T=~/.claude/skills/todos/scripts/todos.sh
sh $T start                                   # show the panel (corner br|bl|tr|tl as 2nd arg, only until dragged)
sh $T new agent-1 "Release 2.0" "a:Write notes" "b:Fix login bug"   # one file per agent/list
sh $T new research "Research" --percent 20    # no steps yet: a % list
sh $T percent research 60
sh $T step agent-1 a active                   # todo | active | done -> animates
sh $T stop                                    # closes the PID in <dir>/.pid
```

In the panel: click a list title to fold it to one line (Harvey ball + %); double-click empty space for dense mode (active steps only, plus a quiet "+N more" row per list that expands it, so nothing looks lost).
Collapse: right-click the panel for one item, Collapse. The panel shrinks to a pill of Harvey balls (one per list, a pulse dot while a step is active); click the pill, or right-click > Expand, to open it. No chrome on the panel. Remembered.
A list shows % until it has steps, then it is step-based.

## Rules

- Keep step titles short and dense (2-5 words).
- Exactly one step `active` at a time unless real work runs in parallel; it pulses.
- Mark `done` only when the user accepted it, never on an agent's own read.
- Update the step the moment state changes; the animation is the point.
- Stop only the PID in `<dir>/.pid`. Never kill by name.
- The binary builds on first `start` (`swiftc`), next to the source.

## <name>.json

```json
{"title":"Release 2.0","steps":[{"id":"a","label":"Write notes","state":"done"}]}
```
