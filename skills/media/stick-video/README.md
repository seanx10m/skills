# stick-video

Hand-drawn stick-figure explainer videos rendered with Python + ffmpeg: wobbly marker-style characters, chalkboards, hand lettering, props, screenshots and a Gemini TTS voiceover. Optional two-host dialogue mode and a "Gen Z mode" cut with your own muted B-roll.

## Requirements

- macOS assumed (`open`, Homebrew paths); the scripts themselves are portable Python.
- `ffmpeg`/`ffprobe`, Python 3 with Pillow (`pip install pillow`).
- `whisper-cli` (`brew install whisper-cpp`) plus a ggml model such as `ggml-large-v3-turbo.bin`.
- `GEMINI_API_KEY` in the environment for the voiceover (never hardcoded).
- Optional: an image generator for props, and your own B-roll file for Gen Z mode (none is bundled).

## Install

    cp -r skills/media/stick-video ~/.claude/skills/

No build step. See `SKILL.md` for the workflow. Fonts in `fonts/` are covered by `fonts/OFL.txt`.
