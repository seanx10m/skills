# Swipe gestures - the working handler

Copy this. It is the product of several rounds of tuning and two real bugs, and
re-deriving it reliably reproduces both.

## Tunable state - declare at the TOP of the script

`let` has no hoisting grace. Any control wired above these declarations throws a
temporal-dead-zone `ReferenceError` and kills the whole script on load, which
presents as a blank deck with the static chrome still rendering.

```js
const KEY = "my-deck-v1";

// Commit distance. User-adjustable: feel is personal and guessing costs a round-trip.
let dragLimit = +localStorage.getItem(KEY + ":drag") || 230;
const wheelLimit = () => dragLimit * 2;   // a swipe racks up distance faster than a drag

// Which way a two-finger swipe pushes the card. The sign of wheel deltaX flips with the
// OS "natural scrolling" setting, so this is a preference, not something to hardcode.
let wheelDir = +localStorage.getItem(KEY + ":dir") || 1;

const WHEEL_DAMP     = 0.30;
const WHEEL_DEADZONE = 2.5;   // ignore jitter
const WHEEL_BIAS     = 1.8;   // deltaX must clearly dominate deltaY to count as horizontal
const WHEEL_QUIET    = 120;   // ms of no wheel events that means "the gesture is over"
const WHEEL_RESTART     = 1.5;  // a NEW gesture: speed this many times the tail's level...
const WHEEL_RESTART_MIN = 8;    // ...AND at least this many px/frame (the slow end of a tail is quantized noise)
const WHEEL_RESTART_RUN = 2;    // ...on this many events IN A ROW (one spike is jitter or a coalesced frame)

// Gesture-level lock. `spent` below is per-CARD, but a macOS momentum stream outlives the
// card it started on - see "One gesture, one card".
let wheelLock = false, wheelLockTimer = null, lockLevel = 0, lockT = 0, lockRise = 0;
// Speed, not delta: when the main thread janks (the commit re-render does) Chrome merges
// several wheel events into one carrying their summed deltaX. Per 16ms frame, that merged
// event is back on the decay curve instead of looking like a fresh 3x push.
const wheelSpeed = e => {
  const dt = e.timeStamp - lockT; lockT = e.timeStamp;
  return Math.abs(e.deltaX) * 16 / Math.max(dt, 16);
};
const holdWheelLock = e => {
  wheelLock = true;
  lockT = e.timeStamp; lockLevel = Math.abs(e.deltaX); lockRise = 0;
  clearTimeout(wheelLockTimer);
  wheelLockTimer = setTimeout(() => { wheelLock = false; }, WHEEL_QUIET);
};

// The lock releases on a QUIET stream, so something must refresh it on every event of
// the tail. It cannot be the card: for the ~220ms between commit and re-render the
// flown card is 700px away and the card under the cursor is not armed yet, so a
// card-attached listener sees nothing and the lock lapses exactly when it is needed.
// Listen at the window, in the CAPTURE phase so it runs before the card's handler.
addEventListener("wheel", e => {
  if (!wheelLock) return;
  const v = wheelSpeed(e);
  // Momentum only ever DECAYS, but noisily. Compare against a smoothed LEVEL of the tail
  // (never its running minimum - one low reading drags a min down and every ordinary
  // event after it looks like a rise), and release only on a SUSTAINED climb: that is
  // the user starting a new swipe, and the second of two quick flicks must not be eaten.
  if (v > Math.max(lockLevel * WHEEL_RESTART, WHEEL_RESTART_MIN)) {
    if (++lockRise >= WHEEL_RESTART_RUN) { wheelLock = false; return; }
  } else {
    lockRise = 0;
    lockLevel += (v - lockLevel) * 0.3;
  }
  e.preventDefault();
  clearTimeout(wheelLockTimer);
  wheelLockTimer = setTimeout(() => { wheelLock = false; }, WHEEL_QUIET);
}, { passive: false, capture: true });

// The pointer release must be caught even when the pointerup lands somewhere other than
// the card - see "The release that never came". ONE pair of window listeners for the whole
// page, delegating to whichever card is mid-drag; per-card window listeners would leak one
// dead closure per swipe.
let activeRelease = null;
addEventListener("pointerup",     () => activeRelease && activeRelease());
addEventListener("pointercancel", () => activeRelease && activeRelease());
```

