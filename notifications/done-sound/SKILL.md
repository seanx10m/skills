---
name: done-sound
description: Play a "tada" celebration sound to signal something finished. Use when the user says "/done-sound", "done sound", "play the tada", "let me know when it merges", "ping me when that merges", "sound when done", or asks to be alerted audibly that a merge, deploy, build, or long task completed.
---

# done-sound

Play the tada sound (volume set to 0.4, 60% quieter than default):

```bash
afplay -v 0.4 ~/.claude/skills/done-sound/assets/tadaa.mp3
```

Fire-and-forget (don't block on it):

```bash
afplay -v 0.4 ~/.claude/skills/done-sound/assets/tadaa.mp3 &
```

## Most common use: merge notification

When the user asks to be told a PR merged, poll then play:

```bash
gh pr checks <PR> --watch && gh pr merge <PR> --squash && afplay -v 0.4 ~/.claude/skills/done-sound/assets/tadaa.mp3
```

Or if the merge is happening elsewhere, wait on it then sound:

```bash
until [ "$(gh pr view <PR> --json state -q .state)" = "MERGED" ]; do sleep 30; done
afplay -v 0.4 ~/.claude/skills/done-sound/assets/tadaa.mp3
```

Always say in text what the sound was for - the sound alone isn't the report.
