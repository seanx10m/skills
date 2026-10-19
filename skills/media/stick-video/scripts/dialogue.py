#!/usr/bin/env python3
"""Two-host voiceover: one continuous take PER SPEAKER, cut together in turn order.
usage: dialogue.py script.md [--voice normal=Umbriel --voice cool=Algieba]
script.md: one paragraph per turn, each starting with the speaker's name and a colon:
    cool: Here's how a plugin ends up inside the app.
    normal: First, who's who. Acme is the front end...
writes vo_full.m4a, words.json, para_starts.json (same shapes voice.py writes) + speakers.json
(one name per paragraph), so scenes.py works unchanged and host() can pick who is on screen.
Why per-speaker takes: per-line TTS resets the voice every clip and sounds choppy; one long take
per speaker keeps each voice consistent, and the cut points come from whisper's paragraph starts."""
import argparse, json, math, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cast import VOICES

ap = argparse.ArgumentParser()
ap.add_argument("script")
ap.add_argument("--voice", action="append", default=[], help="name=GeminiVoice, overrides the cast default")
ap.add_argument("--gap", type=float, default=0.45, help="seconds of silence between turns")
a = ap.parse_args()
voices = {k: v[0] for k, v in VOICES.items()}
for kv in a.voice:
    k, v = kv.split("="); voices[k] = v
styles = {k: v[1] for k, v in VOICES.items()}

paras, spk = [], []
for para in [p.strip() for p in open(a.script).read().split("\n\n") if p.strip()]:
    m = re.match(r"^(\w+):\s*(.*)$", para, re.S)
    if not m: raise SystemExit(f"paragraph has no 'speaker:' prefix: {para[:50]!r}")
    spk.append(m.group(1).lower()); paras.append(m.group(2).strip())
names = sorted(set(spk))
TAIL = "And that is the end of my part."
voice_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice.py")

for n in names:
    os.makedirs(f"take_{n}", exist_ok=True)
    # TAIL is a throwaway last paragraph: TTS often truncates the end of a take, so the real last
    # turn must not be the end of the take. It is recorded, then never used.
    own = [p for p, s in zip(paras, spk) if s == n]
    txt = "\n\n".join(own + [TAIL]) + "\n"
    # a take whose script is unchanged is reused; delete take_<name>/vo_full.m4a to force a re-record
    if os.path.exists(f"take_{n}/vo_full.m4a") and open(f"take_{n}/script.md").read() == txt:
        print(f"reusing take_{n}"); continue
    open(f"take_{n}/script.md", "w").write(txt)
    for f in ("vo_full.m4a", "words.json", "para_starts.json"):
        if os.path.exists(f"take_{n}/{f}"): os.remove(f"take_{n}/{f}")
procs = []
for n in names:
    if os.path.exists(f"take_{n}/vo_full.m4a"): continue
    cmd = [sys.executable, voice_py, "script.md", "-v", voices.get(n, "Puck")]
    if n in styles: cmd += ["-s", styles[n]]
    procs.append((n, subprocess.Popen(cmd, cwd=f"take_{n}")))
for n, pr in procs:
    if pr.wait(): raise SystemExit(f"voice take failed for {n}")

dur = lambda f: float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f],
                                     capture_output=True, text=True).stdout)
T = {n: {"ps": json.load(open(f"take_{n}/para_starts.json")), "w": json.load(open(f"take_{n}/words.json")),
         "d": dur(f"take_{n}/vo_full.m4a")} for n in names}
def silences(f):
    """[(start, end)] of quiet stretches in a take, from ffmpeg silencedetect."""
    err = subprocess.run(["ffmpeg", "-v", "info", "-i", f, "-af", "silencedetect=noise=-40dB:d=0.04", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    st = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", err)]
    en = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", err)]
    return list(zip(st, en))

PAD = 0.05
for n in names:
    t = T[n]; t["sil"] = silences(f"take_{n}/vo_full.m4a")
    # whisper's word times are contiguous, so the real pause between paragraph k and k+1 sits somewhere
    # in [last word of k starts, first word of k+1 ends]; cut in the longest silence found there.
    cuts = []
    for k in range(1, len(t["ps"])):
        prev = [w for w in t["w"] if w[1] < t["ps"][k]]
        nxt = [w for w in t["w"] if w[1] >= t["ps"][k]]
        lo = prev[-1][1] if prev else t["ps"][k] - 0.5
        hi = nxt[0][2] if nxt else t["ps"][k] + 0.5
        cand = [(min(se, hi) - max(ss, lo), max(ss, lo), min(se, hi)) for ss, se in t["sil"] if se > lo and ss < hi]
        cand = [c for c in cand if c[0] > 0.03]
        if cand:
            _, ss, se = max(cand); cuts.append((ss + PAD, se - PAD))
        else:
            print(f"WARN {n} para {k}: no pause found, cutting at whisper's start")
            cuts.append((t["ps"][k] - 0.06, t["ps"][k] - 0.06))
    t["cuts"] = cuts
    if len(t["ps"]) < sum(1 for x in spk if x == n) + 1:
        print(f"WARN {n}: TAIL not found in the take - the last real turn may be truncated")

cnt = {n: 0 for n in names}; segs, words, starts, off = [], [], [], 0.0
for j, s in enumerate(spk):
    k = cnt[s]; cnt[s] += 1; t = T[s]; ps = t["ps"]
    a0 = max(0.0, t["cuts"][k - 1][1]) if k > 0 else max(0.0, ps[0] - 0.06)
    b0 = t["cuts"][k][0]  # TAIL guarantees a cut after every real turn
    segs.append((names.index(s), a0, b0)); starts.append(math.floor((off + max(ps[k], a0) - a0) * 100) / 100)  # floor: never after its first word
    words += [[wd, round(max(t0, a0) - a0 + off, 3), round(min(t1, b0) - a0 + off, 3)]
              for wd, t0, t1 in t["w"] if ps[k] <= t0 < ps[k + 1]]
    off += b0 - a0
    if j < len(spk) - 1: off += a.gap
inp = sum((["-i", f"take_{n}/vo_full.m4a"] for n in names), [])
FMT = "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=mono"
fc = "".join(f"[{i}:a]atrim={x:.3f}:{y:.3f},asetpts=PTS-STARTPTS,{FMT}[s{j}];" for j, (i, x, y) in enumerate(segs))
fc += "".join(f"aevalsrc=0:d={a.gap}:s=48000,{FMT}[g{j}];" for j in range(len(segs) - 1))
fc += "".join(f"[s{j}]" + (f"[g{j}]" if j < len(segs) - 1 else "") for j in range(len(segs)))
fc += f"concat=n={2 * len(segs) - 1}:v=0:a=1[o]"
subprocess.run(["ffmpeg", "-v", "error", "-y", *inp, "-filter_complex", fc, "-map", "[o]", "-c:a", "aac", "-b:a", "192k", "vo_full.m4a"], check=True)
json.dump(words, open("words.json", "w")); json.dump(starts, open("para_starts.json", "w")); json.dump(spk, open("speakers.json", "w"))
print(f"dialogue {off:.1f}s, {len(paras)} turns")
for t, s, p in zip(starts, spk, paras): print(f"  {t:6.2f}  {s:>7}  {p[:55]}")
