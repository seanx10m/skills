---
name: iterm-wt-handoff
description: Hand off active dev work to a fresh agent AND launch that agent in a new iTerm2 pane directly below the current one (or a new tab, window, or right-hand split if asked), already cd'd to the worktree and already reading the handoff doc. Commits outstanding work, records the worktree, writes a terse handoff doc, then spawns the agent. macOS only. Use when the user says "/iterm-wt-handoff", "iterm handoff", "hand this off and open it in iTerm", or wants the next session started for them in iTerm2.
argument-hint: "What will the next agent session focus on?"
---

You are handing off active work to a **fresh agent** and then launching that agent yourself in a new iTerm2 pane, already in the worktree and already reading the handoff doc. Steps 1-4 write the doc; Step 5 launches; Step 6 confirms. Follow them in order.

Do not abbreviate the handoff because a launch is coming. The doc is the entire payload the new agent gets - it starts with an empty context and this one file.

`$ITERM` below means the `scripts/` directory next to this file.

**The normal case is continuation on the SAME worktree, same branch.** Assume that unless the user says otherwise. It changes what the doc is for: the code, the commits, and the branch state all survive on disk and the incoming agent can read them. What does NOT survive is everything that only ever existed in the outgoing session's context - decisions made and their reasons, approaches tried and rejected, gotchas discovered the hard way, and what the user actually said they wanted. That is the payload. Do not spend the doc re-describing code the next agent can read.

## Step 1 - Commit outstanding work

Before writing the doc, ensure the outgoing agent's work is committed:

1. Run `git status` and `git diff --stat`.
2. If there are uncommitted changes relevant to the task, commit them now using conventional commits (`feat:`, `fix:`, `chore:`, `docs:`). Stage specific files - never `git add -A`.
3. If nothing to commit, note that the tree is clean.

Do NOT skip this step. A handoff on an uncommitted tree loses work.

## Step 2 - Identify the worktree

Run `git worktree list` to get the canonical path and branch for the current worktree. Record both - the incoming agent must `cd` to this exact path before doing anything.

**Verification, not narration:** a bare `cd` does not reliably persist across tool-call turns. Landing on the worktree means running `cd <absolute-path> && pwd && git branch --show-current` **as one command** and reading the actual output - never report "on the correct worktree" from a prior turn's `cd` alone. The `Start:` line in the doc (Step 4) should already be a full `cd && ...` chain for this reason; the incoming agent re-verifies it before the first real command too.

## Step 3 - Resolve ambiguity before writing

Read the conversation and the task backlog carefully. Only ask the user a question if, after that reading, you still cannot determine:

- Which tasks are done vs. still in progress
- What the next concrete step is
- Whether the next agent should continue on this branch or a new one

Ask at most 2 clarifying questions. Do not ask things you can infer from context. If you are confident, skip this step entirely.

## Step 4 - Write the handoff document

Save to `/tmp/wt-handoff-<branch-slug>-<date>.md`, not the workspace. Be terse - no prose padding.

```
# Handoff - <branch> - <date>

## Worktree
- Path: <absolute path>
- Branch: <branch>
- Start: cd <path> && pwd && git branch --show-current && <env setup if any>

## Task
One sentence: what this agent is doing and why.
- Modules / seams / adapters touched: <list> (link ADR if the change is motivated by one)
- Constraint: <the binding constraint or design rule driving the approach, if any>

## Done
<bullets - commit SHAs, ADR refs, file paths. No re-writing content already in those artifacts.>

## Decided this session
<The reasoning that dies with this context. Each bullet: the call, and why.
Include approaches tried and abandoned with the reason they failed - that is what
stops the next agent re-walking a dead end. Include gotchas found the hard way
(a flag that must be set, a test that lies, an ordering trap). Include anything
the user said that constrains the work, quoted or close to it. Omit only if the
session genuinely made no decisions.>

## Tree state
Clean. / Uncommitted: <file> - <one-line reason>

## Next steps
1. <immediate next action>
2. ...

## Open questions
<omit section if none>

## Suggested skills
<skills or slash commands the next agent should load, if any>

---
Last task? Suggest: run a code review (e.g. `/code-review`) when done.
```

Redact secrets and PII. If arguments were passed, tailor Task and Next steps to them.

## Step 5 - Launch the incoming agent

```bash
"$ITERM"/iterm-spawn \
  --cwd "<absolute worktree path>" \
  --title "handoff · <repo name>" \
  -- claude "Read <handoff doc path> and execute the Next steps in it, in order."
```

- **The agent command is everything after `--`.** The default is `claude "<prompt>"` (Claude Code). If the user runs a different agent CLI, a wrapper, or a shell alias, put that in place of `claude` - the script runs whatever follows `--` in the new shell. Pass several words to have each one shell-quoted (the first word is left bare so a shell alias still expands), or a single string to run it exactly as written.
- `--cwd` is the worktree path from the handoff doc's `Worktree > Path`, verbatim and absolute.
- The prompt stays short and points AT the doc. Never inline the handoff content into the command - it is a shell argument.
- **Placement defaults to a pane split directly below the pane this session runs in** (found via `$ITERM_SESSION_ID`, so it is correct even if focus moved). If the user asks for a different spot, add the matching flag:
  - "new tab" -> `--tab`
  - "new window" -> `--window`
  - "to the right" / "side by side" -> `--right`
  - "below" or nothing said -> no flag (default)
- Text is written to the new session object, so it cannot land in the wrong terminal.
- `--title` sets the tab title (OSC escape). `--color` (`black red green yellow blue magenta cyan white`) colours the tab; omit it unless asked.
- First run may prompt for macOS Automation permission (terminal controlling iTerm2). Approve it once.

## Step 6 - Confirm

Two lines: the doc path, and that the agent is running in a new iTerm2 pane on `<branch>`.

Do not follow the incoming agent's work. This session's job ends at the launch.