## The handler

Attach to the front card only. `it` is the item; `fly()` animates the card off and
commits the verdict.

```js
function arm(el, it){
  let x = 0, y = 0, sx = 0, sy = 0, down = false, spent = false, idle = null;
  let limit = dragLimit;
  const keep = el.querySelector(".stamp.keep"), close = el.querySelector(".stamp.close");
  const tint = el.querySelector(".tint");

  const move = () => {
    el.style.transform = `translate(${x}px, ${y}px) rotate(${x / 22}deg)`;
    const t = Math.min(Math.abs(x) / limit, 1);          // 0..1 of the way to committing
    const dir = x > 0 ? 1 : x < 0 ? -1 : 0;
    keep.style.opacity  = x > 0 ? t : 0;
    close.style.opacity = x < 0 ? t : 0;
    // Three signals on one number, so the verdict is legible BEFORE you commit to it.
    if (dir) tint.style.background = dir > 0 ? "var(--yes)" : "var(--no)";
    tint.style.opacity = t * 0.16;
    el.style.borderColor = t > 0.04 ? (dir > 0 ? "var(--yes)" : "var(--no)") : "";
    setEdges(t, dir);
  };

  const snapBack = () => {
    el.style.transition = "transform .34s cubic-bezier(.34,1.32,.64,1), opacity .34s";  // slight overshoot reads as springy
    x = 0; y = 0; move();
  };

  const release = () => {
    if (spent) return;
    if (Math.abs(x) > limit) { spent = true; clearTimeout(idle); fly(el, x > 0 ? "keep" : "close", it); }
    else snapBack();
  };

  // --- pointer drag (mouse + touch)
  const up = () => { if (!down) return; down = false; activeRelease = null; release(); };

  el.addEventListener("pointerdown", e => {
    if (e.button !== 0 || spent) return;
    limit = dragLimit; sx = e.clientX; sy = e.clientY;
    el.style.transition = "none";
    try { el.setPointerCapture(e.pointerId); } catch (_) {}  // throws if the pointer is already gone
    down = true;          // AFTER the capture attempt: a throw above must not leave this stuck on
    activeRelease = up;   // window listeners above now own the release
  });
  el.addEventListener("pointermove", e => {
    if (!down) return;
    x = e.clientX - sx; y = e.clientY - sy; move();
  });
  el.addEventListener("lostpointercapture", up);   // capture yanked mid-drag

  // --- trackpad two-finger horizontal swipe.
  // macOS keeps firing momentum wheel events after the fingers lift, so fire the
  // moment the card clears the threshold rather than waiting for the gesture to end.
  el.addEventListener("wheel", e => {
    if (down || spent) return;
    if (Math.abs(e.deltaX) < WHEEL_DEADZONE) return;
    if (Math.abs(e.deltaX) <= Math.abs(e.deltaY) * WHEEL_BIAS) return;  // vertical-ish: let the body scroll
    e.preventDefault();
    if (wheelLock) return;   // momentum tail of the gesture that just committed (window listener holds it)
    limit = wheelLimit();
    el.style.transition = "none";
    x += e.deltaX * WHEEL_DAMP * wheelDir;
    move();
    clearTimeout(idle);
    if (Math.abs(x) > limit) { holdWheelLock(e); release(); }
    else idle = setTimeout(snapBack, 180);   // gesture ended short of the threshold
  }, { passive: false });
}
```

`{ passive: false }` is required - without it `preventDefault()` is ignored and a
horizontal swipe triggers browser back/forward navigation.

## One card, one verdict

A fast second input during the ~180ms fly-off otherwise commits to the *next* item.
Guard inside `fly()`, not at each call site, so keyboard and gesture paths both inherit it:

```js
function fly(el, verdict, it){
  if (el.dataset.spent) return;
  el.dataset.spent = "1";
  el.classList.remove("front");
  /* ...animate, commit... */
}
```

