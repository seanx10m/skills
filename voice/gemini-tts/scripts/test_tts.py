#!/usr/bin/env python3
"""Run: python3 test_tts.py   (no deps, no network)"""
import array, concurrent.futures as cf, importlib.util, math, os, random, time

spec = importlib.util.spec_from_file_location(
    "tts", os.path.join(os.path.dirname(os.path.abspath(__file__)), "tts.py"))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
R = m.RATE


def tone(sec, amp=8000):
    return array.array("h", [int(amp * math.sin(2 * math.pi * 220 * t / R))
                             for t in range(int(sec * R))]).tobytes()


def quiet(sec):
    return b"\x00" * int(sec * R) * 2


def secs(b):
    return len(b) / 2 / R


# the real bug: 641s of runaway trailing silence after good speech
out = m.collapse_silence(tone(3) + quiet(641), 400)
assert 2.9 < secs(out) < 3.1, secs(out)

# runaway with a stray blip stranding the silence mid-buffer (edge-trim misses this)
out = m.collapse_silence(tone(3) + quiet(15) + tone(0.3) + quiet(600), 400)
assert 3.6 < secs(out) < 3.9, secs(out)      # 3 + 0.4 clamp + 0.3 blip

# interior pause longer than keep_ms is clamped, shorter is untouched
assert 2.3 < secs(m.collapse_silence(tone(1) + quiet(9) + tone(1), 400)) < 2.5
assert 2.1 < secs(m.collapse_silence(tone(1) + quiet(0.2) + tone(1), 400)) < 2.3

# leading silence dropped; all-silence -> empty
assert 0.9 < secs(m.collapse_silence(quiet(30) + tone(1), 400)) < 1.1
assert m.collapse_silence(quiet(30), 400) == b""

# chunker keeps every character and never exceeds the cap
t = "\n\n".join("Sentence %d. " % i * 40 for i in range(30))
c = m.chunks(t)
assert all(len(x) <= m.CHUNK for x in c), [len(x) for x in c]
assert sum(len(x) for x in c) > 0.98 * len(t.strip())

# stitch keeps the given order, one gap between non-empty clips, none at the edges
gap = R * 250 // 1000 * 2
o = m.stitch([b"\x01" * 100, b"\x02" * 200, b"\x03" * 300], 250)
assert len(o) == 600 + 2 * gap, len(o)
assert o[:100] == b"\x01" * 100
assert o[100:100 + gap] == b"\x00" * gap
assert o[100 + gap:300 + gap] == b"\x02" * 200
assert o[300 + 2 * gap:] == b"\x03" * 300
assert m.stitch([b"", b"\x01" * 10], 250) == b"\x01" * 10   # empty clip adds no gap
assert m.stitch([], 250) == b""

# the real assembly path: workers finish out of order, output must still be in order.
# Fake PCM of distinct per-chunk byte values and lengths, so a swap is unmissable.
random.seed(0)
with cf.ThreadPoolExecutor(max_workers=5) as ex:
    futs = [ex.submit(lambda i: (time.sleep(random.random() * 0.05), bytes([i + 1]) * (10 * (i + 1)))[1], i)
            for i in range(12)]
    done = [f.result() for f in futs]
assert [c[0] for c in done] == list(range(1, 13)), [c[0] for c in done]
o, at = m.stitch(done, 0), 0
for i, c in enumerate(done):
    assert o[at:at + len(c)] == bytes([i + 1]) * (10 * (i + 1)), "chunk %d landed wrong" % i
    at += len(c)
assert at == len(o)

# truncation check, against the three measured chunks from the observed bad run
assert not m.truncated(2926, 153.2)          # 19.1 chars/sec, healthy
assert not m.truncated(2319, 126.4)          # 18.3 chars/sec, healthy
assert m.truncated(2929, 65.5)               # 44.7 chars/sec, truncated
assert not m.truncated(200, 2.0)             # 100 chars/sec but too short to judge
assert not m.truncated(3000, 3000 / m.MAX_CPS + 1)   # just under the line
assert m.truncated(3000, 3000 / m.MAX_CPS - 1)       # just over it
assert m.truncated(3000, 0.0)                # all-silence chunk: caught, not divide-by-zero
assert not m.truncated(50, 0.0)              # ...unless it was too short to judge anyway

# speak() must raise, not sys.exit: exiting from a worker thread only kills the worker
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tts.py")).read()
assert "sys.exit" not in src[src.index("def speak("):src.index("def truncated(")]

print("ok - %d checks" % 28)
