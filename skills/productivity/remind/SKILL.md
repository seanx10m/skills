---
name: remind
description: Set reminders in macOS Reminders app from a natural-language request (single or multiple items, with times/dates). Use when the user says "remind me to...", "set a reminder", "/remind", or lists several tasks with a time to be reminded about.
disable-model-invocation: true
---

Parse the request into one or more reminders: `{title, datetime}`.

Rules:
- Split multi-task requests ("order X, call Y, do Z") into separate reminders, same datetime unless stated otherwise.
- Normalize relative dates/times ("tomorrow 11:30am") to `YYYY-MM-DD HH:mm`, 24h clock, using today's date for reference.
- Duration phrases ("for about an hour") get appended to the title in parens, e.g. `Admin tasks (~1hr)`  -  do not invent a second reminder for the end time.
- Fix obvious typos in task names silently (e.g. "priarmy" → "primary").

Time resolution (use the user's local timezone; waking window 06:00-20:00):
- No date given → today if the resolved time is still ahead, else tomorrow.
- Bare hour with no am/pm ("11:30", "7"): build both am/pm candidates, drop any outside 06:00-20:00, drop any already past today. If one candidate survives, use it. If several survive, use the soonest. If none survive, roll the surviving in-window candidate(s) to tomorrow.
- Only ask the user when the time is genuinely outside 06:00-20:00 for both am/pm (e.g. "3am", "10pm") or otherwise has no sane default  -  don't ask for ordinary bare times.

Fire all reminders in one `osascript -l JavaScript` call (JXA), via Bash:

```javascript
const Reminders = Application('Reminders');
const list = Reminders.lists.byName('Reminders');
const items = [
  ["TITLE", new Date(YYYY,MM-1,DD,HH,mm,0)],
  // one row per reminder; month is 0-indexed
];
items.forEach(([name, due]) => {
  list.reminders.push(Reminders.Reminder({name, dueDate: due}));
});
"done"
```

Pipe the script into `osascript -l JavaScript <<'EOF' ... EOF`. After running, confirm back tersely: list of titles + datetime, nothing else.
