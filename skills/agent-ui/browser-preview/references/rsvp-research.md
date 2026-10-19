# RSVP speed readers: what the real implementations actually do

Research notes for the `browser-preview` speed reader.
Every claim below is traced to a primary source: a line of source code in a named repo, a patent, a vendor spec, or a peer-reviewed paper.
Blog summaries were not used.

## Sources consulted (primary)

Source code, cloned and read directly at the paths given:

| Reader | Repo | Language | Notes |
|---|---|---|---|
| OpenSpritz | `Miserlou/OpenSpritz` | JS bookmarklet | The original open Spritz clone. `spritz.js`, `style.css`, `spritz.html` |
| Squirt | `cameron/squirt` | JS bookmarklet | `squirt.js`, `squirt.css` |
| jetzt | `ds300/jetzt` | JS Chrome extension | The most carefully engineered of the group. `modules/parse.js`, `modules/exec.js`, `modules/view.js`, `modules/config.js`, `jetzt.css` |
| Sprint Reader | `anthonynosek/sprint-reader-chrome` | JS Chrome extension | Still maintained. `src/engine.js`, `src/reader.js`, `src/utility.js` |
| speedread | `pasky/speedread` | Perl, terminal | Explicitly "the way Spritz probably does it" |
| tspreed | `n-ivkovic/tspreed` | POSIX shell, terminal | v2.6.2 |
| quickreader | `coinstax/quickreader` | Svelte 5 | Recent; useful as a contemporary data point, but note it is an AI-assisted build (it ships a `CLAUDE.md`), so treat it as "current practice" not "authority" |

Squirt's own README names its lineage explicitly, which is why these implementations converge - they are all reimplementations of Spritz:

