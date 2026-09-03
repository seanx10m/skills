#!/usr/bin/env python3
"""Gemini TTS -> m4a. Reads text/markdown from a file or stdin, chunks it, speaks it."""
import argparse, array, base64, concurrent.futures as cf, json, os, re, subprocess, sys, tempfile, time, urllib.error, urllib.request

MODEL = "gemini-2.5-flash-preview-tts"
URL = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
CHUNK = 3000  # chars; well under the per-request TTS limit
RATE = 24000  # Gemini returns raw 24kHz 16-bit mono LE PCM
GAP_MS = 250  # deliberate pause stitched between chunks
# ponytail: fixed worker cap, no token bucket. Each chunk is one blocking HTTPS POST
# that takes minutes, so this is pure I/O wait; 5 in flight cuts a 12-chunk doc from
# ~25min to ~5min while staying inside the per-minute request quota. speak() already
# backs off on 429, so the failure mode of guessing slightly high is a retry, not a run.
JOBS = 5
# Truncation check: Gemini sometimes stops speaking partway through a chunk and pads
# the rest with silence, which collapse_silence() then strips - clean audio, missing
# content, no audible seam. The tell is speech rate, and ONLY the rate - the runaway
# padding fires on healthy chunks too, so dead-air volume is not a truncation signal.
# Healthy narration measured 12.8-20.2 chars/sec of kept audio across many chunks; an
# observed truncated one ran 44.7. 30 sits ~1.5x above the fastest healthy sample and
# ~1.5x below the bad one. Truncation is transient: the same chunk that ran 44.7 came
# back at 19.7 on a re-roll of identical input, which is why the fix is a retry.
MAX_CPS = 30
MIN_CPS_CHARS = 600  # below this the rate is too noisy to judge; skip the check
CPS_TRIES = 3        # first attempt + 2 re-rolls
# Gemini TTS is a sampled autoregressive audio model: with no seed, every request
# draws fresh, so the same text comes back in a subtly different voice each run
# (measured: identical input, two different byte lengths). Pinning generationConfig.seed
# makes it byte-identical run to run (verified: 3/3 identical md5), and holding ONE seed
# across all chunks keeps the speaker from drifting mid-file. Re-rolls deliberately step
# the seed - a retry that resent the same seed would get the same bad audio forever.
# Do NOT reach for temperature=0 instead: greedy decoding made this model return 200s
# with no audio part on 3 of 4 probes.
SEED = 42


def collapse_silence(pcm, keep_ms=400, thresh=400):
    """Collapse every silent run longer than keep_ms down to keep_ms; drop it
    entirely at the edges.

    Gemini's TTS sometimes fails to emit its end-of-audio token and keeps
    generating silence until it hits the output cap - one observed chunk came
    back with 641s (10m41s) of trailing dead air. Edge-trimming alone does not
    catch it, because the runaway can contain stray blips of audio that leave
    the real silence stranded mid-buffer. So collapse every long run, wherever
    it sits."""
    s = array.array("h")
    s.frombytes(pcm[: len(pcm) // 2 * 2])
    if sys.byteorder == "big":
        s.byteswap()
    # Scan in 10ms blocks: max()/min() run at C speed, and 10ms is ample
    # resolution for a keep_ms-scale decision. Sample-by-sample in Python takes
    # minutes on a 30-minute file.
    blk = RATE // 100
    loud = [max(max(s[p : p + blk]), -min(s[p : p + blk])) >= thresh
            for p in range(0, len(s) - blk + 1, blk)]
    keep_blk, n, out, i = max(1, keep_ms // 10), len(loud), array.array("h"), 0
    while i < n:
        j = i
        while j < n and loud[j] == loud[i]:
            j += 1
        run = j - i if loud[i] or (out and j < n) else 0   # drop silence at edges
        if run and not loud[i]:
            run = min(run, keep_blk)                       # clamp interior silence
        out.extend(s[i * blk : (i + run) * blk])
        i = j
    if sys.byteorder == "big":
        out.byteswap()
    return out.tobytes()


def key():
    k = os.environ.get("GEMINI_API_KEY")
    if not k:
        p = os.path.expanduser("~/.gemini_api_key")
        if os.path.exists(p):
            k = open(p).read().strip()
    if not k:
        sys.exit("no API key: set GEMINI_API_KEY or write ~/.gemini_api_key")
    return k


def strip_md(t):
    t = re.sub(r"```.*?```", "", t, flags=re.S)          # code blocks
    t = re.sub(r"^\s*\|.*\|\s*$", "", t, flags=re.M)     # tables
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)           # images
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)       # links -> text
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.M)  # headings
    t = re.sub(r"[*_`>#]+", "", t)                       # inline marks
    t = re.sub(r"^\s*[-+*]\s+", "", t, flags=re.M)       # bullets
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def chunks(t, n=CHUNK):
    out, cur = [], ""
    for para in t.split("\n\n"):
        if len(cur) + len(para) + 2 > n and cur:
            out.append(cur.strip()); cur = ""
        while len(para) > n:  # a single huge paragraph: split on sentences
            cut = para.rfind(". ", 0, n)
            cut = cut + 1 if cut > n // 2 else n
            out.append(para[:cut].strip()); para = para[cut:]
        cur += para + "\n\n"
    if cur.strip():
        out.append(cur.strip())
    return out


