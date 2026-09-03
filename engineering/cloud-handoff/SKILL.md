---
name: cloud-handoff
description: Hand off in-progress local work to a Claude Code cloud session when the user has to leave his machine. Commits the working tree to an ephemeral wip/ branch with a .claude/STATE.md handoff, pushes it, then Slack-DMs the user the ready-to-paste launch prompt so he can start the cloud session from his phone. Use when the user says "/cloud-handoff", "hand this off", "I'm leaving, keep going in the cloud", "send this to the cloud", "take this to Slack".
argument-hint: "[one-line goal for the cloud session]"
---

the user is walking out the door. Get the work to the cloud without him opening a browser.

**Git is the only transport.** A cloud session is always a fresh clone with no access to
his local files, env vars, or locally-configured MCP servers. Anything not pushed does not exist.

Three carriers:
- The **ephemeral `wip/` branch** carries the diff.
- **`.claude/STATE.md`**, committed on that branch, carries the intent.
- The **Slack DM to himself** carries the launch prompt.

## 1. Ephemeral branch — required

```bash
cd "$(git rev-parse --show-toplevel)"
git worktree list          # >1 entry => absolute paths for the rest of this skill
BR="wip/$(date +%m%d-%H%M)-<slug>"
git checkout -b "$BR"
```

Slug from the goal, kebab-case, 3 words max.

## 2. Write the intent

Run the `session-state` skill's `close` verb to produce `.claude/STATE.md`.
Add one line under `## HANDOFF`:

```
- Cloud goal: <the $ARGUMENTS one-liner, or the top NEXT item>
```

## 3. Commit everything and push

```bash
git add -A && git commit -m "wip: handoff $BR" && git push -u origin "$BR"
git status --porcelain     # must be empty
```

Untracked scratch files included. The clone sees only what is pushed.
Never push to `main` or to the branch he was actually working on. `wip/` branches are throwaway.

## 4. Slack him the launch prompt

Send to **his own DM** with `mcp__slack-plus__send_message`, destination `U09Q295MASD`.
Also `pbcopy` it and print it in full in the terminal.
This send is pre-authorized by invoking the skill — do not stop to ask.

```
Start a Claude Code cloud session.

Repo: <org/repo>
Branch: <BR>

First action: read .claude/STATE.md at the repo root. It is the full handoff -
NOW / NEXT / DONE / CONSTRAINTS / FILES / OPEN / HANDOFF.

Goal: <the one-liner>

Work NEXT item 1 first. Commit to <BR>. Reply in this thread when it lands or
when you are blocked - I am on my phone.
```

He copies it from his phone into the Claude DM (`D0AKWMRMJLQ`). Claude replies in-thread
with a `claude.ai/code/session_...` link and runs there, and he steers by replying in that thread.

**Do not try to send it to Claude Tag yourself.** Verified 2026-08-31: Claude Tag ignores
messages posted through the Slack API. A typed `hi` was answered in 16s; an identical `hello`
sent via `chat.postMessage` was never answered. It fails silently.

## 5. Optional — launch it with no paste at all

If he wants it running before he is out of the driveway, `RemoteTrigger` can start the
session directly. This is the supported programmatic path (the `/schedule` skill wraps it),
though a routine is not purpose-built for handoff.

Single `create`, no second call — `run_once_at` about 90 seconds out, fires once, auto-disables:

```json
{"action":"create","body":{
  "name":"handoff: <slug>",
  "run_once_at":"<now+90s, RFC3339 UTC>",
  "job_config":{"ccr":{
    "environment_id":"env_01NnzDuLPyukUMxbWg3Mb464",
    "session_context":{
      "model":"claude-opus-5",
      "sources":[{"git_repository":{"url":"https://github.com/<org>/<repo>"}}],
      "allowed_tools":["Bash","Read","Write","Edit","Glob","Grep"]
    },
    "events":[{"data":{"uuid":"<fresh lowercase v4 uuid>","session_id":"","type":"user",
      "parent_tool_use_id":null,"message":{"role":"user","content":"<the step-4 body>"}}}]
  }}
}}
```

Re-check the clock with `date -u +%Y-%m-%dT%H:%M:%SZ` first — `run_once_at` must be in the future.
Read it back later with `list_runs` then `get_run_log`.

Warn him once: routines can only use claude.ai connectors, not his local MCP servers,
and a routine can only be deleted at `claude.ai/code/routines`, so this leaves an object behind.

## 6. Stop

One line: branch pushed, STATE.md written, prompt in Slack. Nothing else.

## Do not

- Do not open Chrome, `claude-in-chrome`, or `browser-preview`. The whole point is no browser.
- Do not use `text-me` / iMessage. Slack is the delivery channel.
- Do not summarize the session into the Slack message. STATE.md is the summary; the DM is a pointer.
- Do not leave a dirty tree or an unpushed commit.
