// Checks the speed reader's pure functions against the published tables in
// references/rsvp-research.md. Run: node scripts/test_speedread.mjs
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, 'mdview.py'), 'utf8');
const grab = name => {
  const i = src.indexOf(`function ${name}(`);
  assert.ok(i > 0, `${name} not found in mdview.py`);
  let d = 0, j = src.indexOf('{', i);
  for (let k = j; k < src.length; k++) {
    if (src[k] === '{') d++;
    else if (src[k] === '}' && --d === 0) return src.slice(i, k + 1);
  }
  throw new Error(`unbalanced ${name}`);
};

const consts = ['SR_ABBREV', 'SR_NUMERIC', 'SR_SENT_PUNCT', 'SR_END_SENT', 'SR_END_CLAUSE', 'SR_STRIP']
  .map(n => {
    const m = src.match(new RegExp(`^\\s*const ${n} = .*$`, 'm'));
    assert.ok(m, `${n} not found in mdview.py`);
    return m[0].trim();
  }).join('\n');

const fn = new Function('SR',
  `${consts}
   ${grab('srBare')} ${grab('srLenMul')} ${grab('srSentPause')} ${grab('srPivot')}
   ${grab('srSplitWord')} ${grab('srDelay')}
   return { srPivot, srSplitWord, srDelay, srLenMul, srSentPause, srBare, SR_END_SENT };`)({ wpm: 600 });

// 1. ORP table - US 8,903,174 B2 TABLE I / FIG. 7, and the rule every clone copied:
//    1 -> 0, 2-5 -> 1, 6-9 -> 2, 10-13 -> 3, 14+ -> 4
const orp = { a:0, at:1, the:1, word:1, reads:1, spline:2, reader:2, weather:2, sentence:2,
              wandering:2, everything:3, exceptional:3, hyphenation:3, extravagance:3,
              internationalized:4, incomprehensible:4 };
for (const [w, i] of Object.entries(orp)) assert.equal(fn.srPivot(w), i, `pivot ${w}`);

// the patent excludes punctuation from the character count, for the ORP and the multiplier
assert.equal(fn.srPivot('word,'), fn.srPivot('word'), 'comma must not move the pivot');
assert.equal(fn.srPivot('sentence.'), fn.srPivot('sentence'), 'period must not move the pivot');
assert.equal(fn.srBare('("sentence.")'), 'sentence', 'strip both ends');
// and the index can never fall off the end of the token
for (const w of ['I', 'a.', '...', '-', 'x,']) assert.ok(fn.srPivot(w) < w.length, `in range: ${w}`);

// 2. long words: >13, or >9 with a hyphen; hyphen first, else ceil(len/8) parts
assert.deepEqual(fn.srSplitWord('reader'), ['reader']);
assert.deepEqual(fn.srSplitWord('exceptional'), ['exceptional'], '11 chars, no hyphen: whole');
assert.deepEqual(fn.srSplitWord('co-founder'), ['co', 'founder'], '10 with a hyphen: split');
assert.equal(fn.srSplitWord('internationalization').join(''), 'internationalization', 'lossless');
assert.equal(fn.srSplitWord('internationalization').length, 3, 'ceil(20/8) = 3 parts');
for (const w of ['antidisestablishmentarianism', 'well-intentioned-approach'])
  assert.equal(fn.srSplitWord(w).join('').replace(/-/g, ''), w.replace(/-/g, ''), `lossless: ${w}`);

// 3. word time is LENGTH ONLY - patent FIG. 5a: 1-7 = 1x, 8-13 = 1.3x, >13 = 1.6x
const base = 60000 / 600;
assert.equal(fn.srLenMul('the'), 1);
assert.equal(fn.srLenMul('reader'), 1, '6 chars still 1x - Spritz has no short-word ramp');
assert.equal(fn.srLenMul('sentence'), 1.3, '8 chars -> 1.3');
assert.equal(fn.srLenMul('extravagance'), 1.3, '12 chars -> 1.3');
assert.equal(fn.srLenMul('internationalized'), 1.6, '>13 -> 1.6');
assert.equal(fn.srLenMul('sentence.'), fn.srLenMul('sentence'), 'punctuation is not a character');
assert.equal(fn.srDelay({ t:'w', w:'reader' }), base);
assert.equal(fn.srDelay({ t:'w', w:'however,', clause:true }), base * 1.5, 'clause holds the word');
assert.ok(fn.srDelay({ t:'w', w:'a' }) >= 55, 'never faster than the 55ms floor');

// abbreviations, decimals and list markers are not sentence ends
for (const w of ['end.', 'really!', 'why?', '(done.)']) assert.ok(fn.SR_END_SENT.test(w), `sentence end: ${w}`);
for (const w of ['Mr.', 'Dr.', 'etc.', 'e.g.', 'i.e.', '3.14', '12.', '1.'])
  assert.ok(!fn.SR_END_SENT.test(w), `NOT a sentence end: ${w}`);

// 4. the sentence-end pause scales with the sentence just ended - patent FIG. 5b
assert.equal(fn.srSentPause(5), 1.1);
assert.equal(fn.srSentPause(11), 1.1);
assert.equal(fn.srSentPause(12), 2.2, '12 is the first threshold');
assert.equal(fn.srSentPause(22), 2.2);
assert.equal(fn.srSentPause(23), 3.3, 'over 22 words');
assert.equal(fn.srDelay({ t:'b', mult: fn.srSentPause(30) }), base * 3.3);
assert.equal(fn.srDelay({ t:'b' }), base * 2.8, 'a blank with no multiplier is a paragraph beat');

console.log('speed reader: all checks passed');
