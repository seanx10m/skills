---
name: decide-ui
description: Turn a list of items into an interactive decision interface - swipe left/right for yes/no triage over many items, or a tournament bracket for pairwise comparisons that branch down to one winner. ONLY use when the user explicitly invokes /decide-ui (or says "swipe UI", "tinder for X", "tournament this", "bracket this", "decide UI"). Never auto-trigger.
---

# decide-ui

Turn a list of items into ONE self-contained HTML page for making decisions over them - not for browsing, for *deciding*.

## When
Only on explicit `/decide-ui` invocation, or clear asks like "tinder-style swipe for X", "tournament bracket these", "help me pick a winner out of these options". This is a build verb, not a background reflex.

## Pick the mode

| Signal | Mode |
|---|---|
| "swipe", "yes/no", "keep/skip", "tinder", "triage", one item at a time | **Swipe** |
| "compare", "which is better", "tournament", "bracket", "pick a winner", narrowing many options to one | **Tournament** |

If ambiguous, ask which - the two modes produce very different pages and guessing wrong wastes a full build.

## Mode 1: Swipe (binary triage)

One card at a time, decision is per-item and independent (not compared against other items).

- Stacked deck (peek 2-3 cards deep), front card driven by **both** pointer drag and trackpad swipe - see "Gestures" below, and copy the working handler from [`references/swipe-gestures.md`](references/swipe-gestures.md) rather than re-deriving it.
- Swipe right / click check / → key = yes-bucket. Swipe left / click X / ← key = no-bucket. Undo (Z key) pops the last decision back onto the deck.
- KEEP/SKIP-style stamps (or whatever the two bucket labels are) fade in proportional to travel, fly-off animation past the threshold.
- **Show the verdict before it commits, and let the card leave rather than vanish.** One `t` (0..1 of the way to the threshold) drives the stamp, a colour wash over the card face, the card's border colour, and a ✓/✗ badge pair below the deck. The departing card is handed to a fly layer so the commit re-render cannot cut its animation off mid-flight. Both are in [`references/swipe-gestures.md`](references/swipe-gestures.md); "it just disappears" and "I can't tell what I'm doing" are the two complaints that always follow working gestures.
- Progress bar + running tally of both buckets, always visible.
- **Export mid-run, not only at the end.** A persistent "Copy decisions" button in the header, enabled from the first decision, copying a compact paste-back summary. A 200-item deck is several sittings; trapping the output behind finishing all N makes the tool unusable. Copy the buckets as bare ids/numbers plus an `X/N decided` header line so a partial run is unambiguous.
- **Persist progress to `localStorage`** keyed to the deck size, and restore on load. This overrides the general "no persistence" rule below: losing 100 swipes to an accidental tab close is the single worst failure this tool has.
- End screen: two columns, one per bucket, each item listed with a link back to its source if it has one (issue, URL, file). Include a copy button emitting ready-to-run commands when the items are actionable (e.g. `gh issue close N -R owner/repo -c "..."`). "Start over" button resets the deck.
- Card content should show whatever makes the decision legible: title, a body/description snippet (markdown lightly stripped - strip fenced code blocks, heading hashes, bold/link syntax; don't render full markdown), and any facets (labels, tags, price, date) as small chips.
- **Sort the deck so the ordering itself does work.** For backlog/staleness triage that means oldest-first; surface the decision-relevant number on the card (age, days-silent) rather than making the user infer it.

## Gestures (the part that always gets re-litigated)

Three rounds of "too sensitive" and one inverted-direction report says: **do not hardcode feel.** Full working handler in [`references/swipe-gestures.md`](references/swipe-gestures.md).

- **Pointer drag and trackpad swipe are two different inputs.** Pointer events cover mouse + touch; a two-finger trackpad swipe arrives as `wheel` with `deltaX` and is not covered by them. Build both or the page feels dead on a laptop.
- **Swipe direction is a preference, not a fact.** The sign of `wheel` `deltaX` flips with the OS natural-scrolling setting, so it cannot be reasoned out - it is a coin flip you will lose half the time. Ship a **"Flip swipe direction" toggle** persisted to `localStorage`. (This reverses earlier guidance in this skill that said not to build one.)
- **Ship a resistance slider.** Commit distance is personal and costs a full round-trip per guess. Defaults that landed well: **230px** drag, **2x that** for wheel (a swipe racks up distance far faster than a drag), wheel deltas damped to ~0.30.
- Wheel handling needs three guards or it hijacks the page: a small dead zone, a requirement that `|deltaX|` clearly beats `|deltaY|` (~1.8x) so vertical scrolling inside the card body still works, and `overscroll-behavior-x: none` on the body so a swipe doesn't trigger browser back/forward.
- macOS keeps firing momentum `wheel` events after the fingers lift, so **fire the moment the card clears the threshold** rather than waiting for the gesture to end. Use a short idle timer only for the snap-back case.
- Guard one-card-one-verdict (`dataset.spent`). A fast second input during the fly-off otherwise lands on the next item.
- **A per-card flag cannot hold a gesture-scoped lock.** macOS momentum runs ~900ms past the fingers lifting, outliving the card it started on, so the tail drags the *next* card. The lock lives in module scope and releases only on a SUSTAINED rise in wheel speed over a smoothed level of the tail (momentum only decays) - never on a timeout, which either eats a fast second swipe or lets the tail through, and never on one delta over a running minimum: tails are noisy and Chrome merges janked frames into one big delta, so a single-event release hands the rest of the tail to the next card.
- **Clip the page, not just the overscroll.** A card at `translate(700px)` adds ~150px of `scrollWidth`; `overscroll-behavior-x` does not touch that, so a two-finger swipe pans the whole page sideways. `html, body { overflow-x: clip }`.
- **The pointerup may not land on the card.** Listen on the window, set `down = true` only after `setPointerCapture`, and handle `lostpointercapture` - otherwise `down` sticks on and the card follows a button-less cursor forever, never committing.

## Mode 2: Tournament (pairwise bracket)

Narrowing N items down to one winner through head-to-head rounds - use when a flat swipe wouldn't capture relative preference between items.

- Seed the bracket from the item list: pair them up (shuffle or keep list order), byes for odd-one-out or non-power-of-2 counts advance automatically.
- One matchup on screen at a time: two cards side by side (or stacked on narrow viewports), click/tap either to advance it, or keyboard ← / → to pick left/right.
- Track round number and matches remaining; show a compact bracket visualization (even a simple round-by-round list is fine - don't over-build a full bracket-tree graphic unless the item count is small enough to make one legible).
- Losers are recorded, not discarded from view - the end screen should show the full path (who beat whom, final winner) so the "why" of the decision is auditable, not just the result.
- End screen: crown the winner prominently, then a collapsed round-by-round history below it.

## Build steps (both modes)

1. **Get the data.** Ask what to decide over if unclear. Shape it into one JS array - each item needs at least a title/label; pull in whatever else the source has (body, labels, url, price, date) rather than re-deriving it.
2. **Load design.** If a design skill is available (optional), use it for palette/type/layout calibration before writing CSS; otherwise pick a deliberate palette and type scale yourself - these are playful, personality-forward tools (unlike a plain report), so they can take a real point of view.
3. **Write a template + inject the data.** Keep the HTML in a `*.template.html` with a `/*__DATA__*/[]` placeholder and build the final file with a tiny script that substitutes the JSON. Re-running the build after an edit is then one command, and the data never has to survive a hand-edit. Vanilla JS, no build step, no CDN, theme-aware (light + dark).
4. **Verify the script actually executes - before opening it.** See below. Non-negotiable.
4b. **Screenshot a held mid-drag before declaring the feel done.** Overlap bugs - stamp on the chip, a badge parked on the body text - are invisible in the source and obvious in one image. Drive it headless (dispatch `pointerdown` + `pointermove`, hold, screenshot); do not ask the user to be the renderer.
5. **Open it** directly (`open <file>` on macOS, a direct `open` is best since this is HTML, not markdown) so the user sees it now. On a re-open after an edit, `open` only *focuses* an already-open tab and shows stale content - open `"file://<abspath>?v=$(date +%s)"` instead.

### Verify before opening

A blank page costs several confused round-trips, and the failure is invisible from the source: the static chrome still renders, so it looks half-working rather than broken. Extract the `<script>` and run it against a DOM stub:

```bash
python3 -c "
import re; open('_check.js','w').write(re.search(r'<script>(.*)</script>', open('OUT.html').read(), re.S).group(1))"
node --input-type=module -e "
import fs from 'fs';
const mk=()=>({style:{cssText:''},classList:{add(){},remove(){},toggle(){}},dataset:{},append(){},appendChild(){},
  addEventListener(){},querySelector:()=>null,remove(){},select(){},innerHTML:'',textContent:''});
new Function('document','window','navigator','localStorage','addEventListener','confirm','setTimeout',
  fs.readFileSync('_check.js','utf8'))(
  {getElementById:mk,createElement:mk,body:{appendChild(){}},execCommand:()=>true},
  {open(){}},{},{getItem:()=>null,setItem(){}},()=>{},()=>true,()=>{});
console.log('OK');"
rm -f _check.js
```

It catches the whole class of top-to-bottom script deaths, which is what actually goes wrong here.

**Declare all user-tunable state in ONE block at the top of the script.** `let` has no hoisting grace: wiring a control above its `let` throws a temporal-dead-zone `ReferenceError` that kills the entire script on load. This is an easy mistake: a slider wired near the top reading a `let` declared further down.

## Rules
- Self-contained, zero network calls, inline everything.
- Keep it simple: vanilla JS + one file. A framework or a real backend is out of scope unless asked. (`localStorage` progress is the deliberate exception - see Swipe mode.)
- `navigator.clipboard` is not reliably available on `file://` - always fall back to a hidden textarea + `document.execCommand('copy')`. A dead copy button defeats the entire tool.
- Keyboard parity with pointer/drag controls always - arrow keys should do everything a swipe or click does.
- Don't build both modes into one page "just in case" - pick the one the ask calls for. If genuinely unclear, ask.
- When feel is contested twice, stop guessing and **ship the control**. A slider or toggle the user can move ends the loop; a third guess does not.
