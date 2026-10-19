---
name: image-gen
description: Generate images with Google's Gemini image model from a simple prompt + number of options, save them as PNGs, and open them all in macOS Preview (Cmd+C copies any one natively). Use when the user says "generate an image", "make me N options of X", "/image-gen", or wants AI image generation with a native copy-able result.
metadata:
  model: gemini-3.1-flash-image-preview
  platform: macOS
---

# image-gen

Native macOS image generation via the Gemini image API. Prompt + how-many-options
in, PNGs out, opened in Preview. Pick one, Cmd+C, paste anywhere.

## Run it

Binary lives at `app/target/release/imagegen` (relative to this skill folder). Build it first with `cargo build --release` (see Build).

```
imagegen "a fox in a spacesuit, watercolor" 4
imagegen "minimalist logo for a coffee bar" 6 --aspect 16:9
```

- **Arg 1** = prompt (quoted).
- **Arg 2** = number of options, 1-10 (default 4). One API call per option.
- `--aspect 1:1|16:9|9:16|4:3|3:4` (optional).

Images write to a temp dir (ephemeral) and all open in one Preview window. Paths
are printed to stdout.

## API key

Reads `GEMINI_API_KEY` from the env, else the first line of `~/.config/gemini-key`.

```
export GEMINI_API_KEY=your-key
# or
echo "your-key" > ~/.config/gemini-key && chmod 600 ~/.config/gemini-key
```

## Build (first use / after edits)

```
cd <this skill>/app && cargo build --release
```

`imagegen --selftest` runs an offline check (decode + write, no API call).

## Notes
- A refused (safety) option is skipped; the rest still open.
- Files are in `$TMPDIR/imagegen-<pid>/`  -  they survive until the OS clears temp.
  Copy from Preview, or move the PNGs if you want to keep them.
