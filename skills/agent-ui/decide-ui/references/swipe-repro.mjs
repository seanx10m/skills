// Headless repro for the decide-ui swipe handler: the momentum-tail bleed onto the next card
// (clean, jittered, quantized and coalesced tails), the fast second flick, and the pointer path.
// Pulls the handler straight out of swipe-gestures.md (or argv[2]) so it tests the canonical text.
// Needs playwright-core; CHROME_PATH = any Chromium/headless_shell binary. Never opens a window.
//   CHROME_PATH=... node swipe-repro.mjs [path/to/swipe-gestures.md]
import { chromium } from "playwright-core";
import fs from "fs";
const MD = process.argv[2] || new URL("swipe-gestures.md", import.meta.url).pathname;
const blocks = [...fs.readFileSync(MD, "utf8").matchAll(/```js\n([\s\S]*?)```/g)].map(m => m[1]);
const tun = blocks[0], arm = blocks[1];
const fly = blocks.find(b => b.includes("flyLayer.appendChild"));
const edges = blocks.find(b => b.includes("const setEdges"));
const html = `<!doctype html><style>
html,body{overflow-x:clip;overscroll-behavior-x:none;margin:0}
.deck{position:relative;width:520px;height:400px;margin:40px}
.stage,.fly-layer{position:absolute;inset:0}.fly-layer{pointer-events:none;z-index:5}
.card{position:absolute;inset:0;background:#eee;touch-action:none}
.tint{position:absolute;inset:0;opacity:0}.stamp{position:absolute;bottom:26px}
</style><div class="deck"><div class="stage" id="stage"></div><div class="fly-layer" id="fly"></div></div>
<div class="edge keep" id="ek"></div><div class="edge out" id="eo"></div>
<script>
const stage=document.getElementById("stage"), flyLayer=document.getElementById("fly");
const edgeKeep=document.getElementById("ek"), edgeOut=document.getElementById("eo");
${tun}
${edges}
${arm}
${fly}
const items=[...Array(20)].map((_,i)=>({id:i})); let idx=0; window.verdicts=[];
function commit(it,v){ verdicts.push(it.id+":"+v); idx++; render(); }
function render(){ setEdges(0,0); stage.innerHTML="";
  const it=items[idx]; if(!it) return;
  const el=document.createElement("div"); el.className="card front"; el.dataset.id=it.id;
  el.innerHTML='<div class="tint"></div><div class="stamp keep"></div><div class="stamp close"></div>';
  stage.appendChild(el); arm(el,it); }
render();
</script>`;

const browser = await chromium.launch({ headless: true,
  executablePath: process.env.CHROME_PATH });
async function scenario(name, fn) {
  const page = await browser.newPage();
  page.on("pageerror", e => console.log("PAGEERR", e.message));
  await page.route("http://t.test/", r => r.fulfill({contentType:"text/html", body: html}));
  await page.goto("http://t.test/");
  const r = await page.evaluate(fn);
  await page.close();
  return r;
}

