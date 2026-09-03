---
name: text-to-speech
description: Convert a blob of text into spoken audio using OpenAI's text-to-speech (a generic ChatGPT-style voice) and hand the audio file back. Use when the user gives text and asks to "read this aloud", "make audio of this", "text to speech", "TTS this", "narrate this", "turn this into an mp3/voiceover", or invokes /text-to-speech. Produces an audio file (mp3 by default) saved to the Desktop.
---

# text-to-speech

Turns text into an audio file via OpenAI's speech API. The key lives in the
macOS Keychain (service `openai-api-key`, account `openai-tts`) — the script
reads it automatically, so nothing is hardcoded.

## How to run it

```bash
python3 ~/.claude/skills/text-to-speech/scripts/tts.py "TEXT HERE"
```

The script prints the saved file path on stdout (one line). After it returns:
1. Surface the file to the user with `SendUserFile` so they can grab it.
2. Offer to play it, or pass `--play` to play it immediately via `afplay`.

### Input options (pick one)
- Inline: `tts.py "Hello world"`
- From a file: `tts.py -f /path/to/notes.txt`
- From stdin (best for large blobs — avoids shell-quoting issues):
  ```bash
  cat notes.txt | python3 ~/.claude/skills/text-to-speech/scripts/tts.py --play
  ```
  When the text is long, has quotes/newlines, or comes from another file, prefer
  writing it to a temp file and using `-f`, or piping via stdin.

### Common flags
| Flag | Default | Notes |
|---|---|---|
| `-v, --voice` | `alloy` | alloy, ash, ballad, coral, echo, fable, onyx, nova, sage, shimmer, verse |
| `-m, --model` | `gpt-4o-mini-tts` | also `tts-1` (fast) / `tts-1-hd` (higher quality) |
| `--format` | `mp3` | mp3, opus, aac, flac, wav, pcm |
| `-i, --instructions` | — | tone/style steer, e.g. `-i "warm, slow, like a bedtime story"` (gpt-4o-mini-tts only) |
| `--speed` | `1.0` | 0.25–4.0; best on tts-1 / tts-1-hd |
| `-o, --out` | `~/Desktop/tts-<timestamp>.mp3` | output path |
| `--play` | off | play immediately after saving |

`alloy` is the plain, neutral "generic ChatGPT" voice — the default. Only change
it if the user asks for a different tone.

## Notes
- Standard library only — no pip install needed.
- Key precedence: `OPENAI_API_KEY` env var, then Keychain. Rotate the stored key with:
  `security add-generic-password -a openai-tts -s openai-api-key -w 'sk-...' -U`
- Errors (bad key, unknown voice/model) are printed as `ERROR <code>: <detail>`.
