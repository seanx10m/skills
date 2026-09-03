import Foundation
import AVFoundation

// personal-say-tofile — render synthesized speech straight to a WAV file
// (no live playback / no recording needed). Usage: personal-say-tofile <out.wav> <text...>
//
// IMPORTANT — Personal Voice CANNOT be exported to a file. (Verified 2026-07-07.)
// AVSpeechSynthesizer.write(_:toBufferCallback:) works fine for ordinary system
// voices (Samantha, etc.) from a plain unsigned CLI binary — buffers arrive and a
// valid WAV is written. But for a *Personal Voice* the completion closure NEVER
// fires: no buffers are ever delivered and the process hangs indefinitely.
//
// This is a deliberate Apple privacy restriction, NOT a signing/bundling problem.
// Personal Voice authorization succeeds (requestPersonalVoiceAuthorization -> .authorized),
// yet the offline render path is blocked so the cloned voice audio can never be
// exfiltrated to disk — it may only be spoken to live audio output via speak().
// Confirmed the block is unaffected by: ad-hoc codesign (`codesign --sign -`),
// wrapping as a .app bundle with a real Info.plist, or both together. In every
// case a system voice exports and a Personal Voice hangs. There is no public
// entitlement to unlock Personal Voice export.
//
// Net: getting Personal Voice into a file requires an audio loopback driver
// (e.g. BlackHole) capturing speak() output, or mic re-recording — there is no
// pure in-process AVFoundation route. This tool therefore only usefully exports
// ORDINARY voices; it detects the Personal-Voice hang with a watchdog and exits
// with a clear error instead of hanging forever.

func err(_ s: String) { FileHandle.standardError.write((s + "\n").data(using: .utf8)!) }

let args = CommandLine.arguments.dropFirst()
guard args.count >= 2, let outPath = args.first else {
    err("usage: personal-say-tofile <out.wav> <text...>")
    exit(1)
}
let text = args.dropFirst().joined(separator: " ")

let want = ProcessInfo.processInfo.environment["TALKTOME_VOICE"] ?? "auto"

func personalVoices() -> [AVSpeechSynthesisVoice] {
    AVSpeechSynthesisVoice.speechVoices().filter { $0.voiceTraits.contains(.isPersonalVoice) }
}
func norm(_ s: String) -> String { s.replacingOccurrences(of: "\u{2019}", with: "'").lowercased() }
func pickVoice() -> AVSpeechSynthesisVoice? {
    let personals = personalVoices()
    if want.lowercased() == "auto" { return personals.first }
    let w = norm(want)
    if let exact = personals.first(where: { norm($0.name) == w }) { return exact }
    if let sub = personals.first(where: { norm($0.name).contains(w) }) { return sub }
    return personals.first
}

let voice = pickVoice()
if voice == nil { err("personal-say-tofile: no Personal Voice available — using system default") }

let u = AVSpeechUtterance(string: text)
if let v = voice { u.voice = v }
let mult = Double(ProcessInfo.processInfo.environment["TALKTOME_RATE"] ?? "1.0") ?? 1.0
u.rate = min(max(AVSpeechUtteranceDefaultSpeechRate * Float(mult), AVSpeechUtteranceMinimumSpeechRate), AVSpeechUtteranceMaximumSpeechRate)

let synth = AVSpeechSynthesizer()
var outFile: AVAudioFile?

let isPersonal = voice?.voiceTraits.contains(.isPersonalVoice) ?? false

func render() {
    err("render() called, voice=\(String(describing: voice?.name)) personal=\(isPersonal)")

    // Watchdog: Personal Voice never delivers buffers via write(); it would hang
    // forever. If nothing arrives shortly, bail with a clear, actionable error.
    if isPersonal {
        DispatchQueue.main.asyncAfter(deadline: .now() + 8) {
            err("personal-say-tofile: ERROR — Personal Voice (\(voice?.name ?? "?")) cannot be exported to a file.")
            err("  AVSpeechSynthesizer.write() delivers no buffers for Personal Voices (Apple privacy restriction).")
            err("  Use an ordinary system voice for file export, or capture speak() via an audio loopback driver.")
            exit(2)
        }
    }

    synth.write(u) { (buffer: AVAudioBuffer) in
        guard let pcm = buffer as? AVAudioPCMBuffer else { return }
        if pcm.frameLength == 0 {
            exit(0)
        }
        if outFile == nil {
            do {
                outFile = try AVAudioFile(forWriting: URL(fileURLWithPath: outPath), settings: pcm.format.settings)
            } catch {
                err("failed to open output file: \(error)")
                exit(1)
            }
        }
        do {
            try outFile?.write(from: pcm)
        } catch {
            err("write failed: \(error)")
        }
    }
}

if #available(macOS 14.0, *) {
    AVSpeechSynthesizer.requestPersonalVoiceAuthorization { status in
        DispatchQueue.main.async {
            if status != .authorized {
                err("personal-say-tofile: Personal Voice not authorized (status \(status.rawValue)) — using system default")
            }
            render()
        }
    }
} else {
    render()
}

RunLoop.main.run()