And in the keyboard path, ignore input while a card is mid-flight rather than
falling through to the next item:

```js
const front = stage.querySelector(".card.front");
if (front) fly(front, verdict, it);   // no front card = mid-flight; drop the input
```

## One gesture, one card

The third real bug, and the ugliest. `spent` above is per-CARD, but a macOS momentum
wheel stream runs ~900ms past the fingers lifting - far longer than the ~220ms it takes
to commit and re-render. So the back half of ONE physical flick lands on the freshly
armed NEXT card: it slides sideways, tilts, then rubber-bands back to center. The user
sees a card they never touched "reappear". Flick harder and it silently commits a second
verdict.

Per-card state cannot fix this, because the card the state lives on is already gone.
The lock has to sit in module scope and outlive the card - that is what `holdWheelLock`
is for. Take it when a wheel gesture commits, and re-arm it on every swallowed event, so
it releases only once the wheel stream has actually gone quiet for `WHEEL_QUIET` ms
rather than after a fixed timeout that a long momentum tail would outlast.

The pointer path needs no equivalent - `pointerup` ends that gesture cleanly, with no tail.

To reproduce: dispatch ~24 `wheel` events of `deltaX: 70`, then a decaying tail
(`d *= 0.955`, 60 events, 15ms apart), and watch `getComputedStyle(front).transform` on
the card *after* the one you swiped. Unfixed, it picks up a visible rotation. **A clean
tail is not enough** - it passed against a lock that still leaked. Add +-30% jitter per
event, or merge three tail events into one (summed `deltaX`, 45ms gap) at the moment of
the re-render; both made the next card travel ~120px and tilt ~5deg before the fix below.
Dispatch to the element the gesture STARTED on until it leaves the document (Chrome
latches a wheel gesture to its first target), or the card slides out from under a fixed
hit-test point and never commits. [`swipe-repro.mjs`](swipe-repro.mjs) runs all of it
headless.

## The release that never came

The bug that actually gets reported, because it looks like the tool is possessed: you
swipe a card, it travels past the threshold with the stamp at full opacity - and then it
drifts back to centre and the counter never moves.

`down` is the whole story. It is set by `pointerdown` and, in the naive version, cleared
only by a `pointerup` **on the card element**. Miss that one event and `down` stays true
forever. `pointermove` checks nothing but `down`, so from then on the card follows the
bare cursor with no button held - drift right and it tilts right and stamps KEEP, drift
back and it recentres - while `release()`, which only ever runs from `up()`, never fires.
No verdict is ever recorded. The giveaway in a screen recording is the cursor: it shows
`grab`, not `grabbing`, while the card is moving.

Three ways the up goes missing, all of them ordinary:

- `setPointerCapture` throws when the pointer is already gone. Set `down = true` AFTER
  the call, or the throw leaves it stuck on with no capture to deliver the up.
- Capture is lost mid-drag - the deck re-renders on commit and `stage.innerHTML = ""`
  destroys the capturing element. Listen for `lostpointercapture`.
- The up simply lands on another element. Listen on the **window**, not the card.

Use one window-level pair for the page delegating through `activeRelease`, not a pair per
card: `arm()` runs on every render, so per-card window listeners leak a dead closure per
swipe, each pinning a detached DOM node.

To reproduce: `pointerdown` on the card, ten `pointermove`s past the threshold, then
dispatch the `pointerup` on `document.body`. Unfixed, no verdict is recorded, and bare
`pointermove`s afterwards still move the card.

## The exit, and telling the user what they are doing

Two complaints arrive together once the gestures work: *"it just disappears"* and *"I want
a stronger indicator of what I'm doing"*. Both are cheap.

### The card must outlive the re-render

`commit()` re-renders, and `stage.innerHTML = ""` destroys the card **mid-flight** - the
fly-off is a ~500ms animation being cut off at 220ms, which reads as a hard vanish rather
than an exit. Hand the card to a sibling layer the re-render does not touch, and let it
remove itself when the fade actually ends:

