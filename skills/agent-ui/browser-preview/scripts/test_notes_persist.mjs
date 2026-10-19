// Margin comments survive a reload: render a real page with mdview.py, run its own
// script in jsdom, comment through the real UI, then "reload" (a fresh page sharing
// the same localStorage) and check every thread, reply, fold and highlight came back.
// Also: an edited doc re-finds a moved quote, keeps a vanished one as an orphan card,
// and the disk copy (bp-notes-<slug>.json) restores into a wiped browser.
// Run: node scripts/test_notes_persist.mjs   (needs jsdom: run `npm i jsdom` in the directory you run this from)
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, readFileSync } from 'node:fs';
import { tmpdir, homedir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(join(process.cwd(), '/'));
const { JSDOM, VirtualConsole } = require('jsdom');

const tmp = mkdtempSync(join(tmpdir(), 'bp-notes-'));
const mdPath = join(tmp, 'plan.md');
const render = md => {
  writeFileSync(mdPath, md);
  const out = join(tmp, 'plan.preview.html');
  execFileSync('python3', [join(here, 'mdview.py'), mdPath, '--no-open', '-o', out]);
  return readFileSync(out, 'utf8');
};

// Stand-in for marked (CDN, not loadable here): one paragraph per blank-line block,
// with the same lexer/parse shape tagLines() reads, so line tagging is real.
const FAKE_MARKED = `window.marked = {
  lexer(src){ const out = []; const re = /([^\\n][\\s\\S]*?)(\\n\\n+|\\n?$)/g; let m;
    while((m = re.exec(src)) && m[0]) out.push({ type:'paragraph', raw:m[0], text:m[1] }); return out; },
  parse(src){ return this.lexer(src).map(t => '<p>' + t.text.replace(/&/g,'&amp;').replace(/</g,'&lt;') + '</p>').join(''); } };
window.marked.Renderer = function(){ this.code = () => ''; }; window.marked.setOptions = () => {};
window.mermaid = { initialize(){}, run: async () => {} };
window.hljs = { highlightElement(){} };`;

let downloads = [];
async function load(html, storage = {}) {
  const vc = new VirtualConsole();
  vc.on('jsdomError', e => { if (!/Not implemented|navigation/i.test(e.message)) console.error('page error:', e.message, (e.detail && e.detail.stack || '').split('\n').slice(0,3).join(' | ')); });
  const dom = new JSDOM(html.replace(/<script src=[^>]*><\/script>/g, ''), {
    url: 'http://localhost/plan.preview.html', runScripts: 'dangerously', pretendToBeVisual: true, virtualConsole: vc,
    beforeParse(w) {
      for (const [k, v] of Object.entries(storage)) w.localStorage.setItem(k, v);
      w.matchMedia = () => ({ matches: false, addEventListener(){}, addListener(){} });
      w.ResizeObserver = class { observe(){} disconnect(){} };
      w.URL.createObjectURL = b => { w.__lastBlob = b; return 'blob:test'; };
      w.URL.revokeObjectURL = () => {};
      w.HTMLAnchorElement.prototype.click = function () {
        if (this.download) downloads.push({ name: this.download, blob: w.__lastBlob });
      };
      w.document.execCommand = () => true;
      w.eval(FAKE_MARKED);
    },
  });
  const w = dom.window;
  await new Promise(r => setTimeout(r, 60));
  w.copied = [];
  w.eval('copyText = t => { window.copied.push(t); return true; }');
  return w;
}
const dump = w => Object.fromEntries(Object.keys(w.localStorage).map(k => [k, w.localStorage.getItem(k)]));
const threads = w => JSON.parse(w.eval('JSON.stringify(allThreads())'));  // out of jsdom's realm
const blockWith = (w, text) => Array.from(w.document.querySelectorAll('#doc .mline')).find(b => b.textContent.includes(text));

// Select `text` inside its block and post a comment through the real draft card.
function comment(w, text, note) {
  const block = blockWith(w, text);
  assert.ok(block, `block containing "${text}"`);
  const node = w.eval('textNodesOf')(block)[0];
  const at = node.nodeValue.indexOf(text);
  const r = w.document.createRange(); r.setStart(node, at); r.setEnd(node, at + text.length);
  const sf = w.eval('SURFACES[0]');
  const spans = w.eval('rangeSpans')(r, sf);
  const line = Number(block.dataset.mlineStart);
  w.eval('openDraft')(sf.key, line, line, text, spans);
  const card = w.document.querySelector('.rail-card.draft');
  card.querySelector('textarea').value = note;
  card.querySelector('.cb-save').click();
}
const cardFor = (w, quote) => Array.from(w.document.querySelectorAll('#rail .rail-card'))
  .find(c => (c.querySelector('.cb-quote') || {}).textContent === quote);

const DOC1 = '# Plan\n\nThe fox jumps over the lazy dog.\n\nShip the billing page on Friday.\n\nA third paragraph.\n';

// ── 1. comment, reply, fold, then reload ────────────────────────────────────
let w = await load(render(DOC1));
comment(w, 'lazy dog', 'too cute');
comment(w, 'billing page', 'which one?');
let card = cardFor(w, 'billing page');
card.querySelector('textarea').value = 'the v2 one';
card.querySelector('.cb-save').click();
cardFor(w, 'lazy dog').querySelector('.cb-fold').click();
assert.equal(threads(w).length, 2, 'two threads before reload');

const saved = dump(w);
const keys = Object.keys(saved).filter(k => k.startsWith('bp.notes:'));
assert.equal(keys.length, 1, 'one localStorage entry for the doc');
assert.ok(keys[0].endsWith(mdPath), `keyed by the absolute source path: ${keys[0]}`);
assert.match(w.document.getElementById('saveState').textContent, /Saved/, 'header says Saved');
const grp = w.document.getElementById('saveState').parentElement;
assert.ok(grp.classList.contains('savegrp') && grp.contains(w.document.getElementById('restoreBtn')),
  'Saved and Restore are one grouped header control');

w = await load(render(DOC1), saved);
let ts = threads(w);
assert.equal(ts.length, 2, 'both threads restored after reload');
const billing = ts.find(t => t.quote === 'billing page');
assert.deepEqual(billing.comments.map(c => c.text), ['which one?', 'the v2 one'], 'reply restored');
assert.equal(ts.find(t => t.quote === 'lazy dog').collapsed, true, 'fold restored');
const hl = Array.from(w.document.querySelectorAll('#doc .mhl')).map(e => e.textContent).sort();
assert.deepEqual(hl, ['billing page', 'lazy dog'], 'highlights re-anchored on the exact words');
assert.equal(w.document.querySelectorAll('#rail .rail-card').length, 2, 'two cards in the rail');

// new comments after a restore never reuse an id
comment(w, 'third', 'ok');
const ids = threads(w).flatMap(t => [t.id, ...t.comments.map(c => c.id)]);
assert.equal(new Set(ids).size, ids.length, 'ids unique after restore');
// delete is persisted too
cardFor(w, 'third').querySelector('.cb-close').click();
const afterDelete = dump(w);
assert.equal(threads(await load(render(DOC1), afterDelete)).length, 2, 'delete persisted');

// ── 2. copy buttons unchanged ───────────────────────────────────────────────
w = await load(render(DOC1), afterDelete);
w.document.getElementById('copyNotesBtn').click();
assert.equal(w.copied.pop(),
  'L3 "lazy dog"\n  > too cute\nL5 "billing page"\n  > which one?\n  > the v2 one', 'Copy notes (c)');
w.document.getElementById('copyMdNotesBtn').click();
assert.match(w.copied.pop(), /^# Plan[\s\S]*\n---\n\n## Notes\n\nL3 "lazy dog"\n  > too cute\nL5 "billing page"/, 'Copy md + notes (b)');

// ── 3. doc edited: moved quote re-found, vanished quote orphaned (never dropped) ─
const DOC2 = '# Plan\n\nA brand new intro paragraph.\n\nShip the billing page next week.\n\nThe fox naps.\n';
w = await load(render(DOC2), afterDelete);
ts = threads(w);
assert.equal(ts.length, 2, 'no thread dropped after an edit');
assert.deepEqual(Array.from(w.document.querySelectorAll('#doc .mhl')).map(e => e.textContent), ['billing page'],
  'moved quote re-anchored to its new position');
assert.equal(ts.find(t => t.quote === 'billing page').line, 5, 'line follows the text');
const orphan = ts.find(t => t.quote === 'lazy dog');
assert.equal(orphan.orphan, true, 'vanished quote marked orphan');
const rail = Array.from(w.document.querySelectorAll('#rail .rail-card'));
assert.ok(rail[0].classList.contains('orphan'), 'orphan card rendered');
assert.equal(Number(rail[0].dataset.anchor), -1, 'orphan anchored above everything');
w.document.getElementById('copyNotesBtn').click();
assert.match(w.copied.pop(), /"lazy dog"[^\n]*\n  > too cute/, 'orphan still goes out with Copy notes');

// ── 4. disk copy: debounced download, restore into a wiped browser ──────────
downloads = [];
w = await load(render(DOC1));
comment(w, 'lazy dog', 'from disk');
w.dispatchEvent(new w.Event('pagehide'));
await new Promise(r => setTimeout(r, 20));
const dl = downloads.filter(d => /^bp-notes-plan\.json$/.test(d.name));
assert.equal(dl.length, 1, `one disk copy named bp-notes-plan.json (got ${downloads.map(d => d.name)})`);
const mdDl = downloads.filter(d => d.name === 'bp-notes-plan.md');
assert.equal(mdDl.length, 1, `recovery markdown bp-notes-plan.md saved too (got ${downloads.map(d => d.name)})`);
w.document.getElementById('copyMdNotesBtn').click();
assert.equal(await mdDl[0].blob.text(), w.copied.pop(), 'recovery .md is exactly what Copy md + notes gives');
w.dispatchEvent(new w.Event('pagehide'));
assert.equal(downloads.length, 2, 'no more downloads when nothing changed');
const fileText = await dl[0].blob.text();
assert.equal(JSON.parse(fileText).kind, 'bp-notes');

w = await load(render(DOC1));            // fresh browser: empty localStorage
assert.equal(threads(w).length, 0);
await w.eval('notesImport')(fileText);
assert.deepEqual(threads(w).map(t => t.comments[0].text), ['from disk'], 'Restore from file brings the thread back');
assert.equal(w.document.querySelectorAll('#doc .mhl').length, 1, 'and its highlight');
assert.ok(Object.keys(dump(w)).some(k => k.startsWith('bp.notes:')), 'restored notes are autosaved again');

// ── 5. folder mode: keyed <folder>/<relpath>, shared with a single-file render ─
const dir = join(tmp, 'docs'); execFileSync('mkdir', ['-p', join(dir, 'sub')]);
writeFileSync(join(dir, 'sub', 'a.md'), DOC1);
const folderOut = join(tmp, 'docs.preview.html');
execFileSync('python3', [join(here, 'mdview.py'), dir, '--no-open', '-o', folderOut]);
w = await load(readFileSync(folderOut, 'utf8'));
comment(w, 'lazy dog', 'folder note');
const fkeys = Object.keys(dump(w)).filter(k => k.startsWith('bp.notes:'));
assert.equal(fkeys.length, 1);
assert.ok(fkeys[0].endsWith('/docs/sub/a.md'), `folder key is folder + file: ${fkeys[0]}`);
const singleOut = join(tmp, 'a.preview.html');
execFileSync('python3', [join(here, 'mdview.py'), join(dir, 'sub', 'a.md'), '--no-open', '-o', singleOut]);
const w2 = await load(readFileSync(singleOut, 'utf8'), dump(w));
assert.deepEqual(threads(w2).map(t => t.comments[0].text), ['folder note'], 'single-file view of the same file sees it');

console.log('ok - notes persist: reload, reply, fold, delete, copy, re-anchor, orphan, disk restore');
process.exit(0);   // the page's 30s disk timer would otherwise hold node open
