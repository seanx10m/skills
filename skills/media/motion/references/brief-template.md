# __TITLE__ - shared brief

<!-- Template. Fill __TITLE__, __N__, __SUBJECT__, __FACTS__ and __BRAND__ from the brand profile, then save as BRIEF.md in the parent folder. -->

__N__ agents each build ONE seamless 10-second 3D piece, in parallel.
The bar is the hyped "Opus motion" posts on X: real 3D, shaders, lighting and camera work.
A flat HyperFrames slide deck fails this brief.

## The subject (fill from BRAND.md, real facts only)

__SUBJECT__
Facts, names and numbers you may show (from the brand profile; never invent or reassign them):
__FACTS__

## The mark

Use only the brand's own mark, from `assets/brand/`.
If it is pixel or grid-based, build any 3D version from its grid file so it is exact.
Never invent a mascot or a lookalike logo.

## Hard specs

- 1920x1080, exactly 10.0s, 30fps.
- **Seamless loop.** The frame at t=10 must equal the frame at t=0.
  Drive everything from periodic functions of `phase = t / 10`, e.g. `sin(2*PI*phase)`.
  Or design the cycle so its end state is its start state.
  Verify it: snapshot t=0 and t=9.967 and compare them.
- **Deterministic.** No unseeded `Math.random`, no wall clock, no `requestAnimationFrame` as the clock.
  Use a seeded PRNG (mulberry32) at build time.
  Render purely from HyperFrames time (`hf-seek` event / `window.__hfThreeTime`).
- Built with HyperFrames as the frame renderer, using its `three` adapter.
  If the HyperFrames skills are installed, read the three.js adapter notes and `hyperframes-core` first.
  The root needs `data-duration="10"`.
- Local assets only, nothing fetched at render time.
  Three.js r181 is already in your folder at `assets/three/` with an import map in `index.html`.
  Brand files (fonts, mark, characters) are in `assets/brand/`; declare fonts with an in-file `@font-face`.
  GIFs are pre-split into `assets/brand/<name>-frames/`; step through them by time, never play them live.

## Brand

__BRAND__
(Paste the brand profile here: ground, panel, line, text, hero hue, second hue, faces, voice, bans.)
- Never an em dash in on-screen text.
- On-screen text is optional and minimal: at most one short line, timed to a beat.
  The picture carries it.
- Turn tone mapping off and light within range, so the ground measures as the brand's ground hex.

## Avoid the "AI look"

These read as generated, so don't use them: navy space backdrops, halo rings, random particles with no job, heavy bloom everywhere, glassmorphism, gradient meshes, idle floating/breathing.
Every element must PERFORM something: assemble, pour, fly, flip, connect.
Lighting, materials and camera are where the quality comes from: real PBR, shadows or AO, a camera with intent.
Restrained bloom on the hero hue is allowed only if it serves the shot.
Use large soft backgrounds as radial gradients only, since linear ramps band after H.264 encoding.

## Deliverable (in your own folder `<parent>/<your-name>/`, scaffolded by `scripts/new-loop.sh`)

1. `index.html` (or a `build.py` that emits it) that renders on its own.
2. `renders/loop.mp4`, from `npx -y hyperframes render <folder> -o <folder>/renders/loop.mp4`.
3. `frames/`: snapshots at t = 0, 2.5, 5, 7.5, 9.967 (`npx -y hyperframes snapshot <folder> -o <folder>/frames --at 0,2.5,5,7.5,9.967 --no-end`).
   LOOK at them, judge them against this brief, and iterate at least twice before you call it done.
4. Run `npx -y hyperframes lint <folder>` and fix every error.
5. Run `python3 ~/.claude/skills/motion/scripts/seam-check.py <folder>` (loops only).
6. Write `CAPTION.txt`: line 1 = the name, line 2 = one sentence on the shot.

Report back: the mp4 path, two lines on the shot, and whether the loop seam verified.
Do not touch any other agent's folder.
Do not commit or push.
