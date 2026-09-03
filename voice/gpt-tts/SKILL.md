---
name: gpt-tts
description: Fast text-to-speech via OpenAI gpt-4o-mini-tts, built for long documents. Splits the text into chunks, synthesises them concurrently, and stitches the audio back in order, so a long doc takes about as long as its slowest chunk instead of the sum of all of them. Retries transient failures with jittered backoff and fails fast on permanent ones. Use when the user says "/gpt-tts", "narrate this doc", "make an audio version of this", "read this aloud into a file", "TTS this markdown", or wants a long piece of writing turned into an audio file quickly. For a single short sentence the simpler `text-to-speech` skill is fine; use this one when the input is long enough that speed matters.
---

# gpt-tts

Long text in, one audio file out, fast. Uses OpenAI `gpt-4o-mini-tts`.

The whole point is the parallelism: a 20,000-character document is ~12 chunks,
and they synthesise at the same time. Serial TTS on that doc is minutes; this
is roughly one chunk's latency plus stitching.

## Run it

```bash
python3 ~/.claude/skills/gpt-tts/scripts/gpt_tts.py -f doc.md --play
```

The script prints the output path on stdout (one line, last). Progress and
retries go to stderr, so `$(... )` capture stays clean.

After it returns, surface the file to the user with `SendUserFile`.

### Input (pick one)
- Inline: `gpt_tts.py "Hello world"`
- File: `gpt_tts.py -f notes.md`
- Stdin, best for large or quote-heavy blobs: `cat notes.txt | gpt_tts.py`

Prefer `-f` or stdin for anything long. Inline text hits shell-quoting problems.

### Flags
| Flag | Default | Notes |
|---|---|---|
| `-o, --out` | `~/Desktop/gpt-tts-<ts>.m4a` | extension picks the format |
| `-v, --voice` | `alloy` | alloy, ash, ballad, coral, echo, fable, onyx, nova, sage, shimmer, verse |
| `-m, --model` | `gpt-4o-mini-tts` | `tts-1` is lower latency, flatter voice |
| `-i, --instructions` | - | tone steer, e.g. `-i "warm, unhurried, documentary narrator"` |
| `-j, --workers` | `8` | concurrent chunk requests |
| `--chunk-chars` | `1800` | smaller = more parallel, more seams |
| `--speed` | `1.0` | 0.25-4.0 |
| `--play` | off | `afplay` when done |
| `--quiet` | off | suppress stderr progress |
| `--selftest` | - | offline check, no API call, no key needed |

`alloy` is the neutral default voice. Only change it if asked.

Output formats: `.m4a` (default, small), `.wav` (no conversion step),
`.aac`, `.caf`, `.aiff`. Conversion uses macOS `afconvert`; if it is missing
the script writes a `.wav` next to the requested path and says so.

## API key

Precedence: `OPENAI_API_KEY` env, then the first line of `~/.config/openai-key`
(the same file `/image-gen` reads), then the macOS Keychain
(service `openai-api-key`, account `openai-tts`).

Rotate the Keychain copy with:
```bash
security add-generic-password -a openai-tts -s openai-api-key -w 'sk-...' -U
```

## How it works

1. **Chunk** on the largest natural boundary that fits under the limit:
   paragraph, then sentence, then whitespace, then a hard cut. Small
   neighbours get packed back together so you do not fire a request per line.
2. **Fan out** over a thread pool. Results are kept in index order regardless
   of completion order.
3. **Stitch.** Chunks are requested as raw PCM (24 kHz, 16-bit, mono, no
   container) specifically so they concatenate byte-for-byte with no re-encode
   and no seam artifacts from splicing MP3 frames. The joined PCM is wrapped
   in a WAV, then converted if needed.

### Retry behaviour
- Retries `408/409/429/500/502/503/504` and network errors, up to 5 attempts.
- Honours a `Retry-After` header when the server sends one (capped at 60s).
- Otherwise exponential backoff with **full jitter**, so eight workers that all
  hit the same 429 do not retry in lockstep.
- **Fails immediately** on `401`/`403`/`400` and on a permanent 429
  (`insufficient_quota`, `credit_balance_exhausted`) - a billing failure is not
  a rate limit, and backing off five times only delays the same error.
- Any fatal chunk error aborts the run rather than emitting audio with a hole
  in it.

## Notes
- Standard library only. No pip install.
- Long docs are read with one voice per chunk but prosody is decided per
  request, so sentence-level intonation can shift slightly across a chunk
  boundary. Raise `--chunk-chars` to trade parallelism for fewer seams.
- Errors print as `ERROR: HTTP <code>: <detail>` and exit non-zero.
