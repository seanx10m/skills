#!/usr/bin/env python3
"""Fast text-to-speech via OpenAI gpt-4o-mini-tts. Standard library only.

Splits the input into chunks, synthesises them concurrently, and stitches the
audio back together in order. Wall-clock is roughly (slowest chunk), not the
sum of all chunks, so a long document finishes in about the time one chunk
takes rather than one-at-a-time.

Chunks are requested as raw PCM (24 kHz, 16-bit, mono, no container), which is
why they can be concatenated byte-for-byte with no re-encode. The joined PCM is
wrapped in a WAV, then handed to macOS `afconvert` if the requested output is a
compressed format.

Key precedence: OPENAI_API_KEY env, then ~/.config/openai-key, then Keychain.

    python3 gpt_tts.py "Hello there."
    python3 gpt_tts.py -f notes.md -o ~/Desktop/notes.m4a --play
    cat big.txt | python3 gpt_tts.py -v nova -j 12
    python3 gpt_tts.py --selftest        # offline, no API call
"""
import argparse
import concurrent.futures
import datetime
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import wave

KEYFILE = "~/.config/openai-key"
KEYCHAIN_ACCOUNT = "openai-tts"
KEYCHAIN_SERVICE = "openai-api-key"
ENDPOINT = "https://api.openai.com/v1/audio/speech"

VOICES = ["alloy", "ash", "ballad", "coral", "echo", "fable",
          "onyx", "nova", "sage", "shimmer", "verse"]

# OpenAI caps a single speech request at 4096 characters. Staying well under it
# gives shorter per-chunk latency and more chunks to run in parallel.
MAX_CHARS = 1800

# Raw PCM returned by the speech API. Not configurable server-side.
PCM_RATE, PCM_WIDTH, PCM_CHANNELS = 24000, 2, 1

MAX_ATTEMPTS = 5
RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504}
TIMEOUT = 180


# ---------------------------------------------------------------- key

