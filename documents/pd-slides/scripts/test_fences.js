// A directive fence must never reach the reader as literal `:::` text, and a fence
// written INSIDE a code block must survive untouched — that is someone documenting
// the syntax, not using it. Runs the page's real expandBlocks against both.
const fs = require('fs');
const page = fs.readFileSync(process.argv[2], 'utf8');
const scripts = [...page.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const body = scripts[scripts.length - 1];
const src = body.slice(body.indexOf('  function sections(inner)'), body.indexOf('  function buildSlides()'));
const stubs = `
  function escapeHtml(x){ return String(x).replace(/&/g,'&amp;').replace(/</g,'&lt;'); }
  const marked = { parseInline: x => x, parse: x => x };
`;
const expandBlocks = new Function(stubs + src + '\nreturn expandBlocks;')();
const SLIDES = JSON.parse(page.match(/const SLIDES = (\[[\s\S]*?\]);\n/)[1]);
const out = expandBlocks(SLIDES[0].content);
const checks = [
  ['component still expands', out.includes('pd-stat')],
  ['fence inside a code block survives', /:::cards/.test(out) && /### a \| strong/.test(out)],
  ['stray fence dropped', !/^:::bogus/m.test(out)],
  ['line numbers preserved', SLIDES[0].content.split('\n').length === out.split('\n').length],
  ['one-line :::paper consumed server-side', SLIDES[0].paper === 'What shipped'],
  ['one-line form not left on the face', !/:::paper/.test(SLIDES[0].content)],
];
let bad = 0;
checks.forEach(([n, ok]) => { console.log((ok ? 'ok  ' : 'FAIL') + '  ' + n); if(!ok) bad++; });
process.exitCode = bad ? 1 : 0;
