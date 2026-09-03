---
name: loop-pre-flight
description: >
  Loop Pre-Flight mode (✈️) — a toggle-on pre-launch check that, before any substantial task,
  sharpens the prompt and right-sizes the execution so you stop over-orchestrating. On every
  substantive request it runs a fast gate and gives a one-line verdict, then proceeds:
  (1) finish-line — does the ask have a verifiable end state + runnable check + guardrail + cap,
  or is "done" a vibe? (2) shape — climb the ladder (one prompt → workflow → agent → multi-agent);
  is it genuinely parallel with little shared context, or should it run inline? scale agents to
  complexity (don't spawn 100). (3) plan-mode — big / cross-cutting / ambiguous refactor → propose
  plan mode FIRST. (4) runtime — /loop vs Workflow vs inline, cache-aware delays, maker≠verifier.
  Use when the user says "loop pre-flight", "pre-flight on/off", "pre-flight mode", "/loop-pre-flight",
  "check my prompt", "right-size this", "should I fan this out", or before firing a loop / workflow / refactor.
---

## What this mode does

When ACTIVE, **before** doing any substantial task (a loop, a workflow, a multi-file change,
a `/goal`, a refactor), run a fast **preflight gate** and emit a terse verdict, *then act*.
The point is to catch the three recurring waste patterns at launch:

- firing a **workflow** at work that isn't actually parallelizable,
- **over-spawning** (50–100 agents for a job that wants 3, or 1),
- **skipping plan mode** on a big refactor and then steering it by hand.

Default posture is **advise-and-proceed, not block.** Most requests get a one- or two-line
verdict and you keep moving — recreating per-turn friction is the thing this mode exists to kill.
Only **hard-stop** (propose plan mode and wait) for the genuinely big / destructive / ambiguous case.

Source field guides (read for depth when a call is non-obvious):
`~/knowledge base/loop-and-goal-prompts.md` · `~/knowledge base/agent-workflows.md` · `~/knowledge base/loop-runtime-and-caching.md`

---

## Activation (per-session toggle + ✈️ badge)

This mode is **per-session** and drives the ✈️ badge in the status bar via a session-keyed marker
(same convention as `multitask`). A fresh session has no marker, so it reads **OFF** everywhere.

- **On activate** (user turns it on), run once, silently, then confirm in one line that pre-flight is on (✈️):
  `mkdir -p ~/.claude/loop-pre-flight/sessions && touch ~/.claude/loop-pre-flight/sessions/$CLAUDE_CODE_SESSION_ID`
- **On deactivate**, run once:
  `rm -f ~/.claude/loop-pre-flight/sessions/$CLAUDE_CODE_SESSION_ID`

While the marker exists, a `UserPromptSubmit` hook re-injects a one-line reminder each turn, so the gate
keeps firing even after this body scrolls out of context — that reminder, not memory, is what makes it durable.

---

## The gate (run in order; skip rungs that obviously pass)

### A. Finish-line — is this a goal or a wish?
> "If you can't say what 'done' looks like, you don't have a loop. You have a wish."

A launchable task has four parts — name any that are missing and fill them in:
1. **End state** — a concrete condition, not a vibe ("no blanks in Category", not "tidy it up").
2. **A runnable check** the agent can evaluate *itself* — a test, exit code, count, "no X remain".
   - For `/goal`: the evaluator is **blind** (no tools, no files) — the check only works if it forces
     the proof into the transcript. "pytest exits 0" works; "well implemented" doesn't.
3. **One guardrail** — the thing it must never do ("don't delete", "don't touch other files", "draft, don't send").
4. **A cap** — turn or budget ceiling so a stuck run can't burn forever.
5. **A verifier that isn't the maker** — the check is owned by the environment (test / lint / count) or a
   separate skeptical reviewer, *never* the maker's own "looks done." Self-grading is the #1 reliability failure.

Reframe imperatives as verifiable goals: "fix the bug" → "write a test that reproduces it, then make it pass."

**Unattended + mutating or sending?** (a loop that writes files, deletes, ships PRs, or sends messages):
start **read-only / draft-only** first, require an explicit guardrail, and give it an escalation path
(after N failures, stop and surface to a human — don't retry forever). A missing guardrail here is a
near-hard-stop, not a fill-in.

### B. Shape — what execution does this actually want?
Climb the ladder, **stop at the first rung that holds** (cheapest first):
1. **One prompt / inline** — most tasks end here. Try this first.
2. **A workflow** — fixed, *predefined* steps you can name up front.
3. **An agent** — open-ended; the model must decide the steps at runtime.
4. **Multi-agent fan-out** — only when genuinely parallel **and** worth ~15× the tokens.

Two questions decide it:
- **Is the work genuinely parallel with little shared context?** If a later step depends on an
  earlier one, or all parts need the same context → **it's not parallelizable. Run inline / single agent.**
  (Most coding tasks are this. Multi-agent *loses* on shared-context and dependency-heavy work.)
- **Workflow vs agent:** do *you* know the steps (workflow) or must the *model* decide them (agent)?

**Right-size the agent count — scale effort to complexity, don't default to a swarm:**
| Task | Agents |
|---|---|
| Simple fact-find / lookup / single edit | **1** (inline) |
| Direct comparison, a few independent angles | **2–4** |
| Genuinely complex, many independent directions | **10+**, clearly divided |

Reach for a **better model before more agents** — "upgrading the model is a larger gain than doubling the budget."
If you do fan out: each subagent needs **objective + output format (schema) + scoped tools + boundaries**,
and **maker ≠ verifier** (a separate skeptical grader, never self-grading).
If fan-out agents **edit files in parallel**, give each `isolation: "worktree"` so their writes can't collide.

### C. Plan-mode — does this need a plan before a single edit?
**Propose plan mode first and wait for the user to enter it** (Shift+Tab → Plan) when the task is any of:
- a **refactor touching many files** or a cross-cutting / architectural change,
- **destructive or hard to reverse** (deletes, migrations, mass renames, schema changes),
- **scope is ambiguous** ("clean up X", "refactor everything") — pin it down before editing.

For these, the verdict is a hard stop: *"This is a N-file cross-cutting refactor — plan mode first."*
Otherwise, no plan needed; proceed.

### D. Runtime — only if it's a loop / scheduled / long-running
- **`/loop` vs Workflow vs inline:** `/loop` repeats one task self-paced; Workflow orchestrates many agents
  deterministically; inline is everything else. Don't reach past inline without a reason.
- **`delaySeconds` is cache-aware:** the prompt cache is a warm container with a **~5-min TTL**.
  Stay **<270s** to poll warm, or go **1200s+** to amortize one cache miss. **Never 300s** (worst of both).
- **Don't poll harness-tracked background work** — it re-invokes you automatically. Use a long fallback (1200s+), not a tight poll.
- **Memory loop:** repeating work needs a state file it reads at start / writes at end, so it doesn't redo old work.

---

## Verdict format (keep it terse)

One compact block, then act. Example (advise-and-proceed):

```
pre-flight ✈️
  shape:  single agent inline — shared context, not parallelizable (skipped: workflow)
  prompt: added check → "pytest -q exits 0, no unrelated test modified; stop after 25 turns"
  plan:   not needed
```

Example (hard stop):

```
pre-flight ✈️  HOLD
  shape:  14-file cross-cutting refactor → plan mode first
  reason: scope is broad + many call sites; pin the plan before editing
```

If every rung obviously passes, collapse to a single line (`pre-flight ✈️ inline, prompt is launch-ready`) and proceed.

---

## Persistence

**Off by default. Per-session only** — enforced by the marker in *Activation* above, not just intent, so a
fresh session reads OFF for both the model and the status bar. Turning it on with `/loop-pre-flight` applies to
the current session only and never leaks to others. While on, run the gate on every substantial request; do not
drift back to launching first and sizing later (the `UserPromptSubmit` reminder backstops this). Trivial
one-step asks don't need the full block — a single line or silence is fine.

## Trigger phrases

**Mode ON** (sticky; writes the marker, turns on the ✈️ badge): "loop pre-flight", "pre-flight on", "pre-flight mode", "/loop-pre-flight"
**Mode OFF** (removes the marker): "stop pre-flight", "pre-flight off", "/loop-pre-flight off", "normal mode"
**One-off** (run the gate once on this request, answer, then *do NOT* toggle the mode or write the marker):
"check my prompt", "right-size this", "should I fan this out", "size this before I run it"
