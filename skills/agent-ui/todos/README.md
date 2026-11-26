# todos

A floating always-on-top macOS panel that stacks every agent's checklist and animates each step as it moves: a check pops, the row glows, the bar fills, the active step pulses.
Right-click to collapse it to a pill of Harvey balls.

## Requirements

macOS with Xcode command line tools (`swiftc`) and `python3`.

## Install

```bash
cp -r skills/agent-ui/todos ~/.claude/skills/
```

No build step to run by hand: `scripts/todos.sh start` compiles `scripts/Todos.swift` on first use.
Try it:

```bash
T=~/.claude/skills/todos/scripts/todos.sh
sh $T new demo "Demo" "a:First step" "b:Second step"
sh $T start
sh $T step demo a active
```

See `SKILL.md` for every command.
