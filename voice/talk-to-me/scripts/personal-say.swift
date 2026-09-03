import Foundation
import AVFoundation

// personal-say — speak text through a macOS Personal Voice.
// Text comes from argv (joined) or, if none, from stdin.
// Voice selection: env TALKTOME_VOICE
//   - a name substring → match that personal voice
//   - "auto" (default) → first available personal voice
// Falls back to any personal voice, then to the system default voice.

let synth = AVSpeechSynthesizer()

final class Done: NSObject, AVSpeechSynthesizerDelegate {
    func speechSynthesizer(_ s: AVSpeechSynthesizer, didFinish u: AVSpeechUtterance) { exit(0) }
    func speechSynthesizer(_ s: AVSpeechSynthesizer, didCancel u: AVSpeechUtterance) { exit(0) }
}
let done = Done()
synth.delegate = done

func err(_ s: String) { FileHandle.standardError.write((s + "\n").data(using: .utf8)!) }

// gather text
var text = CommandLine.arguments.dropFirst().joined(separator: " ")
if text.isEmpty {
    let data = FileHandle.standardInput.readDataToEndOfFile()
    text = String(data: data, encoding: .utf8) ?? ""
}
text = text.trimmingCharacters(in: .whitespacesAndNewlines)
guard !text.isEmpty else { exit(0) }

let want = ProcessInfo.processInfo.environment["TALKTOME_VOICE"] ?? "auto"

func personalVoices() -> [AVSpeechSynthesisVoice] {
    AVSpeechSynthesisVoice.speechVoices().filter { $0.voiceTraits.contains(.isPersonalVoice) }
}

// normalize curly/straight apostrophes so a name with "'" matches one with "’"
func norm(_ s: String) -> String {
    s.replacingOccurrences(of: "\u{2019}", with: "'").lowercased()
}

func pickVoice() -> AVSpeechSynthesisVoice? {
    let personals = personalVoices()
    if want.lowercased() == "auto" { return personals.first }
    let w = norm(want)
    if let exact = personals.first(where: { norm($0.name) == w }) { return exact }
    if let sub = personals.first(where: { norm($0.name).contains(w) }) { return sub }
    return personals.first
}

func speak() {
    let voice = pickVoice()
    if voice == nil { err("personal-say: no Personal Voice available — using system default") }
    let u = AVSpeechUtterance(string: text)
    if let v = voice { u.voice = v }

    // rate: TALKTOME_RATE is a multiplier on Apple's default rate (1.0 = normal).
    let mult = Double(ProcessInfo.processInfo.environment["TALKTOME_RATE"] ?? "1.0") ?? 1.0
    let target = AVSpeechUtteranceDefaultSpeechRate * Float(mult)
    u.rate = min(max(target, AVSpeechUtteranceMinimumSpeechRate), AVSpeechUtteranceMaximumSpeechRate)

    synth.speak(u)
}

if #available(macOS 14.0, *) {
    AVSpeechSynthesizer.requestPersonalVoiceAuthorization { status in
        DispatchQueue.main.async {
            if status != .authorized {
                err("personal-say: Personal Voice not authorized (status \(status.rawValue)) — using system default")
            }
            speak()
        }
    }
} else {
    speak()
}

RunLoop.main.run()
