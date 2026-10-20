---
name: motion
description: Make 3D motion pieces for any brand or none - real three.js scenes with lighting, materials and camera work, rendered frame-exact through HyperFrames as seamless loops or short films - and keep a living catalog of the motion techniques trending online. Fans several options out to parallel agents, gates each loop, and lays them side by side in one gallery. Use when someone says "motion", "/motion", wants a cool, 3D or hype motion video, a seamless loop, a logo or product visual, or "try a few options". Also use when someone shares a link to a motion post, repo or video and says "add this to motion", "ingest this", or "learn this technique".
---

# Motion

A 3D motion studio with no house brand.
The bar is the hyped "Opus motion" posts: real 3D, shaders, lighting, camera.
A flat 2D slide sequence with fades does not meet it.
Each project brings its own brand; this skill brings the engine, the technique catalog and the checks.

## Four jobs

| Ask | Do |
|---|---|
| "Make a motion piece / try a few options" | **Fan out** (below) |
| A link plus "add this / ingest / learn this" | **Ingest a link** (below) |
| "Fix / push this one further" | Edit that project, then rerun every check in `references/learned-checks.md` |
| "Set up a brand for X" | Write a brand profile (see `references/brand-profile.md`) |

## Fan out: several options in parallel

1. **Brand and story first.** Find or write the project's brand profile (`references/brand-profile.md`): palette, type, mark, voice, real facts.
   Ask for anything you can't find; never invent a logo, a stat or a name.
2. **Pick N concepts** (default 5-6), each a different technique from `references/techniques.md`: proven ones for reliability, plus one or two untried ones to grow the catalog.
3. **Scaffold each** with `scripts/new-loop.sh <parent>/<name> "<Title>" [brand-dir]`.
   It vendors three.js r181 (cached once per machine), the starter loop, and copies `brand-dir` into `assets/brand/` when given.
4. **Write one shared BRIEF.md** in the parent folder from `references/brief-template.md`, with the brand profile pasted in.
   Then launch one background agent per concept, all in a single message, each told to read the brief, own only its folder, and write `CAPTION.txt` (line 1 = name, line 2 = one sentence).
5. **Gate each result**: `scripts/seam-check.py <dir>` for loops, look at its contact sheet, and run every check in `references/learned-checks.md`.
   An agent that dies mid-run often leaves a finished `renders/loop.mp4`: gate it, and write its `CAPTION.txt` yourself.
6. **Show them side by side**: `scripts/gallery.py <parent> "<title>" [accent-hex]`, then open `gallery.html`.
   Copy the mp4s to `~/Desktop/<parent-name>/`.

## Ingest a link

Point this skill at every new motion post. For each link:
1. Extract it with the `xtract` skill from this repo if installed (`--frames` when the words are on screen and the audio is just music); otherwise read the post directly.
   If GitHub is unreachable, use mirror pages and say so.
2. Add or update an entry in `references/techniques.md`: what it looks like, how to build it in three.js inside HyperFrames, and the source.
3. Add one row to `references/sources.md`.
4. If the post teaches a rule (a check, a pacing number, a ban), add it to `references/learned-checks.md` with its origin.
5. If you keep a branded copy of this skill, add the same entry there too, so the catalogs don't drift.

## Hard rules (summary; full list in references/learned-checks.md)

- Seamless loops: drive everything from `phase = t / duration`, and verify the seam.
- Deterministic: a seeded PRNG, render only from HyperFrames time, never `requestAnimationFrame`.
- Local assets only, nothing fetched at render time.
- The background must measure as the brand's ground colour (tone mapping shifts it).
- Real data only: every name, number and logo on screen comes from the brand profile or a real source.

## Before you start

- Node 22+, ffmpeg, python3 and Chrome on PATH (`npx -y hyperframes` fetches the engine).
- Optional but recommended: the HyperFrames agent skills (`hyperframes`, `hyperframes-core`, `hyperframes-animation`) from the HyperFrames project.

## Files

```
assets/loop-template.html     starter three.js loop (seeded PRNG, phase clock, brand tokens at the top, lints clean)
scripts/new-loop.sh           scaffold a self-contained project
scripts/seam-check.py         loop seam gate on renders/loop.mp4
scripts/gallery.py            side-by-side gallery of every option
references/brand-profile.md   what a brand profile holds, and a blank one to fill
references/techniques.md      the living technique catalog (proven + to try)
references/learned-checks.md  checks that accumulate from real mistakes
references/brief-template.md  the shared brief handed to fan-out agents
references/sources.md         every ingested link
```

## Engine

HyperFrames renders the frames (`npx -y hyperframes lint|snapshot|render`).
If the HyperFrames skills are installed, read the `hyperframes-animation` three.js adapter notes before writing the scene.
The contract: listen for the `hf-seek` event (or read `window.__hfThreeTime`) and render that exact time.
The root needs `data-duration` and `data-no-timeline` when there is no GSAP timeline.
