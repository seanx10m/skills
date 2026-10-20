# Learned checks

Every check here came from a real mistake.
When someone flags a new one, add it here once, and every future video runs it (the Mortiflix idea).
Run all of them before calling a piece done.

1. **Real data only.**
   Every name, author, version, count and badge on screen must come from the brand profile or a real source.
   Never assign authors round-robin, and never invent version numbers.
   Origin: a loop credited a record to the wrong person and showed made-up "v2.1" versions (2026-10-19).
2. **The loop seam.**
   Run `scripts/seam-check.py <dir>`.
   The jump from the last frame to the first must be no bigger than an ordinary frame step.
3. **Look at the frames.**
   Snapshot t = 0, 2.5, 5, 7.5, 9.967 and actually read the contact sheet.
   A build that lints is not a build that looks right.
4. **Labels never collide.**
   Orbiting cameras pass labels in front of each other.
   Cull or dim them by depth.
   Origin: the globe loop.
5. **No AI look.**
   Banned: navy space, halo rings, random particles with no job, bloom everywhere, glassmorphism, idle floating.
   Every element performs: assembles, pours, flips, flies, connects.
6. **Not "just HyperFrames".**
   A flat 2D slide sequence with fades does not meet the bar.
   The quality comes from real 3D: lighting, materials, camera.
   Origin: feedback on a first reel (2026-10-19): "This is basically just hyperframes."
7. **Brand words.**
   Follow the brand profile's voice and bans exactly (spelling of product names, banned words, no domains if banned).
   No em dashes on screen.
8. **The mark.**
   Use only the brand's own logo; build 3D versions from its grid or vector, never a lookalike or an invented mascot.
9. **Banding.**
   Large soft fields use radial gradients only.
   Linear ramps band after H.264 encoding.
10. **Depicted actions are data too.**
   A named person shown installing, liking or proposing an edit is a claim about the real record.
   If the source shows 0 installs, do not show four colleagues installing it; use a record with real activity, or keep people anonymous.
   Origin: a loop showed four named colleagues installing a record that had 0 installs (2026-10-19).
11. **The ground must measure as the brand's ground colour.**
   Sample a background pixel from frame 0 and compare it to the profile's ground hex.
   `NeutralToneMapping` shifts it to navy (about rgb(2,5,15)), so the template uses `NoToneMapping` and lights the scene within range.
   Origin: a build found three loops shipping navy grounds (2026-10-19).
