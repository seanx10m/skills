#!/usr/bin/env python3
"""One continuous narration take -> word timings -> paragraph starts.
usage: voice.py script.md [-v Puck] [-s "style"]
writes vo_full.m4a, words.json [[word, t0, t1], ...], para_starts.json [t, ...]
One long take, never per-line clips: per-line TTS resets the voice each line and
sounds choppy. Scenes are cut on the audio afterwards, so no line ever gets cut short."""
import argparse, base64, glob, json, os, re, shutil, subprocess, urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("script")
ap.add_argument("-v", "--voice", default="Puck")
ap.add_argument("-s", "--style", default="Say this like a casual, dry-witted American YouTube explainer, conversational and natural, medium-brisk pace, with short natural pauses between paragraphs:")
a = ap.parse_args()

def tts(script, out, voice, style):
    """Gemini TTS over REST. Key comes from GEMINI_API_KEY (or GOOGLE_API_KEY) only."""
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key: raise SystemExit("set GEMINI_API_KEY in the environment")
    model = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
    text = f"{style}\n\n{open(script).read().strip()}"
    body = {"contents": [{"parts": [{"text": text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}
    req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        json.dumps(body).encode(), {"Content-Type": "application/json", "x-goog-api-key": key})
    resp = json.load(urllib.request.urlopen(req, timeout=600))
    pcm = base64.b64decode(resp["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", "-", "-c:a", "aac", "-b:a", "128k", out],
                   input=pcm, check=True)
tts(a.script, "vo_full.m4a", a.voice, a.style)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "vo_full.m4a", "-ar", "16000", "-ac", "1", "vo_full.wav"], check=True)

def ggml():
    for p in ("~/.cache/openwhispr/whisper-models", "~/Library/Application Support/superwhisper",
              "~/.cache/hyperframes/whisper/models", "/opt/homebrew/share/whisper.cpp/models"):
        for size in ("large-v3-turbo", "medium", "small.en", "small", "base.en"):
            hit = glob.glob(os.path.join(os.path.expanduser(p), f"ggml-{size}.bin"))
            if hit: return hit[0]
    raise SystemExit("no whisper ggml model found")
subprocess.run([shutil.which("whisper-cli"), "-m", ggml(), "-f", "vo_full.wav", "-ojf", "-of", "vo_full", "-ml", "1", "-sow"],
               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
words = [[norm(s["text"]), s["offsets"]["from"] / 1000, s["offsets"]["to"] / 1000]
         for s in json.load(open("vo_full.json"))["transcription"] if norm(s["text"])]
json.dump(words, open("words.json", "w"))

# align each paragraph's first two words to the token stream, in order
paras = [p.strip() for p in open(a.script).read().split("\n\n") if p.strip()]
pos, starts = 0, []
for p in paras:
    ws = [norm(w) for w in p.split() if norm(w)]
    # match up to the first three words; short openers like "and the" recur inside earlier paragraphs
    n = min(3, len(ws))
    match = lambda i: all(i + j < len(words) and words[i + j][0][:4] == ws[j][:4] for j in range(n))
    hit = next((i for i in range(pos, len(words)) if match(i)), None)
    if hit is None and n > 2:  # whisper may garble one word; fall back to two
        hit = next((i for i in range(pos, len(words) - 1)
                    if words[i][0][:4] == ws[0][:4] and words[i + 1][0][:3] == ws[1][:3]), None)
    if hit is None:
        print(f"WARN: could not align paragraph starting {' '.join(ws[:3])!r} - check by hand")
        hit = pos
    # skip most of this paragraph so its own words can't match the next one; keep slack for dropped words
    starts.append(round(words[hit][1], 2)); pos = hit + max(1, int(len(ws) * 0.6))
json.dump(starts, open("para_starts.json", "w"))
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", "vo_full.m4a"], capture_output=True, text=True).stdout)
print(f"take {dur:.1f}s, {len(paras)} paragraphs")
for t, p in zip(starts, paras): print(f"  {t:6.2f}  {p[:60]}")
