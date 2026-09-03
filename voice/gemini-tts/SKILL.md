---
name: gemini-tts
description: Turn a big block of text or a Markdown file into a spoken .m4a audio file using the Gemini TTS API. Use when the user says "/gemini-tts", "read this doc aloud into a file", "make an audio version of this markdown", "narrate this with Gemini", or wants long text converted to an audio file on their Desktop.
---

# Gemini TTS

Text or Markdown in, `.m4a` on the Desktop out. Handles long input by chunking at paragraph boundaries and concatenating the audio.

## Run it

```bash
# a markdown file -> ~/Desktop/<name>.m4a
~/.claude/skills/gemini-tts/scripts/tts.py path/to/doc.md

# stdin -> a named file
pbpaste | ~/.claude/skills/gemini-tts/scripts/tts.py -o ~/Desktop/notes.m4a

# pick a voice and a delivery style
~/.claude/skills/gemini-tts/scripts/tts.py doc.md -v Puck -s "read briskly, upbeat"
```

Flags: `-o` output path, `-v` voice (default `Kore`), `-s` style instruction prepended to each chunk, `--seed` (default 42).

## After generating

By default, once the `.m4a` is written, invoke the `slack-me` skill to DM the file to the user. Skip only if they say not to (e.g. "don't slack it", "just save it").

## Voices

`Kore` (firm, default), `Puck` (upbeat), `Charon` (informative), `Zephyr` (bright), `Enceladus` (breathy), `Fenrir` (excitable), `Leda` (youthful), `Aoede` (breezy), `Sulafat` (warm). Full list in the [Gemini speech docs](https://ai.google.dev/gemini-api/docs/speech-generation).

## Notes

- API key: `GEMINI_API_KEY` env var, else `~/.gemini_api_key`.
- Model `gemini-2.5-flash-preview-tts` returns raw 24kHz 16-bit mono PCM; ffmpeg does the AAC encode.
- Markdown is stripped first (code blocks, tables, and images are dropped, links keep their text) so the narration doesn't read syntax aloud.
- Output is deterministic: `generationConfig.seed` is pinned (`--seed`, default 42), so the same text + voice + seed gives byte-identical audio every run. Without it the model resamples and each run comes back in a subtly different voice. Change `--seed` to roll a different take.
- Requires `ffmpeg` on PATH.
