# Brand profile

A brand profile is everything a motion piece needs to look and sound like one brand.
Keep it in the project as `BRAND.md`, with its files in a `brand/` folder next to it, and pass that folder to `new-loop.sh`.
If the project already has a design system (tokens file, CLAUDE.md, a style guide), copy values from it; never invent a hex, a logo or a fact.

## What it holds

| Field | What to write |
|---|---|
| Ground | The background hex. Loops are checked against it. |
| Panel, line, text | Surface, hairline and text hexes. |
| Hero hue | One accent that carries every key moment. |
| Second hue | Optional, used rarely. |
| Display and body faces | Font names, plus the woff2 files in `brand/`. |
| Mark | The logo file in `brand/`, and if it is pixel or grid-based, a grid `.txt` so 3D builds are exact. |
| Characters | Mascot images or GIFs in `brand/` (GIFs are split into frames per project). |
| Voice | Two or three lines the brand would say, and words it never uses. |
| Real facts | Names, numbers and records allowed on screen, with their source. |
| Bans | Anything that must never appear (a competitor, a domain, a retired logo). |

## Blank profile

```markdown
# <Brand> brand profile

- Ground: #
- Panel: #   Line: #   Text: #
- Hero hue: #
- Second hue: # (rare)
- Display face: <name> (brand/<file>.woff2)
- Body face: <name> (brand/<file>.woff2)
- Mark: brand/<logo>.svg  (grid: brand/<mark>-grid.txt, if pixel-based)
- Characters: brand/<name>.gif
- Voice: "<line>", "<line>". Never say: <words>.
- Real facts (source): <fact> (<where it came from>)
- Bans: <things that never appear>
```