> ## Sister Projects
> * [Spritz](http://www.spritzinc.com/)
> * [OpenSpritz](https://github.com/Miserlou/OpenSpritz)
> * [speedread](https://github.com/pasky/speedread) - A terminal Spritzer.
> * [jetzt](https://github.com/ds300/jetzt) - jetzt, a Spritz Chrome extension

- `cameron/squirt`, `README.md`

---

Spritz's own primary sources, read directly:

| Source | Identifier |
|---|---|
| The patent | **US 8,903,174 B2**, "Serial text display for optimal recognition apparatus and method". Inventors Maik Steffen Maurer, Matthias Klein, Francis Abbott Waldman. Assignee Spritz Holding LLC. Filed 2012-07-12 (PCT), granted 2014-12-02 |
| Continuations (same spec, re-cut claims, no new disclosure) | US 2014/0016867 A1, US 2015/0199944 A1, US 2017/0229101 A1, US 2019/0325848 A1, US 2020/0193939 A1, US 2021/0312890 A1 |
| Foreign family | EP 2872984 B1, JP 6243418 B2, CN 104685464 B, ES 2700224 T3, WO 2014/011884 A1 |
| Spritz's own site | `spritzinc.com/the-science/`, `/faq/`, and the blog posts "Why Spritz Works: It's All About Alignment" (2014-02-16) and part II (2014-02-20), via web.archive.org - the live site no longer carries them |
| Spritz's shipped JS SDK | `sdk.spritzinc.com/js/1.0/js/spritz.min.js` (version string `Spritz_JSSDK 1.0.4, buildDate Fri Apr 04 2014`), `css/spritz.min.css`, and the webhelp docs at `sdk.spritzinc.com/js/1.0/doc/webhelp/` |
| Spritz's commissioned comprehension study | Penn Schoen Berland, June 2014, `sdk.spritzinc.com/www/1.0/psb/Spritz-PSB-study.pdf` |

Things that turned out **not** to exist, so nobody wastes time looking: there is no separate ORP or redicle patent (it is all one 2012 family); `dev.spritzinc.com`, `developer.spritzinc.com` and `docs.spritzinc.com` never existed; the iOS and Android SDK docs are not archived anywhere; and the figures on `/the-science/` are lost even in the Wayback capture (prose survives, images 404).

---

## 1. ORP / pivot letter

### Spritz's own rule - the source everyone else was guessing at

The patent defines the term:

> "In order to prevent or minimize recovery saccades in an RSVP, it is preferable to display each word such that the optimal fixation position does not shift in the display. The focal point of the reader can then remain fixed on the optimal fixation position, which is a specific point in each word that is determined by the total number of characters or width of the word. This optimal recognition position, hereinafter referred to as the 'ORP,' can be identified in the display such that the reader's eyes are directed to focus there as the words are serially presented."

- US 8,903,174 B2, Summary of the Invention

Note the terminology: the patent says **optimal recognition posi*tion***; Spritz's own site says "Optimal Recognition **Point**" on `/the-science/` but "Optimal Recognition **Position**" in the blog. Both abbreviate ORP. The open-source clones all say "point".

**TABLE I, verbatim from US 8,903,174 B2** (1-indexed):

| Total number of text characters | ORP character position | ORP character position ratio |
|---|---|---|
| 3 | 2 | 0.33 |
| 4 | 2 | 0.25 |
| 5 | 2 | 0.20 |
| 6 | 3 | 0.33 |
| 7 | 3 | 0.29 |
| 8 | 3 | 0.25 |
| 9 | 3 | 0.22 |
| 10 | 4 | 0.30 |
| 11 | 4 | 0.27 |
| 12 | 4 | 0.25 |
| 13 | 4 | 0.23 |
| 14-20 | 5 | NA |

The patent is candid that most of this table is interpolation, not measurement:

> "Brysbaert and Nazir had provided recommendations for the ORP character position only for words of 3, 5, 7, and 9 characters in length. Certain embodiments of the present invention rely on having determined ORP character positions for words of 4, 6, 8, and 10-13 characters in length. A ratio based on the ORP character position was created in order to interpolate between the established values … and to extrapolate for words of 10-13 characters in length."

with the ratio defined as:

> "**ORP Character Position Ratio = (ORP Character Position − 1) / Total Number of Text Characters**
>
> The values of the ORP character position for words of 4, 6, 8, and 10-13 characters in length are determined by keeping the ORP character position ratio between 0.20 to 0.33 and applying the above formula. The resulting values of the ORP character positions, which are summarized in TABLE I, were empirically tested and confirmed by the inventors with 20 subjects…"

So the design constraint is **keep the ORP between 20% and 33% into the word**, and Table I is the integer solution to that constraint.

FIG. 7 gives the implementation branch, which supplies the length-1 case Table I omits:
`wl == 1 → orpc = 1`; `1 < wl < 6 → 2`; `5 < wl < 10 → 3`; `9 < wl < 14 → 4`; else `5`.

**That is exactly the OpenSpritz / speedread / jetzt table.** The open-source clones guessed right - which makes sense, since the constraint has only one sensible integer solution.

The patent excludes punctuation from the count:

> "note that 'characters' in this context - i.e. for purposes of counting the number of characters in a word display element - only include parts of the word itself, e.g., letters, and do not include punctuation characters, even though … text may be parsed such that a punctuation mark is included as part of the same display element as a word"

This is the rule jetzt and Squirt implement (`token.replace(/[?.,!:;*-]+$/, "")`) and that OpenSpritz, tspreed, speedread and quickreader do not.

**A pixel-proportional alternative** is also disclosed, for proportional fonts:

> "The average of the ORP character position ratio values in TABLE I yields an **average ORP character position ratio of 0.265**. This can be used to determine the ORP offset … according to the following formula:
>
> **ORP Offset = (Width × Average ORP Character Position Ratio) + (0.5 × Average Character Width)**
>
> where Width is the total width of the text (e.g., a word to be displayed) in pixels and Average Character Width is the Width divided by the total number of characters in the text. This will account for the use of proportionally spaced fonts…"

bounded by claims 15, 29 and 59:

> "the proportion of a word … that is displayed from the word's beginning to the fixed display location is greater than or equal to 0.2 and less than or equal to 0.45."

**Two caveats on the patent's internal consistency.** FIG. 2d's walkthrough says "FIG. 2d shows the display of the longer word 'presentation', where the **5th character** is the ORP character 205" - but "presentation" is 12 characters, and Table I plus claim 8 both say the 4th. Nothing in the document resolves this.
And the patent carves out short words entirely:

> "In serial text display, saccades are most noticeably a problem for words that are five or more characters in length. Therefore, a preferred embodiment … places the ORP at the fixed display location at least for display elements that are five or more characters in length. … when such words (length four or less) are displayed at the fixed display location, exactly which character or proportionate position of these words is displayed at the fixed display location is not necessarily critical for minimizing saccades."

**And the shipping product does not run Table I on the client at all.** Reading Spritz's own `spritz.min.js`, the ORP index is a 4-bit field packed into the stream by the closed server-side `spritzify` engine (`SPRITZ.model.SpritzText.create`, container `"V2"`, encoding `"AAAC"`: bits 0-2 flags `SENTENCE_START=1, BOLD=2, PARAGRAPH_START=4`, bits 3-16 multiplier, **bits 17-20 orp**, bits 21-50 source position). So the client is a dumb renderer.

### The rule, from actual source

**OpenSpritz** (`Miserlou/OpenSpritz`, `spritz.js`, function `pivot`) - this is the table nearly everyone else copied.
Note it is a **1-based** index:

```js
// Find the red-character of the current word.
function pivot(word){
    var length = word.length;

    var bestLetter = 1;
    switch (length) {
        case 1:
            bestLetter = 1; // first
            break;
        case 2:
        case 3:
        case 4:
        case 5:
            bestLetter = 2; // second
            break;
        case 6:
        case 7:
        case 8:
        case 9:
            bestLetter = 3; // third
            break;
        case 10:
        case 11:
        case 12:
        case 13:
            bestLetter = 4; // fourth
            break;
        default:
            bestLetter = 5; // fifth
    };
```

**pasky/speedread** (`speedread`, `sub find_ORP`) - identical rule, expressed as a lookup table, 0-based, and the comment says out loud that it is a guess at Spritz:

```perl
# ORP: Optical Recognition Point (the red-colored alignment pilot),
# the way Spritz probably does it.
sub find_ORP {
	my ($word, $ORPloc) = @_;

	return 4 if (length($word) > 13);
	return (0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3)[length($word)];
}
```

Indexing that array by word length gives: len 1 → 0, len 2-5 → 1, len 6-9 → 2, len 10-13 → 3, len ≥14 → 4.
That is exactly OpenSpritz's table with 1 subtracted.

**jetzt** (`ds300/jetzt`, `modules/view.js`, `calculatePivot`) - same shape, 0-based, written as thresholds:

```js
  // calculate the focal character index
  function calculatePivot (word) {
    var l = word.length;
    if (l < 2) {
      return 0;
    } else if (l < 6) {
      return 1;
    } else if (l < 10) {
      return 2;
    } else if (l < 14) {
      return 3;
    } else {
      return 4;
    }
  }
```

Identical to speedread/OpenSpritz.
jetzt adds one refinement the others lack - it strips trailing punctuation before computing the pivot, so `word,` pivots like `word`:

```js
    this.setWord = function (token, dec) {
      var pivot = calculatePivot(token.replace(/[?.,!:;*-]+$/, ""));
```

- `ds300/jetzt`, `modules/view.js`

**tspreed** (`n-ivkovic/tspreed`) - one letter different at length 2 (it treats a 2-letter word like a 1-letter word):

```sh
		# Set focus letter
		case "$word_len" in
			1|2)         word_focus_pos=1 ;;
			3|4|5)       word_focus_pos=2 ;;
			6|7|8|9)     word_focus_pos=3 ;;
			10|11|12|13) word_focus_pos=4 ;;
			*)           word_focus_pos=5 ;;
		esac
```

**Squirt** (`cameron/squirt`, `squirt.js`) - the outlier. It uses a *formula*, `floor(len/2) - 1`, not a table, and it strips trailing punctuation first (like jetzt) and handles a trailing newline:

```js
  // ORP: Optimal Recgonition Point
  function getORPIndex(word){
    var length = word.length;
    var lastChar = word[word.length - 1];
    if(lastChar == '\n'){
      lastChar = word[word.length - 2];
      length--;
    }
    if(',.?!:;"'.indexOf(lastChar) != -1) length--;
    return length <= 1 ? 0 :
      (length == 2 ? 1 :
          (length == 3 ? 1 :
              Math.floor(length / 2) - 1));
  };
```

Squirt's formula drifts right for long words: a 16-letter word gets index 7, where the Spritz-family table caps at 4.
That is a real disagreement, and Squirt's behaviour is the minority position.

**Sprint Reader** (`anthonynosek/sprint-reader-chrome`, `src/engine.js`) - a coarser 1-based table, and it disagrees with the OpenSpritz family at lengths 2 and 5:

```js
// Assigns the optimal letter position in the word
// This is used to colour the optimal letter in the word
// to aid with comprehension
//
// Function will return the optimal letter position
// 1 based index of characters in the word
function assignOptimalLetterPosition(textItem) {
    // This algroithm will determine the letter based on word length
    var length = textItem.text.length;
    var position = 0;

    if (length == 1) position = 1;
    else if (length >= 1 && length <= 4) position = 2;
    else if (length >= 5 && length <= 9) position = 3;
    else position = 4;

    return position;
}
```

Note it never goes past the 4th letter, even for a 20-character word.

**quickreader** (`coinstax/quickreader`, `src/lib/utils/orp.ts`) - a modern restatement, 0-based, with thresholds shifted by one at the boundaries, and Unicode grapheme-aware:

```ts
/**
 * ORP positioning (based on character count, not code unit count):
 * - 1-2 letters: 1st letter (index 0)
 * - 3-6 letters: 2nd letter (index 1)
 * - 7-9 letters: 3rd letter (index 2)
 * - 10+ letters: 4th letter (index 3)
 */
export function getORPIndex(word: string): number {
	// Use Unicode-aware character count
	const len = toCharArray(word).length;
	if (len <= 2) return 0;
	if (len <= 6) return 1;
	if (len <= 9) return 2;
	return 3;
}
```

### Consensus table

Collapsing the above, with 0-based index:

| Word length | OpenSpritz / speedread / jetzt | tspreed | Sprint Reader | quickreader | Squirt |
|---|---|---|---|---|---|
| 1 | 0 | 0 | 0 | 0 | 0 |
| 2 | 1 | 0 | 1 | 0 | 1 |
| 3 | 1 | 1 | 1 | 1 | 1 |
| 4 | 1 | 1 | 1 | 1 | 1 |
| 5 | 1 | 1 | 2 | 1 | 1 |
| 6 | 2 | 2 | 2 | 1 | 2 |
| 7 | 2 | 2 | 2 | 2 | 2 |
| 8 | 2 | 2 | 2 | 2 | 3 |
| 9 | 2 | 2 | 2 | 2 | 3 |
| 10 | 3 | 3 | 3 | 3 | 4 |
| 11-13 | 3 | 3 | 3 | 3 | 4-5 |
| 14+ | 4 | 4 | 3 | 3 | 6+ |

The dominant rule is unambiguous: **1 → 0; 2-5 → 1; 6-9 → 2; 10-13 → 3; 14+ → 4**, computed on the word with trailing punctuation stripped.

### Colour

**Spritz is red, and the exact value is `#CC0001`.**
The patent is deliberately generic:

> "A colored font, such as a **red font**, may be utilized to emphasize the ORP character 205 as shown in FIG. 2c."

and claims 34 and 37 only require "a different color font for a character displayed at the fixed display location than is used for other characters".
Spritz's own FAQ says "Simply look at the **red character** and trust that your brain retains the whole word."

The actual hex comes from Spritz's shipped SDK, `sdk.spritzinc.com/js/1.0/js/spritz.min.js` (`SPRITZ.display.SpritzReadingPanel`, v1.0.4, 2014-04-04):

```
q = "#FFFFFF"   // redicle background fill
r = "#000000"   // normal character colour
s = "#CC0001"   // ORP ("best letter") character colour
t = "Black"     // redicle rule + tick-mark stroke colour
B = "#E8E8E8"   // grey wipe used in the 750 ms lead-in animation
```

with the highlight as a toggle, default on:

```
nb = function(){ K = I ? s : r }          // I = true by default
this.getHighlightBestLetter = function(){ return I }
this.setHighlightBestLetter = function(a){ I = a, nb() }
```

Note what Spritz does **not** do: the ORP letter is not bolded or enlarged relative to the rest. In the draw routine `yb()` the prefix, ORP character and suffix all use the same font object; only `fillStyle` differs. Bold is a per-word property carried from the source markup (`FLAG_BOLD`), never an ORP treatment.
`#CC0001` is an implementation artefact rather than a published spec - Spritz never wrote a hex value down anywhere - but it is their own shipping code, which is as authoritative as it gets.

The open-source clones all landed within a few percent of it:

| Reader | ORP colour | Source |
|---|---|---|
| **Spritz** | **`#CC0001`** on `#FFFFFF`, rest `#000000` | `spritz.min.js` v1.0.4 |
| OpenSpritz | `#de0000` | `style.css`, `.pivot, .spritz_pivot{ color: #de0000; }` |
| Squirt | `rgb(238, 69, 69)` | `squirt.css`, `.sq .orp{ color: rgb(238, 69, 69); }` |
| jetzt (light) | `#E01000` | `modules/config.js`, `"pivot": "#E01000"` |
| jetzt (dark) | `#73b5ee` (light blue) | `modules/config.js`, `"pivot": "#73b5ee"` |
| Sprint Reader | `#FF8C00` (dark orange) | `src/reader.js`, `highlightOptimalLetterColour = "#FF8C00";` |
| speedread | terminal `red` | `speedread`, `color("red")` |
| tspreed | off by default; `--focus-color` takes a 0-255 ANSI index, or `--focus-bold` bolds instead of colouring | `tspreed` option parsing |
| quickreader | `#ff4444` dark / `#cc0000` light / `#8b0000` sepia | `src/lib/constants.ts` |

The two useful lessons: **jetzt swaps to blue on a dark background** rather than keeping red (red on near-black is low-contrast and vibrates), and **tspreed proves bold-only works** when colour is unavailable.
quickreader is the only one that documents contrast: its constants file records the ORP/background ratios (3.7:1 dark, 5.9:1 light, 11.3:1 sepia) against WCAG 2.1 AA.

### Do non-Spritz readers use a pivot at all?

tspreed is the clean natural experiment: focus highlighting is **opt-in** (`-f`/`--focus`), and when it is off, the word is simply centred on its own midpoint:

```sh
	# No focus letter highlighting
	else
		# Set horizontal position of word
		[ $((word_x + word_len)) -le "$term_width" ] && word_x=$((term_x_center - (word_len / 2)))
```

So plain centred text is a supported mode, not an unheard-of one.
Sprint Reader likewise has a `textPosition` setting where `2 = Optimal text positioning` is only one of the options, and it *disables* both the ORP highlight and the guide when chunk size is greater than one:

```js
    if (highlightOptimalLetter && chunkSize == 1) {
```
```js
    // Do not show the guide if the chunk size is more than 1
    if (chunkSize > 1 || madvAlwaysHideFocalGuide) {
        hideFocalGuide();
```

- `anthonynosek/sprint-reader-chrome`, `src/engine.js` and `src/reader.js`

---

## 2. Placement

### Horizontal: the pivot column is left of centre

This is the single most consistent design decision across implementations, and it is worth stating plainly: **the pivot is locked to a fixed x, and that x is roughly 30% of the frame width, not 50%.**

| Reader | Pivot column x | Source |
|---|---|---|
| **Spritz (the product)** | **35% of the redicle width** | `spritz.min.js`, layout constant `m = .35`, `T = round(width * 0.35)` |
| jetzt | `left: 110px` + half of `width: 10px` = **115px in a 400px box = 28.75%** | `jetzt.css`, `.sr-reader .sr-word-box .sr-reticle` and `.sr-word-box { width: 400px; }` |
| Sprint Reader | **30% of window width**, as an explicit user-facing setting | `src/utility.js`, `madvOptimisedPositionLeftMarginPercent = 30;` |
| Squirt | **34%** of viewport | `squirt.css`, `.sq .reader { left: 34%; }` |
| speedread | column 20 of an 80-column line = **25%** | `speedread`, `my $ORPvisualpos = 20;` |
| OpenSpritz | character cell 11 of a 22-cell monospace row = **~48%** | `spritz.js` padding maths, below |
| tspreed | terminal `x_center` = **50%** | `tspreed`, `word_x=$((term_x_center - word_focus_pos + 1))` |
| quickreader | **50%** (symmetric `1fr auto 1fr` grid) | `src/lib/components/Redicle.svelte` |

Sprint Reader computes it literally:

```js
        leftPaddingBorderOptimised = Math.round(window.innerWidth * (madvOptimisedPositionLeftMarginPercent / 100));
```
- `src/reader.js`

So the field splits: **Spritz itself and the three richest desktop clones (jetzt, Sprint Reader, Squirt) put the pivot column at 28-35%**, while the terminal readers and the newest web one centre it at 50%.
Spritz's 0.35 is the authoritative number, and the clones landing at 28-34% is convergent evidence, not coincidence.

The patent states the constraint the number satisfies:

> "Fixed display location 201 is positioned within the display 200 to accommodate at least four characters to its left"

- US 8,903,174 B2

### Why left of centre

Two distinct reasons, and they are often conflated. Both are real:

1. **The word extends further right than left.** Because the pivot index is ~1/3 into the word, a long word hangs mostly to the right of the pivot. If the pivot sat at 50%, long words would overflow the right edge while the left half sat empty. Putting the pivot at ~30% balances the *frame*, not the word. This is a pure layout argument and it is why 30% and not 50%.
2. **The eye's preferred landing position within a word is left of the word's centre.** This is the psycholinguistic claim (see §4 and the optimal-viewing-position literature). It justifies putting the *highlight* left of the word's middle - i.e. the ORP index rule in §1 - rather than where the pivot column sits on screen.

**Spritz's own justification for (2)** is entirely a citation chain to prior research, not new work of their own. From the patent's Summary:

> "Previous research on word recognition, however, has demonstrated that the eye tends to fixate on characters that are to the left of the center. O'Regan conducted experiments on the fixation point in words ranging in length up to 11 characters, clearly showing that word recognition (naming acuity) depends strongly on the position in the word where the eye is fixating at the moment the word appears."

> "**Words longer than three characters have an optimal fixation position to the left of the middle character for which the time required for word recognition is the shortest. For each letter of deviation from this optimal position, about 20 milliseconds ('ms') are added to lexical decision time or naming latency.**"

> "Rayner … demonstrated that it is possible to get information about a word from up to 4 characters from the left side of the fixation position and up to 15 characters to the right side, resulting in a perceptual span of 20 characters."

> "Note that the ORP character position shifts progressively further from the middle of the word as the total number of characters increases beyond three characters."

Cited: O'Regan et al., *J. Exp. Psych.* 1984 10(2):250-257; Brysbaert & Nazir; Rayner et al., *Perception & Psychophysics* 1980 27(6):537-534 [sic, as printed in the patent]; Rayner 1995; Hyrskykari 2006; Dehaene 2007; Sigurd et al. 2004.

The patent's headline efficiency claim - the one Spritz's marketing rests on - is:

> "The fixation takes about 240 milliseconds ('ms') per word on average. **Only 20% of the time for fixation is used for processing the content.**"

restated on `spritzinc.com/the-science/`:

> "When reading, only around 20% of your time is spent processing content. The remaining 80% is spent physically moving your eyes from word to word and scanning for the next ORP."

That 80/20 framing is the core of the Spritz pitch, and §9 is where it gets tested against the reading literature.

Spritz's own blog adds the argument for why a *fixed* column matters even with a per-word ORP:

> "In Figure 1, the preferred fixation point (character) is indicated **in red**… For example, the ORP is only in the middle of a 3-letter word. **As the length of a word increases, the percentage that the ORP shifts to the left of center also increases.**"

> "…depending on the language you're reading, there is a **low (less than 15%) probability of two adjacent words being the same length** and not requiring a saccade when they are shown to you one at a time."

- `spritzinc.com/why-spritz-works-its-all-about-the-alignment-of-words`, 2014-02-16

A conscientious open-source statement of the second reason: `rollecode/speed-reader`'s README puts it as "research shows fixations occur slightly left of center at the Optimal Viewing Position, and this implementation aligns each word's ORP at the exact same screen position, so the highlighted letter never moves."
That is the vendor-side framing; §9 records what the peer-reviewed literature actually supports.

### Vertical

- **jetzt**: dead centre of its panel. `.sr-word { position: absolute; top: 50%; transform: translateY(-50%); }` in a 100px-tall reader. The panel itself is centred in the viewport (`.sr-reader-wrapper { top: 50%; left: 50%; transform: translate(-50%,-50%) }`).
- **Squirt**: above centre. The modal is `top: 20%; height: 399px`, the word container is `top: 30%` inside it and `.sq .word { top: 34% }`. So the word sits in the upper third of a panel that itself starts a fifth of the way down - noticeably higher than screen centre.
- **tspreed / speedread**: terminal vertical centre (`term_y_center`).
- **quickreader**: flex-centred in its box.

Centre is the common answer; Squirt's above-centre is the deliberate exception (it blurs the underlying page and floats the reader in the upper area).

Squirt is also the only one that actively suppresses the page behind it - a 4px blur on every non-reader top-level child, plus an 80%-white scrim:

```css
.sq-blur {
  filter: blur(4px);
}

.sq-obscure {
  background-color: rgba(255, 255, 255, .8);
  position: fixed;
  width: 100%;
  height: 100%;
}
```
```js
  function blur(){
    map(document.body.children, function(node){
      if(!node.classList.contains('sq'))
        node.classList.add('sq-blur');
    });
  };
```
- `cameron/squirt`, `squirt.css` and `squirt.js`. jetzt does the milder version: a full-screen backdrop at `backdrop_opacity` 0.07 light / 0.86 dark.

### Guide marks

#### Spritz's "redicle" - the original, with exact geometry

Spritz's own spelling in prose is **"redicle"**, though their asset filenames say *reticle* (`powered_by_spritz_reticle.png`, CSS class `.reticle`).
Their definition:

> "A **redicle** is a visual frame where you can look to recognize a word without moving your eyes."

- Spritz JS SDK docs, `Redicle.htm`

> "you're reading text one word at a time in our **'redicle,'** a special visual frame we designed for reading."

- `spritzinc.com/faq/`

The word never appears in the patent, which calls them **"hash marks 202"** marking the **"fixed display location 201"**:

> "Fixed display location 201 is positioned within the display 200 to accommodate at least four characters to its left and can be identified with **hash marks 202**. Other identifiers such as circles, colors or textures may be used."

Claims 33 and 36 narrow it to *"the visual aid comprises **vertical lines above and below** the fixed display location."*

**The exact geometry, from Spritz's shipped renderer.** The redicle is drawn on a `<canvas>`. Layout constants from `spritz.min.js`:

```
l = .4     // font pixel size            = round(height * 0.40)
m = .35    // ORP column x               = round(width  * 0.35)     ← "T", the fixed display location
n = .1     // tick-mark length           = round(height * 0.10)     ← "S"
o = .113   // rule inset from top/bottom = round(height * 0.113)    ← "Z"
p = .03    // rule inset from left/right = round(width  * 0.03)     ← "Y"
u = 2      // stroke width, px
```

and the draw routine (deminified):

```js
ib = function () {
  var xL = Y,                    // left end of rules
      xR = width  - Y,           // right end of rules
      yT = Z,                    // top rule y
      yB = height - Z;           // bottom rule y
  line(xL, yT, xR, yT, 2, "Black");        // top horizontal rule
  line(T,  yT, T,  yT + S, 2, "Black");    // TOP TICK: hangs DOWN from the top rule
  line(xL, yB, xR, yB, 2, "Black");        // bottom horizontal rule
  line(T,  yB - S, T, yB, 2, "Black");     // BOTTOM TICK: rises UP to the bottom rule
};
```

So the redicle is **two full-width horizontal rules - not a box, there are no end verticals - plus two short ticks on the ORP column**, one descending from the upper rule and one ascending to the lower rule. Both 2px wide, each 10% of the redicle height.

Concrete numbers at the SDK default 340 × 70: font 28px; ORP column at x = 119; rules at y = 8 and y = 62 spanning x = 10 → 330; ticks 7px long (y 8→15 and y 55→62).

This settles a detail the clones all got differently: **the ticks point inward, toward the word, and they are anchored to a pair of rules that run the full width.** OpenSpritz's dash-row guide is the closest reproduction; jetzt's hollow-bordered box and Squirt's masked border are simplifications.

Spritz also has a **750ms lead-in**: `z = A = 750`, a grey `#E8E8E8` wipe converging on the ORP column before the first word, stepping every `C = 5` ms. That is the "circulating arrow 203 / countdown indicator 204" of FIG. 2b realised as an animation.

#### The clones

Three genuinely different techniques, all producing "two ticks, above and below, on the pivot column."

**(a) jetzt - a bordered box with a hollow middle.** This is the cleanest.

```css
.sr-reader .sr-word-box .sr-reticle {
  position: absolute;
  left: 110px;
  height: 100px;
  width: 10px;
  border-top: 20px solid #CCC;
  border-bottom: 20px solid #CCC;
  -moz-box-sizing: border-box;
  box-sizing: border-box;
}
```
- `ds300/jetzt`, `jetzt.css`

A 10px × 100px element whose top and bottom 20px are painted and whose middle 60px is transparent.
So: two ticks, each **10px wide and 20px tall**, separated by a **60px gap**, in a **100px-tall** frame, centred on x=115px.
Its colour is themed separately from the pivot (`"reticle": "#efefef"` light, `"#656565"` dark) - i.e. much fainter than the ORP letter.

**(b) Squirt - one full-height rule, masked in the middle.** The reader panel carries a left border down its whole height, and a small opaque block the colour of the background punches a hole in it where the word sits.

```css
.sq .reader {
  position: absolute;
  height: 100%;
  left: 34%;
  width: 46%;
  border-left: 1px solid rgba(0,0,0, .4);
}

.sq .focus-indicator-gap {
  position: absolute;
  height: 111px;
  background-color: #f6f6f6;
  width: 2px;
  left: -2px;
}
```
- `cameron/squirt`, `squirt.css`; the gap element is created inside the word container in `squirt.js`: `makeDiv({'class': 'focus-indicator-gap'}, wordContainer);`

**(c) Sprint Reader - two absolutely positioned 1px borders, sized from the word.** The tick length and the gap are computed from the rendered word rather than hard-coded:

```js
        var margin = wordContainerHeight * 0.05;
        if (fontSize <= 40) margin = wordHeightOuter * 0.2;
        ...
        var height = (wordHeight / 3).toFixed(0);
        divFocalGuideTop.css("height", height + "px");
        divFocalGuideBottom.css("height", height + "px");

        var toptop = middleOfWordContainer - wordOHHalf - margin - height;
        var bottomtop = middleOfWordContainer + wordOHHalf + margin;
```
- `anthonynosek/sprint-reader-chrome`, `src/reader.js`

So: **tick length = one third of the word's height**, **gap between tick and word = 5% of the container height** (or 20% of the word's outer height at small font sizes), both ticks 1px wide (`#focal-guide { border-left: 1px solid #000000; }`), coloured **the same as the ORP letter**:

```js
    var guideColor = $("body").css("color");
    if (highlightOptimalLetter) {
        guideColor = highlightOptimalLetterColour;
    }
```

**(d) OpenSpritz - drawn with text characters.** Because the whole thing is monospace, the guides are literal rows of em-dashes with a notch glyph at the pivot column:

```html
            <div id="guide_top">
――――――――――<span id="notch">&#1092;</span>―――――――――――
            </div>
            <div id="spritz_result"> … </div>
            <div id="guide_bottom">
――――――――――――――――――――――
            </div>
```
- `Miserlou/OpenSpritz`, `spritz.html`

Ten dashes, the notch, eleven dashes - 22 cells total, notch at cell 11.
Guide colour `#dddddd`.
Note the asymmetry: only the **top** guide carries a notch; the bottom is a plain rule.

**(e) speedread - a single red `v` above the column.**

```perl
sub show_guide {
	# Top visual guide
	say(" "x$ORPvisualpos . color('red') . "v" . color('reset') . "\033[K");
}
```

**(f) tspreed - configurable pointer characters, one row above and one below.**

```sh
	[ -n "$focuspointer" ] && [ "$focus" = true ] && {
		term_move $((term_y_center - 1)) "$term_x_center" && printf "%s" "$focus_pointer_1"
		term_move $((term_y_center + 1)) "$term_x_center" && printf "%s" "$focus_pointer_2"
	}
```

---

## 3. Timing model

### Spritz's own model

**Word display multiplier - FIG. 5a of US 8,903,174 B2, verbatim:**

| Text element character length (501) | Text element display multiplier (502) |
|---|---|
| 1-7 | 1 |
| 8-13 | 1.3 |
| > 13 | 1.6 |

**End-of-sentence blank element multiplier - FIG. 5b, verbatim:**

| Text elements in sentence (503) | Blank element display multiplier (504) |
|---|---|
| < 12 | 1.1 |
| 12-22 | 2.2 |
| > 22 | 3.3 |

Two things worth noticing immediately.
First, Spritz slows for long words **far less than jetzt does** (1.6× at its most extreme, vs jetzt's 2.0× at 12-13 characters), and it does not slow at all below 8 characters - no short-word floor.
Second, and this is the genuinely original idea nobody in the open-source corpus copied: **the sentence-end pause is proportional to the length of the sentence that just ended**, not a constant. A 30-word sentence gets three times the recovery pause of a 10-word one. The rationale is stated:

> "While, in alternative embodiments, it is possible to display each element for the same amount of time, it has been demonstrated empirically that a longer display time is beneficial for comprehension of longer words. It has also been demonstrated empirically that a longer pause between sentences is beneficial for comprehension of longer sentences."

Also note the pause is a **blank display element** - an empty frame - not a lengthened word. Same as jetzt's spacers.

**The patent's spec text contradicts FIG. 5b.** The FIG. 6 walkthrough says "step 618 determines whether wis is greater than twenty-two … step 620 determines whether wis is greater than **seven** … step 622 sets m to **1.0**", where FIG. 5b says the thresholds are 12 and 22 with a floor of 1.1. **The claims side with the figure** - claim 41: *"wherein the first predetermined number is twelve and the second predetermined number is twenty-two"*. Treat 12/22 and 1.1/2.2/3.3 as canonical.

**How the multiplier becomes milliseconds.** The patent normalises per document so the nominal wpm is honoured:

> "Step 718 calculates the average word relative duration ('awdr') by dividing the rtd by the wit. Step [7]19 then calculates the default update time ('dut') by dividing the update time ('ut') … by the awdr. Step 720 then sets a timer and the word is displayed for a time equal to the **product of the relative time multiplier and the dut**."

(`rtd` = running sum of multipliers, `wit` = word count.)
This is the same idea as Sprint Reader's word-length algorithm: vary per word, but keep the document total honest.

**The shipping SDK cheats on that.** From `spritz.min.js`:

```
h = 1.21      // fixed average-multiplier normaliser
i = 6e4       // ms per minute
vb = function(wpm){ return Math.floor(i / (wpm * h)) }        // base ms per word
wb = function(mult){ return (1 + mult/100) * vb(currentWpm) } // actual ms for this word
```

So the client formula is:

> **`ms(word) = (1 + multiplier/100) × floor(60000 / (wpm × 1.21))`**

with `multiplier` a per-word **percentage** baked into the stream server-side (14 bits), and **1.21 hard-coded as the average relative duration** rather than computed per document as the patent describes.
At 250 wpm the base slot is `floor(60000 / 302.5) = 198 ms`.

**Punctuation, numbers, paragraphs.**
Punctuation is stripped for both the multiplier and the ORP, but still rendered with the word:

> "step 607 calculates the word length ('wl') with punctuation trimmed from that word. In this embodiment, wl is calculated without including punctuation for purposes of calculating a display multiplier and determining an optimal recognition position character or offset."

Numbers are joined to their units into one frame:

> "when a number e.g., '9,' is displayed together with a unit, e.g. 'feet,' so that, for example, the text '9 feet' may be constitute a single display element and be presented together."

**There is no paragraph-break rule and no numeral-specific timing rule anywhere in the patent.** Parsing identifies "sections (such as paragraphs, chapters, etc.)" at step 404, but the only inter-element pause specified is the end-of-sentence blank. The shipped SDK carries a `FLAG_PARAGRAPH_START = 4` bit but the client never uses it for timing - any paragraph effect lives in the closed server-side `spritzify` engine.

Spritz's own prose (blog part II, 2014-02-20) says something the patent's FIG. 5a does not quite support:

> "**Our research shows that words of 4-to-7 characters spritz through a display the fastest.** Words of other lengths have an algorithmic slowing applied to them by Spritz that facilitates comprehension based on our exhaustive research."

> "since a word is recognized as one item, spritzing does not decode it character by character… Because many short words are similar, their shape is not always easy to recognize. The words 'met' and 'net,' for example, are similar in shape and take a longer time for your brain to process than longer words"

FIG. 5a gives lengths 1-7 the same multiplier of 1, so the "4-to-7 fastest" claim implies a short-word penalty that the disclosed table does not contain.
If it is real, it is in the server-side multiplier - and it would vindicate Squirt's `waitAfterShortWord = 1.2`.

### Base

Universally `60000 / wpm` milliseconds per word.

```js
    var wpm = parseInt(document.getElementById("spritz_selector").value, 10);
    var ms_per_word = 60000/wpm;
```
- `Miserlou/OpenSpritz`, `spritz.js`

```js
    function wpm(wpm){
      _wpm = wpm;
      intervalMs = 60 * 1000 / wpm ;
    };
```
- `cameron/squirt`, `squirt.js`

```js
  function calculateDelay(instr) {
    var interval = 60 * 1000 / config("target_wpm");
```
- `ds300/jetzt`, `modules/exec.js`

```js
    var duration = (1 / (WPM / 60)) * 1000;
```
- `anthonynosek/sprint-reader-chrome`, `src/engine.js`

### Multipliers - Squirt

Squirt's is the most readable, and it is a pure multiplier table on the base interval:

```js
    var waitAfterShortWord = 1.2;
    var waitAfterComma = 2;
    var waitAfterPeriod = 3;
    var waitAfterParagraph = 3.5;
    var waitAfterLongWord = 1.5;
    function getDelay(node, jumped){
      var word = node.word;
      if(jumped) return waitAfterPeriod;
      if(word == "Mr." ||
          word == "Mrs." ||
          word == "Ms.") return 1;
      var lastChar = word[word.length - 1];
      if(lastChar.match('”|"')) lastChar = word[word.length - 2];
      if(lastChar == '\n') return waitAfterParagraph;
      if('.!?'.indexOf(lastChar) != -1) return waitAfterPeriod;
      if(',;:–'.indexOf(lastChar) != -1) return waitAfterComma;
      if(word.length < 4) return waitAfterShortWord;
      if(word.length > 11) return waitAfterLongWord;
      return 1;
    };
```
- `cameron/squirt`, `squirt.js`

Three things worth stealing here:
- The multipliers are **mutually exclusive**, evaluated in priority order - punctuation beats length. A word never gets both.
- **`Mr.` / `Mrs.` / `Ms.` are special-cased** so the abbreviating period does not read as a sentence end. This is the cheapest possible fix for the single most annoying RSVP artefact.
- **Short words are slowed, not sped up** (`< 4` chars → 1.2×). Counter-intuitive, and the opposite of what a naive "time ∝ length" model does. The reasoning is that a 200ms word followed by a 200ms word is fine, but a 3-letter word is over before the eye has settled, so it needs a floor.

### Multipliers - jetzt

jetzt separates *structural* modifiers (from the parser) from *length*, and - crucially - **they do not compound**:

```js
  var DEFAULT_MODIFIERS = {
    normal: 1,
    start_clause: 1,
    end_clause: 1.8,
    start_sentence: 1.3,
    end_sentence: 2.2,
    start_paragraph: 2.0,
    end_paragraph: 2.8,
    short_space: 1.5,
    long_space: 2.2
  }
```
- `ds300/jetzt`, `modules/config.js`

```js
  function calculateDelay(instr) {
    var interval = 60 * 1000 / config("target_wpm");
    if (instr.modifier !== "normal") {
      return interval * config(["modifiers", instr.modifier]);
    } else {
      var len = instr.token.length;
      var mul = 1;
      switch (len) {
        case 6:
        case 7:
          mul = 1.2;
          break;
        case 8:
        case 9:
          mul = 1.4;
          break;
        case 10:
        case 11:
          mul = 1.8;
          break;
        case 12:
        case 13:
          mul = 2;
      }
      return interval * mul;
    }
    return interval;
  }
```
- `ds300/jetzt`, `modules/exec.js`

jetzt is the only reader in the set that distinguishes **entering** a structure from **leaving** it: the word that *starts* a sentence gets 1.3×, the word that *ends* it gets 2.2×.
It also has a `maxModifier` combinator so that when two modifiers land on one token, the larger wins:

```js
  config.maxModifier = function (a, b) {
    return this(["modifiers", a]) > this(["modifiers", b]) ? a : b;
  };
```

And it inserts explicit blank "spacer" frames rather than only lengthening a word - a spacer is a token of `"   "` with modifier `short_space` (1.5×), promoted to `long_space` (2.2×) if a second spacer lands in the same slot:

```js
    // put a spacer before the next token
    this.spacer = function () {
      if (spacerInstruction) {
        spacerInstruction.modifier = "long_space";
      } else {
        spacerInstruction = _addWraps({
          token: "   ",
          modifier: "short_space",
          decorator: ""
        });
      }
    };
```
- `ds300/jetzt`, `modules/parse.js`

### Multipliers - speedread

speedread is the only one that uses a **continuous** length term rather than a step table, and it *adds* rather than multiplies:

```perl
my $wordtime = 0.9; # relative to wpm
my $lentime = 0.04; # * sqrt(length $word), relative to wpm
my $commatime = 2; # relative to wpm
my $fstoptime = 3; # relative to wpm
my $multitime = 1.2; # relative to wpm
my $firsttime = 0.2; # [s]
```

```perl
sub word_time {
	my ($word) = @_;

	my $time = $wordtime;
	if ($word =~ /[.?!]\W*$/) {
		$time = $fstoptime;
	} elsif ($word =~ /[:;,]\W*$/) {
		$time = $commatime;
	} elsif ($word =~ / /) {
		$time = $multitime;
	}
	$time += sqrt(length($word)) * $lentime;
	$time *= 60 / $wpm;

	# Give user some time to focus on the first word, even with high wpm.
	$time = $firsttime if ($wordcounter == 0 and $time < $firsttime);

	return $time;
}
```

The calibration is neat: base 0.9 plus `sqrt(5) × 0.04 ≈ 0.089` for an average 5-letter English word ≈ **0.99**, so the nominal wpm comes out honest.
A 12-letter word gets `0.9 + 0.139 = 1.04×`, i.e. **speedread barely slows for long words** - far less than jetzt's 2.0×.
This is a genuine disagreement in the field.

### Multipliers - tspreed

A ratio against average English word length, with an explicit citation of that average in a comment:

```sh
word_len_average=5 # Based on average English word length of 5.1 letters
```
```sh
	sleep_ms_float=$(calc_float "1000 / (${wpm} / 60)")
	[ "$lengthvary" = true ] && sleep_ms_float="$(calc_float "${sleep_ms_float} * ($([ "$word_len" -gt "$word_len_average" ] && echo "$word_len" || echo $((word_len_average - 1))) / ${word_len_average})")"
```

So: `multiplier = max(len, 4) / 5`.
tspreed is the only reader that lets short words go **faster** than base (a 3-letter word gets 4/5 = 0.8×), the direct opposite of Squirt's short-word floor.
Note also that tspreed's length scaling is **off by default** (`-l`/`--length-vary`).

### Multipliers - quickreader

Multiplicative and compounding, unlike Squirt and jetzt:

```ts
export const PUNCTUATION_DELAY_MULTIPLIER = 1.5; // 50% extra time after punctuation
export const LONG_WORD_THRESHOLD = 10;
export const LONG_WORD_DELAY_MULTIPLIER = 1.2;
```
```ts
	if (punctuation.includes(lastChar)) {
		duration *= punctuationDelayMultiplier;
	}
	if (toCharArray(word).length >= longWordThreshold) {
		duration *= longWordDelayMultiplier;
	}
	if (nameDelayMultiplier > 1 && looksLikeName(word)) {
		duration *= nameDelayMultiplier;
	}
	if (numberDelayMultiplier > 1 && containsNumber(word)) {
		duration *= numberDelayMultiplier;
	}
```
- `coinstax/quickreader`, `src/lib/utils/orp.ts`

It is the only one that slows for **proper nouns** (1.3×) and for **anything containing a digit** (1.3×).
Since these compound, a capitalised 12-letter word ending in a period gets `1.5 × 1.2 × 1.3 = 2.34×` - which is in jetzt's territory but arrived at accidentally.
It also does **not** distinguish comma from period: all of `. , ; : ! ? - –` get the same 1.5×.
That is a regression against Squirt/jetzt/speedread, all three of which separate them.

### Multipliers - Sprint Reader

Sprint Reader is the odd one out: its pauses are **absolute milliseconds appended to the slide**, not multipliers, so they do not scale with wpm.

```js
    pauseAfterComma = true;
    pauseAfterCommaDelay = 250;
    pauseAfterParagraph = true;
    pauseAfterParagraphDelay = 700;
    pauseAfterPeriod = true;
    pauseAfterPeriodDelay = 450;
```
- `anthonynosek/sprint-reader-chrome`, `src/reader.js`

At 400 wpm base = 150ms, those are equivalent to 2.7× (comma), 4.0× (period), 5.7× (paragraph) - notably heavier than everyone else.
At 800 wpm they would become 4.3×/6.0×/9.3×, which is arguably the right behaviour (a comma needs a fixed amount of thinking time, not a fixed proportion), and arguably a bug.

Sprint Reader also offers **three selectable timing algorithms**, which is unique:

1. *Basic* - flat `60000/wpm` per slide.
2. *Word length* - normalises so total duration matches the nominal wpm, then distributes it per-character:
   ```js
       var totalDuration = (totalSegments / WPM) * 60000;
       var totalLength = 0;
       for (var i = 0; i < textData.length; i++) {
           totalLength = totalLength + textData[i].text.length;
       }
       var unitTime = totalDuration / totalLength;
       ...
           t.duration = unitTime * t.text.length;
   ```
   This is the only implementation that **preserves the promised wpm exactly** while varying per-word duration. Everyone else's multipliers make actual wpm lower than the slider says.
3. *Word frequency* - a genuinely interesting information-theoretic model, contributed by a third party, using SUBTLEX-US subtitle frequencies:
   ```js
           bitsOfInformation = -Math.log2(wordProbability[t.text]); // the Shannon information content definition

           // linear interpolation: 4.5 bits -> durShort msec, 25.6 bits -> durLong msec
           var lowInfo = 4.5;
           var highInfo = 25.6; // this numbers are empirical and are taken from the en-US database.
           var durShort = madvWordFreqHighestFreqSlideDuration;
           var durLong = madvWordFreqLowestFreqSlideDuration;

           var a = (durLong - durShort) / (highInfo - lowInfo);
           var b = durShort - lowInfo * a;

           if (!bitsOfInformation) bitsOfInformation = highInfo; // the maximum

           t.duration = a * bitsOfInformation + b; // Linear interpolation. Note: this means WPM setting has no role in this algorithm.
   ```
   with defaults `madvWordFreqHighestFreqSlideDuration = 40` ms and `madvWordFreqLowestFreqSlideDuration = 300` ms (`src/utility.js`).
   So the most common word gets 40ms and an unknown word gets 300ms, and the wpm slider is ignored entirely.
   The source comment is candid that the frequency table comes from movie subtitles and is case-sensitive on purpose (`'I'` is fast, `'i'` is treated as unknown and slow).

   This is the closest thing in the open-source corpus to "short function words go faster": `the`, `of`, `and` land near 40ms not because they are short but because they are frequent.

### Slow start / ramp

Nobody ramps wpm. Four different ways of buying the reader a beat at the start:

- **Squirt** prepends a literal countdown to the token stream:
  ```js
      return function textToNodes(text) {
        text = "3\n 2\n 1\n " + text.trim('\n').replace(/\s+\n/g,'\n');
  ```
  Because each of `3`, `2`, `1` carries a trailing `\n`, `getDelay` gives each the paragraph multiplier (3.5×), so the countdown runs at roughly one per 525ms at 400 wpm.
- **speedread** floors the first word at 200ms: `$time = $firsttime if ($wordcounter == 0 and $time < $firsttime);`
- **tspreed** floors the first word at a full second:
  ```sh
	# Sleep first word for minimum 1 second
	[ "$word_first" = true ] && {
		word_first=false
		[ "$sleep_ms" -lt 1000 ] && sleep_ms=1000
	}
  ```
- **Sprint Reader** has `autoStartSeconds = 2` before it begins.

After a **pause**, Squirt is the only one that does something on resume, and it is a rewind rather than a ramp: pressing left rewinds 10 seconds and then walks backwards to the start of the sentence.
```js
      on('squirt.rewind', function(e){
        // Rewind by `e.value` seconds. Then walk back to the
        // beginning of the sentence.
```
jetzt's `prevSentence()` does the same thing on demand ("go back 5 words, then keep walking back until a `start_sentence` or `start_paragraph` modifier").

There is a real gap here: **no open-source reader ramps speed back up after a pause**, even though the case for it is strong.

---

## 4. Default and range

### Spritz's own defaults

From the official JS SDK docs (`sdk.spritzinc.com/js/1.0/doc/webhelp/Lesson_6_-_Customizing_the_Redicle.htm`), the `SpritzerController` defaults, verbatim:

```js
var spritzerOptions = {
    "redicleWidth"   : 340,
    "redicleHeight"  : 70,
    "defaultSpeed"   : 250,
    "speedItems"     : [250, 300, 350, 400, 450, 500, 550, 600],
    "controlButtons" : ["back", "pauseplay", "rewind"],
    "controlTitles"  : { "pause":"Pause", "play":"Play",
                         "rewind":"Rewind", "back":"Previous Sentence" }
};
```

> "**Note: You can reduce the redicle footprint to a minimum size of 250 pixels wide by 50 pixels high.**"

The internal panel default is lower still - `g = 200; E = g` - so `SpritzReadingPanel` falls back to **200 wpm** when the controller does not set a speed.

Spritz's own FAQ on the range:

> "Yes. The available spritz speeds are 250wpm, 300wpm, 350wpm, 400wpm, and so on, **up to 1000 words per minute**."
> "we've found that it's best to start people in the **200-250wpm** range for their first spritzing experience."

and the blog: *"if you Spritz at 1000 words per minute right away, you will have a hard time"* and *"Spritzing too slow is also very frustrating."*

There is **no WPM figure anywhere in the patent**; it only refers to "the overall speed in average words-per-minute" as a user setting.

So Spritz itself shipped a **250 default with a 250-600 picker and a 1000 ceiling** - markedly more conservative than the 400 the clones adopted.
Note also the control set: **back to previous sentence** and **rewind** are first-class buttons, not power-user extras. Spritz clearly expected people to lose the thread.

### What the clones ship

| Reader | Default WPM | Min | Max | Step | Source |
|---|---|---|---|---|---|
| **Spritz** | **250** (SDK controller); 200 (panel fallback) | 250 in the picker | 600 in the picker, 1000 claimed | 50 | SDK Lesson 6, FAQ |
| Squirt | **400** | (arrow keys, unbounded) | - | 10 | `squirt.js`, `dispatch('squirt.wpm', {value: 400, notForKeen: true});` |
| jetzt | **400** | 100 | 1500 | 10 | `modules/config.js`, `target_wpm: 400` and `H.clamp(100, options.target_wpm + diff, 1500)` |
| Sprint Reader | **400** | - | - | 50 | `src/reader.js`, `WPM = 400;`; `src/utility.js`, `madvWPMAdjustmentStep = 50;` |
| speedread | **250** | - | - | ±10% multiplicative | `speedread`, `my $wpm = 250;` |
| quickreader | **300** | 100 | 900 | 50 | `src/lib/constants.ts` |
| OpenSpritz | none (dropdown) | 200 | 950 | 50 | `spritz.html` `<option>` list |
| tspreed | required argument | 1 | 60000 | - | `tspreed`, `[ "$wpm" -ge 1 ] && [ "$wpm" -le 60000 ]` |

**400 wpm is the modal default** across the three most-developed browser readers.
speedread's author is the one who wrote down his reasoning:

> # The default of 250 words per minut is very timid, designed so that
> # you get used to this.  Be sure to try cranking this up, 500wpm
> # should still be fairly easy to follow even for beginners.

- `pasky/speedread`, header comment

**400 wpm is what the field converged on, but nothing in the research put it there** - it is three bookmarklet authors copying each other, and Spritz itself shipped 250.
jetzt's 1500 ceiling and tspreed's 60000 are not serious reading speeds.
See §9 for what the evidence supports and §10 for the reconciliation.

### What the research says

See §9 below - this section is deliberately separated because the honest answer is less flattering than the defaults suggest.

---

## 5. Typography, and stopping the jitter

### Spritz's own typography - proportional, not monospace

This is the answer to the monospace question, and it is not what the open-source clones assumed.
From `sdk.spritzinc.com/js/1.0/css/spritz.min.css`:

```
@font-face { font-family: SpritzMedienBold;   src: spritz_medien_bold.{eot,woff,ttf,svg#NNMedienBold} }
@font-face { font-family: SpritzMedienMedium; src: spritz_medien_medium.{eot,woff,ttf,svg#NNMedienMedium} }
```

and in JS, `j = "SpritzMedienMedium"` is the default, with `k = "arial"` used only when `localStorage["spritz.language"] == "ru"`.
The face is a licensed cut of **Nouvelle Medien** (the `NN…` SVG font ids). Ascent and descent are hard-modelled as `0.56 × fontSize` and `0.44 × fontSize`, with a ±1px fudge for Firefox.
Font size is `round(redicleHeight × 0.40)` - 28px at the default 70px height.

Spritz's own FAQ:

> "Yes! We've done extensive research into the best fonts to use for readability. **We use a very special font that was designed specifically for reading on digital devices.** Other fonts will work to some extent but fonts that are excessively 'busy' will slow you down significantly as they require more processing from your brain."

They never named it publicly. The `.woff` files are archived at `sdk.spritzinc.com/js/1.0/fonts/` if the real metrics matter.

**How Spritz stops the jitter.** Per-word `measureText`, exactly the technique Squirt, jetzt and Sprint Reader arrived at independently. From `yb(word, orp, position, isBold)`, deminified:

```js
prefix = word.substring(0, orp);
orpCh  = word.substring(orp, orp + 1);
suffix = word.substring(orp + 1);
wPre   = round(measureText(prefix));
wOrp   = round(measureText(orpCh));
half   = round(wOrp / 2);

fillText(prefix, normalFont, "#000000", T - wPre - half, y);
fillText(orpCh,  normalFont, K,          T - half,        y);   // K = "#CC0001"
fillText(suffix, normalFont, "#000000", T + half,        y);
```

**The ORP glyph's horizontal centre is pinned to `T`**, recomputed per word from measured text metrics.
That `+ half` term is the patent's `+ (0.5 × Average Character Width)` made concrete, and the patent says explicitly that the offset formula exists to "account for the use of proportionally spaced fonts".

So: **Spritz is proportional and measures. Monospace is a shortcut the clones took, not the original design.**

### The clones' fonts

| Reader | Font | Source |
|---|---|---|
| **Spritz** | `SpritzMedienMedium` (proportional, a cut of Nouvelle Medien), size = 0.40 × redicle height | `spritz.min.css`, `spritz.min.js` |
| OpenSpritz | `'Droid Sans Mono', sans-serif` | `style.css` |
| jetzt | `"Menlo, Monaco, Consolas, monospace"` | `modules/config.js`, `font_family` |
| Sprint Reader | `"Arial"` at `fontSize = 110` (%) | `src/reader.js`, `getSettingsDefault()` |
| Squirt | `Georgia, serif` (on the modal), word at `font-size: 1.2em` of a 48px modal | `squirt.css` |
| speedread / tspreed | terminal font (monospace by definition) | - |

So it is **not** a clean monospace consensus.
jetzt and OpenSpritz go monospace; Sprint Reader picks a proportional sans; Squirt picks a proportional serif at large size.
jetzt exposes `font_weight` as a setting with default `"normal"`, and applies both family and weight to every span individually:

```js
    this.setFontWeight = function (fontWeight) {
      leftWord.style.fontWeight = fontWeight;
      pivotChar.style.fontWeight = fontWeight;
      rightWord.style.fontWeight = fontWeight;
      decorator.style.fontWeight = fontWeight;
    };
```

None of them adjust letter-spacing.

### The jitter problem - four real techniques

This is the crux of a good implementation, and the four approaches are genuinely different.

**Technique 1 - monospace + invisible padding to a fixed cell count (OpenSpritz).**
Pad the word with dots on both sides so the rendered string is always exactly 22 characters with the pivot at cell 11, then make the dots the same colour as the background:

```js
    word = decodeEntities(word);
    var start = '.'.repeat((11-bestLetter)) + word.slice(0, bestLetter-1).replace('.', '&#8226;');
    var middle = word.slice(bestLetter-1,bestLetter).replace('.', '&#8226;');
    var end = word.slice(bestLetter, length).replace('.', '&#8226;') + '.'.repeat((11-(word.length-bestLetter)));

    var result;
    result = "<span class='spritz_start'>" + start;
    result = result + "</span><span class='spritz_pivot'>";
    result = result + middle;
    result = result + "</span><span class='spritz_end'>";
    result = result + end;
    result = result + "</span>";

    result = result.replace(/\./g, "<span class='invisible'>.</span>");
```
```css
.invisible{
    font-family: 'Droid Sans Mono', sans-serif;
    color: #ffffff;
    position: static;
}
```
- `Miserlou/OpenSpritz`, `spritz.js` and `style.css`

Characters before the pivot: `(11 - bestLetter) + (bestLetter - 1) = 10`, always.
Characters after: `(len - bestLetter) + (11 - (len - bestLetter)) = 11`, always.
Clever, but it breaks on words over ~21 characters (the repeat count goes negative) and it *requires* monospace.
And white-on-white text is a copy-paste and accessibility hazard.

**Technique 2 - measure the pivot glyph and translate the word (Squirt).**
Render the word with one `<span>` per character, then measure the pivot span's box and shift the whole word left by its centre offset:

```js
  function wordToNode(word) {
    var node = makeDiv({'class': 'word'});
    node.word = parseSQInstructionsForWord(word, node);

    var orpIdx = getORPIndex(node.word);

    node.word.split('').map(function charToNode(char, idx) {
      var span = makeEl('span', {}, node);
      span.textContent = char;
      if(idx == orpIdx) span.classList.add('orp');
    });

    node.center = (function(orpNode) {
      var val = orpNode.offsetLeft + (orpNode.offsetWidth / 2);
      node.style.left = "-" + val + "px";
    }).bind(null, node.children[orpIdx]);

    return node;
  };
```

Critically, Squirt **measures the next word before it is shown**, in an off-screen prerenderer, so the measurement never causes a visible reflow:

```js
    var toRender;
    function prerender(){
      toRender = nodes[nodeIdx];
      if(toRender == null) return;
      prerenderer.appendChild(toRender);
      nodes[nodeIdx].center();
    }
```
```css
.sq .word-prerenderer {
  visibility: hidden;
}
```

This is the technique that works with **any** font, proportional included.

**Technique 3 - measure with a canvas, offset with padding (Sprint Reader).**
Same idea, but the measurement is done with `CanvasRenderingContext2D.measureText` rather than DOM layout, which is faster and can be done at parse time for the whole document:

```js
function calculatePixelOffsetToOptimalCenter(textItem, isRightToLeft) {
    var ftUsed = font;
    var ftSize = fontSize;

    var canvas = document.getElementById("word-canvas");
    var context = canvas.getContext("2d");
    context.font = ftSize + "px " + ftUsed;
    ...
    var pxToOptimalStart = context.measureText(wordToOptimalStart).width;
    var pxOptimalLetter = context.measureText(wordOptimalLetter).width;
    var pxOffset = pxToOptimalStart + pxOptimalLetter / 2;
    return pxOffset;
}
```
and the offset is applied as left padding on the word container:
```js
        var px = calculatePixelOffsetToOptimalCenter(textItem);
        var offset = leftPaddingBorderOptimised - px;
        $("#word-container").css("padding-" + orient, offset + "px");
        $("#word-container").css("margin-left", "0");
```
- `anthonynosek/sprint-reader-chrome`, `src/engine.js`, `src/reader.js`

The offset is precomputed once per word during parsing (`textItem.pixeloffsettooptimalletter = calculatePixelOffsetToOptimalCenter(textItem);`), so the hot loop is a single `padding-left` write.

**Technique 4 - measure against the reticle, three spans (jetzt).**
jetzt combines the ideas: three spans (left / pivot / right), measured live, aligned to the reticle element rather than to a hard-coded x:

```js
    this.setWord = function (token, dec) {
      var pivot = calculatePivot(token.replace(/[?.,!:;*-]+$/, ""));
      leftWord.innerHTML = token.substr(0, pivot);
      pivotChar.innerHTML = token.substr(pivot, 1);
      rightWord.innerHTML = token.substr(pivot + 1)
      if (typeof dec !== "undefined") decorator.innerHTML = dec;

      word.offsetWidth;
      var pivotCenter = reticle.offsetLeft + (reticle.offsetWidth / 2);
      word.style.left = (pivotCenter - pivotChar.offsetLeft - (pivotChar.offsetWidth / 2)) + "px";
    };
```
- `ds300/jetzt`, `modules/view.js`

Note the bare `word.offsetWidth;` - a deliberate forced synchronous layout so that `pivotChar.offsetLeft` is correct after the `innerHTML` writes.
This is the most robust of the DOM approaches: it does not care what font is used, and it re-derives the target column from the reticle's actual position, so a themed or resized reticle stays in sync automatically.

**Technique 5 - a symmetric three-cell CSS grid, no measurement at all (quickreader).**

```html
			<div class="word-display" class:italic={isItalic} class:bold={isBold}>
				<span class="before-orp">{parts.before}</span>
				<span class="orp-letter">{parts.orp}</span>
				<span class="after-orp">{parts.after}</span>
			</div>
```
```css
	.word-display {
		display: grid;
		grid-template-columns: 1fr auto 1fr;
		align-items: baseline;
		font-family: var(--font-family);
		font-size: var(--font-size);
		line-height: 1.2;
		white-space: nowrap;
		width: 100%;
	}

	.before-orp {
		text-align: right;
		justify-self: end;
	}

	.orp-letter {
		color: var(--orp-color);
		/* ORP letter is the fixed center point */
		text-align: center;
	}

	.after-orp {
		text-align: left;
		justify-self: start;
	}
```
- `coinstax/quickreader`, `src/lib/components/Redicle.svelte`

This is by far the least code, it is pure CSS, it works with any font, and it needs no measurement, no forced layout, and no prerender pass.
Its one real cost: because the two `1fr` columns are equal, the pivot column lands at exactly 50% of the container, so you cannot get the 30% offset that jetzt/Sprint Reader/Squirt use - unless you change the ratio.
**`grid-template-columns: 0.75fr auto 1.75fr`** (or any pair summing to a fixed total, with the left share ≈ 30%) reproduces the left-of-centre placement while keeping the whole technique.

There is also a subtle jitter source the grid does not fix: the pivot glyph itself has a different advance width for `i` vs `W`, so `text-align: center` inside an `auto` column keeps the *glyph* centred but the glyph's own centre moves relative to its ink. In practice this is sub-pixel and invisible; if it matters, give the pivot cell a fixed `ch`-based width in a monospace font.

---

## 6. What else is on screen

| Feature | Spritz | jetzt | Squirt | Sprint Reader | speedread | quickreader | OpenSpritz |
|---|---|---|---|---|---|---|---|
| Progress bar | no | yes | no | yes (`madvDisplayProgress = true`) | no | yes (`ProgressBar.svelte`) | no |
| Time remaining | no | yes, off by default | no | yes (`showRemainingTime = true`) | no | - | no |
| Current wpm on screen | in the picker | yes | no | yes | yes | yes | via the select |
| Context / current sentence | no | no | no | **yes** | on pause only | no | no |
| Word counter / stats at end | no | yes | yes (with a tweet button) | yes | yes | - | no |
| Back to previous sentence | **yes, a default button** | yes (keyboard) | yes (rewind 10s then to sentence start) | yes | no | no | no |

Spritz's default control set is worth calling out - `"controlButtons": ["back", "pauseplay", "rewind"]`, where `back` is titled "Previous Sentence".
The frame itself carries nothing but the word and the redicle. **Spritz put re-reading in the chrome and kept the frame empty**, which is the opposite of the "add a context line" instinct.

**jetzt's progress bar** is a one-line trick - it animates a border width, so it costs nothing:
```js
    this.setProgress = function (percent) {
      progressBar.style.borderLeftWidth = Math.ceil(percent * 4) + "px";
    };
```
```css
.sr-reader .sr-word-box .sr-progress {
  position: absolute;
  bottom: -10px;
  width: 400px;
  height: 3px;
  border-left: 0px solid #CCC;
  transition: border 0.34s ease;
}
```

**jetzt's time-remaining** recomputes only every 5th word, from measured elapsed time rather than from the nominal wpm:
```js
      } else if (index % 5 === 0) {
        calculateRemaining();
      }
```
```js
    function calculateRemaining () {
      var words = instructions.length;
      var timestamp = Math.round(new Date().getTime() / 1000);
      var elapsed = timestamp - reader.started;
      var remaining = (elapsed * (words - index)) / index;
      reader.setMessage(Math.round(remaining) + "s left");
    }
```
- `ds300/jetzt`, `modules/exec.js`. It is hidden by default (`show_message: false`) and toggled with `/`.

**Sprint Reader is the only one with a persistent context line.** It has four separate settings for it:
```js
    madvAutoHideSentence = false;
    madvAutoHideSentenceSeconds = 5;
    madvDisplaySentenceAtReaderOpen = true;
    madvDisplaySentenceTopBorder = true;
    madvDisplaySentenceWhenPaused = true;
    madvSentenceBackwardWordCount = 20;
    madvSentencePositionPercentOffset = 50;
```
- `src/utility.js`. So: show the surrounding sentence (up to 20 words back) when the reader opens and whenever it is paused, optionally auto-hiding after 5 seconds.

**speedread shows two lines of context on pause**, with the current word highlighted yellow in place:
```perl
sub print_context {
	my ($wn) = @_;
	# One line up and to its beginning
	print "\r\033[K\033[A\033[K";
	# First line of context
	say $lastlines[1] if $lastlines[1];
	# In second line of context, highlight our word
	my $line0 = $lastlines[0];
	my $c0 = color('yellow');
	my $c1 = color('reset');
	$line0 =~ s/^((?:.*?(?:-|\s)+){$wn})(.*?)(-|\s)/$1$c0$2$c1$3/;
	say $line0;
}
```

This is the right pattern: **context on pause, not context during play**.
A context line rendered while the stream is running defeats the point of RSVP - the eye leaves the pivot column to read it.

**jetzt shows enclosing punctuation as separate side panels** rather than inline, which is a nice idea nobody else has. Quotes, parens, headings and blockquotes become "wraps" drawn in flanking boxes:
```js
  var wraps = {
    guillemot: {left: "«", right: "»"},
    double_quote: {left: "“", right: "”"},
    parens: {left: "(", right: ")"},
    heading: {left: "#", right: ""},
    blockquote: {left: "›", right: ""}  // U+203A
  };
```
and the reader re-balances its own padding so the word box never shifts when a wrap appears:
```js
    this.setWrap = function (left, right) {
      leftWrap.innerHTML = left;
      rightWrap.innerHTML = right;

      var lw = leftWrap.offsetWidth;
      var rw = rightWrap.offsetWidth;

      wrapper.style.paddingLeft = "50px";
      wrapper.style.paddingRight = "50px";
      if (lw > rw) {
        wrapper.style.paddingRight = 50 + (lw - rw) + "px";
      } else if (rw > lw) {
        wrapper.style.paddingLeft = 50 + (rw - lw) + "px";
      }
    };
```
It also appends a "decorator" span carrying the trailing punctuation, so the pivot alignment is computed on the bare word while the comma or period is still visible.

### Chunking

Only **Sprint Reader** supports multi-word chunks, and it is off by default:
```js
    chunkSize = 1;
```
Note what it *disables* when chunking is on - both the ORP highlight and the focal guide:
```js
    if (highlightOptimalLetter && chunkSize == 1) {
```
```js
    // Do not show the guide if the chunk size is more than 1
    if (chunkSize > 1 || madvAlwaysHideFocalGuide) {
```
That is the correct call: a pivot letter is meaningless once there are two words in the frame, because there is no single point the eye should land on.

speedread has a `-m`/`--multiword` mode that joins short words, and the author's own verdict is in the header comment:
> # speedread can join short words together if you specify the -m switch.
> # It did not work well for pasky so far, though.

See §9 for what the perceptual-span literature says about why chunking cannot work the way its advocates hope.

---

## 7. Non-prose handling

### Long words - Spritz's rule and the 13-character number

The patent splits, and hyphenates:

> "Also, in some embodiments, a word having a length of greater than thirteen characters is divided into first and second display elements such that a first portion of the word is displayed first (**along with a hyphen**) and then the second portion of the word is displayed next."

> "The ORP-RSVP display 200 can accommodate text of up to 20 characters in length without saccades, although it is preferred to limit the display to 13 characters for improved comprehension. Words longer than 13 characters can be hyphenated and displayed as two consecutive segments. **Research has confirmed that approximately two-thirds of the users preferred the hyphenated technique over the single display of the full word.**"

Claimed at 18 and 62. The 13 and 20 come from Rayner's 20-character perceptual span and Rayner 1995's comprehension result, plus a frequency argument: *"according to Sigurd, only 0.4% of the words in the English language are longer than 13 characters."*

`spritzinc.com/the-science/`:

> "Because the human eye can focus on about 13 characters at a time, Spritzing requires only 13 characters' worth of space inside our redicle."

and the FAQ, on `hippopotomonstrosesquipedaliophobia`:

> "Most people's focal distance … is right around 13 characters using standard font sizes… In reality, a long word requires your eye to break it into multiple pieces and that is how your brain stores it. We analyze each word and break them up based on this standard and show you long words in multiple pieces."

**jetzt's `word.length > 13` threshold and its `-` decorator are therefore an exact match to the patent** - the only clone that got this right. Sprint Reader's 17 is more permissive; everyone else does not split at all.

### Long words in the clones

Three positions:

**jetzt splits them**, and this is the most considered implementation in the corpus:
```js
  function wordShouldBeSplitUp(word) {
    return word.length > 13 || word.length > 9 && word.indexOf("-") > -1;
  }

  // split a long word into sensible sections
  function splitLongWord (word) {
    if (wordShouldBeSplitUp(word)) {
      var result = [];

      var dashIdx = word.indexOf("-");
      if (dashIdx > 0 && dashIdx < word.length - 1) {
        result.push(word.substr(0, dashIdx));
        result.push(word.substr(dashIdx + 1));
        return H.flatten(result.map(splitLongWord));
      } else {
        var partitions = Math.ceil(word.length / 8);
        var partitionLength = Math.ceil(word.length / partitions);
        while (partitions--) {
          result.push(word.substr(0, partitionLength));
          word = word.substr(partitionLength);
        }
        return result;
      }
    } else {
      return [word];
    }
  }
```
- `ds300/jetzt`, `modules/parse.js`

Threshold **>13 characters** (or >9 with a hyphen); split at the hyphen first if there is one, otherwise into `ceil(len/8)` roughly equal parts; every fragment but the last gets a `-` decorator so the reader sees the continuation:
```js
      trunks.forEach(function (t) {
        instructions.push(_addWraps({
          token: t,
          modifier: "normal",
          decorator: "-"
        }));
      });
```
The 13 threshold is not a coincidence - it is exactly where the ORP table stops moving.

**Sprint Reader splits them with real hyphenation patterns**, which is the highest-quality approach:
```js
            if (madvEnableLongWordHyphenation) {
                var textDecoded = htmlEntitiesDecode(textOnSlide);
                if (textDecoded.length > madvLongWordTriggerCharacterCount) {
                    // Split the word using hyphenate and language pattern
                    var splitFirst = $().hyphenateWord(textOnSlide, language.pattern, madvLongWordTriggerCharacterCount);
                    var splitWord = adjustStringArray(splitFirst, madvLongWordMinCharacterPerSlidePostSplit, madvLongWordTriggerCharacterCount);
```
with defaults:
```js
    madvLongWordCharacterTriggerDoNotJoin = 4;
    madvLongWordMinCharacterPerSlidePostSplit = 6;
    madvLongWordTriggerCharacterCount = 17;
```
- `src/engine.js`, `src/utility.js`. It bundles Hypher plus per-language TeX hyphenation patterns (`lib/jquery.hypher/`), so `internationalization` breaks at real syllable boundaries. Threshold **17 characters**, minimum 6 characters per fragment, and a trailing fragment of ≤4 characters is glued back onto the previous one rather than shown alone.

**OpenSpritz, Squirt, speedread, tspreed, quickreader do not split at all.**
OpenSpritz will actively break: its padding maths produces `'.'.repeat(negative)` for words over 21 characters.

### Hyphenated words

Sprint Reader treats hyphens as first-class, with two opposite behaviours depending on context:
```js
            // HYPHENATED WORDS
            // We detect hyphenated words and split them according to the hyphen
```
- if the hyphen is a line-break artefact (`foo-\nbar`), it **rejoins** them and drops the hyphen (`madvConsolidateHyphenatedWord = true`)
- otherwise it **splits** at the hyphen (`madvEnableHyphenatedWordSplit = true`)
- but a two-part hyphenated word whose halves total ≤12 characters is kept whole, with `co-founder` given as the source's own example:
```js
            if (i == 0 && splitHyphenated.length == 2) {
                var combinedLength = splitHyphenated[0].length + splitHyphenated[1].length;
                if (combinedLength <= 12) {
                    tempText.text = splitHyphenated[0] + "-" + splitHyphenated[1];
```

jetzt splits at hyphens only for words over 9 characters (see above). Squirt treats a trailing `-` as a comma-class pause. OpenSpritz treats any word containing `-` as a "double up" case (3× duration).

### Numbers and decimals

Only two readers do anything.

**Sprint Reader** reassembles numbers that whitespace tokenising broke apart, so `3.14` and `1,000` do not become two slides:
```js
        // NUMBERS AND DECIMALS
        // Clean up for numbers with decimals
        if (madvEnableNumberDecimalDetection) {
            if (textOnSlide.slice(-1) == "." || textOnSlide.slice(-1) == ",") {
                // We have found a comma or period.
                // Check elements for the remainder of the number.
                exText = textOnSlide;
                recursiveCheckForNumber(i, splitText);
```
It also has explicit handling for **numbered lists** (`1.`, `2.` at the start of a line) so a list marker does not read as a sentence end.

**quickreader** slows any token containing a digit by 1.3×, with a thorough comment on what that covers:
```ts
/**
 * Check if a word contains a number.
 * Matches any word containing digits, which covers:
 * - Integers: "42", "-100", "+5"
 * - Decimals: "98.4", "3.14", "-0.5"
 * - Scientific notation: "1.5e10", "6.022e23"
 * - Percentages: "100%", "98.4%"
 * - Fractions: "1/2", "3/4"
 * - Dates, times, measurements, etc.
 */
function containsNumber(word: string): boolean {
	return /\d/.test(word);
}
```

### Acronyms

Only **Sprint Reader**:
```js
        // Test for an acronym
        // If the slide ends in a period and contains one other
        // character which is not a number
        if (madvEnableAcronymDetection) {
            if (textOnSlide.slice(-1) == "." && textOnSlide.length >= 2) {
                if (isNaN(textOnSlide[0])) {
```
`madvEnableAcronymDetection = true` by default. It recursively glues `U.` `S.` `A.` back into `U.S.A.` so the periods are not read as three sentence ends.

Squirt's `Mr.`/`Mrs.`/`Ms.` special case is the poor man's version of the same idea.

### Images, tables, code

**Everything strips to plain text. Nothing pauses on a figure.** But two readers avoid the problem by never selecting those elements in the first place.

**jetzt** walks the DOM with an explicit whitelist. `PRE`, `CODE`, `TABLE`, `IMG`, `FIGURE` are not on it:
```js
    var validParents = {
      "DIV": true,
      "ARTICLE": true,
      "BLOCKQUOTE": true,
      "MAIN": true,
      "SECTION": true,
      "UL": true,
      "OL": true,
      "DL": true
    };

    var validChildren = {
      "P": true,
      "H1": true,
      "H2": true,
      "H3": true,
      "H4": true,
      "H5": true,
      "H6": true,
      "SPAN": true,
      "DL": true,
      "OL": true,
      "UL": true,
      "BLOCKQUOTE": true,
      "SECTION": true
    };
```
- `ds300/jetzt`, `modules/select.js`

And in `parseDom` it skips `SCRIPT` and `#comment` nodes, marks headings with a `#` wrap and a paragraph-level pause, and marks blockquotes with a `›` wrap:
```js
          case "SCRIPT":
            break;
```
```js
          case "H1": … case "H6":
            inst.clearWrap();
            inst.pushWrap(wraps.heading);
            inst.modNext("start_paragraph");
            parseDom(node,inst);
            inst.spacer();
            inst.popWrap(wraps.heading);
            inst.modPrev("end_paragraph");
            break;
```

jetzt also has an academic-text feature nobody else has - it can strip in-text citations before reading, with a genuinely elaborate regex covering APA, MLA, CMS, ASA and IEEE forms:
```js
  // regexp that matches in-text citations
  var _reInTextCitation = (function () {
    var au = "((\\S\\.\\s)?(\\S+\\s)?\\S+?)";          // author
    var et = "(,?\\set\\sal\\.?)";                     // et al.
    var yr = "((16|17|18|19|20)\\d{2}[a-z]?)";         // year restricted in 17c.-21c.
    var pt = "([a-z]{1,4}\\.\\s\\d+)";                 // part: p. 199, chap. 5, etc.
    …
    var ie = "\\[\\d+\\]";                             // IEEE
```
Off by default (`strip_citation: false`).

**OpenSpritz and Squirt** both punt to a readability extractor (Diffbot and Readability respectively), which discards non-prose for them.

**The gap:** a diagram, a table or a code block in the source has no representation in any of these readers. For a Markdown preview tool that renders Mermaid and tables, the right behaviour - pause the stream and show the block - is not something any existing implementation does, so there is no prior art to copy.

---

## 8. Bionic Reading

Bionic Reading is a **different mechanism from ORP**, and conflating them is the common error.
ORP moves the *word* so a chosen letter lands under the eye; the word is presented alone, one at a time, and the reader's eye never moves.
Bionic Reading leaves the text where it is, in normal paragraphs, and bolds the *leading* characters of each word to give the eye a landing target on every word.
ORP is a **positioning** technique for serial presentation. Bionic is a **typographic** technique for parallel presentation.
They are not combinable in any interesting way, because in RSVP there is only one word on screen and it is already aligned.

### The exact rule, from the patent

The only authoritative specification is Renato Casutt's patent application:

> **GB2552586A**, "Speed reading system and method", inventor Renato Casutt. Priority 2016-06-10, filed 2017-06-12, published 2018-01-31. **Legal status: withdrawn.** Sibling filings: FR1755215, US 15/213,418 (pub. US20170358238).
> https://patents.google.com/patent/GB2552586A/en

The description states the rules verbatim:

> Rule 1 - Every word is displayed in bionic typography.
> Rule 2 - **3/5 of the beginning word are depicted in BOLD. 2/5 of the ending word are depicted in BASE FONT.**
> Rule 3 - In individual letters (count as a word) and short connecting words such as "and" that contain **three of fewer letters, only the beginning letter is depicted in BOLD.** The final letters of the word are depicted in BASE FONT.
> Rule 4 - In **words with four letters, the first two letters** are depicted in BOLD. The final letters of the word are depicted in BASE FONT.
> Rule 5 - In compound words - these are words that are composed of two main words - each of the two words is treated as an individual word, but they remain in their coupled function.
> Rule 6 - Words with an existing distinction - e.g. italics, bold (semi-bold/bold), upper case (capital letters), etc. - are enhanced with a font weight of bionic-typography.
> Rule 7 - **Numbers are not depicted in bionic-typography.**

Restated in claim 9:

> "...the at least one distinction-type rule is that **3/5 of the beginning of each word are made distinct**, whereas in **words with up to three alphanumeric characters only the first alphanumeric character is made distinct**, in **words with four alphanumeric characters the first two alphanumeric characters are made distinct** and **numbers are not made distinct**..."

So the canonical rule is:

| Word length (alphanumeric chars) | Bolded leading chars |
|---|---|
| 1-3 | 1 |
| 4 | 2 |
| ≥5 | 3/5 × n, "rounded or truncated" (the patent does not fix which) |
| pure numbers | 0 |

### "Saccade" is a frequency parameter, not a per-word one

The patent separates a **distinction-type rule** (how much of a word is bolded) from a **frequency rule** (which words get bolded at all), and defines seven presets:

| Preset | Period (frequency) | Fraction bolded |
|---|---|---|
| TYPO1 | every word | 3/5 |
| TYPO2 | every word | 2/5 |
| TYPO3 | every 2 words | 2/5 |
| TYPO4 | every 3 words | 2/5 |
| TYPO5 | every 4 words | 2/5 |
| TYPO6 | every 5 words | 3/5 |
| TYPO7 | every 6 words | 3/5 |

Claim 6 defines "period" as "the number of words or sentences from a distinction up to a subsequent distinction".

The patent also grounds the terminology in eye-movement physiology:

> "During a fixation, the eye is directed at a fixation point 10 for about 0.3 seconds. It then jumps to another fixation point 10 in a quick, jerky movement (saccade). In the fixation phases, high-resolution detail visual images are captured via the fovea of the eye, but during saccades, no perception is possible."

### The vendor's own parameters

From https://bionic-reading.com/br-apps/ , verbatim:

> **Fixation** - "With "Fixation" you define the expression of the letter combinations. **Choose a value from 1 to 5. 3 is defined as the base value.**"
> **Saccade** - "With "Saccade" you define the visual jumps from Fixation to Fixation. **Choose a value from 10 to 50. 10 is defined as the base value.**"
> **Opacity** - "With "Opacity" you define the visibility of your Fixation. You can also adjust the visibility of the remaining letters individually to your needs. **Choose a value from 100 to 0. 100 is defined as the base.**"

Note the units do not reconcile: the product's saccade is 10-50, the patent's period is 1-6 words, and nothing published by Bionic Reading explains the mapping.
Their developer framework reference (https://developer.bionic-reading.com/framework/index.html) documents no types, ranges or defaults, only that omitted values fall back to `BionicReadingSettings`.

### What the shipping product actually renders

The de-facto open-source reference is `Gumball12/text-vide` (MIT), which was reverse-engineered from the real Bionic Reading API rather than from the patent.
Its entire rule is one table - and note it is a table of **non-bold trailing counts**, not bold counts:

```ts
const FIXATION_BOUNDARY_LIST = [
  [0, 4, 12, 17, 24, 29, 35, 42, 48],
  [1, 2, 7, 10, 13, 14, 19, 22, 25, 28, 31, 34, 37, 40, 43, 46, 49],
  [
    1, 2, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31, 33, 35, 37, 39,
    41, 43, 45, 47, 49,
  ],
  [
    0, 2, 4, 5, 6, 8, 9, 11, 14, 15, 17, 18, 20, 0, 21, 23, 24, 26, 27, 29, 30,
    32, 33, 35, 36, 38, 39, 41, 42, 44, 45, 47, 48,
  ],
  [
    0, 2, 3, 5, 6, 7, 8, 10, 11, 12, 14, 15, 17, 19, 20, 21, 23, 24, 25, 26, 28,
    29, 30, 32, 33, 34, 35, 37, 38, 39, 41, 42, 43, 44, 46, 47, 48,
  ],
];

export default (word: string, fixationPoint: number) => {
  const { length: wordLength } = word;
  const fixationBoundary =
    FIXATION_BOUNDARY_LIST[fixationPoint - 1] ?? FIXATION_BOUNDARY_LIST[0];

  const fixationLengthFromLast = fixationBoundary.findIndex(
    boundary => wordLength <= boundary,
  );

  let fixationLength = wordLength - fixationLengthFromLast;

  if (fixationLengthFromLast === -1) {
    fixationLength = wordLength - fixationBoundary.length;
  }

  return Math.max(fixationLength, 0);
};
```

- `Gumball12/text-vide`, `packages/text-vide/src/getFixationLength.ts`

Evaluated, this gives bolded leading characters per word length:

| len | fp1 | fp2 | fp3 | fp4 | fp5 |
|---|---|---|---|---|---|
| 1 | 0 | 1 | 1 | 0 | 0 |
| 2 | 1 | 1 | 1 | 1 | 1 |
| 3 | 2 | 1 | 1 | 1 | 1 |
| 4 | 3 | 2 | 2 | 2 | 1 |
| 5 | 3 | 3 | 3 | 2 | 2 |
| 6 | 4 | 4 | 3 | 2 | 2 |
| 7 | 5 | 5 | 4 | 2 | 2 |
| 8 | 6 | 5 | 4 | 3 | 2 |
| 9 | 7 | 6 | 5 | 3 | 2 |
| 10 | 8 | 7 | 5 | 3 | 3 |
| 12 | 10 | 8 | 6 | 4 | 3 |
| 15 | 12 | 9 | 8 | 6 | 4 |
| 20 | 16 | 13 | 10 | 8 | 6 |

**fixationPoint 3 - Bionic Reading's own stated base value - is approximately `ceil(n/2)`.**
None of the five presets is the patent's 3/5 rule.
`text-vide`'s library default is `fixationPoint: 1`, which bolds nearly the whole word and does not match the product; if you copy the table, set 3.

The author documented his reverse-engineering in `text-vide/HOW.md`:

> "This module was developed by referring to the official BR API. However, there is a difference in that it is implemented with a slightly different logic... First, I found the rule below through the BR API call result."

with the fixationPoint-1 non-bold table:

| Length (min) | Length (max) | Non-bold chars |
|---|---|---|
| 0 | 4 | 1 |
| 5 | 12 | 2 |
| 13 | 16 | 3 |
| 17 | 24 | 4 |
| 25 | 29 | 5 |
| 30 | 35 | 6 |
| 36 | 42 | 7 |
| 43 | 48 | 8 |
| 49 | ∞ | 9 |

and the token rules, which agree with the patent on numbers:

> "Special characters at the Beginning or End of a word are **not** highlighted." / "a Dash (`-`) among special characters located inside a word is treated the same as a Space." / "If there are only numbers, highlight nothing."

**Two defects in the shipped table, if you copy it:**

1. Off-by-one at n=17. The comparison is `wordLength <= boundary`, so boundary `17` puts a 17-character word in the 3-non-bold bucket, while `HOW.md` says 17-24 should be 4. Every other bucket edge agrees.
2. `FIXATION_BOUNDARY_LIST[3]` (fixationPoint 4) contains a stray `0` mid-array: `..., 18, 20, 0, 21, 23, ...`. It shifts every subsequent index, so words of length ≥21 at fp4 get one fewer bolded character than the table implies. `kylesnowschwartz/pi-bionic-reading` vendors the table verbatim, stray `0` included.

`text-vide` does not implement saccade at all (README: `| Saccade | ❌ |`).
`kylesnowschwartz/pi-bionic-reading` does, exactly as the patent's frequency rule, and defaults `fixation: 3` to match the vendor's base value:

```ts
	if (wordIndex % saccade !== 0) {   // bold every Nth word
```

`Jwuthri/BionicReading` (Python) is the closest open-source match to the patent, using a percentage rather than a table:

```python
def __init__(self, fixation: float = 0.6, saccades: float = 0.75, opacity: float = 0.75, ...)
```
```python
        if len(token) <= 2:
            return token[0], token[1:]
        last_char_index = round(self.fixation * len(token))
        return token[:last_char_index], token[last_char_index:]
```

`fixation = 0.6` is literally the patent's 3/5, with `round()` as the rounding rule.

### Does it work?

**No. Three independent peer-reviewed studies find no reading-speed benefit, and two find a cost.**

> Snell, J. (2024). **No, Bionic Reading does not work.** *Acta Psychologica*, **247**, 104304. https://doi.org/10.1016/j.actpsy.2024.104304

> "It has recently been claimed that presenting text with the first half of each word printed in bold... facilitates reading. However, empirical tests of this claim are lacking, and theoretically one might expect a cost rather than a benefit. Here I tested participants' reading speed of 100 paragraphs that were presented either in 'Bionic' or in normal font. **Statistical analyses revealed no significant difference in reading times between Bionic and normal reading. I conclude that Bionic Reading does not facilitate reading.**"

The null held in both early and late trials and for both slower and faster readers - so it is not explained by unfamiliarity or by reader skill.

> Beelders, T. R. (2025). **Guiding the gaze: How bionic reading influences eye movements.** *Journal of Eye Movement Research*, **18**(5), 49. https://doi.org/10.3390/jemr18050049

> "It was found that **Bionic font does not significantly change eye movements when reading. Fixation durations, number of fixations and reading speeds were not significantly different between the two formats.** Furthermore, **fixations were spread throughout the word and not only on leading characters**, even when using Bionic font; hence, participants were not able to 'auto-complete' the words. Additionally, Bionic font did not facilitate easier processing of low-frequency or unfamiliar words."

Reading speed 131.1 wpm standard vs 130.8 wpm Bionic, t(52) = 0.134, p = 0.9.
That second sentence is the important one: it falsifies the *mechanism*, not just the speed claim.

> Spear, A. I., Johnson, R. L., Yun, H., Ashby, J., & Kleinsmith, A. L. (2025). **To boldly go where no text has gone before: The effects of boldface letters on eye movements in reading.** *Attention, Perception, & Psychophysics*, **87**(4), 1270-1286. https://doi.org/10.3758/s13414-025-03067-w

Bolding the first half of every word "did not facilitate reading relative to bolding the middle half or last half of every word and, in fact, led to costs relative to regular unbolded reading."
(Publisher and PubMed blocked automated fetch; that wording comes from search-result extracts of those pages rather than a rendered page. Citation metadata verified via Crossref.)

Non-peer-reviewed but well powered: Readwise ran an online test with 3,334 starters and 2,074 completing all four sections, finding no significant speed or comprehension difference - Bionic came out 2.6 wpm slower than a 327.9 wpm baseline. https://blog.readwise.io/bionic-reading-results/

**Claims that could not be substantiated:** the widely circulated "University of Central Lancashire 2023, 8-12% faster" figure has no journal article, preprint, DOI or university page behind it. Treat it as unverified marketing.

Even `text-vide`'s own repo concedes the point in `ABOUT_READABILITY.md`: "Bionic-Reading is a technique still under study... So it seems to some people that it doesn't work".

**Implication for this project:** if Bionic-style bolding ships, ship it as a *display preference*, not as a speed feature, and do not make a performance claim for it.

---

## 9. What the research actually says

This section is the honest one. The short version: **RSVP does not buy comprehension, and at every rate it costs something.** The 2016 PSPI review is the authoritative synthesis and it is not friendly to the product category.

### The baseline reading rate is lower than everyone assumes

> Rayner, K., Schotter, E. R., Masson, M. E. J., Potter, M. C., & Treiman, R. (2016). So much to read, so little time: How do we read, and can speed reading help? *Psychological Science in the Public Interest*, **17**(1), 4-34. doi:10.1177/1529100615623267

> "Reading rates of this kind seem extraordinary, given that college-educated adults who are considered good readers usually move along at about **200 to 400 wpm**." (p. 4)

> "Bear in mind, however, that a normal pace for most readers is **200 to 400 wpm**. This is faster than we normally gain information through listening, and pretty good for most purposes." (p. 29)

The larger and more recent meta-analysis narrows that considerably:

> Brysbaert, M. (2019). How many words do we read per minute? A review and meta-analysis of reading rate. *Journal of Memory and Language*, **109**, 104047. doi:10.1016/j.jml.2019.104047

> "we estimate that the average silent reading rate for adults in English is **238 words per minute (wpm) for non-fiction and 260 wpm for fiction**… The estimates are lower than the numbers often cited in scientific and popular writings… For silent reading of English non-fiction most adults fall in the range of **175 to 300 wpm**; for fiction the range is **200 to 320 wpm**."

190 studies, 18,573 participants.
So the honest baseline is **~238-260 wpm**, and the widely repeated "300 wpm average" is already optimistic.
Which means a **400 wpm default is not a mild nudge - it is roughly 1.6× the reader's natural rate**, and the clones' choice of 400 has no research behind it.

### The trade-off is real and the review says so flatly

> "The research shows that there is a trade-off between speed and accuracy. It is unlikely that readers will be able to double or triple their reading speeds (e.g., from around 250 to 500-750 words per minute) while still being able to understand the text as well as if they read at normal speed." (p. 4)

> "there is no such magic bullet. There is a trade-off between speed and accuracy in reading, as there is in all forms of behavior." (p. 29)

### What it concludes about RSVP specifically

> "In summary, although immediate comprehension may be successful with single sentences presented using RSVP speeds well beyond typical reading rates, scaling up to full text passages yields **substantial comprehension costs**." (p. 22)

> "Two studies of text comprehension using RSVP indicated that this method led to comprehension equivalent to that of normal reading **when total presentation time was equal to that of normal reading**. When the RSVP stream was sped up, however, comprehension and memory suffered." (p. 21)

> "First, when pauses between sentences were not included in RSVP presentations of text, comprehension clearly suffered (Masson, 1983). Second, **speeding text presentation beyond normal reading rates consistently led to reduced levels of comprehension and memory** (Juola et al., 1982; Potter et al., 1980). These results indicate that the mental operations responsible for assembling viewed words into meaningful ideas and retaining them in memory cannot be completed if adequate time is not provided." (pp. 27-28)

> "Therefore, the promise that RSVP can produce faster reading without compromising understanding and memory **is not supported by the research we reviewed**." (p. 28)

Their one concession, and it is the honest case for building an RSVP mode at all:

> "The real practical application of RSVP may be for wearable technology like smartwatches and glasses with optical displays that have only enough space to present one or two words at a time. The RSVP method may be the only viable way to display text on these screens. **If the message is not too long or complex, RSVP may suffice to get it across.**" (p. 28)

### The review takes Spritz apart by name

> "Consider, first, the website's mention of the optimal recognition point, which should sound familiar if you recall the optimal viewing position, or OVP (O'Regan et al., 1984)… However, **contrary to the implication of the Spritz website, readers are capable of identifying words whether or not they look at the OVP; there is just a slight loss of processing efficiency if their eyes land on a different point in the word.** Moreover, the research we reviewed on parafoveal preview benefit suggests that readers begin to process words before looking directly at them, rather than 'once the ORP is found.'" (p. 26)

On Spritz's 80/20 claim - the one quoted in §2 above - the review does the arithmetic:

> "Spritz has also been quoted by media outlets as saying that only 20% of the reader's time is spent processing content while 80% of the time is spent moving the eyes… saccades during reading last approximately 20 to 35 ms (we will use 25 ms for simplicity), and fixations last approximately 250 ms. Thus, our estimate of the percentage of time spent moving the eyes… is **only about 10% of the total reading time**. If we assume that we are always processing content while reading… a more accurate statement might be that 100% of the time is spent processing content and, during that time, the eyes are moving 10% of the time." (p. 27)

**The 80/20 figure is the single load-bearing claim in Spritz's marketing, and it is off by a factor of eight.**

On Spritz's "every saccade has a penalty in both time and comprehension":

> "eye movements are under control of the brain and are used to access the text in precisely the way we need it to be presented. Thus, they certainly do not waste time… **A regression is more likely to be the solution to discombobulation… than a cause of it.**" (p. 27)

**But the review does concede the ORP-centring point, narrowly, and this quote is worth having exactly:**

> "**To be fair to Spritz, centering words at the OVP may be an improvement over RSVP methods in which words are left justified.** This is because, with left justification, words of different lengths will be placed such that their OVPs are in different locations and the reader will probably be viewing the word from a non-optimal position. However, when words are centered, as in the RSVP paragraph experiment described earlier (Potter et al., 1980), the eye will remain close to the OVP." (p. 26)

Read carefully: pivot alignment is better **than other RSVP layouts**. It is not evidence that RSVP beats a page.
That is the correct justification for implementing an ORP - and the only one the literature supports.

### Optimal viewing position: what it actually is, and two things marketing gets wrong

Two constructs get conflated constantly:

- **OVP (optimal viewing position)** - where in an *isolated* word the eye must land for fastest recognition. A performance optimum.
- **PVL (preferred viewing location)** - where the eye *actually lands* in continuous reading. A behavioural fact.

> Liu, Y., Huang, R., Li, L., & Wang, J. (2015). Aging and the optimal viewing position effect in Chinese. *Frontiers in Psychology*, **6**, 1656. doi:10.3389/fpsyg.2015.01656

> "For words in alphabetic languages (e.g., English, French), the **OVP is a little to the left of the center of words**… Fixations tend to be made at locations a little to the left of a word's center during the natural reading of languages like English and French, which **Rayner (1979) referred to as the preferred viewing location (or PVL)**… while the OVP may indicate the optimal position for word identification, the PVL represents the locations that are actually fixated in words during natural reading, **and these need not be the same**."

**The PVL, measured.** The best primary numbers come from:

> McConkie, G. W., Kerr, P. W., Reddix, M. D., & Zola, D. (1988). Eye movement control during reading: I. The location of initial eye fixations on words. *Vision Research*, **28**(10), 1107-1118. doi:10.1016/0042-6989(88)90137-X (open preprint: Center for the Study of Reading Technical Report 406)

66 college students reading two chapters of a novel:

> "For words with four or more letters, there are more fixations near the center than at either end. In most cases… the most frequently fixated location is **at, or just left of, the center of the word**."

> "For each word length, the relationship is linear with very similar slopes, ranging from **−0.45 to −0.53 and averaging −0.49**… These predicted means were within three-tenths of a character position from each other, ranging from **−0.6 to −0.9 character positions from the center of the word, and averaging −0.7**."

> "**word length has very little effect on the means of the landing site distributions.** Rather, the means of these distributions are simply a linear function of the distance of the launch site from the center of the word."

> "the median saccade length for the data set… was **7.0 character positions**."

**This is a direct problem for the ORP story.** The eye's functional target is the **word centre**, not a length-dependent fraction; the observed ~0.7-character leftward bias is a **saccadic range error** that scales with launch distance at about half a character per character - not a preference for a special recognition point.
Spritz's Table I says the ORP moves from 33% of the way into a 3-letter word to 25% into a 12-letter word. McConkie's data says the target does not move with length at all.

**The OVP effect largely disappears in continuous reading.**

> Vitu, F., O'Regan, J. K., & Mittau, M. (1990). Optimal landing position in reading isolated words and continuous text. *Perception & Psychophysics*, **47**(6), 583-600. doi:10.3758/BF03203111

as restated in a primary source I could verify:

> Nuthmann, A., Engbert, R., & Kliegl, R. (2005). Mislocated fixations during reading and the inverted optimal viewing position effect. *Vision Research*, **45**(17), 2201-2217. doi:10.1016/j.visres.2005.02.014

> "For gaze durations… such an **OVP effect was observed in an isolated word recognition paradigm (O'Regan, Lévy-Schoen, Pynte, & Brugaillère, 1984), but not in continuous reading (Vitu, O'Regan, & Mittau, 1990)**. For continuous reading, however, Vitu et al. (2001…) reported several **inverted optimal viewing position (IOVP) effects** for fixation durations: For example, single fixations… were **longest, not shortest, near the word centers**."

In continuous reading, fixation durations are **longest** at word centre - the exact opposite of what "the eye must find the ORP before the word can be processed" predicts.
Rayner et al. 2016 make the compatible point at p. 16: the effect "is even smaller during natural reading of text (Vitu, O'Regan, & Mittau, 1990), probably because of the ability to obtain parafoveal preview."

**And the OVP is not a property of the eye.** Liu et al. (2015) note it sits at the word *centre* in Hebrew and Arabic (Farid & Grainger 1996; Deutsch & Rayner 1999; Jordan et al. 2011), and the PVL is right-of-centre for right-to-left scripts.
A left-of-centre ORP is a fact about left-to-right alphabetic reading habits and where information sits in English words, not about human vision.

**How big is the OVP cost?** There is a genuine discrepancy in the literature here, and it matters.
Rayner et al. 2016, p. 16, say the effect is "small, on the order of only a few milliseconds."
The Spritz patent quotes "about 20 milliseconds… added to lexical decision time or naming latency" per letter of deviation, attributing it to O'Regan et al. 1984.
And a modern primary source finds a much larger accuracy cost:

> Li, L., Li, S., Wang, J., McGowan, V. A., Liu, P., Jordan, T. R., & Paterson, K. B. (2017). Aging and the optimal viewing position effect in visual word recognition: Evidence from English. *Psychology and Aging*, **32**(4), 367-376. doi:10.1037/pag0000163 (PMC5459221)

Lexical decisions were fastest for 5- and 9-letter words fixated between their beginning and middle letters; for 9-letter words accuracy was **~95% at positions 3-5 vs ~65% at position 9**.

The O'Regan 1984 paper itself is paywalled with no repository copy, so the "20-30 ms per letter" figure could only be confirmed from secondary restatements. **Do not assert it as primary.** What is safe to say: the OVP effect is real for isolated words, its magnitude is disputed, and it substantially weakens or inverts in continuous reading.

### Perceptual span, and why "read a whole line at once" is impossible

> "In general, in English the size of the perceptual span is **3 to 4 letter spaces to the left of fixation** (McConkie & Rayner, 1976; Rayner, Well, & Pollatsek, 1980) and **14 to 15 letter spaces to the right of fixation** (McConkie & Rayner, 1975; Rayner & Bertera, 1979)." - Rayner et al. 2016, p. 10

Independently confirmed in:

> Rayner, K., Slattery, T. J., & Bélanger, N. N. (2010). Eye movements, the perceptual span, and reading speed. *Psychonomic Bulletin & Review*, **17**(6), 834-839. doi:10.3758/PBR.17.6.834

The *word-identification* span is much smaller:

> "The word-identification span is about **7 characters to the right of fixation** in English (see Rayner, 1998). Thus, with normal text, there is a small window comprising the currently fixated word and one or two words to the right within which words are identified." (p. 11)

Other parameters worth having:
- Fixation duration **~250 ms** (p. 8); empirical range 205-266 ms across fast and slow readers (Rayner et al. 2010).
- Forward saccades **20-35 ms**, spanning **~7 letters** (p. 9); median 7.0 characters (McConkie et al. 1988).
- **~30%** of words are skipped; `the` is skipped "about 50% of the time or more" (p. 9).
- Saccade programming takes **150-200 ms** (p. 8).
- Regressions: **10-15%** of saccades (p. 9).

On chunking and peripheral reading:

> "when people are asked to report the identity of a word that is presented so briefly that they cannot make an eye movement, accuracy is high in the fovea but drops off dramatically outside of it, with performance reaching chance level around the middle of the parafovea (approximately 3° of visual angle away from fixation; Bouma, 1973)… **These facts cast doubt on suggestions from speed-reading proponents that people can read more effectively by using peripheral vision, taking in an entire line or even an entire page at a time.**" (p. 7)

> "readers do not access any information from the lines above or below the line currently being read (Pollatsek, Raney, LaGasse, & Rayner, 1993). **This is important because it is inconsistent with the speed-reading claim that someone can read an entire page at once.**" (p. 11)

> "readers were extremely disrupted when even a single letter in the fovea was masked - their reading rates **dropped by half**… Therefore, readers were not able to read effectively by relying on parafoveal and peripheral vision alone." (p. 11)

**So: multi-word chunking in an RSVP frame is not supported.** A 2-3 word chunk exceeds the ~7-character word-identification span, which means the reader must saccade within the frame - and once they are saccading, the entire premise of RSVP is gone.
This vindicates Sprint Reader's choice to disable both the pivot highlight and the guide when `chunkSize > 1`, and pasky's honest note that multiword "did not work well for pasky so far."

### Removing regressions costs comprehension, even on easy text

This is the strongest single result against RSVP, and it isolates the variable cleanly:

> Schotter, E. R., Tran, R., & Rayner, K. (2014). Don't believe what you read (only once): Comprehension is supported by regressions during reading. *Psychological Science*, **25**(6), 1218-1226. doi:10.1177/0956797614531148

Method: a gaze-contingent **trailing mask** that blanks each word once the eyes pass it. That removes rereading **while leaving the reader in full control of pacing** - so speed is not confounded.

> "There was also a main effect of display condition (b = −0.92, z = 5.09, p < .001); subjects were **less accurate at answering comprehension questions in the trailing-mask condition than during normal reading**… The interaction was only marginally significant (b = 0.70, z = 1.90, p = .06), which suggests that restricting the opportunity to reread words with the trailing-mask paradigm **decreased comprehension globally, and not exclusively for ambiguous (i.e., garden-path) sentences**." (p. 1221)

> "comprehension was not significantly different between cases in which subjects made a regression (**M = 84%**…) or did not make a regression (**M = 78%**; p > .98) during normal reading… In contrast, comprehension was significantly poorer when subjects did not make a regression in the trailing-mask condition (**M = 71%**)…" (p. 1224)

> "**Although RSVP might be fine for reading short, simple sentences in which readers would not typically make regressions**, given that readers normally make regressions 10% to 15% of the time…, removing this ability will have drastic negative consequences for the understanding of sentences… although regressions (and saccades in general) add a small amount of time to the reading process, **the benefits they provide for understanding far outweigh the costs**." (p. 1225)

**About 7 percentage points of comprehension, at the reader's own pace, on ordinary sentences.** Slowing the stream down does not recover it. Only real, position-accurate back-navigation would - and Rayner et al. note (p. 27) that no app has demonstrated one:

> "many of these buttons merely start the text (or sentence) over from the beginning… it has not been shown that these methods for regressing (or skipping forward) in RSVP are as effective as the eyes are in conventional reading, in which readers have a spatial representation of the text and a sense of where to move their eyes"

Related, and an argument against any fixed global wpm:

> "the finding that readers' eyes remained on words that had disappeared for as long as they would have if the words had still been there suggests that the reading system naturally delays looking directly at the next word until it has performed a certain amount of linguistic processing of the currently fixated word. Therefore, **devices that present words faster than readers' natural pace may run the risk of presenting a word before the brain is prepared to process and understand it**." (p. 10)

> "The implication is that speed-reading devices that control the timing of word presentation may not be ready to use 'out of the box' but instead may need to be **tailored to each individual user** based on how that person would naturally process the text." (p. 9)

### The RSVP experiments, by rate

**Potter, Kroll & Harris (1980)**, in *Attention and Performance VIII*, pp. 395-418. RSVP at 200, 400 or 600 wpm vs printed pages at equal total duration, using Bransford & Johnson paragraphs.

> "At all rates, including 600 wpm, over 80% of the RSVP readers recalled the key topic word… **Nonetheless, detailed recall accuracy dropped markedly as the rate of presentation increased.**" (via Rayner et al. 2016, pp. 21-22; Potter is a co-author of the review)

> "while average accuracy was similar for normal reading and RSVP when the text was presented at about **200 wpm**…, what the readers were able to remember was somewhat different between the two forms of presentation: **At higher rates, a crucial word was more likely to be missed by normal readers than RSVP readers.**"

That last sentence is the strongest genuinely pro-RSVP finding in the whole review: **under a fixed time budget, RSVP guarantees exposure to every word**, whereas a page reader runs out of time and never reaches the end.

**Juola, Ward & McNamara (1982)**, *JEP: General*, **111**, 208-227: comprehension similar to normal reading when wpm was equated, but "**performance dropped by about 50%** when the rate was increased" (Rayner et al. 2016, p. 22).

**Masson (1983)**, *Memory & Cognition*, **11**(3), 262-274. doi:10.3758/BF03196973 - the inter-sentence pause result:

> "**Masson (1983) showed that without these pauses, comprehension success was reduced in the RSVP condition relative to a condition in which people skimmed passages presented in full view for the same duration.**" (Rayner et al. 2016, p. 22)

**Inter-sentence pauses are not a nicety. RSVP without them is worse than skimming at the same rate.**
Both of the studies showing RSVP/normal parity had them. This retroactively justifies jetzt's `end_sentence: 2.2` / `end_paragraph: 2.8` spacer frames and Spritz's sentence-length-proportional blank element as the most important part of either timing model.

**Masson (1986)**, *Journal of Memory and Language*, **25**, 588-604 - the pro-RSVP datum, for single sentences at 600 wpm: predictability effects were substantial, proving comprehension was happening during the stream. But "somewhat less than those reported in earlier studies" at normal rates, and Potter et al. (1993) at 600 wpm found readers misreported the nonword "dack" as "deck" **40%** of the time.

**Benedetto et al. (2015)** - the only objective comprehension test of Spritz-style RSVP that existed when the review was written:

> Benedetto, S., Carbone, A., Pedrotti, M., Le Fevre, K., Amel Yahia Bey, L., & Baccino, T. (2015). Rapid serial visual presentation in reading: The case of Spritz. *Computers in Human Behavior*, **45**, 352-358. doi:10.1016/j.chb.2014.12.043

> "That study involved a passage of text taken from George Orwell's *1984*, and participants were allowed to pause the RSVP stream whenever they wanted. Taking these pauses into account, **the average reading speed in the traditional reading condition and that in the RSVP condition were very similar and somewhat slower than normal reading (200 and 209 wpm, respectively). Reading via RSVP increased eye fatigue relative to traditional reading and, although accuracy was equivalent on comprehension questions that required making inferences, it was poorer on comprehension questions that assessed literal comprehension of the text.** These data suggest that readers were still able to get the gist of the passage when reading at normal rates via RSVP but that their ability to maintain a veridical representation of the wording of the text was impaired. **It is likely that even the gist representation would have been impaired at faster RSVP rates.**" - Rayner et al. 2016, p. 28

Two things to sit with.
**Given a pause button, readers self-selected 209 wpm.** The speed benefit vanished entirely once the reader controlled pacing.
**And even at parity speed, literal comprehension was worse and eye fatigue was higher.**
Brysbaert (2019) notes Ricciardi & Di Nocera (2017) replicated this.

**Acklin & Papesh (2017)** - the modern direct test of the apps:

> Acklin, D., & Papesh, M. H. (2017). Modern speed-reading apps do not foster reading comprehension. *The American Journal of Psychology*, **130**(2), 183-199. doi:10.5406/amerjpsyc.130.2.0183

Abstract, verbatim:

> "The current study explored variables that may affect reading comprehension during RSVP reading, including **text difficulty (6th grade and 12th grade), text presentation speed (static, 700 wpm, and 1,000 wpm), and working memory capacity (WMC)**."

> "**Consistent with recent work showing a tenuous relationship between comprehension and WMC, participants' WMC did not predict comprehension scores.** Instead, comprehension was most affected by reading speed: **Static text was associated with superior performance, relative to either RSVP reading condition.** Furthermore, **slower RSVP speeds yielded better verbatim comprehension, and faster speeds benefited inferential comprehension.**"

Two caveats worth keeping: the article is paywalled, so effect sizes and accuracy percentages could not be obtained; and **there is no RSVP condition at or near normal reading rate**, so it establishes that 700 and 1,000 wpm are worse than static, and says nothing about 250-400 wpm.
The "faster speeds benefited inferential comprehension" result is presumably readers falling back on gist when verbatim encoding fails - the same pattern Just, Masson & Carpenter found in trained speed readers.

**Rubin & Turano (1992)** - the highest RSVP rates ever reported, and the one most often cited by vendors:

> Rubin, G. S., & Turano, K. (1992). Reading without saccadic eye movements. *Vision Research*, **32**(5), 895-902. doi:10.1016/0042-6989(92)90032-E

> "The average speeds for text of an intermediate letter size (8X acuity) were **1171 words/min for RSVP and 303 words/min for PAGE text**… All subjects continued to read RSVP text faster, and **6 subjects read at the maximum testable rate (1652 words/min) with at least 75% correct on the comprehension tests**… We interpret these results as an indication that the programming and execution of saccadic eye movements impose an upper limit on conventional reading speed."

**Do not cite this as pro-RSVP without the caveats.** Brysbaert (2019, p. 42) supplies them: passages were **95-125 words**, comprehension was **four multiple-choice questions with a 3/4 pass criterion**, the median rate was **790 wpm**, and 1,652 wpm was **the ceiling of the apparatus**, not a measured limit. His framing:

> "these reading speeds are only possible for very brief time intervals when maximal use can be made of iconic and short-term memory. In addition, **they require a recuperation period afterwards** (just like running 100 meters at maximum speed does)."

A four-item multiple-choice test on a 100-word passage is a gist check, not a comprehension measure.

**Trained speed readers**, for context on what "speed reading" achieves generally:

> Just, M., Masson, M., & Carpenter, P. (1980). The differences between speed reading and skimming. *Bulletin of the Psychonomic Society*, **16**, 171.

> "The speed readers did better than skimmers on general comprehension questions about the gist of the passages **but not quite as well as people reading at normal speed**. Normal readers… were able to answer questions about **details** of the text relatively well, while skimmers and speed readers… **did not differ from each other** on these items… **the students of speed-reading courses are essentially being taught to skim and not really read.**" - Rayner et al. 2016, p. 24

> "when the three groups of participants were given more technical texts (taken from *Scientific American*), for which background knowledge would be very sparse, the speed readers no longer showed an advantage over the skimmers, even on general questions." (p. 24)

Also: Calef, Pieper & Coffey (1999) - a speed-reading course took readers from **280 → 400 wpm** while comprehension fell from **81% → 74%**.

### The mechanistic ceiling - the one number that argues RSVP has any headroom at all

> Primativo, S., Spinelli, D., Zoccolotti, P., De Luca, M., & Martelli, M. (2016). Perceptual and cognitive factors imposing "speed limits" on reading rate: A study with the rapid serial visual presentation. *PLoS ONE*, **11**(4), e0153786. doi:10.1371/journal.pone.0153786

> "The presence of a mask caused a steep decline in reading rate, with an estimated masking cost of about 200 wpm. When the decoding process was isolated, RR approached values of **1200 wpm**. When the number of stimuli exceeded the short-term memory span, RR decreased to **800 wpm**. The semantic context contributed to reading speed only by a factor of 1.4. Finally, **eye movements imposed an upper limit on RR (around 300 wpm)**. Overall, data indicate a **speed limit of 300 wpm**, which corresponds to the time needed for eye movement execution, i.e., the most time consuming mechanism."

**Critical caveat, in the paper's own words:** "**Text comprehension was not evaluated since it goes beyond the scope of the present work.**"
These are word-report thresholds, not comprehension thresholds.
So it is good evidence that saccades cost roughly 300 wpm of mechanical headroom - i.e. there *is* something for RSVP to recover. It is **not** evidence that 1,200 wpm RSVP is readable.

### Spritz's own commissioned study says comprehension went down

Worth recording because it is Spritz's own data, published on their own SDK host: Penn Schoen Berland, commissioned by Spritz, two online waves of 500, June 2-9 and June 11-17 2014, `sdk.spritzinc.com/www/1.0/psb/Spritz-PSB-study.pdf`.

| | 116-word email | 210-word article |
|---|---|---|
| Control (traditional), seconds | 35.3 | 63.8 |
| Spritz, full speed options | 28.7 | 54.8 |
| Spritz, limited (≥250 wpm) | 23.8 | 45.4 |
| **Control, % correct** | **82%** | **76%** |
| **Spritz, full speed, % correct** | **77%** | **71%** |
| **Spritz, limited, % correct** | **76%** | **68%** |

Spritz's own gloss was "SPRITZ READING COMPREHENSION IS COMPARABLE."
Comprehension fell in every cell, and the 8-point gap on the article is at or past the ±5.1-point sampling error at 90% confidence on n=250.

### Where comprehension actually starts dropping

There is **no clean dose-response curve of comprehension against RSVP wpm on realistic text** in the literature. What exists supports this banding:

| Rate | Evidence | Verdict |
|---|---|---|
| **~200 wpm** | Potter et al. 1980: accuracy "similar for normal reading and RSVP… at about 200 wpm". Juola et al. 1982: similar when wpm equated. Benedetto et al. 2015: self-paced RSVP settled at 209 wpm and was **still** worse on literal comprehension with more eye fatigue | Parity on gist; measurable verbatim deficit; no speed gain |
| **~250-350 wpm** | **No direct comprehension study at these rates that I could find.** Inference only: at or just above normal rate, below the 400 wpm where Potter saw detail recall drop; Primativo et al. put the eye-movement ceiling on normal reading at ~300 wpm, so this is where RSVP's mechanical advantage first exists | Defensible as the safe band, by interpolation - not by direct evidence |
| **400-600 wpm** | Potter et al. 1980: topic-word recall still >80% at 600 wpm but "detailed recall accuracy dropped markedly". Juola et al. 1982: "performance dropped by about 50%". Potter et al. 1993 at 600 wpm: 40% misreport rate for anomalous words | Gist survives; detail and verbatim memory degrade substantially. Borderline |
| **700-1,000 wpm** | Acklin & Papesh 2017: both worse than static text | Reliably degraded |
| **>1,000 wpm** | Rubin & Turano's 1,652 wpm is 100-word passages, 4 MC questions, apparatus ceiling | Not reading |

**Two constraints that apply at every rate, independent of wpm:**

1. **Pauses.** Masson 1983: remove inter-sentence pauses and RSVP falls below same-duration skimming.
2. **Rereading.** Schotter et al. 2014: removing regressions costs ~7 points of comprehension at the reader's own pace on ordinary sentences. Slowing down does not fix it.

### Bottom line

RSVP buys nothing on comprehension and probably costs something.
At matched time budgets it is roughly at parity for gist; at normal rates it is already worse on literal comprehension and more fatiguing; above normal rates it degrades consistently; and it structurally removes two things - parafoveal preview and regressions - that are demonstrably load-bearing.
When readers were given a pause button, they chose 209 wpm.

The ORP rationale is the weakest part of the vendor story. The review's concession is narrow: centring at the OVP beats **left-justifying in an RSVP frame**. It is not evidence that ORP alignment beats a book.

The honest case for shipping an RSVP mode is Rayner's own (p. 28): small screens, short or simple messages, or a fixed time budget where the alternative is not finishing at all.
For a Markdown preview tool, add one more: **it is a different way to move through a document you have already read, or want a fast pass over.** That is a legitimate use, and it does not require claiming a comprehension benefit.

---

## 10. What I'd implement

### Where the current implementation already stands

`scripts/mdview.py` already ships an RSVP reader. For reference, the current values:

```js
  function srDelay(it){
    const base = 60000 / SR.wpm;
    let m = it.head ? 1.35 : 1;
    const L = it.w.replace(/[^\p{L}\p{N}]/gu, '').length;
    if(L > 7) m += (L - 7) * 0.055;
    if(/[,;:)\]"'’”]$/.test(it.w)) m *= 1.5;
    if(/[.!?][)\]"'’”]?$/.test(it.w)) m *= 2.1;
    return Math.max(55, base * m);
  }
  function srPivot(w){ const n = w.length; return n <= 1 ? 0 : n <= 5 ? 1 : n <= 9 ? 2 : 3; }
```
```css
  #sr-word .l{ flex:1; text-align:right; white-space:pre; overflow:hidden; }
  #sr-word .r{ flex:1; text-align:left;  white-space:pre; overflow:hidden; }
  #sr-word .p{ color:var(--accent); flex:none; }
  #sr-guide{ width:min(560px,86%); height:0; border-top:2px solid var(--line); position:relative; }
  #sr-guide::before,#sr-guide::after{ content:''; position:absolute; left:50%; width:2px; height:11px;
                                      background:var(--line); transform:translateX(-1px); }
```
plus `SR_REC_WPM = 400`, a 120-1000 slider at step 10, a `1.6×` blank frame at block breaks, an always-visible context line, and a diagram/table/code pause card.

Against the research above, six things are worth changing and two are worth keeping loudly.

### 1. Pivot index - extend the table to 4, and strip trailing punctuation

Current: `n <= 1 ? 0 : n <= 5 ? 1 : n <= 9 ? 2 : 3` - caps at index 3, and computes on the raw token.

Both are fixable in one line. The consensus rule (§1), which is also Spritz's FIG. 7 branch, adds the 14+ case; and Spritz's patent, jetzt and Squirt all strip punctuation first:

```js
  function srPivot(w){
    const n = w.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, '').length || w.length;
    return n <= 1 ? 0 : n <= 5 ? 1 : n <= 9 ? 2 : n <= 13 ? 3 : 4;
  }
```

The punctuation strip matters more than the 14+ case: without it, `word,` and `word` pivot one character apart, so the pivot column visibly walks whenever a clause ends. That is the exact jitter the whole design exists to prevent.

### 2. Move the pivot column to ~30% - this is the biggest single change

Current layout is the symmetric three-cell grid, pivot at 50%.
Spritz uses 35%, Sprint Reader 30%, jetzt 28.75%, Squirt 34%.
Nobody serious uses 50%.

The reason is layout, not psychology (§2): with the pivot ~1/3 into the word, a long word hangs mostly to the right, so a centred pivot leaves the left half of the frame empty and overflows the right.

The fix is one line, because the existing flex layout already does the right thing - just unbalance the flex weights:

```css
  #sr-word .l{ flex:0.72; text-align:right; }
  #sr-word .r{ flex:1.68; text-align:left;  }
```

which puts the pivot cell at 0.72/2.40 = **30%** of the word row.
Then move the guide ticks to match:

```css
  #sr-guide::before,#sr-guide::after{ left:30%; }
```

Verify by eye with a long word (`internationalisation`) and a short one (`is`) - the pivot must not move and the right tail must not clip.

### 3. Add the sentence-length-proportional pause

This is the highest-value change after the column position, and it comes from the strongest research finding in §9.

Masson (1983): **remove inter-sentence pauses and RSVP comprehension falls below same-duration skimming.** Both studies that found RSVP/normal parity had them.
And Spritz's FIG. 5b makes the pause proportional to the sentence that just ended - an idea no open-source reader copied, and the one thing in the Spritz patent that is genuinely clever.

Current code gives a flat `2.1×` at a sentence end and `1.6×` at a block break. Recommended:

| Words in the sentence just ended | Sentence-end multiplier |
|---|---|
| < 12 | 1.6 |
| 12-22 | 2.4 |
| > 22 | 3.2 |

Spritz's own numbers are 1.1 / 2.2 / 3.3, but those are applied to a *separate blank frame*, and the existing implementation lengthens the last word instead. Folding the blank into the word means the multipliers should be a little higher at the bottom and a little lower at the top.
Better still, follow Spritz and jetzt and emit an actual blank frame - the eye gets a real rest, and the recovery pause is not spent staring at a word it has already read.

Paragraph break: keep a separate, larger value. jetzt uses `end_paragraph: 2.8`, Squirt 3.5×. The current 1.6× is too short - `2.8×` is the better default.

### 4. Fix the punctuation classes

Current code lumps `,;:` together at 1.5× and `.!?` at 2.1×. That is right in shape. Two gaps:

- **`Mr.` / `Mrs.` / `Ms.` / `Dr.` / `St.` and initials read as sentence ends.** Squirt's one-line fix is the cheapest thing in this whole document:
  ```js
  if(/^(Mr|Mrs|Ms|Dr|St|Prof|vs|etc|e\.g|i\.e)\.$/.test(it.w)) return base;
  ```
  Sprint Reader's recursive acronym detector is the thorough version; the regex covers 95% of it.
- **A trailing decimal point or a numbered list marker.** `3.14` and `1.` both trip the sentence-end branch. Guard with `if(/^\d+[.,]?$/.test(it.w))`.

### 5. Slow start

Nobody ramps wpm, but everybody buys the reader a beat (§3). Currently there is none.

Cheapest version, matching tspreed and speedread:

```js
  // first word of a run gets a real beat, regardless of wpm
  if(SR.firstOfRun){ SR.firstOfRun = false; return Math.max(700, base * m); }
```
set on `srPlay()`, cleared after one word.

Squirt's `3 / 2 / 1` countdown is the more charming version and costs three synthetic tokens.
Either is better than dropping the reader straight into a 400 wpm stream mid-sentence after a pause.

### 6. Default WPM - this is the honest one

Current default is **400**, matching Squirt, jetzt and Sprint Reader.

The research does not support it (§9):
- Average adult silent reading is **238-260 wpm** (Brysbaert 2019, n = 18,573).
- Spritz's own SDK default was **250**, and their FAQ recommends starting people at **200-250**.
- Benedetto et al. (2015): given a pause button, readers **self-selected 209 wpm**.
- Potter et al. (1980): parity with normal reading at ~200 wpm; detail recall dropped markedly as rate rose.
- 400 wpm is roughly **1.6× the reader's natural rate**, which is exactly the band Rayner et al. say cannot be reached "while still being able to understand the text as well as if they read at normal speed."

But 400 is also the number every browser RSVP reader ships, it is what the current implementation already saves as a per-user preference, and the honest use case for this feature is a **fast pass over a document**, not primary reading.

So: **keep 400 as the recommendation button, but say what it is.** Change the label from an unqualified recommendation to something the research can stand behind - e.g. a "400 (fast pass)" chip alongside a "250 (reading pace)" chip, with 250 as the default for a first-time user who has no saved preference.
That is a one-line change to `SR_REC_WPM` plus a second preset, and it stops the tool making a claim the literature contradicts.

Slider range: **150-800**, step 25. The current 120 floor is below any plausible reading rate and the 1000 ceiling is in the band Acklin & Papesh showed to be reliably worse than static text.

### 7. Keep - the context line, but only on pause

The current implementation shows `#sr-ctx` continuously. That is worth reconsidering.

speedread shows context **only on pause**; Sprint Reader shows the sentence on open and on pause with an optional auto-hide.
A context line visible during play invites the eye off the pivot column, which defeats the mechanism.

But there is a real argument the other way here that the prior art does not cover: this reader draws a live cursor on the **document** (`#sr-cursor`, `.sr-here`), so the reader can already look away and find their place. That is a better solution to the same problem than a context strip, and it is genuinely novel - Rayner et al. specifically note (p. 27) that no RSVP app has demonstrated position-accurate back-navigation, and a document-side cursor plus click-to-seek is exactly that.

Recommendation: **keep the document cursor, fade the context line during play and show it fully on pause.**

### 8. Keep, and be proud of - the diagram pause

```
     Classic one-word-at-a-time reading over the rendered doc. Words stream at
     the chosen wpm; anything that is a picture rather than a sentence - a
     mermaid diagram, a table, an image, a code block - stops the stream and is
     shown whole, because a diagram is not readable one token at a time.
```

**No prior implementation does this.** jetzt and Squirt avoid the problem by never selecting non-prose (jetzt's DOM whitelist excludes `PRE`, `TABLE`, `IMG`); everything else strips to plain text and streams a table's cells as if they were a sentence.
Pausing on the block and showing it whole is the right behaviour and there is no prior art to copy - so it is worth keeping the comment that explains why.

### Recommended values, collected

| Parameter | Value | Source |
|---|---|---|
| Pivot index | `n≤1→0, ≤5→1, ≤9→2, ≤13→3, else 4`, punctuation stripped | Spritz FIG. 7 / TABLE I; OpenSpritz, speedread, jetzt all identical |
| Pivot column x | **30%** of the word row | Sprint Reader 30%, jetzt 28.75%, Spritz 35%, Squirt 34% |
| Pivot colour | a saturated red on light (`#CC0001`-`#E01000`), a light blue or amber on dark | Spritz `#CC0001`; jetzt swaps to `#73b5ee` on dark |
| Guide marks | two ticks on the pivot column, above and below, pointing inward, ~10% of frame height, in a faint neutral - not the pivot colour | Spritz redicle geometry; jetzt themes the reticle separately from the pivot |
| Vertical placement | frame centre | jetzt, tspreed, speedread, quickreader |
| Base duration | `60000 / wpm` | universal |
| Long word | `+ (L − 7) × 0.055` for L > 7, capped around 1.6× | Spritz FIG. 5a caps at 1.6; jetzt reaches 2.0 which is too heavy |
| Comma / colon / semicolon | `× 1.5` | Squirt 2.0, jetzt 1.8, quickreader 1.5 |
| Sentence end | `× 1.6 / 2.4 / 3.2` by sentence length (<12 / 12-22 / >22 words) | Spritz FIG. 5b + claim 41 |
| Paragraph break | `× 2.8`, as a blank frame | jetzt `end_paragraph: 2.8` |
| Abbreviation guard | `Mr. Mrs. Ms. Dr. St. Prof. vs. etc. e.g. i.e.` → no sentence pause | Squirt |
| Numerals | no sentence pause on a bare `12.` or `3.14` | Sprint Reader's number/decimal detection |
| Long-word split | > 13 characters, split at a hyphen if present, else into `ceil(len/8)` parts, with a `-` continuation mark | Spritz patent (13 + hyphen) and jetzt (identical) |
| Minimum frame | ~55 ms | matches Sprint Reader's word-frequency floor of 40 ms |
| First word of a run | floor at ~700 ms | tspreed 1000 ms, speedread 200 ms, Sprint Reader 2 s |
| Default WPM | **250** for a first-time user; 400 offered as an explicit "fast pass" preset | Brysbaert 2019 (238-260); Spritz's own 250 default; Benedetto 2015 (self-selected 209) |
| Slider | 150-800, step 25 | above 800 the comprehension evidence is uniformly negative |
| Chunking | do not build it | perceptual span ~7 chars for word identification; Sprint Reader disables the pivot when chunking; pasky's own verdict was that it did not work |
| Bionic-style bolding | if shipped, ship it as a display preference with no speed claim | Snell 2024, Beelders 2025, Spear et al. 2025 all null or negative |

### One thing not to do

Do not add a comprehension or speed claim to the UI.
Every vendor claim in this space that has been tested has failed: Spritz's 80/20 figure is off by ~8× (Rayner et al. 2016, p. 27), Spritz's own commissioned study showed comprehension **down** in all four cells, and all three peer-reviewed tests of Bionic Reading are null or negative.
"A different way to move through a document" is defensible. "Read faster with the same comprehension" is not.

---

## 11. How the ORP should be visually differentiated

Section 1 recorded *what* every reader does to the pivot letter: almost all of them colour it red.
This section asks whether any of that is justified, and the honest answer is that almost none of it is.

The short version, before the evidence:

- **Spritz's patent claims colour, not red**, and it is the only treatment the patent discloses for the character. There is no enumeration of alternatives and no stated reason for choosing colour.
- **The ORP highlight has been directly tested exactly once**, in an n = 18 CHI paper, and it changed nothing measurable.
- **Every adjacent line of evidence runs against a hue highlight**, and one runs specifically against colour and in favour of a brightness step.
- **In every implementation in the corpus, the pivot letter is the *lowest*-contrast character in the word.** The highlight makes the letter you most want fixated the hardest one to see. This is arithmetic, not opinion, and nobody seems to have noticed.
- **The preference for blue-on-dark over red-on-dark is well founded**, but not for the reason it feels like. Red on near-black is a straightforward luminance-contrast failure. It is not chromostereopsis.

### 11.1 Does the Spritz patent claim red?

**No. It claims colour as a genus, and only for the character at the fixed display location.**

The word "red" appears exactly once in the whole of US 8,903,174 B2, as a non-limiting example in the FIG. 2c walkthrough:

> "A colored font, such as a **red font**, may be utilized to emphasize the ORP character 205 as shown in FIG. 2 c."

The operative claims are 34 and 37, which are word-for-word identical apart from their preambles:

> "**34.** The method of claim 32 wherein providing the visual aid comprises using a different color font for a character displayed at the fixed display location than is used for other characters."

> "**37.** The computer program product of claim 35 wherein providing the visual aid comprises using a different color font for a character displayed at the fixed display location than is used for other characters."

These depend from claims 32 and 35, whose subject is "providing a visual aid to **mark the fixed display location**".
So colouring the ORP character is claimed as a species of marking the *location*, not as a free-standing act of emphasising the character.
Claims 33 and 36 are the sibling species: "the visual aid comprises vertical lines above and below the fixed display location".

**There is no generic "visually distinguishable characteristic" claim.**
The words "distinguish" and "distinguishable" do not occur anywhere in the patent.
"Emphasize" occurs once, in the FIG. 2c sentence above.
"Highlight" occurs once, and it is about a companion full-text display, not the ORP character.
Of the 62 claims, only 32-37 touch visual marking at all, and only 34 and 37 mention colour.

**And there is no enumeration of alternatives for the character.**
This is the finding worth dwelling on, because the patent *does* enumerate alternatives one paragraph earlier, for the location markers:

> "Fixed display location 201 is positioned within the display 200 to accommodate at least four characters to its left and can be identified with hash marks 202. **Other identifiers such as circles, colors or textures may be used.**"

No parallel sentence exists for the ORP character.
A full-text search of US 8,903,174 B2 returns **zero occurrences** of "bold", "italic", "italics", "underline", "underlining", "typeface", "font weight", "weight" and "stroke".
The only formatting vocabulary ever applied to the character is "colored font" and "different color font".
The two settings passages that mention "the color or texture of the ORP indicators" are about the hash marks, not the letter.

**No rationale is given for choosing colour.**
The patent supplies pages of empirical justification for the ORP *position*: the 0.265 average position ratio, the 20 ms per letter of deviation, the interpolation of Table I, the 20-subject confirmation.
For the colour it supplies one bare "may be utilized to emphasize", and never compares colour against any other treatment, because it never names another treatment for the character.

**The claim was added by amendment and never re-cut.**
The original application publication US 2014/0016867 A1 has 38 claims and none of them mention colour, a visual aid, hash marks, or any emphasis at all.
Claims 32-37 were added during prosecution before grant.
All five later continuations (US 2015/0199944 A1, US 2017/0229101 A1, US 2019/0325848 A1, US 2020/0193939 A1, US 2021/0312890 A1) recite the trio verbatim, renumbered 4/5/6 or 89/90/91, and **all five are Abandoned**.
No continuation ever tried to broaden it to "visually distinguishable" or narrow it to red.
Checking the granted siblings for completeness: US 9,483,109 B2, US 9,552,596 B2, US 10,332,313 B2, US 10,712,916 B2 and US 11,644,944 B2 claim nothing about colouring the ORP character.
**US 8,903,174 B2 claims 34 and 37 are the only live granted claims in the entire Spritz portfolio that recite colour on the ORP character.**

### 11.2 Bionic Reading is the mirror image, and it is legally dead

Bionic Reading is the obvious counter-example because it uses weight rather than hue, so it is worth knowing whether Casutt had a reason.

He did not write one down, and the patent never granted anywhere.

Independent claim 1 is deliberately mechanism-agnostic:

> "**1.** A method for handling texts when they are reproduced on a display, in which a digitized text that is to be processed is selected; a software program is loaded, which includes at least one rule for the setting of at least one distinction that is perceptible when reproduced on the display…"

- US 2017/0358238 A1, claim 1 (substantively identical to GB 2552586 A claim 1)

The mechanism is pinned down in the dependents, and it is weight:

> "**6.** …in which the distinctions correspond to the emphasis of individual text components."
> "**7.** …in which the emphasis is carried out in a bold typeface."
> "**10.** …in which active distinctions are used, in particular extra bold or bold letters."
> "**11.** …in which distinctions are added to the beginnings of words, in particular the beginning letters."

The catch-all enumeration is GB 2552586 A claim 19, and the omission in it is the point:

> "**19.** …wherein active distinctions are shown using one or more of the following: semibold font, bold font, extrabold font, negative font, font size, font width, font style, capitalization, underlining, highlighting,"

(The trailing comma is in the published text.)
**Colour is absent from that list.**
Every member is a typographic property, and "highlighting" is used throughout the specification to mean emphasis already present in the source text that must be preserved, not a hue.
Colour is never mentioned as a text-emphasis mechanism anywhere in GB 2552586 A, EP 3255556 A1 or US 2017/0358238 A1.

**But no rationale for weight over colour is given either**, because the patent never contemplates colour as an option.
What it does give is a rationale for emphasising word-beginnings at all:

> "The brain center that is responsible for reading assists the eye through selective simplification. For example, when reading at the usual speed, no word is registered by the eye from the first letter to the last. The observer only absorbs the beginning letters of a word; the brain center then combines these with the ending letters of a word that the reader knows."

The shipping product's dimming of the word's tail is disclosed only in relative typographic terms, never as opacity:

> "…with the remaining word fragments then being depicted in a **less conspicuous and thus less visible** fashion."

The words "opacity", "transparency", "opaque" and "faded" do not occur anywhere in the family.

**Legal status: GB 2552586 A is Withdrawn. EP 3255556 A1 is Withdrawn. US 2017/0358238 A1 is Abandoned.**
There is no enforceable Casutt patent on bolding word-heads in any jurisdiction I can see.

A sweep of Google Patents with claims-scoped queries (`CL=("optimal recognition position" AND "color")`, `CL=("rapid serial visual presentation")`, `CL=("pivot letter")`, `CL=("focus letter")`) turned up **nothing else**.
"Optimal recognition position" is essentially a Spritz-proprietary term.
The nearest non-Spritz RSVP patent that claims colour is US 6,130,968 A (Peter McIan, Expired), and its colour claims are about the *background*, not an anchor character.

### 11.3 Longitudinal chromatic aberration: is red or blue sharper?

**Red is optically much better than blue, and it is not close. But the effect only bites near the acuity limit, and a pivot letter at 48px is nowhere near it.**

The eye's refractive power varies with wavelength by roughly 2 dioptres across the visible spectrum.
Wald and Griffin measured "approximately 3.2 diopters" across 750 to 365 nm on 14 observers with a spectral stigmatoscope.

- Wald, G. & Griffin, D.R. (1947). The change in refractive power of the human eye in dim and bright light. *JOSA* 37(5): 321-336. doi:10.1364/JOSA.37.000321

The usable modern equation is Thibos's, reproduced verbatim by Marimont and Wandell:

> "They express defocus by using the equation D(λ) = q1 - q2/(λ - q3) where λ is wavelength in micrometers and D(λ) is defocus in diopters. The values for the parameters that we use are q1 = 1.7312, q2 = 0.63346, and q3 = 0.21410, which imply an **in-focus wavelength of 580 nm**."

- Thibos, L.N., Ye, M., Zhang, X. & Bradley, A. (1992). The chromatic eye: a new reduced-eye model of ocular chromatic aberration in humans. *Applied Optics* 31(19): 3594-3600. doi:10.1364/AO.31.003594
- quoted in Marimont, D.H. & Wandell, B.A. (1994). Matching color images: the effects of axial chromatic aberration. *JOSA A* 11(12): 3113-3122. doi:10.1364/JOSAA.11.003113

Evaluating that published equation against a 580 nm reference gives the defocus for each display primary:

| λ (nm) | Defocus (D) | |
|---|---|---|
| 400 | -1.68 | |
| **450** | **-0.95** | a saturated blue primary |
| 500 | -0.48 | |
| 555 | -0.13 | |
| 580 | 0 | in focus |
| 620 | +0.17 | |
| **650** | **+0.28** | a saturated red primary |
| 700 | +0.43 | |

400 to 700 nm spans **2.10 D**, which is the canonical "about 2 D".
**A saturated blue is about 3.5 times further from focus than a saturated red.**
(The per-wavelength values are an evaluation of the published equation, not numbers printed in the paper.)

Marimont and Wandell computed what that does to the retinal image, and the language is stark:

> "From the computed OTF it is apparent that high-spatial-frequency components of the image can play little role in contrast and color appearance and that in the spatial-frequency range from 5 to 20 cycles/deg **the visual system is dichromatic, because there is no contrast in the short-wavelength receptor signal**."

> "Figure 4 illustrates that **short-wavelength light from a line source will spread roughly half a degree of visual angle** across the retina."

> "Chromatic aberration obliterates the short-wavelength cone response beyond a few cycles per degree."

Half a degree of spread is enormous next to a letter stroke.
So blue is genuinely, measurably blurrier; red at 0.28 D is inside ordinary refractive tolerance and is close to optically free.

**Two caveats, both of which matter.**

First, the in-focus wavelength is a modelling convention, not a measurement.
Marimont and Wandell assumed 580 nm; Thibos assumed 589 nm.
The current primary literature explicitly reopens the question:

> "It remains an open question what wavelength is brought into best focus by the human eye… our results support alternative lines of evidence that accommodation is guided by chromatic mechanisms that maximize signal quality in a color-opponent channel."

- Chin, B.M., Banks, M.S., Nankivil, D., Roorda, A. & Cooper, E.A. (2026). Focusing on color: How the eye chooses which wavelength to see best. *Science Advances* 12(14): eaea5693. doi:10.1126/sciadv.aea5693

Second, and decisively for our case, **the reading literature says the effect only appears near the acuity limit**.
Legge and Rubin measured reading rate under four luminance-matched filters, blue (430 nm), green (550 nm), red (650 nm) and grey:

> "Under photopic conditions, the reading rates of normal subjects were **independent of wavelength, with the exception of characters near the acuity limit**… On the whole, wavelength only occasionally plays a significant role in reading. When it does, performance tends to be depressed either in the red or the blue and to be nearly optimal for green or gray."

> "We conclude that for luminance-matched text, there is **no important effect of wavelength on reading performance** for normal subjects, except possibly for letters quite near the acuity limit."

And the exception itself:

> "Subjects NH and DR still showed no effect of wavelength… However, subjects MK and HR exhibited depressed performance in the blue. Despite repeated attempts at improved refraction to compensate for chromatic aberration, the effects persisted. **When character size was increased to 0.5° the blue effect disappeared.**"

- Legge, G.E. & Rubin, G.S. (1986). Psychophysics of reading. IV. Wavelength effects in normal and low vision. *JOSA A* 3(1): 40-51. doi:10.1364/JOSAA.3.000040

The same direction is found in grating acuity (Pokorny, J., Graham, C.H. & Lanson, R.N. (1968), *JOSA* 58(10): 1410-1414, doi:10.1364/JOSA.58.001410, where blue acuity was lower than red, yellow and green for four of five subjects, attributed to neural rather than dioptric factors) and in modern two-point resolution (Buabeng, Y. & Hammond, B.R. (2026). Wavelength dependence of fine spatial resolution in human vision. *Attention, Perception & Psychophysics* 88: 136. doi:10.3758/s13414-026-03244-5: "separation thresholds varied significantly with wavelength with short-wave light (420 nm) yielding poorer resolution compared to long-wave light (660 nm)").

**A speed reader's pivot letter is 30-100px tall, which is many times 0.5 degrees at a normal viewing distance.**
So the LCA argument, though real, does not reach our case.
It is a reason not to set 9px body text in saturated blue.
It is not a reason to prefer red for a 68px glyph, and it is emphatically not a reason to reject the user's blue.

**One folklore item to kill while we are here.**
The chain "S cones are sparse at the fovea, therefore blue text is hard to read" is not made by any peer-reviewed paper I could find.
The anatomy is real: S cones are 7-8% of foveal cones, and there is an S-cone-free zone about 100 µm (0.35 degrees, 20-25 arcmin) wide at the point of peak cone density.

> "(3) foveal blue cones are sparse, irregularly spaced, and missing in a zone about 100 microns (0.35 degrees) in diameter near the site of peak cone density"

- Curcio, C.A., Allen, K.A., Sloan, K.R., Lerea, C.L., Hurley, J.B., Klock, I.B. & Milam, A.H. (1991). Distribution and morphology of human cone photoreceptors stained with anti-blue opsin. *J Comp Neurol* 312(4): 610-624. doi:10.1002/cne.903120411
- the psychophysical original is Williams, D.R., MacLeod, D.I.A. & Hayhoe, M.M. (1981). Foveal tritanopia. *Vision Research* 21(9): 1341-1356. doi:10.1016/0042-6989(81)90241-8. Note: this paper has no abstract indexed in MEDLINE or Europe PMC and Elsevier blocks automated retrieval, so it is cited as existing rather than quoted.

But the inference is broken, because **S cones do not feed the luminance channel at all** (Eisner, A. & MacLeod, D.I.A. (1980). Blue-sensitive cones do not contribute to luminance. *JOSA* 70(1): 121-123).
A blue letter among grey letters carries large L+M luminance contrast, delivered by a dense L/M mosaic that runs right through the foveal centre.
Foveal tritanopia removes a chromatic signal the task never depended on.

### 11.4 Chromatic versus luminance channels

This is where the received wisdom needs correcting in *both* directions.

**What is true: the chromatic channels are low-pass and lose to luminance almost immediately.**

> "Both blue-yellow and red-green contrast sensitivity functions have similar low-pass characteristics… These functions indicate that the **limiting acuities based on red-green and blue-yellow colour discriminations are similar at 11 or 12 cycles/deg**… at low spatial frequencies below 0.5 cycles/deg, contrast sensitivity is greater to the chromatic gratings… **Above 0.5 cycles/deg, contrast sensitivity is greater to monochromatic than to chromatic gratings.**"

- Mullen, K.T. (1985). The contrast sensitivity of human colour vision to red-green and blue-yellow chromatic gratings. *J Physiol* 359: 381-400. doi:10.1113/jphysiol.1985.sp015591

The crossover at **0.5 c/deg** is the number to remember, and it is far lower than most people assume.
Above it, luminance wins at everything.
The chromatic cutoff at 11-12 c/deg is roughly a fifth of the luminance system's ~50-60 c/deg foveal limit.

Bypassing the optics with interference fringes shows how much of the S-cone deficit is optical rather than neural:

> "the visual system has a spatial bandwidth **1.8 times lower for isoluminant red-green than for isochromatic** stimuli. On the other hand, we find **no difference in bandwidth or sensitivity of the neural visual system for isoluminant red-green and S-cone-isolated stimuli**."

- Sekiguchi, N., Williams, D.R. & Brainard, D.H. (1993). Efficiency in detection of isoluminant and isochromatic interference fringes. *JOSA A* 10(10): 2118-2133. doi:10.1364/JOSAA.10.002118

**What is NOT true: that reading collapses at equiluminance.**
I expected the literature to say this and it does not.
Two independent studies find that high chromatic contrast sustains near-normal reading speed:

> "When color contrast is high, normal subjects can read **as rapidly as with high luminance contrast (greater than 300 words/min)**. Curves of reading speed versus contrast have the same shape for the two forms of contrast and are superimposed when contrast is measured in multiples of a threshold value. **When both color and luminance contrast are present, there is no sign of additive interaction, and performance is determined by the form of contrast yielding the highest reading rate.**"

- Legge, G.E., Parish, D.H., Luebker, A. & Wurm, L.H. (1990). Psychophysics of reading. XI. Comparing color contrast and luminance contrast. *JOSA A* 7(10): 2002-2010. doi:10.1364/JOSAA.7.002002

> "When luminance contrast was reduced to near the threshold for reading, **chromatic contrast sustained reading rates of nearly 300 words per minute**, almost as high as those found with high luminance contrasts. **Low-pass filtering of chromatic text had a proportionately greater effect on small characters**, as would be predicted from the lower bandwidth of chromatic visual channels. Arguments are presented suggesting that reading rates for equiluminant text are sustained by **luminance transients introduced by transverse chromatic aberrations of the eye**."

- Knoblauch, K., Arditi, A. & Szlyk, J. (1991). Effects of chromatic and luminance contrast on reading. *JOSA A* 8(2): 428-439. doi:10.1364/JOSAA.8.000428

Three things fall out of this, and the third is the one that governs the design.

1. "Reading needs luminance" is too strong as stated. Chromatic contrast alone supports full reading speed.
2. But Knoblauch's own caveat undercuts that mechanistically: the equiluminant reading may be riding on luminance transients manufactured by the eye's *transverse* chromatic aberration, not on a genuinely chromatic achievement.
3. **Legge's sentence is the design rule: when both are present, there is no additive gain, and performance follows whichever channel is better.** Colour laid on top of already-adequate luminance contrast buys you nothing. It just fails to hurt.

**The part that does transfer to a single letter, and it is the strongest argument in this whole section.**

Reading acuity is not really the question for a pivot letter.
The pivot letter's job is to *anchor a fixation*, and that is an oculomotor question, not a legibility question.
On that question the literature is unambiguous:

> "The results showed that abrupt onsets (new objects) are especially effective in capturing attention and the eyes, but that luminance increments that do not accompany the appearance of new objects capture attention as well. **Color singletons do not capture attention** unless subjects have experienced the color singleton as a search target in a previous experimental session. **Both abrupt onsets and luminance increments elicit reflexive, involuntary saccades whereas transient color changes do not.**"

- Irwin, D.E., Colcombe, A.M., Kramer, A.F. & Hahn, S. (2000). Attentional and oculomotor capture by onset, luminance and color singletons. *Vision Research* 40(10-12): 1443-1458. doi:10.1016/S0042-6989(00)00030-4

**A luminance increment elicits a reflexive saccade. A hue change does not.**
If the pivot marker's job is to pull the eye to a spot, it needs to be a luminance step, and the ORP convention has been using the one channel that does not do the job.

Three supporting results, all pointing the same way:

- **Red is not special.** With stimuli equated for cone contrast, "we found no advantage for unique hues over their nonunique complementary colors… **reddish-greenish pairs were not significantly different in salience**." Only 10 of 21 red-green comparisons reached significance, and green won six of those. Wool, L.E., Komban, S.J., Kremkow, J., Jansen, M., Li, X., Alonso, J.-M. & Zaidi, Q. (2015). Salience of unique hues and implications for color theory. *Journal of Vision* 15(2):10. doi:10.1167/15.2.10. **"Red grabs attention" is folklore.**
- **Chromatic responses are simply slower.** "visual onset latencies were **30-35 ms longer for color**… these differences in visual onset latency translated directly into differences in saccadic reaction time." White, B.J., Boehnke, S.E., Marino, R.A., Itti, L. & Munoz, D.P. (2009). Color-related signals in the primate superior colliculus. *J Neurosci* 29(39): 12159-12166. doi:10.1523/JNEUROSCI.1986-09.2009. For S-cone stimuli specifically the penalty is worse, and "this reaction time difference was **twice as large for saccadic responses**" (Bompas, A. & Sumner, P. (2008). *Journal of Vision* 8(8):10. doi:10.1167/8.8.10).
- **A permanent irrelevant singleton gets actively suppressed.** "when the conditions were changed to avoid capture by the singleton, accuracy for the letter inside the irrelevant singleton was **reduced below the level observed for letters inside nonsingleton distractors**, an indication of active suppression of processing at the singleton location." Gaspelin, N., Leonard, C.J. & Luck, S.J. (2015). Direct evidence for active suppression of salient-but-irrelevant sensory inputs. *Psychological Science* 26(11): 1740-1750. doi:10.1177/0956797615597913. See also Luck, S.J., Gaspelin, N., Folk, C.L., Remington, R.W. & Theeuwes, J. (2021). Progress toward resolving the attentional capture debate. *Visual Cognition* 29(1): 1-21. doi:10.1080/13506285.2020.1848949.

That last one is uncomfortable for the whole ORP-highlight idea.
A cue that is present on every single word and is never task-relevant is precisely the stimulus readers learn to suppress, and suppression pushes processing at that location *below* baseline.
You would be marking the letter you most want read as the letter to inhibit.

**So the answer to "luminance or hue?" is luminance, but not for the legibility reason.**
Hue is fine for legibility at this glyph size.
Hue is the wrong channel for *anchoring a fixation*, which is what the ORP marker is for.

### 11.5 Colour vision deficiency

**Prevalence.**
Red-green CVD affects about 8% of men and 0.4% of women of European descent, and 4-6.5% of men of Chinese and Japanese ethnicity.

- Birch, J. (2012). Worldwide prevalence of red-green color deficiency. *JOSA A* 29(3): 313-320. doi:10.1364/JOSAA.29.000313

The breakdown matters more than the headline, because **most red-green CVD is anomalous trichromacy, not dichromacy**.
For Caucasian males the standard figures are roughly protanomaly 1.1%, deuteranomaly 4.6%, protanopia 1.0%, deuteranopia 1.3%.

- Sharpe, L.T., Stockman, A., Jägle, H. & Nathans, J. (1999). Opsin genes, cone photopigments, color vision and color blindness. In Gegenfurtner & Sharpe (eds), *Color Vision: From Genes to Perception*, CUP, pp. 3-52. Note: cvrl.org was unreachable during this research, so these are the widely reproduced figures rather than a verified table read from the chapter.

So about **2.3% of men are dichromats and about 5.7% are anomalous trichromats**.
"Red fails for 8% of men" overstates it.
Red *degrades* for about 8% and approaches useless for about 2.3%.
Tritan defects run about 1 in 500, autosomal dominant with incomplete penetrance, so with no sex bias (Went & Pronk 1985; Weitz et al. 1992; OMIM #190900).

**The mechanism, and it is asymmetric in a way that matters enormously here.**
Luminance is built almost entirely from L and M cones; S cones contribute essentially nothing.
A protanope has no L cones, so protanopic luminance is carried by M alone and long-wavelength light drives far less luminance signal.
A deuteranope has no M cones, so long-wavelength light drives *more* luminance than normal.
Brettel, Viénot and Mollon put it in one sentence:

> "The small elements that appear red to the normal observer are **dark for the protanope and light for the deuteranope**."

- Brettel, H., Viénot, F. & Mollon, J.D. (1997). Computerized simulation of color appearance for dichromats. *JOSA A* 14(10): 2647-2655, p. 2651. doi:10.1364/JOSAA.14.002647
- the fast sRGB implementation is Viénot, F., Brettel, H. & Mollon, J.D. (1999). Digital video colourmaps for checking the legibility of displays by dichromats. *Color Research and Application* 24(4): 243-252

**Running that algorithm on our actual palette** (page light `#FBFBF9` / ink `#202832`, page dark `#131319` / ink `#e4e4ea`):

| Pivot | Observer | Appears as | vs page | vs neighbouring letters |
|---|---|---|---|---|
| `#CC0001` on light | normal | `#CC0001` | 5.68:1 | **2.53:1** |
| | protan | `#4A4A09` dark olive | 8.91:1 | **1.60:1** |
| | deutan | `#757500` mid olive | 4.71:1 | 3.06:1 |
| | tritan | `#949400` | 3.12:1 | 4.63:1 |
| `#73b5ee` on dark | normal | `#73b5ee` | 8.44:1 | **1.73:1** |
| | protan | `#AFAFEE` | 8.98:1 | 1.63:1 |
| | deutan | `#A5A5EF` | 8.13:1 | 1.80:1 |
| | tritan | `#9999FF` | 7.36:1 | 1.98:1 |

**Read the protan row for red carefully.**
Against a *light* page, protanopia actually improves the red pivot's background contrast, because the red goes darker on a light ground.
Against a *dark* page it does the opposite, and the same effect that helps on white is what destroys red on black.
Independent arithmetic substituting M-cone-only luminance into the WCAG formula gives `#CC0001` on `#FFFFFF` = **9.50:1** for a protanope (better than the 5.89:1 a trichromat gets), and `#CC0001` on `#121212` = **1.97:1** (far worse than the trichromat's 3.18:1).
**Protanopia is not a symmetric penalty. It punishes exactly the dark-mode case and rewards the light-mode case.**

But look at the column that actually carries the signal.
Against the *neighbouring letters*, the light-mode red drops from 2.53:1 to **1.60:1** for a protanope.
For that reader the pivot letter is a slightly-off dark letter and nothing more.

**Blue survives, and the reason is structural rather than lucky.**
Blue/yellow discrimination is preserved in red-green CVD, because the missing or shifted photopigment is L or M and the S-versus-(L+M) opponent axis is intact.
Brettel et al.'s own method rests on exactly this:

> "we infer from reports on unilateral inherited color vision deficiencies that a stimulus of **575 nm is perceived as the same yellow, and a stimulus of 475 nm as the same blue**, by trichromats as by protanopes and deuteranopes"

Every protan and deutan confusion line collapses onto that blue-yellow axis.
So a hue separated from its surround along blue-yellow survives; a hue separated only along red-green does not.
`#73b5ee` barely moves under simulation and keeps its luminance.
Amber survives for the same reason, at the yellow end, and it is the better of the two on a dark ground because it is brighter still.
There is no single hue that survives protan, deutan *and* tritan, which is itself an argument for not leaning on hue.

**Standards.**
WCAG 2.2 SC 1.4.1 Use of Color (Level A), normative text:

> "Color is not used as the only visual means of conveying information, indicating an action, prompting a response, or distinguishing a visual element."

SC 1.4.3 Contrast (Minimum) (Level AA):

> "The visual presentation of text and images of text has a contrast ratio of at least 4.5:1"

with the large-text exception at 3:1, where large is defined as at least 18pt, or 14pt bold, or 24px / 18.66px bold in CSS.

**There is no accessibility guidance anywhere that addresses highlighting a single character inside a word.**
I checked the WCAG 2.2 success criteria, the Understanding documents and the Techniques list.
Nothing addresses intra-word character emphasis, and nothing addresses RSVP or serial text presentation at all.
The nearest structural analogue is Technique **G183**, "Using a contrast ratio of at least 3:1 to distinguish inline text links from surrounding text":

> "the contrast ratio between the link text and the static text must be at least 3:1"

and G183 additionally recommends a non-colour cue: "authors may still consider using an alternative or additional way to indicate links, such as an underline or bold text".
That is the same geometry as ours: one coloured run inside a longer differently-coloured run.
It is not normative for a pivot letter, but it is the pattern the Working Group reached for when facing the identical problem, and **applying its 3:1 threshold to pivot-versus-neighbour contrast is a defensible house rule.**

**Is the coloured pivot an SC 1.4.1 violation?**
On the strict reading, no, but only because of a design decision made for other reasons.
The pivot letter *is* conveying information: "fixate here" is squarely "indicating an action" and "prompting a response" in the criterion's own language.
So 1.4.1 is engaged.
But it is satisfied, because in a correctly built RSVP reader the pivot's location is *also* conveyed by spatial alignment (the fixed 30% column) and by the reticle ticks above and below it, both of which are achromatic.
The Understanding document supports this directly: "This should not in any way discourage the use of color on a page, or even color coding if it is complemented by other visual indication."

**The corollary is the one to write down: the colour is not carrying the information. The fixed column is.**
If you ever removed the alignment and left only the colour, it would become a 1.4.1 violation.
Which is another way of saying the highlight is redundant with a cue that already works better.

SC 1.4.3 is a different matter, because the pivot letter is text and none of the three exceptions applies.
At our palette: `#CC0001` on `#FBFBF9` is 5.68:1 and passes.
`#73b5ee` on `#131319` is 8.44:1 and passes.
`#73b5ee` on a light page would be 2.12:1 and fails at any size, and `#CC0001` on a `#1a1a1a` page would be 2.96:1 and also fails at any size.
**The existing red/blue split is correct, and each colour fails AA in the other mode.** The interesting part is why.

APCA, the lightness-contrast model built specifically because WCAG 2 mishandles dark colours, agrees emphatically: `#CC0001` on `#121212` scores **Lc -24.6**, below APCA's absolute floor of Lc 30 for text of any size.
Two models that disagree about a great many dark-mode colours both condemn red on near-black.
(APCA is not adopted; visual contrast was removed from the WCAG 3 Working Draft in July 2023 and the WCAG 3 algorithm is still to be determined.)

### 11.6 Dark mode: why saturated red on near-black looks wrong

**The answer is plain luminance contrast. It is not chromostereopsis. Almost everything else written about this is folklore.**

**The real mechanism, with the arithmetic.**
The sRGB red primary carries only 0.2126 of luminance and in `#CC0001` it is the only channel lit.

```
#CC0001:  R = 204/255 = 0.800000 -> ((0.800000+0.055)/1.055)^2.4 = 0.603827
          G = 0                  -> 0
          B = 1/255   = 0.003922 -> 0.003922/12.92               = 0.000304
          Y = 0.2126(0.603827) + 0.7152(0) + 0.0722(0.000304) = 0.128396
```

**Even at 80% red drive, `#CC0001` reaches only 12.8% of white's luminance.**
Against a light ground that gap is large and the contrast is fine.
Against a near-black ground there is simply not enough light in the glyph to build a ratio.

The killer framing is the comparison to its own neighbours.
On our dark page the surrounding body text sits at **14.61:1** and a red pivot would sit at **3.14:1**.
The pivot would be roughly **five times lower in contrast than every letter around it**.
The one glyph you most want the eye to land on would be the least visible glyph in the word.

**The perceptual name for what that feels like is Gregory's equiluminance instability, not chromostereopsis.**
At or near equiluminance, borders defined by colour alone become unstable and "jazzy", because the luminance pathway that carries most spatial-form information is nearly blind there and the edge is left to the lower-resolution chromatic pathway.

- Gregory, R.L. (1977). Vision with isoluminant colour contrast: 1. A projection technique and observations. *Perception* 6(1): 113-119. doi:10.1068/p060113
- Cavanagh, P., Adelson, E.H. & Heard, P. (1992). Vision with equiluminant colour contrast: 2. A large-scale technique and observations. *Perception* 21: 219-226
- Gregory, R.L., Cavanagh, P., Mollon, J. & Troscianko, T. (2009). All's jazzy and unstable on the colour front. *Perception* 38(1). PMC2997677

Red on near-black is not literally equiluminant, but at 3:1 the luminance channel is only weakly driven while the chromatic channel is driven hard.
That is the shoulder of Gregory's regime, and it is why the glyph reads as soft and floaty.
Note that this is the *same* cause as the arithmetic above, described perceptually rather than photometrically. It is not a competing explanation.

**Chromostereopsis: real phenomenon, wrong explanation.**
It is well documented (Vos, J.J. (1960). *JOSA* 50(8): 785-790; Ye, M., Bradley, A., Thibos, L.N. & Zhang, X. (1991). *Vision Research* 31(10): 1787-1796; Thompson, May & Stone (1993). *Displays* 14(4): 227-234; threshold measured at Δx = 0.003, Δy = 0.004 by Ozolinsh & Muizniece (2015). *Front Psychol* 6:337. doi:10.3389/fpsyg.2015.00337).
But it is a **binocular disparity** effect that requires two chromatically different stimuli present simultaneously at the same physical depth, so that transverse chromatic aberration displaces their retinal images differently in the two eyes.
The archetype in the literature is "blue lettering on a red background".
**A red letter among black letters on white is not a red/blue pair**, because black emits nothing.
On a dark ground there is a broadband neighbour, so a small depth signal is possible in principle, but the effect is a *depth* percept rather than discomfort, it varies in sign between individuals, and at 3:1 luminance contrast it is buried under a far larger legibility problem.
Design writing applies the term to any red-plus-anything-on-dark, which is not what the literature describes.
**Label: real effect, folklore explanation.**

**Purkinje shift and rod involvement: anatomically impossible here.**
Two independent reasons.
First, CIE 191:2010 puts the mesopic range at 0.005 to 5.0 cd/m², and a typical display at 200-400 cd/m² peak white puts our dark-mode body text at roughly 160-320 cd/m² and even the near-black background at 1-2 cd/m².
A bright display in a dim room is photopic at the point of regard.
Second, and decisively at any ambient level, **reading is foveal and the fovea has no rods**: the rod-free zone is 0.350 mm, or 1.25 degrees (Curcio, C.A., Sloan, K.R., Kalina, R.E. & Hendrickson, A.E. (1990). Human photoreceptor topography. *J Comp Neurol* 292(4): 497-523).
The Purkinje shift is a rod phenomenon and there are no rods where you are reading.
**Label: folklore. Delete it from the argument.**

**LCA-driven "accommodation hunting": unsupported.**
The physics is real but the behavioural consequence is not established.
Bernal-Molina, P., Esteve-Taboada, J.J., Ferrer-Blasco, T. & Montés-Micó, R. (2018), *Journal of Optometry* 12(1): 38-43, PMC6318541, measured accommodative response 0-3 D for both polarities: "The slopes for the ARs of the four conditions were not significantly different from each other" (p = 0.16), and "contrast polarity does not seem to influence the accommodative response when reading text from an electronic microdisplay".
Jiménez et al. (2020), *Vision Research* 166: 33-42, doi:10.1016/j.visres.2019.11.006, do find that colour combination modulates accommodative and pupillary dynamics, but the affected combination was blue-on-red and no fatigue outcome was established.
**Label: unverified, trending folklore. Do not use it as an argument.**

**Halation: the polarity effect is real, the halation mechanism is not.**
The positive polarity advantage (dark text on light beats light on dark) is well replicated:

> "colour contrast (red text on green background) **could not compensate for a lack of luminance contrast**"

- Buchner, A. & Baumgartner, N. (2007). Text-background polarity affects performance irrespective of ambient illumination and colour contrast. *Ergonomics* 50(7): 1036-1063. doi:10.1080/00140130701306413

That sentence is the single best one-line citation in this entire section, because it is the empirical statement of the thing the arithmetic shows: **hue does not substitute for luminance.**

> "pupil sizes were smaller and proofreading performance was better with positive than with negative polarity displays. The results are compatible with the hypothesis that the positive polarity advantage is an effect of display luminance."

- Piepenbrock, C., Mayr, S. & Buchner, A. (2013). Smaller pupil size and better proofreading performance with positive than with negative polarity displays. *Ergonomics*
- see also Piepenbrock, Mayr & Buchner (2014). Positive display polarity is particularly advantageous for small character sizes. *Human Factors* 56(5): 942-951. doi:10.1177/0018720813515509

**The established mechanism is pupil size**, not bleeding: brighter field, constricted pupil, smaller blur circle, sharper retinal image.
Every source asserting that light-on-dark text "bleeds" for astigmatic readers is a blog or a vendor post.
No peer-reviewed study measures halation as a distinct effect, and none tests an astigmatism-by-polarity interaction.
The term is borrowed from photographic film emulsion, where it names a real physical process with no direct analogue in the eye.
**Label: folklore as a named effect.**

**Verdict on the mechanisms.**

| Mechanism | Status |
|---|---|
| Low luminance contrast of saturated red | **REAL, and it is the entire answer** |
| Protanopic amplification of exactly that failure | **REAL**, and specific to dark mode |
| Gregory equiluminance instability ("vibrating") | **REAL**, and a restatement of the first, not a rival |
| Chromostereopsis | Real effect, **misapplied** here |
| LCA / accommodation hunting | **Unverified** |
| Purkinje shift / rod involvement | **Folklore**, anatomically impossible foveally |
| Halation, astigmatism story | **Folklore** as a named effect |

### 11.7 Why jetzt is blue: the commit archaeology

Section 1 records jetzt as the one reader that swaps red for `#73b5ee` on dark.
It turns out there is nothing written down anywhere, and the history is more interesting than the absence.

- **d599ecf, 2014-03-05, initial commit.** `.sr-pivot { color: red; }` in `jetzt.css`, the bare CSS keyword, one rule for both themes.
- **8d70ea4, 2014-03-10, Ian Zapolsky, "Dark theme for jetzt speedreader"** (PR #33). Adds `.sr-reader.sr-dark .sr-word-box .sr-word .sr-pivot { color: #00ff00; }`. **The first dark pivot was pure green, not blue.** The commit body reads in full: "Added a dark theme for jetzt, taking into account comments from ds300. Trying to stay truer to the control methods have already been written. Changed the way the CSS is implemented, to instead add the sr-dark class to the sr-reader element." Not a word about the colour.
- **7772b46, 2014-03-17, "Fixes unsettable dark-theme color bug".** Merges the dark and light selectors, deleting the `#00ff00` rule entirely. Dark reverts to red.
- **c6ea00a, 2014-03-18, "custom themes more or less done".** The pivot moves out of CSS into a themes object in `config.js`. **Both** themes get `"pivot_color": "#E01000"`.
- **9f2782e, 2014-03-22, "updated changelog and manifest".** The dark theme's pivot silently becomes `"#73b5ee"`. The same commit retunes `progress_bar_foreground`. The changelog diff *in that very commit* lists only "configuration page including custom themes". The colour change is not mentioned.

`readme.md` never mentions the pivot colour at all.
**The blue is an undocumented drive-by tweak in a commit named after a changelog edit, four days after the pivot had been unified on red, and twelve days after the dark pivot was pure green.**
No issue, no PR discussion, no rationale.

The green episode is worth keeping, because it is the textbook worst case and it lasted a week.
`#00ff00` against jetzt's `#E0E0E0` dark text is ΔL\* = **-1.4** and ΔE00 = 32.4, of which **98.8% is chromatic**.
That is an essentially equiluminant chromatic edge on a single small glyph, precisely the configuration §11.4 says the visual system handles worst.
Somebody's eyes evidently told them, and the rule was removed inside seven days without anyone writing down why.

### 11.8 The structural finding nobody in the corpus noticed

Recomputing every implementation in §1 against its own background and its own neighbouring letters:

| Implementation | ORP | ORP vs background | Neighbours vs background | **ORP vs neighbours** |
|---|---|---|---|---|
| Spritz | `#CC0001` | 5.89:1 | 21.00:1 | 3.57:1 |
| OpenSpritz | `#de0000` | 5.11:1 | 12.63:1 | 2.47:1 |
| Squirt | `rgb(238,69,69)` | 3.49:1 | 11.69:1 | 3.35:1 |
| jetzt light | `#E01000` | 4.78:1 | 12.21:1 | 2.55:1 |
| jetzt dark | `#73b5ee` | 6.02:1 | 10.00:1 | **1.66:1** |
| Sprint Reader light | `#FF8C00` | **2.33:1** | 21.00:1 | 9.00:1 |
| Sprint Reader dark | `#FF8C00` | 9.00:1 | 21.00:1 | 2.33:1 |
| quickreader dark | `#ff4444` | 5.11:1 | 13.18:1 | 2.58:1 |
| quickreader light | `#cc0000` | 5.40:1 | 15.96:1 | 2.96:1 |
| quickreader sepia | `#8b0000` | 8.50:1 | 7.09:1 | **1.20:1** |
| rollecode dark | `#ff6b6b` | 7.13:1 | 19.80:1 | 2.78:1 |
| rajesh light | `#e74c3c` | 3.82:1 | 12.61:1 | 3.30:1 |
| rajesh dark | `#e74c3c` | 4.56:1 | 15.27:1 | 3.35:1 |
| **browser-preview light (now)** | `#CC0001` | 5.68:1 | 14.36:1 | 2.53:1 |
| **browser-preview dark (now)** | `#73b5ee` | 8.44:1 | 14.61:1 | **1.73:1** |

**In every single row except quickreader's sepia, the ORP letter has less luminance contrast against the page than its own neighbours do.**
The highlight universally makes the pivot the weakest character in the word.

Decomposing the ORP-versus-neighbour difference into lightness and chroma in CIELAB makes the same point in the other currency:

| Pair | ΔE00 | ΔL\* | ΔC\* | ΔH\* | lightness share |
|---|---|---|---|---|---|
| Spritz light, `#CC0001` vs `#000000` | 42.0 | 42.5 | 88.4 | 0.0 | 32.5% |
| jetzt light, `#E01000` vs `#333333` | 36.9 | 26.0 | 94.0 | 0.0 | 21.7% |
| jetzt dark, `#73b5ee` vs `#E0E0E0` | 23.2 | -17.7 | 35.6 | 0.0 | 33.2% |
| jetzt dark v1, `#00ff00` vs `#E0E0E0` | 32.4 | **-1.4** | 119.8 | 0.0 | **1.2%** |
| Sprint Reader dark, `#FF8C00` vs `#ffffff` | 35.4 | -30.5 | 84.1 | -0.1 | 26.6% |
| **browser-preview light (now)** | 40.8 | 26.8 | 80.6 | 47.9 | 22.2% |
| **browser-preview dark (now)** | 24.0 | -19.3 | 32.3 | -6.9 | 36.8% |

**Two-thirds to 99% of the signal is chromatic in every case.**
The convention delivers its cue almost entirely down the channel that Irwin et al. showed does not elicit reflexive saccades.

And one more number worth sitting with: **the current dark blue is a far weaker signal than the current light red.**
ΔE00 24.0 against 40.8, so a little over half the perceptual distance.
The blue that reads as "more refreshing" is the *quieter* cue, not the better-engineered one.
That is a genuine and useful piece of information about what is actually wanted here, and §11.11 takes it seriously rather than treating it as an error to correct.

### 11.9 What else is used in the wild

The corpus in §1 was Spritz plus six clones.
Widening the survey to every RSVP reader whose source could be read gives the full taxonomy, and it has more shape than the "everyone copies Spritz's red" summary suggests.

**Colour plus weight** is more common than §1 implied.

| Implementation | Treatment | Source |
|---|---|---|
| **tspreed** | **bold AND red together**, by default | shipped `default.rc`: `focusbold=true` and `focuscolor=1` (ANSI red). The render path applies both: `[ "$focusbold" = true ] && printf "%s" "$term_bold"` then `[ -n "$focuscolor" ] && term_color "$focuscolor"` |
| **pasky/speedread** | red on an already-bold word, so hue is the only delta | `sub show_word` |
| **rajeshsatpathy1/SpeedReader** | `color: var(--highlight-color); font-weight: bold;` | `src/components/ReaderDisplay.css:60-62`. `--highlight-color` is `#e74c3c` in light, dark *and* matrix themes; `#d35400` in sepia |
| Mootikins/rsvp-term | red + bold + `┬`/`┴` guide ticks | `src/ui/rsvp.rs:69-72`, `base_style.fg(Color::Red).add_modifier(Modifier::BOLD)` |
| one-more-refactor/flick-tui | red + bold + rail notch | `src/ui.rs:187`, `const ACCENT: Color = Color::Red;` |
| JuustKiwi/SpeedReader | user-configurable colour, default red, + bold | `src/ui.rs:195`; `src/config.rs` reads `highlight_color=` from `~/.config/speedreader.conf` |
| skuzzymiglet/greedy | red + bold | `speedread.go:20` |
| arozx/speedreader-go | ANSI-256 `196` + bold, rest `255` | `main.go:51-54` |
| ZhYGuoL/RSVP-OS | **system tint + semibold**, no hardcoded colour | `RSVPWordView.swift:47-51`, `.foregroundStyle(.tint).fontWeight(.semibold)` |

**This correction matters for §1**, which described tspreed as offering `--focus-bold` as an alternative to colouring.
It is not an alternative.
When `-f`/`--focus` is on, tspreed's shipped defaults apply bold *and* red simultaneously.
**tspreed is the only reader in the original corpus that deliberately stacks two channels**, and it happens to be the one that gets the evidence right by accident.

**Weight alone is an empty cell.**
Across everything surveyed, no shipping RSVP reader distinguishes the ORP by weight without also changing hue.
The one candidate, `metcalfc/brr`, bolds all three word segments, so weight carries zero information.

**Underline appears twice, never alone.**
shawnpinciara/RSVPReaderDS draws a 2px filled red rect under the glyph (`drawFilledRect(xCur, ulY, cw*scale, 2, kRed)`, header comment "ORP letter red+underlined, centred on ORP").
Nobody ships underline as the sole signal.

**Glow appears once.**
rollecode/speed-reader: `.orp-char { color:#ff6b6b; filter: drop-shadow(0 0 20px rgba(220,38,38,.6)); }` on `#0a0a0a`, neighbours pure white.

**Background chip: nobody.**
Not one implementation surveyed puts a coloured chip behind the pivot glyph.

**"Nothing at all" is a well-populated category, not an oddity.**
Six with citable source: `rdearman/rsvp-ratatui` (single `Span::styled`, no `orp` token anywhere), `ambevill/rsvp-reader` (one `create_text` call), `stupakzm/Text-Processor-RSVP` (plain `printf`, the only ANSI in 595 lines is cursor positioning), `Gingerbreadfork/panic-reader` (`<p class="text-black text-center text-4xl py-64">{wordBeingRead}</p>`, no split logic), plus **tspreed** (highlight off by default) and **c3c3l14/speedreader**, whose default highlight colour is literally its text colour (`let mut highlight = Color::White;`, red only behind an explicit `--highlight` flag).
The last two are the interesting kind: they implemented ORP marking and chose *off* as the default.

**Three real departures from red, and what they have in common.**

- **`kivanceski/rsvp.nvim` links the pivot to the `ErrorMsg` highlight group** and picks no colour at all: `accent = { link = "ErrorMsg" }` in `lua/rsvp.lua:18`, documented as `RsvpAccent` in `doc/rsvp.txt`. It inherits whatever the user's colourscheme uses for errors. This is the most environment-respectful approach in the entire survey and the only one that lands correctly on any theme by construction.
- **`jamestomasino/stutter`'s night theme inverts figure and ground**: `--textHighlight: #fff` with `--textColor: #f00` on black, so the pivot is white among red letters. Not a different accent, a reversal.
- **`ZhYGuoL/RSVP-OS` uses the macOS system tint plus semibold**, hardcoding nothing.

Set alongside jetzt's undocumented `#73b5ee`, the pattern is clear: **the implementations that departed from red mostly did so by deferring to the platform or the user, not by reasoning about perception.**
**Not one repository in the survey contains a perceptual or accessibility argument for its pivot colour, and there are zero mentions of colour blindness anywhere, in jetzt or in any of the others.**

**Sprint Reader deserves a note** because it is the only one that exposes the decision.
`reader.html` has a "Highlight optimal letter (choose below)" checkbox plus a colour-picker widget, so `#FF8C00` is a default rather than a design.
It is also **theme-independent**: the same orange on white and on black.
That is the only value in the corpus that clears 3:1 against *both* grounds (2.33:1 on white, 9.00:1 on black), which is presumably an accident but is worth noticing.

**quickreader documents contrast ratios, and most of them are wrong.**
`src/lib/constants.ts` lines 17-25 claim WCAG-verified numbers.
Recomputing:

| Pair | Claimed | Actual | |
|---|---|---|---|
| dark ORP/bg `#ff4444` on `#1a1a1a` | 3.7:1 | **5.11:1** | wrong |
| light ORP/bg `#cc0000` on `#f5f5f5` | 5.9:1 | **5.40:1** | wrong |
| sepia ORP/bg `#8b0000` on `#f4ecd8` | 11.3:1 | **8.50:1** | wrong by 25% |
| high-contrast ORP/bg `#ff0000` on `#000000` | 5.3:1 | 5.25:1 | correct |
| dark text/bg `#e0e0e0` on `#1a1a1a` | 12.8:1 | **13.18:1** | wrong |
| light text/bg `#1a1a1a` on `#f5f5f5` | 12.8:1 | **15.96:1** | wrong by 25% |
| sepia text/bg `#5c4b37` on `#f4ecd8` | 8.2:1 | **7.09:1** | wrong |
| high-contrast text/bg `#ffffff` on `#000000` | 21:1 | 21.00:1 | correct |

Six of eight are wrong, two of them by more than a quarter.
This is the only reader in the corpus that documents its contrast, and the numbers were never checked.
It is also, per §1, an AI-assisted build, which is a reasonable guess at how confident-looking unverified numbers got into a constants file.

### 11.10 Is there any actual study?

**Yes, exactly one, and it found nothing.**

**Kosch, T., Schmidt, A., Thanheiser, S. & Chuang, L.L. (2020). One does not Simply RSVP: Mental Workload to Select Speed Reading Parameters using Electroencephalography. *Proceedings of the 2020 CHI Conference on Human Factors in Computing Systems* (CHI '20), Paper 637, 1-13. doi:10.1145/3313831.3376766**

n = 18, repeated measures, two factors at three levels.
The Text Alignment factor is precisely our question:

> "A centered condition presented words within a bounding box that is centered in the display (see Figure 2a). An ORP condition centered each word around the ORP (see Figure 2b). An **ORP with colored letter condition colored the ORP red in addition** (see Figure 2c). This approach is similar to the algorithm employed by Spritz Inc."

Crossed with Presentation Speed at 200 / 350 / 500 WPM, against a normal-PDF baseline, measuring comprehension (10 questions per condition), NASA-TLX, EEG alpha power, EEG theta power and eye blinks.

> "Interestingly, **Text Alignment did not influence any of our measurements**. Thus, it is clear that Presentation Speed will continue to be a limiting factor. Until this is resolved, spatial factors such as the ideal presentation of text, which includes font readability could be relatively less important and should only be considered after optimizing Presentation Speeds."

No significant main effect of Text Alignment on comprehension, workload, alpha or theta, and no interaction with speed.
Speed drove everything, with large effect sizes.
Corroborated by the same lab's follow-on (Grootjen, J.W., Thalhammer, P. & Kosch, T. (2024). Your Eyes on Speed: Using Pupil Dilation to Adaptively Select Speed-Reading Parameters in Virtual Reality): "Kosch et al. explored the combination of ORP and color and found no significant difference… ORP is not a decisive factor influencing the perceived mental workload."

**So the entire direct evidence base for the coloured ORP letter, in either direction, is one n = 18 null.**
Nobody has ever compared bold, underline, a background chip or a size change against colour or against nothing in an RSVP reader.
Be fair about what a null at n = 18 is worth: the study was powered for speed effects, only the (b) vs (c) contrast isolates colour cleanly, and it sits inside a null main effect.
It is weak evidence of absence, not evidence of absence.

**A citation-laundering warning, because I nearly repeated it.**
A claim circulates that Dingler et al. (2015) compared underlined ORPs against coloured ORPs and found no difference in workload or comprehension but faster subjective adaptation to colour.
**That is not what the paper does.**
The paper is real:

**Dingler, T., Sahami Shirazi, A., Kunze, K. & Schmidt, A. (2015). Assessment of Stimuli for Supporting Speed Reading on Electronic Devices. *Proceedings of the 6th Augmented Human International Conference* (AH '15), 117-124. doi:10.1145/2735711.2735796**

But its independent variable is a kinetic pacer versus RSVP:

> "We designed the study using a between subject measure design with the reading stimuli as the only independent variable. The stimuli comprised two levels: **kinetic and RSVP**."

and the "underline" is a whole-line sweeping pacer over normally laid-out static text, not an ORP treatment:

> "we decided to use the technique of dynamically underlining lines of text as kinetic stimulus… this dynamic line placed under a line of text that moves from left to right in a predetermined speed"

There is no underlined-ORP condition anywhere in it.
The misdescription originates in **Kosch et al.'s own related-work section**, is repeated near-verbatim by Grootjen et al. (2024), and propagates onward from there.
**There is no published comparison of underlined against coloured ORPs.**
Combined with the survey finding that no shipping reader uses underline as its sole ORP signal, **underline is untried in both the literature and the wild.**

*A side finding from the same paper worth flagging:* Dingler et al. built their RSVP condition on Squirt and describe its marker as blue: "A **blue letter** marks the position where the reader's eye is supposed to focus on." Squirt's own CSS is `rgb(238, 69, 69)`, a red. Either they modified it or the paper misdescribes its own stimulus. Unresolved; §1's value stands.

**The one study that is genuinely on point is not an RSVP study at all, and it is the most important citation in this section.**

**Ducrot, S., Lété, B., Vernet, M., Massendari, D. & Danna, J. (2025). Improving Reading and Eye Movement Control in Readers with Oculomotor and Visuo-Attentional Deficits. *Journal of Eye Movement Research* 18(4): article 25. doi:10.3390/jemr18040025. PMID 40708798, PMC12286046. Open access.**

25 adults plus 24 children, lexical decision on isolated laterally-presented words with eye tracking.
The manipulation is exactly ours, under a different name (the preferred viewing location, the same construct Spritz calls the ORP):

> "All stimuli were displayed in light gray <COLOR 216 216 216>. The PVL saliency was manipulated by presenting either a **colored <COLOR 0 255 0>, brighter <COLOR 255 255 255>, or a neutral <216 216 216>** letter at the PVL."

Courier New 22pt on black, each character subtending about 0.38 degrees.
So: three conditions, green versus white versus grey, on the PVL letter only.

The abstract's result:

> "this manipulation had **no effect on initial landing positions in proficient readers**, who already landed most frequently at the PVL, suggesting that PVL saliency is irrelevant once automatized saccade targeting routines are established. In contrast, the manipulation shifted the peak of the landing site distribution toward the PVL for a cluster of readers with immature saccadic strategies… **but only in the brightness condition**, and had a more compelling effect in a cluster with oculomotor instability."

Three clusters, derived post hoc from landing behaviour:

- **Cluster 1, proficient readers.** Already landing on the PVL, so neither manipulation moved anything. And colour cost them: "for Cluster 1, the presence of a colored PVL **increased error rates (6.1%)**", with the authors' own reading: "We speculate that a colored letter may **interfere with whole-word orthographic processing**."
- **Cluster 2, immature saccadic strategies.** "there was a significant effect of brightness on the location of ILPs", against "ILP frequency at P1 and P2 **did not differ between the color and neutral conditions**."
- **Cluster 3, oculomotor instability.** Both helped: "both brightness and color led to fewer fixations."

Across conditions, brightness beat colour by 74 ms:

> "reaction times were significantly shorter when the PVL was brighter (M = 1021 ms) than when it was colored (M = 1095 ms, p = 0.004)"

And the authors pre-empt the obvious objection themselves:

> "the contrast ratio between the color condition … equals 1.18 … the brightness condition … equals 1.16. **The contrast ratio is almost identical between the two conditions, which does not explain their differentiated effects.**"

The last detail is the one that should change how the highlight is designed:

> "**almost all participants reported being unaware of the presence of the brightness condition, whereas all participants detected the color condition.** It is possible that the color requires additional irrelevant visual processing and may have disrupted the perception of the overall structure of the word."

**Contrast-matched, and brightness worked while colour did not.
The brightness cue was invisible to the reader and still moved their eyes.
The colour cue was noticed by every single participant and moved nothing, while costing skilled readers 6.1% in errors.**

Two provenance notes, in the interest of not overclaiming.
The 74 ms figure and the 6.1% error figure were read from the Europe PMC full text (`PMC12286046`, `fullTextXML`); MDPI's own page and PMC's HTML both block automated retrieval, and a second reader who could only reach the abstract could not confirm them.
The abstract string renders the child group as "24 s graders", a mangled token that is most likely "second graders" but which I could not resolve. It does not bear on the adult result.
And note the task is lexical decision on isolated words, not RSVP, so the transfer is an inference rather than a measurement.

**One calibration number worth having.**
Ducrot's brightness step was `#FFFFFF` against `#D8D8D8` neighbours.
By the WCAG formula that is a **1.43:1** pivot-to-neighbour ratio, and by simple luminance ratio 1.46.
(Their own "1.16" appears to use a different formula or measured display luminances; the discrepancy is unresolved, so treat 1.43:1 as the WCAG-equivalent figure.)
**The effective luminance step is small.**
You do not need a dramatic brightness difference to move a landing position, which is good news for a design that also has to stay readable.

**Everything adjacent runs the same way.**

- **Within-word colour costs about 33 ms per word.** Pre-registered lexical decision, 192 participants, five within-word segmentation techniques including colour: "even with a moderate amount of training, these visual interventions **always slow down word identification**, but each to a different extent (between **32.7ms - color technique** - and 70.7ms - connection technique)." Termuende, M., Larson, K. & Nacenta, M. (2026). The Impact of Visual Segmentation on Lexical Word Recognition. *IEEE TVCG* 32(1): 857-867. doi:10.1109/TVCG.2025.3634641. Colour was the *least* costly of the five and still cost 32.7 ms. At 500 WPM the whole per-word budget is 120 ms.
- **More within-word salience, worse reading.** Five conditions, L2 eye tracking: "the Bold to Gray and Gray to Bold conditions, both involving stronger within-word visual salience, **reduced reading efficiency without improving comprehension accuracy**… stronger within-word visual salience may instead interfere with reading efficiency." Zhang, Z., Zhao, H. & Wang, Y. (2026). Bionic Reading in L2 academic contexts: an eye-tracking study. *Acta Psychologica* 270: 107723. doi:10.1016/j.actpsy.2026.107723
- **Colouring one letter measurably changes how the word is processed.** "simply **coloring a single letter** instead of the whole word **eliminated the Stroop effect**." Besner, D., Stolz, J.A. & Boutilier, C. (1997). The Stroop effect and the myth of automaticity. *Psychonomic Bulletin & Review* 4(2): 221-225. doi:10.3758/BF03209396. Replicated by Manwell, L.A., Roberts, M.A. & Besner, D. (2004). *Psychon Bull Rev* 11(3): 458-462. doi:10.3758/BF03196595. Disputed on mechanism, not on cost, by Marmurek, H.H.C. (2003). *J Gen Psychol* 130(2): 207-224, and Monahan, J.S. (2001). *J Gen Psychol* 128(1): 98-112.
- **Bionic Reading, the nearest shipped analogue, has now failed four independent tests.** "no significant difference in reading times between Bionic and normal reading. I conclude that Bionic Reading does not facilitate reading" (Snell, J. (2024). No, Bionic Reading does not work. *Acta Psychologica* 247: 104304. doi:10.1016/j.actpsy.2024.104304). "Bionic Reading's claims were not supported by this study… and, in fact, **led to costs relative to regular unbolded reading**" (Spear, A.I., Johnson, R.L., Yun, H., Ashby, J. & Kleinsmith, A.L. (2025). To boldly go where no text has gone before: the effects of boldface letters on eye movements in reading. *Attention, Perception & Psychophysics* 87(4): 1270-1286. doi:10.3758/s13414-025-03067-w). Also Beelders, T.R. (2025). *J Eye Mov Res* 18(5): 49. doi:10.3390/jemr18050049, whose finding kills the mechanism outright: "fixations were spread throughout the word and not only on leading characters, even when using Bionic font; hence, participants were **not able to 'auto-complete' the words**." And Možina, K., Kovačević, D. & Blaznik, B. (2025). *SAGE Open* 15(4). doi:10.1177/21582440251376158.

**This last group is a warning against over-reading the recommendation below.**
"Use luminance, not hue" does **not** license Bionic-style per-word bolding.
That exact manipulation has been tested four times and failed, twice with a measured cost.
Ducrot's result supports a luminance step on a *single* letter, which is a different manipulation from re-weighting half of every word, and the two should not be conflated.

**How strong is all this?**
It is a converging-evidence argument, not a proof, and the honest statement of it is:

> There is no evidence that colouring the ORP letter helps.
> There is one direct null test, at n = 18.
> There is a consistent body of adjacent work showing that within-word visual heterogeneity costs somewhere between nothing and about 30 ms per word.
> One study that manipulated exactly this letter found that brightness moved the eyes where colour did not, at matched contrast.
> The burden of proof sits with the highlight, not against it.

Each individual link is contestable, and the doc is stronger for saying so.
Termuende coloured letter *groups*, not one letter.
The Stroop work was designed to disrupt word reading and does not measure reading speed.
Case mixing changes glyph *shape*, which colour does not, so the case-mixing cost is an upper bound on what to expect from colour rather than an estimate of it.
Ducrot's task is lexical decision on isolated words, not continuous RSVP.
And Kosch's null is underpowered.
It is the agreement across four unrelated methods that carries the weight, not any one of them.

### 11.11 Recommendation

**The single most useful thing in this section is a sign error.**

Every implementation in §11.8, ours included, gives the pivot letter *less* contrast against the page than its neighbours have.
Ducrot's working condition did the opposite: the PVL letter was `#FFFFFF` while its neighbours were `#D8D8D8`, an **increment** of 1.43:1 by the WCAG formula.
Her colour condition, `#00FF00` against the same `#D8D8D8`, was a step of 1.04:1, effectively no luminance step at all, and it moved nothing.

So the rule is one line:

> **The pivot letter must be the letter with the MOST contrast against the page, not the least. On a light theme that means darker than its neighbours. On a dark theme it means brighter.**

Our dark blue `#73b5ee` is currently a luminance *decrement* against `#e4e4ea`.
Our light red `#CC0001` is currently a contrast *decrement* against `#202832`.
Both have the sign backwards, and the fix costs almost nothing.

**The second useful thing: the step needed is small.**
Ducrot moved landing positions with 1.43:1, and her participants did not consciously notice the brightness cue at all.
You do not need a dramatic difference.
That matters, because the only way to build a luminance increment on a light background is to dim the non-pivot letters (black is the floor), and a big dim would look washed out.
A small one does not.

**And a third: hue is not forbidden, it is just not load-bearing.**
Legge et al. (1990) is explicit that when both contrasts are present there is no additive interaction and performance follows whichever channel is better.
Hue laid on top of an adequate luminance step buys nothing measurable, and at this glyph size it costs nothing either (Legge & Rubin 1986).
So the user's preference for blue is not an error to be corrected.
It is a free parameter, and it should be spent on whatever is nicest to look at, once the luminance step is doing the actual work.

Which also explains the preference itself.
The current dark blue is ΔE00 24.0 from its neighbours where the light red is 40.8, so the blue is a little over half the perceptual shout.
Red is more salient than the task needs, and it is an alarm colour.
"More refreshing to see" is a report about *intensity*, not about hue, and the right response is not to make the cue louder but to move it into the channel where a quiet cue still works.

#### Recommended values

Against the current palette (`--bg:#FBFBF9` / `--ink:#202832` light, `--bg:#131319` / `--ink:#e4e4ea` dark, `mdview.py` lines 219-227).
The non-pivot letters of the word being displayed get their own token rather than inheriting `--ink`.

**Light theme**

| Role | Value | vs page | |
|---|---|---|---|
| page | `#FBFBF9` | | |
| word, non-pivot letters | `#3F4A5A` | 8.67:1 | dimmed one step from `--ink` |
| **pivot letter** | **`#4A0A10`** | **15.10:1** | AA at any size |

Pivot versus neighbours: **1.74:1**, an increment, above Ducrot's working 1.43:1.
ΔE00 30.0, of which 27.8% is lightness.
`#4A0A10` is a very deep maroon, so it keeps the Spritz lineage visually while carrying its cue on the luminance channel.

**Dark theme**

| Role | Value | vs page | |
|---|---|---|---|
| page | `#131319` | | |
| word, non-pivot letters | `#B4B4C0` | 9.01:1 | dimmed one step from `--ink` |
| **pivot letter** | **`#CFE3F8`** | **14.10:1** | AA at any size |

Pivot versus neighbours: **1.56:1**, an increment.
ΔE00 13.4, 62.5% lightness.
`#CFE3F8` is the user's `#73b5ee` moved up the lightness axis until it sits *above* its neighbours instead of below them.
The hue is preserved. Only the sign is fixed.

**Stronger variants**, if the gentle step reads as too subtle in use:

| | neighbours | pivot | pivot/page | pivot/neighbours |
|---|---|---|---|---|
| light | `#4A5666` (7.20:1) | `#3B0A0A` | 16.43:1 | 2.28:1 |
| dark | `#9A9AA8` (6.66:1) | `#BBD7F5` | 12.47:1 | 1.87:1 |
| dark, amber | `#9A9AA8` (6.66:1) | `#FFD08A` | 12.90:1 | 1.94:1 |

**Do not go past those.**
Dimming the neighbours below about 6.5:1 starts to cost word legibility for the sake of a cue that is redundant with the fixed pivot column anyway.

#### The CVD fallback is automatic, and that is the point

Running the Viénot/Brettel/Mollon simulation over the recommended pairs:

| | normal | protan | deutan | tritan |
|---|---|---|---|---|
| light, pivot vs neighbours | 1.74:1 | 1.99:1 | 1.64:1 | 1.41:1 |
| light, pivot vs page | 15.10:1 | 16.89:1 | 14.31:1 | 12.21:1 |
| dark, pivot vs neighbours | 1.56:1 | 1.60:1 | 1.54:1 | 1.50:1 |
| dark, pivot vs page | 14.10:1 | 14.39:1 | 13.90:1 | 13.50:1 |

**The cue barely moves under any form of colour vision deficiency**, because a luminance step is not a colour signal.
Compare the current light red, whose pivot-versus-neighbour contrast collapses from 2.53:1 to **1.60:1** for a protanope.
No separate CVD fallback is needed.
There is nothing to fall back *from*.

That is the strongest practical argument for the whole change, independent of the reading science: moving the cue onto the luminance channel makes it correct for the ~8% of men with red-green CVD and the ~0.2% with tritan defects, in the same stroke, without a second code path.

And SC 1.4.1 stops being a question you have to reason about.
It is currently satisfied only because the fixed 30% pivot column happens to carry the position non-chromatically.
With a luminance step it is satisfied twice over, by the alignment *and* by a non-colour visual difference, which is exactly what the Understanding document asks for: colours that "differ not only in their hue, but that also have a significant difference in lightness".

#### Should the user get a choice?

**Yes, but a small one, and not this one.**

The reader already persists preferences in `localStorage` under `bp.wpm`, `bp.srmode` and `bp.srdock` (`mdview.py` lines 2994-2997, 3258, 3271), so a fourth key costs nothing structurally.

But a colour picker is the wrong control, and Sprint Reader is the cautionary example: it ships a full colour-picker widget for `highlightOptimalLetterColour`, which hands users a decision that §11.10 says nobody has the evidence to make, and whose default (`#FF8C00`) it then applies identically to a white page and a black one.

Offer **three named options on one key**, `bp.srorp`:

| Option | Light | Dark | |
|---|---|---|---|
| **Standard** (default) | `#4A0A10` on `#3F4A5A` | `#CFE3F8` on `#B4B4C0` | luminance step, hue retained |
| **Strong** | `#3B0A0A` on `#4A5666` | `#BBD7F5` on `#9A9AA8` | for anyone who finds Standard too quiet |
| **Off** | `--ink`, no dim | `--ink`, no dim | the whole word at one value |

**"Off" is not a joke option and it should be a real one.**
Six readers in the survey ship with no pivot treatment at all, two of them (tspreed and `c3c3l14/speedreader`) having implemented it and then chosen off as the default.
The direct study found the highlight changed nothing measurable.
Gaspelin's suppression result predicts that a cue present on every word and never task-relevant is exactly what a reader learns to inhibit, which would make it worse than neutral over a long session.
And the fixed pivot column already does the positional work on its own.
Someone who reads a lot with this thing may well end up preferring nothing, and there is no evidence to tell them they are wrong.

**Do not offer**: a free colour picker, a red-on-dark option, a blue-on-light option, or a bold option.
The first hands over an unmakeable decision.
The second and third fail SC 1.4.3 at any size (2.96:1 and 2.12:1 respectively).
The fourth invites the Bionic Reading comparison, which has failed four independent tests, and weight interacts badly with the existing 640 font-weight and with the zero-width pivot-cell layout that §5 uses to kill the jitter.

#### What I would not change

The **pivot column at 30%** stays exactly as it is.
It is the cue that is actually carrying the information, it is achromatic, it is what satisfies SC 1.4.1 today, and it is the one part of the Spritz design with real support behind it (O'Regan et al. 1984; Vitu et al. 1990).

The **reticle ticks** stay too, in `--line`.
They are a second achromatic position cue and they cost nothing.

And the honest caveat to sit alongside all of the above: **none of this will make anyone read faster.**
Kosch et al. found alignment and colour changed nothing while speed changed everything.
Benedetto et al. found Spritz impaired literal comprehension and increased visual fatigue relative to normal reading, with the ORP red letter present but never manipulated (Benedetto, S., Carbone, A., Pedrotti, M., Le Fevre, K., Yahia Bey, L.A. & Baccino, T. (2015). Rapid serial visual presentation in reading: the case of Spritz. *Computers in Human Behavior* 45: 352-358. doi:10.1016/j.chb.2014.12.043 - note 352-358, not the 60-67 that circulates).
The case for the change in §11.11 is that it is **correct rather than backwards**, that it is **robust to colour vision deficiency for free**, and that it **stops the pivot being the least legible letter in the word**.
It is not a performance claim, and §9 already records why performance claims in this area should be treated with suspicion.

### 11.12 Corrections to earlier sections

Three things this research turned up that amend what §1 says.

1. **tspreed does not offer bold *instead of* colour.** Its shipped `default.rc` sets `focusbold=true` and `focuscolor=1` together, and the render path applies both. When `-f` is on, tspreed's pivot is bold *and* red. It is the only reader in the original corpus that stacks two channels, which by accident is the only one that gets the evidence right.
2. **quickreader's documented contrast ratios are mostly wrong.** Six of the eight numbers in `src/lib/constants.ts` lines 17-25 do not match the values they describe, two of them by more than 25%. §1 cites those figures approvingly; they should be cited as *claimed*, with the recomputed values in §11.9.
3. **Two implementations belong in §1's colour table.** `rollecode/speed-reader`: `.orp-char { color:#ff6b6b; filter: drop-shadow(0 0 20px rgba(220,38,38,.6)); }` on `#0a0a0a`, the only glow in the corpus. `rajeshsatpathy1/SpeedReader`: `.word-highlight { color: var(--highlight-color); font-weight: bold; }`, `#e74c3c` in light, dark and matrix themes and `#d35400` in sepia, the only web reader that adds weight.

### 11.13 What could not be verified

Stated plainly, so nobody re-treads it.

- **Spritz's `#CC0001` has no public primary source.** The value in §1 comes from reading their shipped `spritz.min.js`; `sdk.spritzinc.com` now returns 403 to automated retrieval. The value is almost certainly right, but it cannot be re-derived from a live URL today.
- **Williams, MacLeod & Hayhoe (1981) "Foveal tritanopia"** has no abstract indexed in MEDLINE or Europe PMC and Elsevier blocks retrieval. Cited as existing; the foveal S-cone numbers here come from Curcio et al. (1991) instead, which is properly indexed.
- **Ducrot et al.'s 74 ms and 6.1% figures** were read from the Europe PMC full text. MDPI and PMC HTML both block automated access, and a second reader who could only reach the abstract could not confirm them. The abstract-level pattern (brightness works, colour does not, neither helps proficient readers) is solid.
- **The Sharpe et al. (1999) CVD prevalence table** is quoted from the widely reproduced figures; cvrl.org was unreachable.
- **Campbell & Green (1965)** is the standard source for the ~50-60 c/deg luminance acuity limit, but PMC holds scanned page images only and Wiley blocks retrieval. Treat that number as textbook fact rather than verbatim-sourced here.
- **Squirt's marker colour** is `rgb(238, 69, 69)` in its own CSS, but Dingler et al. (2015) describe their Squirt-based stimulus as blue. Unresolved.
- **"McConkie & Zola shading" does not exist.** If that citation turns up in any source on this topic, it is spurious; their classic manipulations were alternating case and cross-saccade letter substitution.
- **"Wallace, Yang & Bhattacharya"** matches no paper. The findings usually attached to it (comprehension stable to ~350 WPM) do appear in the RSVP literature, but not under those names.
- **No Nielsen Norman Group evaluation of Bionic Reading exists** that I could find. Anyone citing one should be asked for the URL.