```js
function fly(el, verdict, it){
  if (el.dataset.spent) return;
  el.dataset.spent = "1";
  el.classList.remove("front");
  const dir = verdict === "keep" ? 1 : -1;

  const from = el.style.transform;
  flyLayer.appendChild(el);
  el.style.zIndex = "30";
  // Re-parenting discards the element's style state, so the browser has no from-value to
  // interpolate and SKIPS the transition entirely (the card blinks out instead of fading).
  // Re-assert the current transform, force a reflow to record it, THEN animate.
  el.style.transition = "none";
  el.style.transform = from;
  el.style.opacity = "1";
  void el.offsetWidth;
  el.style.transition = "transform .5s cubic-bezier(.22,.72,.3,1), opacity .42s ease-out";
  el.style.transform = `translate(${dir * 620}px, ${dir * 60}px) rotate(${dir * 22}deg) scale(.94)`;
  el.style.opacity = "0";

  const done = () => el.remove();
  el.addEventListener("transitionend", done, { once: true });
  setTimeout(done, 800);                       // transitionend never fires under reduced-motion

  setTimeout(() => setEdges(0, 0), 160);
  setTimeout(() => commit(it, verdict), 220);  // deck advances while the old card is still leaving
}
```

Keeping the 220ms commit is deliberate: the deck should feel instant. Only the *departing*
card runs long, and it does so in a layer nothing else cares about.

### Three signals off one number

`t` (0..1 of the way to the threshold) drives everything, so they cannot disagree:

- **stamp** - KEEP / OUT, fading in
- **tint** - a wash of the verdict colour across the card face, capped at `0.16`; above that
  it fights the body text
- **border** - the card's own edge takes the verdict colour
- **badges** - a ✓ and a ✗ that brighten and scale with travel

```js
const REST = 0.16;                       // both stay faintly lit so the targets are known
const setEdges = (t, dir) => {           // dir +1 keep / -1 out / 0 none
  edgeKeep.style.opacity = dir > 0 ? REST + (1 - REST) * t : REST;
  edgeOut.style.opacity  = dir < 0 ? REST + (1 - REST) * t : REST;
  edgeKeep.style.transform = `scale(${0.86 + (dir > 0 ? t : 0) * 0.3})`;
  edgeOut.style.transform  = `scale(${0.86 + (dir < 0 ? t : 0) * 0.3})`;
};
```

Call `setEdges(0, 0)` at the top of `render()` too, or the badge stays lit under the next card.

**Put the badges BELOW the deck, not flanking it.** Two failed placements, both caught by
screenshotting a held mid-drag rather than reasoning about it: beside the deck, the card
travels sideways straight through them; above the card in z-order, they park a circle on
top of the body text. Below is the only band the card does not cross.

**And check the stamp against the chip.** The default `top: 24px` for both puts KEEP
directly on top of the category chip. Move the stamps to `bottom: 26px` - the lower half of
a card is nearly always empty.

## Required CSS

```css
/* overscroll-behavior-x stops the browser BACK gesture. It does NOT stop the page from
   scrolling when the document genuinely overflows - and a card at translate(700px) adds
   ~150px of scrollWidth, so without the clip a two-finger swipe pans the whole page
   sideways instead of moving the card. `clip` rather than `hidden`: hidden makes the
   element a scroll container (still pannable, and it breaks sticky ancestors). */
html, body { overflow-x: clip; overscroll-behavior-x: none; }
.card { touch-action: none; user-select: none; will-change: transform; }

/* the stage is what re-renders; the fly layer is what survives it */
.deck { position: relative; width: 100%; max-width: 520px; height: 400px; }
.stage, .fly-layer { position: absolute; inset: 0; }
.fly-layer { pointer-events: none; z-index: 5; }

.tint { position: absolute; inset: 0; border-radius: inherit; opacity: 0; pointer-events: none; }
.stamp { position: absolute; bottom: 26px; z-index: 2; }   /* NOT top - that is where the chip lives */

.edge {                                    /* below the deck: the only band the card never crosses */
  position: absolute; bottom: -74px; width: 50px; height: 50px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  opacity: .16; z-index: 20; pointer-events: none;
  transform: scale(.86); transition: opacity .14s linear;
}
.edge.keep { right: 14px; color: var(--yes); background: var(--yes-soft); border: 2px solid var(--yes); }
.edge.out  { left:  14px; color: var(--no);  background: var(--no-soft);  border: 2px solid var(--no); }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important } }
```