def speak(text, voice, k, seed):
    body = json.dumps({
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
            "seed": seed,
        },
    }).encode()
    req = urllib.request.Request(
        URL.format(m=MODEL), data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": k})
    # ponytail: 3 tries, fixed backoff. A single read timeout used to nuke a 12-chunk run.
    # Raises rather than exiting: this runs in a worker thread, where exiting only kills
    # the worker and would leave the run stitching a hole into the output.
    for attempt in range(3):
        try:
            if attempt:  # a no-audio response is deterministic under a fixed seed
                body = json.dumps({**json.loads(body), "generationConfig": {
                    **json.loads(body)["generationConfig"], "seed": seed + attempt}}).encode()
                req.data = body
            with urllib.request.urlopen(req, timeout=300) as r:
                d = json.load(r)
            return base64.b64decode(d["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503) and attempt < 2:
                time.sleep(10 * (attempt + 1)); continue
            raise RuntimeError(f"gemini {e.code}: {e.read().decode()[:600]}")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt == 2:
                raise RuntimeError(f"gemini request failed after 3 tries: {e}")
            print(f"  retry {attempt + 1}/2 after {e}", file=sys.stderr, flush=True)
            time.sleep(10 * (attempt + 1))
        except (KeyError, IndexError):
            # A 200 with no audio part - observed as {"finishReason": "OTHER"} on a chunk
            # that renders fine on a re-roll. Same flake class as a timeout, so it shares
            # the same 3 tries instead of killing the run.
            if attempt == 2:
                raise RuntimeError(f"no audio in 3 responses: {json.dumps(d)[:400]}")
            print(f"  no audio (retry {attempt + 1}/2): {json.dumps(d)[:160]}",
                  file=sys.stderr, flush=True)
            time.sleep(10 * (attempt + 1))


def truncated(nchars, secs):
    """True if the model plainly stopped speaking partway through the chunk.

    nchars is the CHUNK text only, never the style prefix - the prefix is an
    instruction, not narration, so counting it would inflate the rate on short
    chunks. Rate is measured against POST-collapse seconds, since the padding
    collapse_silence() strips is exactly the audio that was never speech.
    secs <= 0 means the chunk came back as pure silence - the same bug taken to its
    limit, so it fails the check rather than stitching nothing and calling it fine."""
    return nchars >= MIN_CPS_CHARS and (secs <= 0 or nchars / secs > MAX_CPS)


def stitch(clips, gap_ms):
    """Concatenate clips IN THE GIVEN ORDER, with a gap_ms pause between non-empty ones."""
    gap = b"\x00" * (RATE * gap_ms // 1000 * 2)
    pcm = bytearray()
    for c in clips:
        if pcm and c:
            pcm += gap
        pcm += c
    return bytes(pcm)


def render(i, n, text, args, k):
    """Speak one chunk, collapse its silence, re-roll if the model truncated.
    Returns (clip_pcm, kept_secs, chars_per_sec). Raises if it never comes back whole."""
    for attempt in range(CPS_TRIES):
        try:
            raw_pcm = speak(f"{args.style}: {text}" if args.style else text, args.voice, k,
                            args.seed + attempt * 1000)
        except RuntimeError as e:
            raise RuntimeError(f"chunk {i}/{n}: {e}")  # name the chunk; workers interleave
        clip = collapse_silence(raw_pcm, args.gap_ms)
        secs = len(clip) / 2 / RATE
        cps = len(text) / secs if secs else float("inf")
        line = (f"[{i}/{n}] {len(text)} chars, {len(raw_pcm) / 2 / RATE:.1f}s -> "
                f"{secs:.1f}s, {cps:.1f} chars/sec")
        if len(raw_pcm) - len(clip) > 10 * RATE * 2:
            line += (f"\n  !! dropped {(len(raw_pcm) - len(clip)) / 2 / RATE:.0f}s of dead air "
                     f"(Gemini runaway-silence bug)")
        bad = truncated(len(text), secs)
        if bad and attempt < CPS_TRIES - 1:
            line += f"\n  !! [{i}/{n}] looks truncated (>{MAX_CPS} chars/sec), re-rolling"
        print(line, file=sys.stderr, flush=True)
        if not bad:
            return clip, secs, cps
    raise RuntimeError(f"chunk {i}/{n} still truncated after {CPS_TRIES} tries: "
                       f"{len(text)} chars in {secs:.1f}s = {cps:.1f} chars/sec "
                       f"(healthy is 13-21). Refusing to write audio missing content.")


def main():
    a = argparse.ArgumentParser()
    a.add_argument("input", nargs="?", help="text/markdown file (default: stdin)")
    a.add_argument("-o", "--out", default=None, help="output .m4a (default: ~/Desktop/<name>.m4a)")
    a.add_argument("-v", "--voice", default="Kore")
    a.add_argument("-s", "--style", default="", help="delivery instruction, e.g. 'read warmly, slowly'")
    a.add_argument("--gap-ms", type=int, default=GAP_MS, help="max silence kept anywhere, and the pause stitched between chunks")
    a.add_argument("--seed", type=int, default=SEED, help="fixes the voice; same seed = same audio")
    a.add_argument("-j", "--jobs", type=int, default=JOBS, help="chunks rendered concurrently")
    args = a.parse_args()

    raw = open(args.input).read() if args.input else sys.stdin.read()
    text = strip_md(raw)
    if not text:
        sys.exit("nothing to say")

    out = args.out or os.path.expanduser(
        "~/Desktop/%s.m4a" % (os.path.splitext(os.path.basename(args.input))[0] if args.input else "gemini-tts"))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)

    k = key()
    parts = chunks(text)
    # Chunks render concurrently but futs is in submission order, so reading the
    # results in list order puts chunk N's audio back at position N. Progress lines
    # interleave; the ordered summary below is the one to read.
    err = None
    with cf.ThreadPoolExecutor(max_workers=max(1, min(args.jobs, len(parts)))) as ex:
        futs = [ex.submit(render, i, len(parts), c, args, k) for i, c in enumerate(parts, 1)]
        try:
            done = [f.result() for f in futs]
        except Exception as e:  # one bad chunk fails the run - never a file with a hole
            for f in futs:
                f.cancel()
            err = e
    if err:
        sys.exit(f"aborted: {err}")

    print("--- in order ---", file=sys.stderr)
    for i, (clip, secs, cps) in enumerate(done, 1):
        print(f"[{i}/{len(parts)}] {len(parts[i - 1])} chars, {secs:.1f}s, {cps:.1f} chars/sec",
              file=sys.stderr)
    pcm = stitch([c for c, _, _ in done], args.gap_ms)
    print(f"total {len(pcm) / 2 / RATE:.1f}s", file=sys.stderr)

    with tempfile.NamedTemporaryFile(suffix=".pcm", delete=False) as f:
        f.write(pcm); tmp = f.name
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", str(RATE),
                    "-ac", "1", "-i", tmp, "-c:a", "aac", "-b:a", "96k", out], check=True)
    os.unlink(tmp)
    print(out)


if __name__ == "__main__":
    main()
