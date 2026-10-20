# motion

Make 3D motion pieces for any brand: real three.js scenes with lighting, materials and camera work, rendered frame-exact through [HyperFrames](https://www.npmjs.com/package/hyperframes) as seamless 10-second loops or short films.
It fans several concepts out to parallel agents, gates each loop (seam, frames, brand, real data), and lays them side by side in one gallery.
It also keeps a living catalog of motion techniques: point it at a new motion post and it learns the technique.

## Requirements

- Node 22+ (`npx -y hyperframes` fetches the renderer), `ffmpeg`, `python3`, Chrome
- three.js r181 is fetched once with `npm pack` and cached in `~/.cache/motion/`
- Optional: the HyperFrames agent skills, and `xtract` from this repo for ingesting links

## Install

```bash
cp -r skills/media/motion ~/.claude/skills/
```

## Use

Ask for "a few motion options for <brand>", or:

```bash
sh ~/.claude/skills/motion/scripts/new-loop.sh my-loops/voxel "Voxel" path/to/brand
npx -y hyperframes render my-loops/voxel -o my-loops/voxel/renders/loop.mp4
python3 ~/.claude/skills/motion/scripts/seam-check.py my-loops/voxel
python3 ~/.claude/skills/motion/scripts/gallery.py my-loops "My brand" "#FF6A3D"
```

A brand is a `BRAND.md` plus a `brand/` folder of fonts, logo and characters; see `references/brand-profile.md`.
