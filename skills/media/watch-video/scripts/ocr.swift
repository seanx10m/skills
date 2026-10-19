// Native macOS OCR via the Vision framework. No pip, no brew - the point is that
// reading a slide's text costs no image tokens at all.
// Usage: ocr <image> [image ...]   ->   <<<FILE:path>>> followed by its lines.
import Foundation
import Vision
import AppKit

for path in CommandLine.arguments.dropFirst() {
    print("<<<FILE:\(path)>>>")
    guard let img = NSImage(contentsOfFile: path),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = true
    try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
    for obs in (req.results ?? []) {
        if let c = obs.topCandidates(1).first, c.confidence > 0.3 { print(c.string) }
    }
}