// in-page helpers are injected as a string so each scenario can use them
const H = `
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let seed=7; const rnd=()=>((seed=(seed*16807)%2147483647)/2147483647);
const P={x:300,y:240};
// Chrome latches a wheel gesture to the element it started on; re-hit-test only once that node is gone.
let latch=null; const wheel=dx=>{ if(!latch||!latch.isConnected) latch=document.elementFromPoint(P.x,P.y)||document.body; const t=latch;
  t.dispatchEvent(new WheelEvent("wheel",{deltaX:dx,deltaY:0,clientX:P.x,clientY:P.y,bubbles:true,cancelable:true})); };
let maxX=0,maxRot=0; const probe=()=>{ const f=document.querySelector(".card.front");
  if(!f||f.dataset.id==="0") return; const m=new DOMMatrix(getComputedStyle(f).transform);
  maxX=Math.max(maxX,Math.abs(m.m41)); maxRot=Math.max(maxRot,Math.abs(Math.atan2(m.b,m.a)*180/Math.PI)); };
async function flick(n=24,d=70){ latch=null; for(let i=0;i<n;i++){ wheel(d); probe(); await sleep(15);} }
// tail: d*=0.955 per 15ms event. noise: multiplicative jitter. coalesce: at ~commit+220ms the
// re-render janks a frame and the browser merges k events into one (summed delta, longer gap).
async function tail(n,{noise=0,quant=false,coalesceAt=-1,k=3,jank=1}={}){ let d=70;
  for(let i=0;i<n;i++){ d*=0.955; let v=d*(1+noise*(2*rnd()-1)); if(quant) v=Math.round(v);
    if(i>=coalesceAt && i<coalesceAt+jank*k && coalesceAt>=0){ let s=v; for(let j=1;j<k;j++){ d*=0.955; s+=quant?Math.round(d):d; } await sleep(15*(k-1)); v=s; i+=k-1; }
    wheel(v); probe(); await sleep(15);} }
`;
const out = {};
const mk = (body) => new Function(`return (async()=>{${H}${body}})()`);
const cases = {
  "clean tail (doc repro)":          `await flick(); await tail(60); await sleep(400); return {verdicts, maxX, maxRot};`,
  "noisy tail +-30%":                `await flick(); await tail(60,{noise:.3}); await sleep(400); return {verdicts, maxX, maxRot};`,
  "quantized + noisy":               `await flick(); await tail(70,{noise:.3,quant:true}); await sleep(400); return {verdicts, maxX, maxRot};`,
  "coalesced frame at re-render":    `await flick(); await tail(60,{coalesceAt:16,k:3}); await sleep(400); return {verdicts, maxX, maxRot};`,
  "noisy tail +-10%":                `await flick(); await tail(60,{noise:.1}); await sleep(400); return {verdicts, maxX, maxRot};`,
  "sustained jank (3 merged frames)": `await flick(); await tail(60,{coalesceAt:14,k:3,jank:3}); await sleep(400); return {verdicts, maxX, maxRot};`,
  "fast second flick commits":       `await flick(); await tail(20,{noise:.3}); await flick(); await tail(40); await sleep(400); return {verdicts, maxX:-1};`,
  "second flick after short pause":  `await flick(); await tail(30,{noise:.3}); await sleep(60); await flick(); await tail(40); await sleep(400); return {verdicts, maxX:-1};`,
  "pointer drag then hover":         `const el=document.querySelector(".card.front"); const o={bubbles:true,pointerId:1,button:0,clientY:240};
     el.dispatchEvent(new PointerEvent("pointerdown",{...o,clientX:300})); for(let i=1;i<=10;i++) el.dispatchEvent(new PointerEvent("pointermove",{...o,clientX:300+i*30}));
     document.body.dispatchEvent(new PointerEvent("pointerup",{...o,clientX:600})); await sleep(300);
     for(let i=0;i<20;i++){ const t=document.elementFromPoint(300,240); t.dispatchEvent(new PointerEvent("pointermove",{...o,clientX:300+i*20})); probe(); await sleep(15);} return {verdicts,maxX,maxRot};`,
};
// seed sweep for the noisy cases so one lucky seed can't hide the hole
for (const [name, body] of Object.entries(cases)) {
  const seeds = name.includes("noisy") || name.includes("second") ? [1,2,3,4,5,6,7,8] : [7];
  const rs = [];
  for (const s of seeds) rs.push(await scenario(name, mk(body.replace(/^/, `seed=${s};`))));
  const bad = rs.filter(r => name.includes("second") ? r.verdicts.length < 2 : (r.verdicts.length !== 1 || r.maxX > 1));
  console.log(`${bad.length ? "FAIL" : "pass"}  ${name}  [${bad.length}/${rs.length} bad]  e.g. ` + JSON.stringify(bad[0] || rs[0]));
}
await browser.close();
