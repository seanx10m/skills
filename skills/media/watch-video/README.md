# watch-video

Lets Claude "watch" a video: keyframes picked by pixel change, on-screen text via macOS Vision OCR, and a local audio transcript.

- Platform: macOS (OCR uses the Vision framework). Requires `ffmpeg`/`ffprobe`, `python3` + `numpy`. Optional: `Pillow`, `yt-dlp` (URLs), `whisper-cli` or `whisper` (transcript).
- Install: `cp -r skills/media/watch-video ~/.claude/skills/`
- Build: the OCR helper is compiled automatically on first run from `scripts/ocr.swift` (needs `swiftc` from the Xcode command line tools). Manual: `swiftc -O -o scripts/ocr scripts/ocr.swift`.
- Self-check: `python3 scripts/watch.py --selftest`
