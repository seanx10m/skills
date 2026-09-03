// Pull pairSlides/scoreMatch straight out of the generated page and run it against a
// fake section list — the allocator is pure, so it needs no DOM.
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
const grab = (start, end) => src.slice(src.indexOf(start), src.indexOf(end));
const code = grab("  const STOP = new Set(", "  // Opening the pane, or moving a slide")
  .replace(/function sectionizePaper\(\)\{[\s\S]*?\n  \}\n/, '')
  .replace(/function headText\(sec\)\{[\s\S]*?\n  \}\n/, 'function headText(sec){ return sec.h; }\n');
let SLIDES = [];
eval(code + "\nglobalThis.pairSlides = pairSlides;");
function check(name, slides, heads, want){
  SLIDES = slides;
  const got = pairSlides(heads.map(h => ({h})));
  const ok = JSON.stringify(got) === JSON.stringify(want);
  console.log((ok ? 'ok  ' : 'FAIL') + '  ' + name + '  -> ' + JSON.stringify(got) +
              (ok ? '' : ' want ' + JSON.stringify(want)));
  if(!ok) process.exitCode = 1;
}
const S = (title, paper='') => ({title, paper});
check('exact + fuzzy + explicit + gap-fill',
  [S('Why this deck'), S('The vocabulary'), S('A slide with no paper match at all'), S('Closing','The deletion test')],
  ['Why this deck exists','The component vocabulary','Something unrelated','The deletion test'],
  [0,1,2,3]);
check('every slide distinct even with zero title matches',
  [S('aaa'), S('bbb'), S('ccc')], ['one','two','three'], [0,1,2]);
check('order beats a late fuzzy hit',
  [S('Setup'), S('Results')], ['Setup and scope','Results'], [0,1]);
check('short paper shares the last section rather than blanking',
  [S('a'), S('b'), S('c')], ['one','two'], [0,1,1]);
check('explicit anchor wins out of order, others fill around it',
  [S('a','three'), S('b'), S('c')], ['one','two','three'], [2,0,1]);
check('no paper sections at all', [S('a')], [], [-1]);