## The swipe that drags the whole page

Reported as "it's laggy and it drags my whole screen to the side". Neither word is about
the handler: the page is genuinely scrolling.

A card at `translate(700px)` sits outside the stage, and nothing clips it, so the
document's `scrollWidth` grows - measured at **+156px** mid-flight. That is a real
horizontal scroll, and a two-finger swipe pans it. `overscroll-behavior-x: none` does not
help; it governs the browser's back/forward gesture, not an overflowing document. Clip it
at the root (see Required CSS). Measure rather than eyeball:
`document.documentElement.scrollWidth - clientWidth` during a fly-off.

The "laggy" half is the card's large blurred box-shadow being re-rasterized every frame of
a transform. `will-change: transform` puts the card on its own layer so the shadow is
rasterized once. Only ~3 cards exist at a time, so the layer cost is nothing.

## The lock that ate the next swipe

The gesture lock above has an obvious failure mode, and it is worth stating because the
fix for one bug caused it: hold the lock until the wheel stream goes quiet, and a user who
flicks twice in quick succession loses the second flick entirely. Their new gesture arrives
while the previous momentum is still trailing, so it refreshes the lock instead of breaking
it. That presents as "sometimes when I swipe, it doesn't respond" - the worst kind of
report, because it is intermittent and the handler looks correct.

The discriminator is physical, not temporal: **momentum only ever decays.** A timeout
cannot do this job - any value long enough to outlast a real tail is also long enough to
eat a fast second swipe.

### The release that fired too early

The first version of that discriminator tracked the running MINIMUM of `|deltaX|` and
released on any single delta above 1.5x it. It passed a clean synthetic tail and still
leaked: "sometimes when you swipe one, the 2nd card starts to swipe a bit". Real tails
break a min-floor two ways, and each release hands the rest of the tail (~120px of travel,
~5deg of tilt) to the next card:

- **Jitter.** Momentum decays on a trend, not monotonically. One low reading drags a
  running min well under the trend, and the next ordinary reading is then 1.5x above it.
- **Coalescing.** The commit re-render blocks the main thread for a frame or two, and
  Chrome merges the wheel events that queued up into one carrying their summed `deltaX` -
  a 3x "rise" that is really three frames of the same decaying tail.

So the handler measures **speed** (`deltaX` per 16ms frame, from `e.timeStamp`), compares
it to a **smoothed level** of the tail (an EMA, which lags above a decaying curve rather
than below it), and releases only when the climb is **sustained** (`WHEEL_RESTART_RUN`
events in a row) and **absolute** (over `WHEEL_RESTART_MIN` px/frame, since the slow end of
a tail is integer noise where 1 to 2 is already a 2x "rise"). A genuine new flick clears
all three within its first two or three events, and a real flick never misses those.

Reproduce by firing a full flick, ~20 decaying tail events, then a second full flick with
no pause, and again with a 60ms pause. The second must commit both times.

## The controls that end the tuning loop

```html
<label class="slider">
  resistance
  <input type="range" id="sens" min="80" max="500" step="10" value="230">
  <output id="sensVal">230</output>px
</label>
<button id="flipDir">Flip swipe direction</button>
```

```js
$("sens").value = dragLimit;
$("sensVal").textContent = dragLimit;
$("sens").oninput = e => {
  dragLimit = +e.target.value;
  $("sensVal").textContent = dragLimit;
  localStorage.setItem(KEY + ":drag", dragLimit);
};

$("flipDir").onclick = () => {
  wheelDir = -wheelDir;
  localStorage.setItem(KEY + ":dir", wheelDir);
};
```

Both take effect on the next gesture - `arm()` re-reads `dragLimit` at gesture start,
so no re-render is needed.