def get_key():
    env = os.environ.get("OPENAI_API_KEY")
    if env:
        return env.strip()
    keyfile = os.path.expanduser(KEYFILE)
    if os.path.exists(keyfile):
        with open(keyfile, encoding="utf-8") as fh:
            key = fh.readline().strip()
        if key:
            return key
    try:
        out = subprocess.run(
            ["security", "find-generic-password",
             "-a", KEYCHAIN_ACCOUNT, "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True, text=True, check=True)
        if out.stdout.strip():
            return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    sys.exit(f"ERROR: no OpenAI API key. Set OPENAI_API_KEY, or write one to "
             f"{KEYFILE}, or store it in the Keychain with:\n"
             f"  security add-generic-password -a {KEYCHAIN_ACCOUNT} "
             f"-s {KEYCHAIN_SERVICE} -w 'sk-...' -U")


# ---------------------------------------------------------------- chunking

def chunk_text(text, limit=MAX_CHARS):
    """Split on the largest natural boundary that fits: paragraph, then
    sentence, then whitespace, then a hard cut. Never exceeds `limit`."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks = []
    for para in paras:
        if len(para) <= limit:
            chunks.append(para)
            continue
        for sent in _split_keeping_under(para, limit):
            chunks.append(sent)
    # Pack small neighbours back together so we do not fire a request per line.
    packed, buf = [], ""
    for c in chunks:
        candidate = f"{buf}\n\n{c}" if buf else c
        if len(candidate) <= limit:
            buf = candidate
        else:
            if buf:
                packed.append(buf)
            buf = c
    if buf:
        packed.append(buf)
    return packed


def _split_keeping_under(para, limit):
    sents = re.split(r"(?<=[.!?])\s+", para)
    out, buf = [], ""
    for s in sents:
        candidate = f"{buf} {s}".strip() if buf else s
        if len(candidate) <= limit:
            buf = candidate
        else:
            if buf:
                out.append(buf)
            buf = s if len(s) <= limit else ""
            if not buf:
                out.extend(_hard_wrap(s, limit))
    if buf:
        out.append(buf)
    return out


def _hard_wrap(s, limit):
    """Last resort for a single 'sentence' longer than the limit (minified
    text, a URL wall, a language without western punctuation)."""
    out = []
    while len(s) > limit:
        cut = s.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        out.append(s[:cut].strip())
        s = s[cut:].strip()
    if s:
        out.append(s)
    return out


# ---------------------------------------------------------------- synthesis

class FatalAPIError(Exception):
    """A non-retryable API failure — bad key, bad param, no credits."""


def _post(key, payload):
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def synth_chunk(key, text, voice, model, instructions, speed, on_retry=None):
    """One chunk to PCM bytes, with backoff. Retries transient failures only;
    a 401/403/400 fails immediately rather than burning five attempts."""
    payload = {"model": model, "voice": voice, "input": text,
               "response_format": "pcm"}
    if instructions:
        payload["instructions"] = instructions
    if speed and speed != 1.0:
        payload["speed"] = speed

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return _post(key, payload)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            # A quota/billing 429 is permanent, unlike a rate-limit 429 —
            # backing off five times just delays the same failure.
            if e.code not in RETRY_STATUS or _is_permanent_429(body):
                raise FatalAPIError(f"HTTP {e.code}: {body.strip()}") from None
            if attempt == MAX_ATTEMPTS:
                raise FatalAPIError(
                    f"HTTP {e.code} after {MAX_ATTEMPTS} attempts: "
                    f"{body.strip()}") from None
            # Honour the server's own pacing when it gives one.
            delay = _retry_after(e.headers) or _backoff(attempt)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt == MAX_ATTEMPTS:
                raise FatalAPIError(
                    f"network failure after {MAX_ATTEMPTS} attempts: {e}") from None
            delay = _backoff(attempt)

        if on_retry:
            on_retry(attempt, delay)
        time.sleep(delay)


PERMANENT_429 = ("insufficient_quota", "credit_balance_exhausted",
                 "billing_hard_limit_reached")


def _is_permanent_429(body):
    low = body.lower()
    return any(marker in low for marker in PERMANENT_429)


def _retry_after(headers):
    raw = headers.get("Retry-After") if headers else None
    try:
        return min(float(raw), 60.0)
    except (TypeError, ValueError):
        return None


def _backoff(attempt):
    # Exponential with full jitter — keeps a fleet of parallel workers from
    # retrying in lockstep after a shared 429.
    return random.uniform(0, min(2 ** attempt, 30))


def synth_all(key, chunks, voice, model, instructions, speed, workers, quiet):
    """Run every chunk concurrently, return PCM bytes in original order."""
    results = [None] * len(chunks)
    done = [0]

    def note(i):
        def _on_retry(attempt, delay):
            if not quiet:
                print(f"  chunk {i + 1}: retry {attempt} in {delay:.1f}s",
                      file=sys.stderr)
        return _on_retry

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(synth_chunk, key, c, voice, model, instructions,
                        speed, note(i)): i
            for i, c in enumerate(chunks)
        }
        for fut in concurrent.futures.as_completed(futures):
            i = futures[fut]
            results[i] = fut.result()   # FatalAPIError propagates, cancels rest
            done[0] += 1
            if not quiet:
                print(f"  {done[0]}/{len(chunks)} chunks", file=sys.stderr)
    return results


# ---------------------------------------------------------------- output

def write_wav(pcm_parts, path):
    with wave.open(path, "wb") as w:
        w.setnchannels(PCM_CHANNELS)
        w.setsampwidth(PCM_WIDTH)
        w.setframerate(PCM_RATE)
        for part in pcm_parts:
            w.writeframes(part)


def convert(wav_path, out_path):
    """WAV -> whatever the output extension asks for, via macOS afconvert."""
    ext = os.path.splitext(out_path)[1].lower()
    if ext == ".wav":
        shutil.move(wav_path, out_path)
        return out_path
    fmt = {".m4a": ("m4af", "aac"), ".aac": ("adts", "aac"),
           ".caf": ("caff", "aac"), ".aiff": ("AIFF", None)}.get(ext)
    if not fmt or not shutil.which("afconvert"):
        fallback = os.path.splitext(out_path)[0] + ".wav"
        shutil.move(wav_path, fallback)
        print(f"NOTE: cannot produce {ext}, wrote WAV instead", file=sys.stderr)
        return fallback
    cmd = ["afconvert", "-f", fmt[0]]
    if fmt[1]:
        cmd += ["-d", fmt[1], "-b", "64000"]
    cmd += [wav_path, out_path]
    subprocess.run(cmd, check=True, capture_output=True)
    os.remove(wav_path)
    return out_path


# ---------------------------------------------------------------- cli

def resolve_text(args):
    if args.file:
        with open(os.path.expanduser(args.file), encoding="utf-8") as fh:
            text = fh.read()
    elif args.text:
        text = args.text
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        sys.exit("ERROR: no input. Pass text, use -f FILE, or pipe on stdin.")
    text = text.strip()
    if not text:
        sys.exit("ERROR: input is empty.")
    return text


def main():
    p = argparse.ArgumentParser(description="Parallel OpenAI text-to-speech.")
    p.add_argument("text", nargs="?", help="text to speak")
    p.add_argument("-f", "--file", help="read text from a file")
    p.add_argument("-o", "--out", help="output path (default ~/Desktop/...m4a)")
    p.add_argument("-v", "--voice", default="alloy", choices=VOICES)
    p.add_argument("-m", "--model", default="gpt-4o-mini-tts")
    p.add_argument("-i", "--instructions", help="tone/style steer")
    p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("-j", "--workers", type=int, default=8,
                   help="concurrent chunk requests (default 8)")
    p.add_argument("--chunk-chars", type=int, default=MAX_CHARS)
    p.add_argument("--play", action="store_true", help="afplay when done")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--selftest", action="store_true",
                   help="offline check, no API call")
    args = p.parse_args()

    if args.selftest:
        return selftest()

    text = resolve_text(args)
    chunks = chunk_text(text, args.chunk_chars)
    workers = max(1, min(args.workers, len(chunks)))

    out = os.path.expanduser(args.out) if args.out else os.path.join(
        os.path.expanduser("~/Desktop"),
        f"gpt-tts-{datetime.datetime.now():%Y%m%d-%H%M%S}.m4a")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

    if not args.quiet:
        print(f"{len(text)} chars -> {len(chunks)} chunks, {workers} workers",
              file=sys.stderr)

    started = time.time()
    try:
        parts = synth_all(get_key(), chunks, args.voice, args.model,
                          args.instructions, args.speed, workers, args.quiet)
    except FatalAPIError as e:
        sys.exit(f"ERROR: {e}")

    tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    write_wav(parts, tmp_wav)
    final = convert(tmp_wav, out)

    if not args.quiet:
        secs = sum(len(x) for x in parts) / (PCM_RATE * PCM_WIDTH)
        print(f"{secs:.0f}s of audio in {time.time() - started:.1f}s",
              file=sys.stderr)
    print(final)

    if args.play:
        subprocess.run(["afplay", final])


# ---------------------------------------------------------------- selftest

def selftest():
    # chunking never exceeds the limit, and loses no words
    src = ("Alpha beta gamma. " * 200) + "\n\n" + ("Delta epsilon. " * 200)
    ch = chunk_text(src, 500)
    assert ch, "expected chunks"
    assert all(len(c) <= 500 for c in ch), [len(c) for c in ch]
    assert " ".join(ch).split() == src.split(), "chunking dropped/reordered words"

    # a single unbroken blob still gets cut
    blob = "x" * 5000
    assert all(len(c) <= 400 for c in chunk_text(blob, 400))

    # short input stays one chunk
    assert len(chunk_text("Hello there.", 500)) == 1

    # PCM concat -> WAV keeps every frame, in order
    a, b = b"\x01\x02" * 100, b"\x03\x04" * 50
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    write_wav([a, b], tmp)
    with wave.open(tmp, "rb") as w:
        assert w.getframerate() == PCM_RATE
        assert w.getnframes() == (len(a) + len(b)) // PCM_WIDTH
        assert w.readframes(w.getnframes()) == a + b
    os.remove(tmp)

    # retryable vs fatal classification
    assert 429 in RETRY_STATUS and 500 in RETRY_STATUS
    assert 401 not in RETRY_STATUS and 400 not in RETRY_STATUS
    assert all(0 <= _backoff(n) <= 30 for n in range(1, 8))
    assert _retry_after({"Retry-After": "3"}) == 3.0
    assert _retry_after({"Retry-After": "junk"}) is None
    assert _retry_after({"Retry-After": "9999"}) == 60.0

    # a quota 429 must not be retried; a plain rate-limit 429 must be
    assert _is_permanent_429('{"code": "credit_balance_exhausted"}')
    assert _is_permanent_429('{"type": "insufficient_quota"}')
    assert not _is_permanent_429('{"message": "Rate limit reached, retry soon"}')

    print("selftest OK")


if __name__ == "__main__":
    main()
