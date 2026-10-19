// Streaming mode: `browserpreview.sh live` serves the page, so every comment lands on
// disk as it is posted - <doc>.notes.md (doc + ## Notes, what an agent reads) and
// <doc>.notes.jsonl (append-only events) next to the doc - and `browserpreview.sh listen`
// prints each new one as a single line. Also: a page that lost its localStorage (new
// port = new origin) gets its notes back from the server.
// Run: node scripts/test_notes_stream.mjs   (needs jsdom: run `npm i jsdom` in the directory you run this from)
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import { mkdtempSync, writeFileSync, readFileSync, existsSync, realpathSync } from 'node:fs';
import { tmpdir, homedir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(join(process.cwd(), '/'));
const { JSDOM, VirtualConsole } = require('jsdom');
if (!process.env.BP_LIVE_SERVER) { console.log('skip - notes stream: set BP_LIVE_SERVER to the optional live server'); process.exit(0); }
const sleep = ms => new Promise(r => setTimeout(r, ms));
const until = async (fn, what, ms = 6000) => {
  for (const t = Date.now(); Date.now() - t < ms; await sleep(50)) { const v = fn(); if (v) return v; }
  throw new Error('timed out waiting for ' + what);
};

const tmp = realpathSync(mkdtempSync(join(tmpdir(), 'bp-stream-')));
const doc = join(tmp, 'review.md');
writeFileSync(doc, '# Review\n\nThe fox jumps over the lazy dog.\n\nShip the billing page on Friday.\n');
const notesMd = join(tmp, 'review.notes.md'), notesLog = join(tmp, 'review.notes.jsonl');
const procs = [];
process.on('exit', () => procs.forEach(p => { try { p.kill(); } catch {} }));

const bp = join(here, 'browserpreview.sh');
const srv = spawn('bash', [bp, 'live', doc, '--no-open', '--port', '0'], { stdio: ['ignore', 'pipe', 'pipe'] });
procs.push(srv);
let srvOut = ''; srv.stdout.on('data', d => srvOut += d); srv.stderr.on('data', d => srvOut += d);
const portFile = join(tmp, '.pdplus', 'port');
await until(() => existsSync(portFile) && readFileSync(portFile, 'utf8').trim(), 'server port file');
const { port, token } = JSON.parse(readFileSync(portFile, 'utf8'));
const base = `http://127.0.0.1:${port}`;

const FAKE = `window.marked = {
  lexer(src){ const out = []; const re = /([^\\n][\\s\\S]*?)(\\n\\n+|\\n?$)/g; let m;
    while((m = re.exec(src)) && m[0]) out.push({ type:'paragraph', raw:m[0], text:m[1] }); return out; },
  parse(src){ return this.lexer(src).map(t => '<p>' + t.text + '</p>').join(''); },
  Renderer: function(){ this.code = () => ''; }, setOptions(){} };
window.mermaid = { initialize(){}, run: async () => {} }; window.hljs = { highlightElement(){} };`;
async function load() {
  const html = await (await fetch(base + '/')).text();
  const vc = new VirtualConsole();
  vc.on('jsdomError', e => { if (!/Not implemented|navigation/i.test(e.message)) console.error('page error:', e.message); });
  const dom = new JSDOM(html.replace(/<script src=[^>]*><\/script>/g, ''), {
    url: `${base}/?k=${token}`, runScripts: 'dangerously', pretendToBeVisual: true, virtualConsole: vc,
    beforeParse(w) {
      w.matchMedia = () => ({ matches: false, addEventListener(){}, addListener(){} });
      w.ResizeObserver = class { observe(){} disconnect(){} };
      w.fetch = (u, o) => fetch(new URL(u, `${base}/`), o);
      w.navigator.sendBeacon = () => true;
      w.eval(FAKE);
    },
  });
  await sleep(300);
  return dom.window;
}
function comment(w, text, note) {
  const block = Array.from(w.document.querySelectorAll('#doc .mline')).find(b => b.textContent.includes(text));
  const node = w.eval('textNodesOf')(block)[0], at = node.nodeValue.indexOf(text);
  const r = w.document.createRange(); r.setStart(node, at); r.setEnd(node, at + text.length);
  const sf = w.eval('SURFACES[0]'), line = Number(block.dataset.mlineStart);
  w.eval('openDraft')(sf.key, line, line, text, w.eval('rangeSpans')(r, sf));
  const card = w.document.querySelector('.rail-card.draft');
  card.querySelector('textarea').value = note;
  card.querySelector('.cb-save').click();
}

// listener first, so it sees the comments as they arrive (Monitor-style: one line each)
const listen = spawn('bash', [bp, 'listen', doc], { stdio: ['ignore', 'pipe', 'pipe'] });
procs.push(listen);
let heard = ''; listen.stdout.on('data', d => heard += d); listen.stderr.on('data', d => heard += d);
await sleep(400);

let w = await load();
comment(w, 'lazy dog', 'too cute');
await until(() => existsSync(notesMd) && readFileSync(notesMd, 'utf8').includes('too cute'), 'notes.md on disk');
const md = readFileSync(notesMd, 'utf8');
assert.match(md, /^# Review[\s\S]*\n## Notes\n\nL3 "lazy dog"\n  > too cute/, 'notes.md = doc + ## Notes');
const ev = readFileSync(notesLog, 'utf8').trim().split('\n').map(JSON.parse);
assert.equal(ev.length, 1);
assert.equal(ev[0].type, 'comment'); assert.equal(ev[0].text, 'too cute'); assert.equal(ev[0].quote, 'lazy dog');
await until(() => heard.includes('too cute'), `listen line (got: ${JSON.stringify(heard)})`);
assert.match(heard, /^comment L3 "lazy dog" > too cute$/m, 'listen prints one line per comment');

// a reply streams too, appended - the log is never rewritten
const card = Array.from(w.document.querySelectorAll('#rail .rail-card')).find(c => c.textContent.includes('too cute'));
card.querySelector('textarea').value = 'make it plainer';
card.querySelector('.cb-save').click();
await until(() => heard.includes('make it plainer'), 'reply line');
assert.match(heard, /^reply L3 "lazy dog" > make it plainer$/m);
assert.equal(readFileSync(notesLog, 'utf8').trim().split('\n').length, 2, 'event log appended');

// new origin (empty localStorage): the server snapshot restores the notes
w = await load();
await until(() => w.eval('allThreads().length') === 1, 'restore from server snapshot');
assert.equal(w.eval('allThreads()[0].comments.length'), 2);
assert.equal(w.document.querySelectorAll('#doc .mhl').length, 1, 'highlight re-anchored');

console.log('ok - stream: notes.md + jsonl on disk as you comment, listen prints each, server restore');
process.exit(0);
