---
name: text-me
description: Send a message or files to your own iMessage self-chat from a local script. Use whenever the user says "text me", "text me this", "send it to my phone", or asks for a file to land in iMessage. Also covers diagnosing iMessage send failures (error 25).
---

# Text me

Sends to the user's iMessage self-chat via `osascript` and Messages.app.
No browser, no computer-use, no synthetic input - it is a local script.

```bash
~/.claude/skills/text-me/scripts/text-me.sh "message"
~/.claude/skills/text-me/scripts/text-me.sh "here's the render" /path/to/file.mp4
~/.claude/skills/text-me/scripts/text-me.sh "" /path/a.wav /path/b.mp4   # files only
```

The script stages, sends, waits for delivery, prints per-file status, and cleans up.
Recipient defaults to `${TEXT_ME_TO:?set TEXT_ME_TO to your iMessage number}` (your own number); override with `TEXT_ME_TO`.

## The one thing that matters: staging

**Messages.app is sandboxed.** An AppleScript file alias does NOT mint a sandbox
exception the way the UI's drag / open-panel does. Send a file from `~/Desktop`,
`~/Music`, `~/Documents`, or `/tmp` and Messages accepts the send, fails to open the
file, and writes `error=25` / `transfer_state=6` - the bubble reads **Not Delivered**.

Copy the file into a path in Messages' entitlements first, then send from there.
`~/Library/Messages/` is the one that actually works:

```bash
S=~/Library/Messages/Attachments/_textme && mkdir -p "$S"
cp "/path/to/file" "$S/"
osascript -e 'tell application "Messages" to send (POSIX file "'"$S/file"'" as alias) to participant "${TEXT_ME_TO:?set TEXT_ME_TO to your iMessage number}"'
rm -rf "$S"
```

This is exactly what the UI does - working attachments in `chat.db` all live under
`~/Library/Messages/Attachments/`.

### Entitled paths

`codesign -d --entitlements - /System/Applications/Messages.app`

| Path | Entitlement | Works from AppleScript? |
|---|---|---|
| `~/Library/Messages/` | `temporary-exception.files.home-relative-path.read-write` | **yes - use this** |
| `~/Media/`, `~/Library/SMS/`, `~/Library/Caches/com.apple.MobileSMS/` | same | untested |
| `/private/var/tmp/com.apple.messages/` | `temporary-exception.files.absolute-path.read-write` | untested |
| `~/Downloads` | `files.downloads.read-write` | **no - still error 25** |
| drag / open panel | `files.user-selected.read-write` | n/a (UI only) |

`~/Downloads` being entitled and still failing is the trap.
Do not assume an entitlement in the list is enough - stage in `~/Library/Messages/`.

## Text vs attachments

Plain text needs no staging and works directly:

```bash
osascript -e 'tell application "Messages" to send "hello" to participant "${TEXT_ME_TO:?set TEXT_ME_TO to your iMessage number}"'
```

Only attachments hit the sandbox problem.

## Verify - always

`osascript` exits 0 on a send that silently fails. Never report success off the exit code.
Read `chat.db` instead:

```bash
sqlite3 ~/Library/Messages/chat.db "select m.is_sent, m.error, a.transfer_state,
  round(a.total_bytes/1048576.0,1)||'MB', substr(a.filename,-30)
  from message m
  join message_attachment_join j on j.message_id=m.ROWID
  join attachment a on a.ROWID=j.attachment_id
  where a.is_outgoing=1 order by m.date desc limit 3;"
```

| Reading | Meaning |
|---|---|
| `is_sent=1, error=0, transfer_state=5` | delivered |
| `error=25, transfer_state=6` | sandbox - the file was outside an entitled path |
| `is_sent=0, error=0, transfer_state=5` | still in flight, keep polling |

Large files take time.
188MB took roughly 45s to flip `is_sent` to 1, so poll rather than checking once.

## Finding the self-chat

your own handle is `${TEXT_ME_TO:?set TEXT_ME_TO to your iMessage number}`, self-chat is `chat.ROWID=1`, guid `any;-;${TEXT_ME_TO:?set TEXT_ME_TO to your iMessage number}`.
If that ever changes, the account handle is in the DB:

```bash
sqlite3 ~/Library/Messages/chat.db "select distinct destination_caller_id from message where is_from_me=1;"
```

A self-chat splits almost exactly 50/50 sent/received, because each message is recorded
twice - once outgoing, once as the receipt copy. Do not mistake that for a two-way thread.

## Gotchas

- Size is not the limit people assume. A 188MB wav went through fine.
- Filenames with `:` and `|` arrive from yt-dlp as fullwidth `：` and `｜`. Quote every path; copy the real name from `ls` rather than retyping.
- Failed bubbles cannot be deleted by script. They sit in the thread as "Not Delivered" until the user removes them by hand - so verify before spamming retries.
- Clean up the staging dir after sending. Leaving 188MB copies inside `~/Library/Messages/Attachments/` bloats the Messages store.
- The Messages AppleScript dictionary is half-broken on current macOS. `name of every account` errors `-1728`; `id of every account` works. Do not read an account error as a send failure.
- Reading the unified log (`log show`) needs admin. your account is not in `admin`, so that diagnostic route is closed - use `chat.db` instead.

## Scope

Self-chat only.
Per the user's Slack rule, never message another person unless he explicitly names the recipient in that request.
