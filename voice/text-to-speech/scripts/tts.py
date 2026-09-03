#!/usr/bin/env python3
"""Text-to-speech via OpenAI. Standard library only — no pip deps.

The API key is read from the macOS Keychain (service "openai-api-key",
account "openai-tts"), with an OPENAI_API_KEY env var taking precedence.

Usage examples:
    python3 tts.py "Hello there, this is a test."
    echo "a longer blob of text" | python3 tts.py --voice nova --play
    python3 tts.py -f notes.txt -o ~/Desktop/notes.mp3
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

KEYFILE = "~/.config/openai-key"
KEYCHAIN_ACCOUNT = "openai-tts"
KEYCHAIN_SERVICE = "openai-api-key"
ENDPOINT = "https://api.openai.com/v1/audio/speech"
VOICES = ["alloy", "ash", "ballad", "coral", "echo", "fable",
          "onyx", "nova", "sage", "shimmer", "verse"]
FORMATS = ["mp3", "opus", "aac", "flac", "wav", "pcm"]


def get_key():
    """OPENAI_API_KEY env wins, then ~/.config/openai-key (same file image-gen
    reads), then the macOS Keychain."""
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
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        sys.exit("ERROR: OpenAI API key not found. Set OPENAI_API_KEY or store "
                 "it with:\n  security add-generic-password -a openai-tts "
                 "-s openai-api-key -w 'sk-...' -U")


def resolve_text(args):
    if args.file:
        with open(os.path.expanduser(args.file), encoding="utf-8") as fh:
            text = fh.read()
    elif args.text:
        text = args.text
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        sys.exit("ERROR: no input text (pass an argument, --file, or pipe stdin).")
    text = text.strip()
    if not text:
        sys.exit("ERROR: input text is empty.")
    return text


def main():
    p = argparse.ArgumentParser(description="OpenAI text-to-speech.")
    p.add_argument("text", nargs="?", help="Text to speak. Omit to read stdin.")
    p.add_argument("-f", "--file", help="Read text from a file instead.")
    p.add_argument("-v", "--voice", default="alloy", choices=VOICES,
                   help="Voice (default: alloy).")
    p.add_argument("-m", "--model", default="gpt-4o-mini-tts",
                   help="Model (default: gpt-4o-mini-tts; also tts-1, tts-1-hd).")
    p.add_argument("--format", default="mp3", choices=FORMATS,
                   help="Audio format (default: mp3).")
    p.add_argument("-i", "--instructions",
                   help="Tone/style guidance (gpt-4o-mini-tts only).")
    p.add_argument("--speed", type=float, default=1.0,
                   help="0.25-4.0; best on tts-1/tts-1-hd (default: 1.0).")
    p.add_argument("-o", "--out", help="Output path (default: ~/Desktop/tts-<ts>.<fmt>).")
    p.add_argument("--play", action="store_true", help="Play with afplay after saving.")
    args = p.parse_args()

    text = resolve_text(args)

    out = args.out
    if not out:
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        out = f"~/Desktop/tts-{ts}.{args.format}"
    out = os.path.expanduser(out)

    body = {
        "model": args.model,
        "input": text,
        "voice": args.voice,
        "response_format": args.format,
    }
    if args.speed != 1.0:
        body["speed"] = args.speed
    if args.instructions:
        body["instructions"] = args.instructions

    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {get_key()}",
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            audio = r.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        sys.exit(f"ERROR {e.code}: {detail}")
    except urllib.error.URLError as e:
        sys.exit(f"ERROR: request failed: {e.reason}")

    with open(out, "wb") as fh:
        fh.write(audio)
    print(out)

    if args.play:
        subprocess.run(["afplay", out], check=False)


if __name__ == "__main__":
    main()
