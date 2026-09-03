---
name: dream-outcome
description: >
  Dream Outcome mode (🏝️) — a toggle-on posture that flips the default from *narrating the plan*
  to *showing the destination*. When ACTIVE, before any substantial build (a feature, a UI, an
  architecture, a refactor, a multi-step task), do NOT lead with an implementation walkthrough.
  Instead produce one simple, elegant, interactive artifact that lets the user SEE what the end
  result will look like — a self-contained HTML mockup of the final UI, a clickable prototype, a
  small animation, or a crisp visual of the architectural decision — open it in the browser, and
  keep the prose to a few lines. It is the sibling of loop-pre-flight (✈️): pre-flight right-sizes
  *how* the work runs; dream-outcome shows *what the work produces* before building it. Toggle per
  session or globally. Use when the user says "dream outcome", "dream outcome on/off", "/dream-outcome",
  "show me the end result", "show me what it'll look like", "less plan more picture", "stop describing
  just show me", or complains that an agent is talking about implementation instead of showing the outcome.
---

## What this mode does

This mode does **not** stop you from planning. It changes **what the user reviews.**

Still build the implementation plan — file layout, phases, sequencing — you need it to do the work.
But that plan is **for the agent, not the review surface.** It goes behind the fold: write it to a
file, hold it in plan mode, or keep it ready to expand on request. What you put in front of the user
to approve is **one artifact that shows the finished thing**, plus at most a few lines of prose.

The recurring waste this kills: an agent spends its whole reply making the user read *how* it will
build something, when the user only cares *what it will look like when it's done* — and can only
really judge the plan by seeing that outcome anyway. So show the destination; that's the thing they
sign off on. The route stays your concern, available if they ask to see it.

Sibling mode: **loop-pre-flight (✈️)** — `~/.claude/skills/loop-pre-flight/SKILL.md`.
Pre-flight right-sizes *how* a task runs (shape, agent count, plan-mode). Dream-outcome shows
*what* the task produces before a line of real code exists. Run both when active: pre-flight's
verdict can be one line; the dream artifact is the centerpiece.

---

## The posture (what to do on a substantial build request)

1. **Pick the lightest artifact that conveys the outcome.** Stop at the first that fits:
   - **UI / app / page** → a single self-contained **HTML mockup** of the *final screen*, real-ish
     content, real layout, the one primary interaction wired with a little CSS/JS. Open it in the browser.
   - **Flow / multi-screen** → a tiny **clickable prototype**: 2–4 states toggled from one HTML file.
   - **Architecture / data-flow / agent topology / a decision between options** → a crisp **diagram**
     (Mermaid `graph TD`, per global rules) or a side-by-side of the 2–3 options, rendered visually.
   - **A behavior / transition / "feel"** → a small **animation** in HTML/CSS that demonstrates it.
   - **Pure logic / data shape** → a worked **example of the final output** (the actual JSON/table/CLI
     output the user will get), not a description of the code that makes it.

2. **Make it real, not lorem — and make it look like *their app*.** Use plausible content, the
   user's actual domain, real labels. Don't ship generic Bootstrap-looking HTML: ground the mockup
   in the **target app's own front-end style** first (see "Use the app's design tokens" below).
   One elegant primary action wired and clickable beats ten static boxes.

3. **Open it so they can see it.** Write the artifact to a file and open it visually — reuse
   `browser-preview` for Markdown+Mermaid docs, or `open <file>.html` for a standalone mockup.
   Never paste raw Mermaid or a wall of HTML into the chat (per global rules).

4. **Then shut up — but keep the plan ready.** A few lines max: what they're looking at, the one
   open question that changes the outcome (if any), and "want this for real? say go." No phase list,
   no file tour, no library rationale *in the reply* — but you should still have that plan formed
   (tucked in a file, plan mode, or one expand-on-ask away: "say 'show the plan' for the how"). The
   artifact is the **approval gate**; the plan is the thing it gates. If pre-flight (✈️) is also on,
   its verdict collapses to one line.

5. **Build only on go.** The artifact is a throwaway preview the user signs off on. Their "go"
   approves the *outcome*; the plan you already formed is what you then execute (and *then* the
   plan/altitude talk is welcome, if they want it).

## Use the app's design tokens (not generic HTML)

The mockup should be mistakable for the real product, not a fresh blank-canvas page. **Before
writing any CSS, pull the target app's own style** so colors, type, spacing, and components match:

1. **Find the tokens.** Grep the project's front-end for where style lives — CSS custom properties
   (`--color-*`, `--space-*`, `theme.css`, `tokens.css`), a Tailwind config, a theme file, or a
   component library entry point. Copy the real hex/rem values into the mockup; don't eyeball them.
2. **Copy a real component.** If the app has a Button/Card/Input you can read, port its markup +
   classes rather than inventing one. Reuse beats reinvention here too.
3. **Use a project style skill if one exists.** e.g. `brand-frontend` for brand-styled UI — it reads
   the real component cache. Match whatever stack/brand is known.
4. **Only fall back to neutral defaults** when the app has no discoverable front-end (backend-only
   repo, brand-new project). Say so in one line when you do.

The point is fidelity: the user judges the outcome by seeing *their* product finished, so the closer
the artifact sits to their actual FE, the more real the sign-off.

## Reuse, don't reinvent

This mode is a posture, not a renderer. Lean on what's installed:
- `prototype` / `baoyu-design` skills for richer mockups and design explorations.
- `browser-preview` to render a Markdown doc (with Mermaid diagrams + tables) to the browser.
- Plain `open file.html` for a one-off self-contained mockup.

## When NOT to dream

Skip the artifact and just answer for: trivial one-liners, pure questions, debugging an existing
thing, or anything where there is no "outcome to look at" (a config change, a git operation, a
factual lookup). Don't manufacture a mockup for work that has no visual or structural surface —
that's just a different kind of stalling. If unsure whether the artifact helps, ask one line.

---

## Activation (per-session toggle + global toggle + 🏝️ badge)

Resolution mirrors caveman/talk-to-me: an explicit **per-session OFF** wins, else a **per-session ON**
marker, else the **global** flag. So a fresh session inherits the global default but can be flipped
locally without leaking.

- **Session ON** (default activation): `mkdir -p ~/.claude/dream-outcome/sessions && touch ~/.claude/dream-outcome/sessions/$CLAUDE_CODE_SESSION_ID && rm -f ~/.claude/dream-outcome/sessions/$CLAUDE_CODE_SESSION_ID.off`
- **Session OFF**: `mkdir -p ~/.claude/dream-outcome/sessions && rm -f ~/.claude/dream-outcome/sessions/$CLAUDE_CODE_SESSION_ID && touch ~/.claude/dream-outcome/sessions/$CLAUDE_CODE_SESSION_ID.off`
- **Global ON** ("globally", "everywhere", "by default"): `touch ~/.claude/dream-outcome-on`
- **Global OFF**: `rm -f ~/.claude/dream-outcome-on`

After flipping, confirm in one line (🏝️). While active, a `UserPromptSubmit` hook re-injects a
one-line reminder each turn, so the posture survives this body scrolling out of context.

## Trigger phrases

**Mode ON** (sticky session): "dream outcome", "dream outcome on", "dream mode", "/dream-outcome",
"show me the end result", "show me what it'll look like", "less plan more picture", "stop describing just show me"
**Global ON**: "dream outcome globally", "dream outcome everywhere", "dream outcome by default"
**Mode OFF**: "stop dream outcome", "dream outcome off", "/dream-outcome off", "normal mode"
**One-off** (do it once for this request, don't write any marker): "dream this one", "just show me the outcome for this"
