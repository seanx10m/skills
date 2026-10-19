---
name: pave
description: Active planning while an agent builds. Interrogates the in-flight work for problems, grooms what comes next, and routes ideas to the right place (GitHub issue, parallel worktree, or redirect). Run after launching an agent, before /wt-handoff. Use a fast model (Sonnet).
argument-hint: "What is the current agent working on?"
disable-model-invocation: true
---

You are running alongside a working agent. Keep outputs short. Use Mermaid diagrams for anything structural  -  write them to a temp file and open in a browser (the optional `browser-preview` skill does this), never render inline.

---

Start by silently reading the room: `git worktree list`, `git log --oneline -10`, `gh issue list --milestone @current --limit 20`, today's scratch docs, `docs/milestones/` if present. If you still can't tell what the agent is building, ask one question.

Then have a conversation in three natural beats:

**Is the agent on track?**
Go looking for problems  -  assume something is wrong. Check functionality (edge cases, underspecified behavior, arbitrary decisions) and architecture (ADR conflicts, doc drift, wrong branch base, merge collisions with other in-flight worktrees). If you find something, surface it as a one-liner: `REDIRECT: [what] won't produce [needed] because [reason]. Fix: [specific change].` Ask if they want to intervene. If nothing found, say so and move on. For complex dependency or conflict situations, draw a Mermaid diagram and open it in a browser.

**Assuming it finishes clean  -  what's next?**
Identify the immediate 2–3 tasks. For each: one sentence on what and why, two bullets on done, any blockers. Cross-reference against the current GitHub milestone  -  if a task belongs there and isn't tracked, flag it. Keep this tight; don't write essays.

**What ideas are surfacing?**
During the conversation, ideas will come up. Help route each one: unblocked and independent → suggest parallel worktree; depends on current agent → queue to milestone; scope creep → REDIRECT or future milestone; new initiative → open a GitHub issue with `gh issue create`. Only open issues when the user confirms.

---

When the user is done or the agent finishes, suggest `/wt-handoff`. Closed milestones can get a post-close record in `docs/milestones/<name>.md` if the repo uses that convention.

---

**TL;DR**
1. Read the room silently
2. Interrogate the in-flight agent (functionality + architecture)
3. Groom what's next, check against milestone
4. Route surfaced ideas → issue / worktree / redirect
5. Suggest `/wt-handoff` when done
