---
name: session-state
description: Manage a .claude/STATE.md file for token-efficient cross-session context handoff. Caveman-style, high-density format. Three verbs: /session-state update (append checkpoint mid-session), /session-state close (finalize at end of session), /session-state read (orient at session start). Always write STATE.md to the project root at .claude/STATE.md.
argument-hint: "update | close | read"
---

Manage `.claude/STATE.md` — the single source of truth for cross-session context. Format is caveman-style: ultra-compressed, no articles, no filler, bullets only, timestamps as `HH:MM`.

## STATE.md format

```
# STATE — <project> — <YYYY-MM-DD>

## NOW
<one line: what's in flight right now>

## NEXT
1. <immediate next action>
2. <following action>

## DONE
- HH:MM <what shipped> [<commit-sha if any>]
- HH:MM <decision made + why in ≤8 words>

## CONSTRAINTS
- <binding rule / hard limit discovered this session>

## FILES
- <path> — <what changed, 5 words max>

## OPEN
- <unresolved question or blocker>
```

Rules:
- No prose. No "we decided to". Just the fact.
- DONE entries: append-only, newest last.
- NEXT: overwrite each update, keep ≤3 items.
- CONSTRAINTS: permanent until explicitly removed.
- OPEN: remove when resolved.

---

## Verbs

### `update` (mid-session checkpoint)
Append to DONE what just completed. Rewrite NEXT with current top actions. Add any new CONSTRAINTS or OPEN items. Add FILES touched. Keep NOW current. Do not rewrite the whole file — surgical edits only.

### `close` (end of session)
Finalize STATE.md for handoff:
1. Move anything in-progress to DONE or NEXT (nothing ambiguous).
2. Rewrite NEXT so item 1 is the single most important action for the next session.
3. Add a `## HANDOFF` block at the bottom:
   ```
   ## HANDOFF
   - Start: cd <worktree-path> && <env cmd if needed>
   - Branch: <branch>
   - Tree: clean / uncommitted: <file> — <reason>
   - Skills: <suggest /skill-name for next session>
   ```
4. Commit outstanding work if any (conventional commit, specific files only).

### `read` (session start / orient)
Read `.claude/STATE.md`. Output a 3-bullet orient:
- **Resuming:** <NOW value>
- **First action:** <NEXT item 1>
- **Watch:** <CONSTRAINTS or OPEN items worth flagging>
Then ask: "Continue, or different focus?"

---

## File location
Always `.claude/STATE.md` in the project root (not /tmp). Create `.claude/` if it doesn't exist. If no project root is detectable, use the current working directory.

## If STATE.md doesn't exist
On `update` or `close`: create it from scratch using the format above. On `read`: say "No STATE.md found — clean session."
