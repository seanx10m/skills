#!/usr/bin/env bash
# UserPromptSubmit hook: when Talk-to-Me narration is ON for this session, inject a
# reminder so the reply is written to be HEARD (prose, not tables/code/symbols).
# When personality mode is also ON, inject a second block that asks the agent to color
# the reply with the persona of whoever the Personal Voice is named after.
# Stdout from a UserPromptSubmit hook is added to the model's context.
set -uo pipefail
SK="$HOME/.claude/skills/talk-to-me"; STATE="$SK/state"

input=$(cat)
sid=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null)

# Resolution: an explicit per-session marker wins; only with NO marker fall back to global.
# (A session explicitly OFF gets no reminder injected even when the global flag is ON.)
on=0
if [ -n "$sid" ] && [ -f "$STATE/sessions/$sid.off" ]; then on=0
elif [ -n "$sid" ] && [ -f "$STATE/sessions/$sid" ];   then on=1
elif [ -f "$STATE/narrate-on" ];                        then on=1
fi
[ "$on" = 1 ] || exit 0

cat <<'EOF'
<talktome-voice-mode>
Talk-to-Me narration is ON — this reply will be read aloud by a synthetic voice. Write it to be HEARD, not seen:
- Use plain, conversational prose in full sentences.
- Avoid markdown tables, code blocks, bullet lists, headings, and stray symbols; say things in words instead. (If the user explicitly needs code, keep it minimal and put it at the end.)
- Don't dictate long file paths, flags, or identifiers unless essential — describe them generally.
- Prefer shorter, more general answers; lead with the point in spoken language.
</talktome-voice-mode>
EOF

# Personality mode: shape the narration to match the namesake of the Personal Voice.
if [ "$(cat "$STATE/personality" 2>/dev/null)" = "on" ]; then
  voice=$(cat "$STATE/voice" 2>/dev/null || echo "auto")
  printf '<talktome-personality voice="%s">\n' "$voice"
  cat <<'EOF'
Personality mode is ON. The Personal Voice named above is named after someone.
If that name refers to a recognizable public figure or character, subtly color THIS reply with
their known speaking persona — their cadence, warmth, characteristic phrasing and outlook — while
keeping every fact accurate and the answer genuinely helpful. Keep it tasteful homage, not broad
caricature, and never put invented claims or quotes into a real person's mouth. For example, a
Morgan Freeman voice should sound calm, wise, measured and quietly reflective, with the occasional
gentle, sweeping observation. If the name is just an ordinary person's name (not a recognizable
figure), narrate normally without adopting any persona.
</talktome-personality>
EOF
fi
