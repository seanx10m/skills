# Investigation notes (2026-07-07)

Two parallel attempts were made to get a macOS Personal Voice into a file:

**Pure Swift/AVFoundation (dead end).** `AVSpeechSynthesizer.write(_:toBufferCallback:)`
is Apple's only documented offline TTS-to-buffer API. It works perfectly for ordinary
system voices from a plain unsigned CLI binary — confirmed by exporting Samantha
end-to-end. For a Personal Voice, the completion closure never fires; no buffers are
ever delivered and the process hangs indefinitely. `requestPersonalVoiceAuthorization`
still reports `.authorized`, so the block is downstream in the synthesis pipeline, not
an auth failure. Tried and ruled out: ad-hoc codesigning (`codesign --sign -`), wrapping
as a full `.app` bundle with a real `Info.plist`, and both combined — the same binary
exports a system voice fine and hangs on Personal Voice regardless. There is no public
entitlement to unlock this; it's an intentional privacy restriction (Personal Voice
audio must never leave the device except as live speech to output hardware).

**BlackHole loopback (works).** Since Personal Voice can only ever be *spoken*, capture
what it speaks. Route system audio output to a virtual loopback device (BlackHole)
instead of speakers, record that device's input side with ffmpeg, run `personal-say`
normally, stop the capture, restore the original output device, transcode to MP4.
This is what `scripts/record.sh` automates.

Net: getting Personal Voice into a file requires either this loopback approach, or
physically re-recording speaker output via a microphone. There is no in-process route.
