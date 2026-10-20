# Technique catalog

This is a living file.
Every link you ingest adds or updates an entry here (see SKILL.md, "Ingest a link").
Each entry: what it looks like, how to build it in three.js inside HyperFrames, and where it came from.
"Proven" means a shipped loop used it (Oct 2026).

## Proven

### Voxel assembly
Look: loose cubes and labelled cards swarm, then snap into a pixel or grid logo with a mechanical overshoot, and peel back out.
Build: `InstancedMesh` of `RoundedBoxGeometry`, one per logo grid cell, 3 deep.
Each instance lerps from a swarm pose to its cell, with a staggered `back.out`-style overshoot computed per instance from phase.
The lighting does the work: a soft spot key with falloff, PCF shadows on a dark floor, a cool rim plus an accent back rim, GTAO, no bloom. (It used Neutral tone mapping, which turned the ground navy; use NoToneMapping.)
Proven. The strongest of the first six.

### Raymarched liquid chrome
Look: an accent chrome drop pinches off droplets that pour into the logo, which then drains back into a ball.
Build: one SDF fragment shader on a fullscreen quad.
JS computes every drop's position from time and passes it in as uniforms.
`smin` blends the drops into box SDFs of the logo cells.
Lighting comes from analytic studio softboxes, with soft shadows, AO in the march, and a glossy floor reflection.
Squash, stretch and follow-through are computed per drop.
A render takes about 35s.
Proven. Source idea: @woodxbt / @flxrnc "Motion Lab" chrome pour.

### Tile field flyover
Look: the camera flies low over thousands of dark tiles while ripples roll them over to flash accent, then cranes overhead as the logo flips up.
Build: an `InstancedMesh` of beveled boxes.
Camera travel is a whole number of tile periods, which is what makes the loop exact.
Ripples are rings of radius f(t - t0), and each tile's flip angle comes from its distance to the ring.
Proven. Source idea: Cinetic v1.1 launch film (white tile wave).

### GPU particle morph
Look: 65k points flow from a ribbon into the logo, then into a hub with streams in and out.
Build: `THREE.Points` with a custom `ShaderMaterial`.
Every target shape is a vertex attribute, and the vertex shader mixes between them with staggered smoothstep plus a CAPPED curl-noise detour.
Uncapped noise throws particles into the lens.
Points are drawn as lit sphere impostors with alpha-to-coverage, so no CPU sorting is needed.
Proven. Source idea: the Mortiflix particle knot.

### Card helix with rack focus
Look: the camera rides down a double helix of skill cards, and one card pulls out, flips to "Installed", and slots back.
Build: thin rounded slabs with `CanvasTexture` faces (await `document.fonts` first).
Depth of field is faked with pre-blurred texture sets chosen by distance.
The helix is periodic in pair count, so the descent loops.
Proven.

### Network orbit
Look: author badges fire packets along tube arcs into the core, and the core fires packets out to the agent surfaces.
Build: `TubeGeometry` arcs with moving light pulses, a `Reflector` floor, and HTML labels positioned from projected coordinates.
Caution: labels collide during a 360 orbit.
Keep labels few and dimmed by depth, or orbit less than 360 and bounce back.
Proven. It is the busiest of the six, and the closest to the "AI look".

### Card wall into Claude (sign-in animation, 3D)
Look: the product sign-in wall as real tilted 3D slabs; resting cards dim, one lifts and installs, one flips, one flies into a dark chat window that pulses accent.
Build: slabs with `CanvasTexture` faces drawn from a procedural pixel-art cover generator and the product card layout; spot key plus PCF shadows on a backing plane.
Loop trick: each row's content repeats every 5 cards and drifts exactly 5 cards per loop.
Proven. A variant adds an accent power ring that closes as cards land.

### Router rail yard
Look: a question card fires a light packet down rails into a voxel logo on a turntable, which throws onto a spur; the station lights and sends an answer card home.
Build: PBR steel rails, GTAO, high-threshold bloom, shader groove trail behind the packet, logo from the brand grid with a hinged jaw.
Character GIFs are stepped by time; play a long GIF at 0.8x so whole cycles fit 10s.
Proven.

### Geneva-drive flywheel
Look: a machined watch-movement wheel stepped 90 degrees per station by an exact Geneva cross-and-pin, with a pendulum-simulated cradle.
Build: exact Geneva geometry plus a damped click; one turn per loop closes the seam.
Caution: frame-averaged motion blur dimmed frames to 1/4 once, and small engraved labels ghost under blur.
Proven.

### Monoliths and hourglass
Look: dark slabs engraved with jobs light from within as skill cartridges click in; an hourglass drains and gets pushed back.
Loop trick: solve sand levels so t=10 matches t=0, and flip the hourglass 180 degrees, which looks identical.
Caution: the far floor reads gray; push it toward the ground colour.
Proven.

### Cartridge console
Look: brand modules seat into a console, which powers on accent and labels each capability.
Proven.

## Not yet built (from ingested sources)

- **One morphing object:** a single shape becomes a button, then a loader, then a chart, then a card, with a cursor driving it. Source: @0xkerazcity playbook, @twoclipping "Shape morphing through UI states".
- **Carrier-object transitions:** every cut has an object that carries it, a reason, and the word it lands on. Source: Mortiflix transition board.
- **Expanding bento grid:** one tile unfolds into product UI. Source: @beamnxw ideas list.
- **Engraving / etched style:** line-hatched shading as a style frame. Source: @LexnLin engraving-style Claude ad on motionvideo.xyz.
- **Landing-page 3D fly-over:** a flat page tilted into 3D and flown over. Source: @twoclipping on motionvideo.xyz.
- **Code-designed sound:** each text fragment gets one soft sound, and every sound is designed in code with measured sync points. Source: Cinetic, earshot.
