// Toggles: raw <details><summary> blocks in the markdown render as collapsible toggles.
// Renders a real page with mdview.py, runs its script in jsdom, and checks that line tags
// still line up with the source inside and after a toggle (the comment rail depends on
// it), that each toggle's body is wrapped for its left rule, that a mermaid diagram in a
// closed toggle renders only when the toggle opens, and that the header button opens and
// closes every toggle.
// Run: node scripts/test_toggles.mjs   (needs jsdom: run `npm i jsdom` in the directory you run this from)
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

const MD = [
  'Intro line.',                         // 1
  '',
  '<details><summary>The claim</summary>', // 3
  '',
  'Inside one.',                         // 5
  '',
  '```mermaid',                          // 7
  'graph TD',
  '  A --> B',
  '```',
  '',
  '<details><summary>Nested</summary>',  // 12
  '',
  'Inside two.',                         // 14
  '',
  '</details>',                          // 16
  '',
  '</details>',                          // 18
  '',
  'After the toggle.',                   // 20
  '',
].join('\n');

const tmp = mkdtempSync(join(tmpdir(), 'bp-toggles-'));
const mdPath = join(tmp, 'plan.md');
writeFileSync(mdPath, MD);
const out = join(tmp, 'plan.preview.html');
execFileSync('python3', [join(here, 'mdview.py'), mdPath, '--no-open', '-o', out]);
const html = readFileSync(out, 'utf8');

// Stand-in for marked (CDN, not loadable here): one token per blank-line block, an HTML
// block when it starts with "<", a mermaid fence as <pre class="mermaid">. parse() joins
// the pieces as one string, so the browser nests blocks inside <details> exactly as it
// does with the real marked.
const FAKE = `window.marked = {
  lexer(src){ const out = []; const re = /([^\\n][\\s\\S]*?)(\\n\\n+|\\n?$)/g; let m;
    while((m = re.exec(src)) && m[0]){ const t = m[1];
      out.push({ type: t.startsWith('<') ? 'html' : (t.startsWith('\\u0060\\u0060\\u0060') ? 'code' : 'paragraph'), raw:m[0], text:t }); }
    return out; },
  parse(src){ return this.lexer(src).map(t => t.type === 'html' ? t.text
    : t.type === 'code' ? '<pre class="mermaid">' + t.text.split('\\n').slice(1, -1).join('\\n') + '</pre>'
    : '<p>' + t.text + '</p>').join('\\n'); } };
window.marked.Renderer = function(){ this.code = () => ''; }; window.marked.setOptions = () => {};
window.__ran = [];
window.mermaid = { initialize(){}, run: async ({ nodes }) => { Array.from(nodes).forEach(n => { n.setAttribute('data-processed', 'true'); window.__ran.push(n.textContent.trim().split('\\n')[0]); }); } };
window.hljs = { highlightElement(){} };`;

const vc = new VirtualConsole();
vc.on('jsdomError', e => { if (!/Not implemented|navigation/i.test(e.message)) console.error('page error:', e.message); });
const dom = new JSDOM(html.replace(/<script src=[^>]*><\/script>/g, ''), {
  url: 'http://localhost/plan.preview.html', runScripts: 'dangerously', pretendToBeVisual: true, virtualConsole: vc,
  beforeParse(w) {
    w.matchMedia = () => ({ matches: false, addEventListener(){}, addListener(){} });
    w.ResizeObserver = class { observe(){} disconnect(){} };
    w.eval(FAKE);
  },
});
const w = dom.window;
await new Promise(r => setTimeout(r, 80));
const doc = w.document.getElementById('doc');
const lineOf = text => {
  const el = Array.from(doc.querySelectorAll('.mline')).find(e => e.textContent.trim().startsWith(text));
  return el ? Number(el.dataset.mlineStart) : null;
};

// line tags line up inside, nested inside, and after the toggle
assert.equal(lineOf('Intro line.'), 1, 'paragraph before the toggle');
assert.equal(lineOf('The claim'), 3, 'summary carries the opening tag line');
assert.equal(lineOf('Inside one.'), 5, 'paragraph inside the toggle');
assert.equal(lineOf('Nested'), 12, 'nested summary');
assert.equal(lineOf('Inside two.'), 14, 'paragraph inside the nested toggle');
assert.equal(lineOf('After the toggle.'), 20, 'paragraph after the toggle keeps its line');

// each toggle body is wrapped once, for the left rule
const outer = doc.querySelector('details');
assert.ok(outer.querySelector(':scope > .tg-body'), 'outer body wrapped');
assert.equal(outer.querySelectorAll(':scope > .tg-body').length, 1, 'wrapped once');
assert.ok(outer.querySelector('details > .tg-body'), 'nested body wrapped');

// mermaid in a closed toggle waits for the toggle to open
assert.equal(JSON.stringify(Array.from(w.__ran)), '[]', 'no diagram rendered while its toggle is closed');
outer.open = true;
outer.dispatchEvent(new w.Event('toggle'));
await new Promise(r => setTimeout(r, 30));
assert.equal(JSON.stringify(Array.from(w.__ran)), '["graph TD"]', 'diagram rendered when its toggle opened');

// the header button appears and opens/closes every toggle
const btn = w.document.getElementById('toggleAllBtn');
assert.equal(btn.hidden, false, 'button shown when the doc has toggles');
btn.click();
assert.ok(Array.from(doc.querySelectorAll('details')).every(d => d.open), 'all open');
btn.click();
assert.ok(Array.from(doc.querySelectorAll('details')).every(d => !d.open), 'all closed');

console.log('ok - toggles: line tags, wrapped bodies, deferred mermaid, open/close all');
