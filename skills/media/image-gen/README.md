# image-gen

Generate images with Google Gemini image model from a prompt and a count, save PNGs, and open them all in macOS Preview.

- Platform: macOS (uses Preview). Requires Rust (`cargo`) and an `GEMINI_API_KEY` (env var, or first line of `~/.config/gemini-key`).
- Install: `cp -r skills/media/image-gen ~/.claude/skills/`
- Build (required, no prebuilt binary): `cd ~/.claude/skills/media/image-gen/app && cargo build --release`
- Check: `app/target/release/imagegen --selftest` (offline).
