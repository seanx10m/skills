import Cocoa
import AVFoundation

// talk-reader — speak text in a Personal Voice while showing a floating, top-of-screen
// "karaoke" panel that highlights each word as it's spoken and auto-scrolls.
// Controls: big centered ⏸/▶ pause-resume at the bottom, ✕ close bottom-right. Draggable.
//   • Click any word to (re)start reading from that word.
//   • Scroll freely; long text scrolls, auto-scroll follows the spoken word.
// Non-activating (won't steal focus). Keyboard: Space=pause, Esc=close (when focused).
// Global control via signals: SIGUSR1 toggles pause.
//   → "Pause Talking" Quick Action runs:  pkill -SIGUSR1 -x talk-reader
// Text from argv (joined) or stdin. Voice/rate via TALKTOME_VOICE / TALKTOME_RATE.
// Auto-closes when finished.

func readInput() -> String {
    var t = CommandLine.arguments.dropFirst().joined(separator: " ")
    if t.isEmpty {
        t = String(data: FileHandle.standardInput.readDataToEndOfFile(), encoding: .utf8) ?? ""
    }
    return t.trimmingCharacters(in: .whitespacesAndNewlines)
}

let text = readInput()
let spoolPath = ProcessInfo.processInfo.environment["TALKTOME_SPOOL"] ?? ""
if text.isEmpty && spoolPath.isEmpty { exit(0) }

let want = ProcessInfo.processInfo.environment["TALKTOME_VOICE"] ?? "auto"
let mult = Double(ProcessInfo.processInfo.environment["TALKTOME_RATE"] ?? "1.0") ?? 1.0
// The user's own Personal Voice. Their prompts are read back in it, never in the reply voice.
let meWant = ProcessInfo.processInfo.environment["TALKTOME_ME_VOICE"] ?? "me"

func norm(_ s: String) -> String { s.replacingOccurrences(of: "\u{2019}", with: "'").lowercased() }

// ── brand theme ──────────────────────────────────────────────────────────────
// Values copied from brand's frontend cache:
//   less-variables/lib/colors/light-colors/colors.css  (--palette-* tokens)
//   --brand-primary-brand-pank for the signature magenta.
// Light-mode primary, density-first, no glassmorphism — per the brand-frontend skill.
enum Brand {
    static func c(_ r: Int, _ g: Int, _ b: Int, _ a: CGFloat = 1) -> NSColor {
        NSColor(srgbRed: CGFloat(r) / 255, green: CGFloat(g) / 255, blue: CGFloat(b) / 255, alpha: a)
    }
    static let gray0    = c(255, 255, 255)   // white (button fill)
    static let paper    = c(252, 252, 253)   // content surface — near-white
    static let gray10   = c(248, 248, 249)   // header/footer bar tint (--palette-gray-10)
    static let gray20   = c(244, 244, 247)   // ghost-button chip fill (--palette-gray-20)
    static let gray30   = c(234, 236, 241)   // hairline divider
    static let gray40   = c(218, 220, 229)   // panel border
    static let gray50   = c(186, 188, 197)   // resize-grip hairlines (--palette-gray-50)
    static let gray60   = c(154, 156, 165)   // upcoming (not-yet-spoken) text
    static let gray70   = c(106, 108, 117)   // ghost icon (legacy)
    static let gray80   = c(74,  76,  85)    // secondary control icon (--palette-gray-80)
    static let gray100  = c(42,  44,  53)    // spoken-trail text
    static let teal10   = c(215, 239, 246)   // active-state tint (--palette-teal-10)
    static let teal70   = c(26,  127, 147)   // primary fill + active indicator (--palette-teal-70)
    static let teal80   = c(1,   105, 126)   // primary button border (--palette-teal-80)
    static let pank     = c(255, 72,  118)   // --brand-primary-brand-pank (reserved for create only)

    // Inter is the brand body face (installed system-wide here). Fall back gracefully.
    static func font(_ size: CGFloat, _ style: String, system: NSFont.Weight) -> NSFont {
        NSFont(name: "Inter-\(style)", size: size)
            ?? NSFont(name: "Inter", size: size)
            ?? NSFont.systemFont(ofSize: size, weight: system)
    }
}

// ── Inline markdown (the small subset the terminal shows) ────────────────────
// We render **bold**, *italic*, and `code`. Markers are stripped and the inner text
// kept; the returned plain string is what we BOTH display and speak, so the karaoke
// highlight (which indexes the spoken string) stays aligned with what's on screen.
// Unmatched markers are left literal. Underscores are deliberately NOT emphasis —
// they collide with the code identifiers (users_table, __init__) that fill dev
// narration; block-level markers (#, >, bullets) are stripped upstream in the hook.
enum InlineKind { case bold, italic, code }

func parseInline(_ src: String) -> (text: String, runs: [(NSRange, InlineKind)]) {
    let chars = Array(src)
    let n = chars.count
    var out = String()
    var runs: [(NSRange, InlineKind)] = []
    var i = 0

    func isSpace(_ c: Character) -> Bool { c == " " || c == "\t" || c == "\n" }
    func appendSpan(_ inner: [Character], _ kind: InlineKind) {
        let start = (out as NSString).length
        let s = String(inner)
        out += s
        runs.append((NSRange(location: start, length: (s as NSString).length), kind))
    }

    while i < n {
        let c = chars[i]
        // **bold**
        if c == "*", i + 1 < n, chars[i + 1] == "*" {
            var j = i + 2, inner: [Character] = [], closed = false
            while j < n {
                if chars[j] == "*", j + 1 < n, chars[j + 1] == "*" { closed = true; break }
                inner.append(chars[j]); j += 1
            }
            if closed && !inner.isEmpty { appendSpan(inner, .bold); i = j + 2; continue }
        }
        // *italic* — no whitespace just inside the markers (markdown rule; also keeps a
        // stray "a * b" from being swallowed), and it never spans a line break.
        if c == "*", i + 1 < n, !isSpace(chars[i + 1]) {
            var j = i + 1, inner: [Character] = [], closed = false
            while j < n {
                if chars[j] == "*" { closed = true; break }
                if chars[j] == "\n" { break }
                inner.append(chars[j]); j += 1
            }
            if closed, let last = inner.last, !isSpace(last) { appendSpan(inner, .italic); i = j + 1; continue }
        }
        // `code`
        if c == "`" {
            var j = i + 1, inner: [Character] = [], closed = false
            while j < n {
                if chars[j] == "`" { closed = true; break }
                if chars[j] == "\n" { break }
                inner.append(chars[j]); j += 1
            }
            if closed && !inner.isEmpty { appendSpan(inner, .code); i = j + 1; continue }
        }
        out.append(c); i += 1
    }
    return (out, runs)
}

// Text view that reports the character index of a click.
final class ClickableTextView: NSTextView {
    var onClickIndex: ((Int) -> Void)?
    override func mouseDown(with event: NSEvent) {
        let p = convert(event.locationInWindow, from: nil)
        let idx = characterIndexForInsertion(at: p)
        onClickIndex?(idx)
    }
}

// Bottom-right resize handle: draws the classic diagonal grip and drags the window's
// size live while pinning the top-left corner (so the panel "grows" downward/rightward).
final class ResizeGrip: NSView {
    var minSize = NSSize(width: 380, height: 176)
    private var startMouse = NSPoint.zero
    private var startFrame = NSRect.zero

    override func draw(_ dirty: NSRect) {
        Brand.gray50.setStroke()
        let p = NSBezierPath(); p.lineWidth = 1.5; p.lineCapStyle = .round
        for d: CGFloat in [3, 7, 11] {
            p.move(to: NSPoint(x: bounds.maxX - d, y: bounds.minY))
            p.line(to: NSPoint(x: bounds.maxX, y: bounds.minY + d))
        }
        p.stroke()
    }

    override func resetCursorRects() { addCursorRect(bounds, cursor: .crosshair) }

    override func mouseDown(with e: NSEvent) {
        guard let w = window else { return }
        startMouse = NSEvent.mouseLocation
        startFrame = w.frame
    }
    override func mouseDragged(with e: NSEvent) {
        guard let w = window else { return }
        let now = NSEvent.mouseLocation
        let newW = max(minSize.width, startFrame.width + (now.x - startMouse.x))
        let newH = max(minSize.height, startFrame.height - (now.y - startMouse.y))
        // keep the top-left corner fixed (NSWindow origin is bottom-left)
        let f = NSRect(x: startFrame.minX, y: startFrame.maxY - newH, width: newW, height: newH)
        w.setFrame(f, display: true, animate: false)
    }
}

// ── Dino face ───────────────────────────────────────────────────────────────────
// The pixel dinosaur, drawn from its native 24×24 grid. Rows 12–16 are the mouth;
// five patches over those rows give five jaw positions. No sprite sheet, no PNGs —
// `level` is the whole interface.
final class RexFace: NSView {
    static let pink = NSColor(srgbRed: 255/255.0, green: 72/255.0, blue: 118/255.0, alpha: 1)
    static let body = [
        "........................", "........................",
        "........................", "........................",
        "........###########.....", ".......#############....",
        "......###############...", "###############.######..",
        "###############.#######.", "###..##########.########",
        "########################", "########################",
        ".##..##.##.#############", "..#..#..##.#############",
        "...........#############", "...##.##.###############",
        "...##.##.###############", ".######################.",
        ".#####################..", ".####################...",
        "........................", "........................",
        "........................", "........................",
    ]
    static let mouths: [[String]] = [
        [".##..##.##.", "...########", "...########", "...########", "...########"],  // shut
        [".##..##.##.", "...##.##.##", "...########", "...########", "...########"],
        [".##..##.##.", "..#..#..##.", "...##.##.##", "...########", "...########"],
        [".##..##.##.", "..#..#..##.", "...........", "...##.##.##", "...##.##.##"],
        [".##..##.##.", "..#..#..##.", "...........", "...........", "...##.##.##"],  // wide
    ]

    var level = 0 { didSet { if level != oldValue { needsDisplay = true } } }
    override var isFlipped: Bool { true }

    override func draw(_ dirty: NSRect) {
        var rows = RexFace.body
        for (i, patch) in RexFace.mouths[max(0, min(4, level))].enumerated() {
            var chars = Array(rows[12 + i])
            for (j, ch) in patch.enumerated() { chars[j] = ch }
            rows[12 + i] = String(chars)
        }
        // No antialiasing, so the mark stays crisp at header size without forcing an
        // integer scale. Cell BOUNDARIES are rounded, never each rect independently:
        // at 34pt a cell is 1.4px, and rounding rects separately lets neighbours grow
        // into a 1-cell gap and swallow it — which is how the eye disappears.
        NSGraphicsContext.current?.shouldAntialias = false
        let px = min(bounds.width, bounds.height) / 24
        let ox = (bounds.width - px * 24) / 2
        let oy = (bounds.height - px * 24) / 2
        let edge = (0...24).map { (ox + CGFloat($0) * px).rounded() }
        let edgeY = (0...24).map { (oy + CGFloat($0) * px).rounded() }
        RexFace.pink.setFill()
        for (y, row) in rows.enumerated() {
            for (x, ch) in row.enumerated() where ch == "#" {
                NSBezierPath(rect: NSRect(x: edge[x], y: edgeY[y],
                                          width: edge[x + 1] - edge[x],
                                          height: edgeY[y + 1] - edgeY[y])).fill()
            }
        }
    }
}

// Letters → jaw openness. Driven by WHERE a sound is made, not how loud it is:
// open vowels drop the jaw, bilabials (m/b/p) shut it, fricatives barely move it.
// Runs of vowels and runs of consonants each collapse to one viseme, so a word
// yields a syllable-ish cadence instead of a twitch per letter.
func visemes(for word: String) -> [Int] {
    let jaw: [Character: Int] = [
        "a": 4, "o": 3, "u": 3, "w": 3, "e": 2, "i": 2, "y": 2,
        "m": 0, "b": 0, "p": 0,
        "l": 2, "r": 2, "g": 2, "k": 2, "q": 2,
        "f": 1, "v": 1, "s": 1, "z": 1, "c": 1, "t": 1, "d": 1, "n": 1, "h": 1, "j": 1, "x": 1,
    ]
    let vowels = Set("aeiouy")
    var out: [Int] = []
    var runVowel: Bool? = nil
    var runMax = 0
    for ch in word.lowercased() where ch.isLetter {
        let isV = vowels.contains(ch)
        let lvl = jaw[ch] ?? 1
        if runVowel == isV {
            runMax = max(runMax, lvl)
        } else {
            if runVowel != nil { out.append(runMax) }
            runVowel = isV
            runMax = lvl
        }
    }
    if runVowel != nil { out.append(runMax) }
    return out.isEmpty ? [1] : out
}

final class Controller: NSObject, AVSpeechSynthesizerDelegate, NSWindowDelegate {
    let synth = AVSpeechSynthesizer()
    var text: String
    var ns: NSString
    var panel: NSPanel!
    var textView: ClickableTextView!
    var pauseButton: NSButton!
    var isPaused = false
    var restarting = false          // suppress finish() during a click-driven restart
    var baseOffset = 0              // start of the current utterance within `text`
    var spokenIndex = 0             // start of the word currently being spoken (absolute)
    var rate = mult                 // live speed multiplier; the speed selector mutates this
    let speeds: [Double] = [0.75, 1.0, 1.25, 1.5, 1.75, 2.0]
    var speedChip: NSButton!
    var sigSource: DispatchSourceSignal?
    let baseColor = Brand.gray60            // upcoming words, muted
    let spokenColor = Brand.gray100         // spoken trail, full ink
    let hiBack = Brand.teal10               // current-word fill — brand's teal active tint
    let hiRule = Brand.teal70               // 2px teal rule — brand's active indicator (not magenta)
    // Dino mode: the pixel dinosaur lip-syncs in a left gutter instead of a static mark.
    let dinoMode = ProcessInfo.processInfo.environment["TALKTOME_FACE"] == "dino"
    var face: RexFace?
    var faceTimer: Timer?
    var faceSeq: [Int] = []
    var faceStep = 0
    var lastWordAt: CFTimeInterval = 0
    var lastWordLen = 0
    var charsPerSec = 14.0          // learned from the callbacks; survives a speed change
    // Session name for the header caption; magenta is create-only, so the brand mark is the icon.
    lazy var title = ProcessInfo.processInfo.environment["TALKTOME_TITLE"]
        ?? (dinoMode ? "Dino" : "Claude Code")
    let repo = ProcessInfo.processInfo.environment["TALKTOME_REPO"] ?? ""
    let branch = ProcessInfo.processInfo.environment["TALKTOME_BRANCH"] ?? ""
    var inlineRuns: [(NSRange, InlineKind)]   // bold/italic/code spans over `text`
    // live mode: a spool directory the shell hook drops blocks into as the turn streams.
    let spool = ProcessInfo.processInfo.environment["TALKTOME_SPOOL"] ?? ""
    var spoolTimer: Timer?
    var speakEnd = 0                // end of what has been handed to the synthesiser
    var idle = true
    var meRanges: [NSRange] = []                 // spans of the user's own words, in order
    var offsets: [ObjectIdentifier: Int] = [:]   // per-utterance start offset within `text`
    var lastUtt: AVSpeechUtterance?              // only the final utterance ends the run

    init(text raw: String) {
        // Strip inline markers up front so `text`/`ns` (what we speak and index) match
        // the styled string we display — the karaoke highlight depends on that alignment.
        let parsed = parseInline(raw)
        self.text = parsed.text
        self.ns = parsed.text as NSString
        self.inlineRuns = parsed.runs
        super.init()
    }

    // SF Symbol at a deliberate point-size + weight — reads cleaner than the default render.
    func symbol(_ name: String, _ pt: CGFloat, _ weight: NSFont.Weight) -> NSImage? {
        let cfg = NSImage.SymbolConfiguration(pointSize: pt, weight: weight)
        return NSImage(systemSymbolName: name, accessibilityDescription: name)?
            .withSymbolConfiguration(cfg)
    }

    // Load a bundled asset from the skill's assets folder (independent of any app bundle).
    func asset(_ name: String) -> NSImage? {
        let p = (NSHomeDirectory() as NSString)
            .appendingPathComponent(".claude/skills/talk-to-me/assets/\(name)")
        return NSImage(contentsOfFile: p)
    }
    func headerIcon() -> NSImage? { asset("panel-icon.png") ?? symbol("waveform", 14, .medium) }
    func brandLogo() -> NSImage? { asset("brand-logo.png") }

    // Top-left caption = the Claude session name (its ai-title), bold, next to the mark.
    func captionString() -> NSAttributedString {
        NSAttributedString(string: title, attributes: [
            .font: Brand.font(16, "SemiBold", system: .semibold),   // heading reads larger than the body text
            .foregroundColor: Brand.gray100,
        ])
    }

    // GitHub mark — the Octicons silhouette as SVG (vector, tints cleanly as a template).
    // Falls back to the PNG only if the SVG can't be loaded.
    func ghIcon() -> NSImage? {
        let img = asset("github-mark.svg") ?? asset("github-icon.png")
        img?.isTemplate = true
        return img
    }

    // Footer-left git context: repo (bold) + branch (muted). nil when not in a repo.
    func gitCaption() -> NSAttributedString? {
        guard !repo.isEmpty || !branch.isEmpty else { return nil }
        let s = NSMutableAttributedString()
        if !repo.isEmpty {
            s.append(NSAttributedString(string: repo, attributes: [
                .font: Brand.font(11, "SemiBold", system: .semibold), .foregroundColor: Brand.gray80]))
        }
        if !branch.isEmpty {
            if !repo.isEmpty {
                s.append(NSAttributedString(string: "  ", attributes: [.font: Brand.font(11, "Regular", system: .regular)]))
            }
            s.append(NSAttributedString(string: branch, attributes: [
                .font: Brand.font(11, "Regular", system: .regular), .foregroundColor: Brand.gray60]))
        }
        return s
    }

    func buildWindow() {
        let screen = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1280, height: 800)
        let w = min(900, screen.width * 0.7)
        let h: CGFloat = 224
        let x = screen.midX - w / 2
        let y = screen.maxY - h - 24
        let frame = NSRect(x: x, y: y, width: w, height: h)

        // .resizable on a borderless panel → drag any edge to expand; Auto Layout reflows live.
        panel = NSPanel(contentRect: frame,
                        styleMask: [.borderless, .nonactivatingPanel, .resizable],
                        backing: .buffered, defer: false)
        panel.isFloatingPanel = true
        panel.level = .floating
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = true
        panel.isMovableByWindowBackground = true
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.delegate = self
        panel.minSize = NSSize(width: 460, height: 184)
        // Light-mode primary: hold the brand light theme even when macOS is in dark mode.
        panel.appearance = NSAppearance(named: .aqua)

        // Solid brand surface — near-white body, hairline border, tight radius.
        let surface = NSView(frame: NSRect(origin: .zero, size: frame.size))
        surface.wantsLayer = true
        surface.layer?.backgroundColor = Brand.paper.cgColor
        surface.layer?.cornerRadius = 4          // a touch tighter than before
        surface.layer?.masksToBounds = true
        surface.layer?.borderWidth = 1
        surface.layer?.borderColor = Brand.gray40.cgColor
        panel.contentView = surface

        // ── Header (tinted bar): robot mark + session name (left) · brand logo (right) ──
        let header = NSView(); header.wantsLayer = true
        header.layer?.backgroundColor = Brand.gray10.cgColor
        header.translatesAutoresizingMaskIntoConstraints = false
        surface.addSubview(header)

        // The header mark. In dino mode it is a live view that lip-syncs, not an image —
        // one face, in the spot the eye already goes for branding.
        let icon: NSView
        if dinoMode {
            let f = RexFace()
            face = f
            icon = f
        } else {
            let iv = NSImageView()
            iv.image = headerIcon()
            iv.imageScaling = .scaleProportionallyUpOrDown  // transparent sticker — fit, don't crop
            icon = iv
        }
        icon.translatesAutoresizingMaskIntoConstraints = false
        header.addSubview(icon)

        let caption = NSTextField(labelWithAttributedString: captionString())
        caption.translatesAutoresizingMaskIntoConstraints = false
        caption.lineBreakMode = .byTruncatingTail
        header.addSubview(caption)

        let logo = NSImageView()
        logo.translatesAutoresizingMaskIntoConstraints = false
        logo.image = brandLogo()
        logo.imageScaling = .scaleProportionallyUpOrDown
        logo.toolTip = "brand"
        header.addSubview(logo)

        let headRule = NSView(); headRule.wantsLayer = true
        headRule.layer?.backgroundColor = Brand.gray40.cgColor   // clear connecting border
        headRule.translatesAutoresizingMaskIntoConstraints = false
        header.addSubview(headRule)

        // ── Control bar (tinted footer): restart · play/pause (teal) · stop — centered ──
        let bar = NSView(); bar.wantsLayer = true
        bar.layer?.backgroundColor = Brand.gray10.cgColor
        bar.translatesAutoresizingMaskIntoConstraints = false
        surface.addSubview(bar)

        let barRule = NSView(); barRule.wantsLayer = true
        barRule.layer?.backgroundColor = Brand.gray40.cgColor   // clear border splitting body from footer
        barRule.translatesAutoresizingMaskIntoConstraints = false
        bar.addSubview(barRule)

        // secondary control: bare gray glyph — no disc, no border
        func ghost(_ sym: String, _ action: Selector, _ tip: String) -> NSButton {
            let b = NSButton(title: "", target: self, action: action)
            b.translatesAutoresizingMaskIntoConstraints = false
            b.isBordered = false
            b.image = symbol(sym, 17, .medium)
            b.imagePosition = .imageOnly
            b.imageScaling = .scaleNone   // draw the glyph at its exact size — it cannot stretch
            b.contentTintColor = Brand.gray80
            b.toolTip = tip
            return b
        }

        let restart = ghost("arrow.counterclockwise", #selector(restartReading), "Restart")

        // primary control: bare teal glyph — no disc — larger than its gray siblings
        pauseButton = NSButton(title: "", target: self, action: #selector(togglePause))
        pauseButton.translatesAutoresizingMaskIntoConstraints = false
        pauseButton.isBordered = false
        pauseButton.contentTintColor = Brand.teal70   // the icon itself is the teal accent
        pauseButton.imagePosition = .imageOnly
        pauseButton.imageScaling = .scaleNone   // exact size, centered — cannot stretch
        pauseButton.keyEquivalent = " "
        applyPauseStyle()

        let stop = ghost("stop.fill", #selector(stopReading), "Stop")
        stop.keyEquivalent = "\u{1b}"

        // speed chip — bare, gray, on-theme; drops a menu of paces, applied from the current word
        speedChip = NSButton(title: "", target: self, action: #selector(showSpeedMenu))
        speedChip.translatesAutoresizingMaskIntoConstraints = false
        speedChip.isBordered = false
        speedChip.image = symbol("chevron.down", 9, .semibold)
        speedChip.imagePosition = .imageRight
        speedChip.imageScaling = .scaleNone
        speedChip.contentTintColor = Brand.gray80
        speedChip.toolTip = "Reading speed"
        styleSpeedChip()

        // one centered row holding every control, evenly spaced
        let cluster = NSStackView(views: [restart, pauseButton, stop, speedChip])
        cluster.translatesAutoresizingMaskIntoConstraints = false
        cluster.orientation = .horizontal
        cluster.alignment = .centerY
        cluster.spacing = 16
        bar.addSubview(cluster)

        // footer-left: GitHub mark + repo/branch (only when launched inside a git repo)
        var ghViews: (NSImageView, NSTextField)? = nil
        if let gitCap = gitCaption() {
            let gh = NSImageView()
            gh.translatesAutoresizingMaskIntoConstraints = false
            gh.image = ghIcon()
            gh.imageScaling = .scaleProportionallyDown
            gh.contentTintColor = Brand.gray70
            gh.toolTip = repo.isEmpty ? branch : "\(repo) / \(branch)"
            bar.addSubview(gh)

            let gitLabel = NSTextField(labelWithAttributedString: gitCap)
            gitLabel.translatesAutoresizingMaskIntoConstraints = false
            gitLabel.lineBreakMode = .byTruncatingTail
            gitLabel.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
            gitLabel.toolTip = gh.toolTip
            bar.addSubview(gitLabel)
            ghViews = (gh, gitLabel)
        }

        // ── Text scroller (fills the middle, reflows on resize) ─────────────────────
        let scroll = NSScrollView()
        scroll.translatesAutoresizingMaskIntoConstraints = false
        scroll.hasVerticalScroller = true
        scroll.autohidesScrollers = true
        scroll.drawsBackground = false

        let tv = ClickableTextView()
        tv.isEditable = false
        tv.isSelectable = false
        tv.drawsBackground = false
        tv.textContainerInset = NSSize(width: 4, height: 6)
        tv.autoresizingMask = [.width]
        tv.textContainer?.widthTracksTextView = true
        tv.onClickIndex = { [weak self] idx in self?.startFromClick(idx) }

        tv.textStorage?.setAttributedString(styledAttr(plain: text, runs: inlineRuns))
        textView = tv
        scroll.documentView = tv
        surface.addSubview(scroll)

        // bottom-right resize grip — a clear handle to grab (edges still resize too)
        let grip = ResizeGrip()
        grip.minSize = panel.minSize
        grip.translatesAutoresizingMaskIntoConstraints = false
        surface.addSubview(grip)   // added last → sits on top of the bar, catches the drag

        let headerH: CGFloat = dinoMode ? 56 : 46, barH: CGFloat = 64
        var cons: [NSLayoutConstraint] = [
            header.topAnchor.constraint(equalTo: surface.topAnchor),
            header.leadingAnchor.constraint(equalTo: surface.leadingAnchor),
            header.trailingAnchor.constraint(equalTo: surface.trailingAnchor),
            header.heightAnchor.constraint(equalToConstant: headerH),

            icon.leadingAnchor.constraint(equalTo: header.leadingAnchor, constant: 14),
            icon.centerYAnchor.constraint(equalTo: header.centerYAnchor),
            icon.widthAnchor.constraint(equalToConstant: dinoMode ? 48 : 28),
            icon.heightAnchor.constraint(equalToConstant: dinoMode ? 48 : 28),

            caption.leadingAnchor.constraint(equalTo: icon.trailingAnchor, constant: 8),
            caption.centerYAnchor.constraint(equalTo: header.centerYAnchor),
            caption.trailingAnchor.constraint(lessThanOrEqualTo: logo.leadingAnchor, constant: -10),

            logo.trailingAnchor.constraint(equalTo: header.trailingAnchor, constant: -14),
            logo.centerYAnchor.constraint(equalTo: header.centerYAnchor),
            logo.widthAnchor.constraint(equalToConstant: 22),
            logo.heightAnchor.constraint(equalToConstant: 22),

            headRule.leadingAnchor.constraint(equalTo: header.leadingAnchor),
            headRule.trailingAnchor.constraint(equalTo: header.trailingAnchor),
            headRule.bottomAnchor.constraint(equalTo: header.bottomAnchor),
            headRule.heightAnchor.constraint(equalToConstant: 1),

            bar.bottomAnchor.constraint(equalTo: surface.bottomAnchor),
            bar.leadingAnchor.constraint(equalTo: surface.leadingAnchor),
            bar.trailingAnchor.constraint(equalTo: surface.trailingAnchor),
            bar.heightAnchor.constraint(equalToConstant: barH),

            barRule.leadingAnchor.constraint(equalTo: bar.leadingAnchor),
            barRule.trailingAnchor.constraint(equalTo: bar.trailingAnchor),
            barRule.topAnchor.constraint(equalTo: bar.topAnchor),
            barRule.heightAnchor.constraint(equalToConstant: 1),

            // one centered control row: restart · play/pause · stop · speed
            cluster.centerXAnchor.constraint(equalTo: bar.centerXAnchor),
            cluster.centerYAnchor.constraint(equalTo: bar.centerYAnchor),

            pauseButton.widthAnchor.constraint(equalToConstant: 42),
            pauseButton.heightAnchor.constraint(equalToConstant: 42),
            restart.widthAnchor.constraint(equalToConstant: 32),
            restart.heightAnchor.constraint(equalToConstant: 32),
            stop.widthAnchor.constraint(equalToConstant: 32),
            stop.heightAnchor.constraint(equalToConstant: 32),

            scroll.topAnchor.constraint(equalTo: header.bottomAnchor),
            scroll.bottomAnchor.constraint(equalTo: bar.topAnchor),
            scroll.trailingAnchor.constraint(equalTo: surface.trailingAnchor, constant: -16),

            grip.trailingAnchor.constraint(equalTo: surface.trailingAnchor, constant: -5),
            grip.bottomAnchor.constraint(equalTo: surface.bottomAnchor, constant: -5),
            grip.widthAnchor.constraint(equalToConstant: 14),
            grip.heightAnchor.constraint(equalToConstant: 14),
        ]
        cons.append(scroll.leadingAnchor.constraint(equalTo: surface.leadingAnchor, constant: 16))
        if let (gh, gitLabel) = ghViews {
            cons += [
                gh.leadingAnchor.constraint(equalTo: bar.leadingAnchor, constant: 14),
                gh.centerYAnchor.constraint(equalTo: pauseButton.centerYAnchor),
                gh.widthAnchor.constraint(equalToConstant: 15),
                gh.heightAnchor.constraint(equalToConstant: 15),

                gitLabel.leadingAnchor.constraint(equalTo: gh.trailingAnchor, constant: 7),
                gitLabel.centerYAnchor.constraint(equalTo: gh.centerYAnchor),
                gitLabel.trailingAnchor.constraint(lessThanOrEqualTo: restart.leadingAnchor, constant: -12),
            ]
        }
        NSLayoutConstraint.activate(cons)
        panel.orderFrontRegardless()
    }

    // Primary glyph — play when paused, pause when speaking. Larger than the gray siblings.
    func applyPauseStyle() {
        pauseButton.image = symbol(isPaused ? "play.fill" : "pause.fill", 24, .medium)
        pauseButton.toolTip = isPaused ? "Resume" : "Pause"
    }

    @objc func togglePause() {
        if isPaused { synth.continueSpeaking(); isPaused = false }
        else { synth.pauseSpeaking(at: .word); isPaused = true; restFace() }
        applyPauseStyle()
    }

    // Restart the whole transcript from the top.
    @objc func restartReading() { speak(from: 0) }

    // "1×", "1.5×", "0.75×" — drop a trailing .0
    func fmt(_ r: Double) -> String {
        (r.truncatingRemainder(dividingBy: 1) == 0 ? String(Int(r)) : String(r)) + "×"
    }

    // Bare gray chip — current speed + a small chevron, styled like the other controls.
    func styleSpeedChip() {
        speedChip.attributedTitle = NSAttributedString(string: fmt(rate) + " ", attributes: [
            .font: Brand.font(12, "SemiBold", system: .semibold),
            .foregroundColor: Brand.gray80,
        ])
    }

    @objc func showSpeedMenu(_ sender: NSButton) {
        let menu = NSMenu()
        menu.font = Brand.font(12, "Regular", system: .regular)
        for (i, s) in speeds.enumerated() {
            let item = NSMenuItem(title: fmt(s), action: #selector(speedMenuItem(_:)), keyEquivalent: "")
            item.target = self; item.tag = i
            item.state = (s == rate) ? .on : .off
            menu.addItem(item)
        }
        menu.popUp(positioning: nil, at: NSPoint(x: 0, y: sender.bounds.height + 4), in: sender)
    }

    @objc func speedMenuItem(_ sender: NSMenuItem) {
        guard sender.tag >= 0 && sender.tag < speeds.count else { return }
        setRate(speeds[sender.tag])
    }

    // Apply a new speed: remember it for next time, refresh the chip, pick up from the current word.
    func setRate(_ r: Double) {
        rate = r
        styleSpeedChip()
        let p = (NSHomeDirectory() as NSString).appendingPathComponent(".claude/skills/talk-to-me/state/rate")
        try? String(r).write(toFile: p, atomically: true, encoding: .utf8)
        if synth.isSpeaking || isPaused { speak(from: spokenIndex) }   // re-speak current word at new pace
    }

    @objc func stopReading() { synth.stopSpeaking(at: .immediate); NSApp.terminate(nil) }

    func installSignalHandler() {
        signal(SIGUSR1, SIG_IGN)
        let src = DispatchSource.makeSignalSource(signal: SIGUSR1, queue: .main)
        src.setEventHandler { [weak self] in self?.togglePause() }
        src.resume()
        sigSource = src
    }

    func pickVoice() -> AVSpeechSynthesisVoice? {
        let personals = AVSpeechSynthesisVoice.speechVoices().filter { $0.voiceTraits.contains(.isPersonalVoice) }
        if want.lowercased() == "auto" { return personals.first }
        let w = norm(want)
        if let e = personals.first(where: { norm($0.name) == w }) { return e }
        if let s = personals.first(where: { norm($0.name).contains(w) }) { return s }
        return personals.first
    }

    // ONE styler for both the initial fill and every live append, so a streamed block is
    // pixel-identical to one that was there from the start.
    func styledAttr(plain: String, runs: [(NSRange, InlineKind)], me: Bool = false) -> NSMutableAttributedString {
        let para = NSMutableParagraphStyle()
        para.lineSpacing = 4
        para.paragraphSpacing = 7        // a visible gap between paragraphs, like the terminal's blank lines
        // The user's own words read as a quote: indented, italic, a size down from the reply.
        if me {
            para.paragraphSpacing = 14
            para.firstLineHeadIndent = 16
            para.headIndent = 16
        }
        let attr = NSMutableAttributedString(string: plain, attributes: [
            .font: me ? NSFontManager.shared.convert(Brand.font(15, "Medium", system: .medium),
                                                     toHaveTrait: .italicFontMask)
                      : Brand.font(18, "Medium", system: .medium),
            .foregroundColor: baseColor,
            .paragraphStyle: para,
        ])
        if me { return attr }
        // Inline styling overlay. Only the FONT (slant/weight/mono) is set here - never the
        // color - because the karaoke repaint owns foreground/background and the font survives
        // it, so bold/italic/code stay distinct as the spoken trail advances over them.
        let boldFont   = Brand.font(18, "SemiBold", system: .semibold)
        let italicFont = NSFontManager.shared.convert(Brand.font(18, "Medium", system: .medium), toHaveTrait: .italicFontMask)
        let codeFont   = NSFont.monospacedSystemFont(ofSize: 16, weight: .medium)
        let total = (plain as NSString).length
        for (r, kind) in runs where NSMaxRange(r) <= total {
            switch kind {
            case .bold:   attr.addAttribute(.font, value: boldFont,   range: r)
            case .italic: attr.addAttribute(.font, value: italicFont, range: r)
            case .code:   attr.addAttribute(.font, value: codeFont,   range: r)
            }
        }
        return attr
    }

    // Append a streamed block to the live panel. Extends the spoken/indexed string and the
    // displayed one together, so the karaoke highlight stays aligned.
    func append(_ raw: String, me: Bool = false) {
        let parsed = parseInline(raw)
        guard !parsed.text.isEmpty, let ts = textView?.textStorage else { return }
        let sep = text.isEmpty ? "" : "\n\n"
        let offset = (text as NSString).length + (sep as NSString).length
        let shifted = parsed.runs.map { (NSRange(location: $0.0.location + offset, length: $0.0.length), $0.1) }
        if me { meRanges.append(NSRange(location: offset, length: (parsed.text as NSString).length)) }
        ts.beginEditing()
        if !sep.isEmpty { ts.append(styledAttr(plain: sep, runs: [])) }
        ts.append(styledAttr(plain: parsed.text, runs: parsed.runs, me: me))
        ts.endEditing()
        text += sep + parsed.text
        ns = text as NSString
        inlineRuns += shifted
        // repaint the already-spoken trail over the grown storage
        if spokenIndex > 0 {
            ts.addAttribute(.foregroundColor, value: spokenColor, range: NSRange(location: 0, length: min(spokenIndex, ts.length)))
        }
        if idle && !isPaused { speak(from: speakEnd) }
    }

    // Watch the spool for blocks the hook drops mid-turn. `.done` means the turn ended, so
    // once the spool is empty and speech has caught up, the panel closes exactly as before.
    func startSpool() {
        guard !spool.isEmpty else { return }
        spoolTimer = Timer.scheduledTimer(withTimeInterval: 0.2, repeats: true) { [weak self] _ in
            guard let self = self else { return }
            let fm = FileManager.default
            let files = ((try? fm.contentsOfDirectory(atPath: self.spool)) ?? [])
                .filter { $0.hasSuffix(".txt") }.sorted()
            for f in files {
                let full = (self.spool as NSString).appendingPathComponent(f)
                let body = (try? String(contentsOfFile: full, encoding: .utf8)) ?? ""
                try? fm.removeItem(atPath: full)
                let t = body.trimmingCharacters(in: .whitespacesAndNewlines)
                if !t.isEmpty { self.append(t, me: f.hasSuffix(".me.txt")) }
            }
            let done = fm.fileExists(atPath: (self.spool as NSString).appendingPathComponent(".done"))
            if done && files.isEmpty && self.idle && self.speakEnd >= self.ns.length && !self.isPaused {
                NSApp.terminate(nil)
            }
        }
    }

    // A reply voice (morgan, lily...) must never speak the user's own words back at them.
    func pickMeVoice() -> AVSpeechSynthesisVoice? {
        let personals = AVSpeechSynthesisVoice.speechVoices().filter { $0.voiceTraits.contains(.isPersonalVoice) }
        let w = norm(meWant)
        return personals.first(where: { norm($0.name) == w })
            ?? personals.first(where: { norm($0.name).contains(w) })
            ?? pickVoice()
    }

    // Split the pending text at every speaker boundary: the user's spans in their voice,
    // everything else in the session voice.
    func segments(from start: Int) -> [(Int, String, AVSpeechSynthesisVoice?)] {
        var out: [(Int, String, AVSpeechSynthesisVoice?)] = []
        var i = start
        while i < ns.length {
            if let r = meRanges.first(where: { NSLocationInRange(i, $0) }) {
                let end = min(NSMaxRange(r), ns.length)
                out.append((i, ns.substring(with: NSRange(location: i, length: end - i)), pickMeVoice()))
                i = end
            } else {
                let next = meRanges.map { $0.location }.filter { $0 > i }.min() ?? ns.length
                out.append((i, ns.substring(with: NSRange(location: i, length: next - i)), pickVoice()))
                i = next
            }
        }
        return out
    }

    func utterance(_ s: String, voice: AVSpeechSynthesisVoice?) -> AVSpeechUtterance {
        let u = AVSpeechUtterance(string: s)
        if let v = voice { u.voice = v }
        u.rate = min(max(AVSpeechUtteranceDefaultSpeechRate * Float(rate),
                         AVSpeechUtteranceMinimumSpeechRate), AVSpeechUtteranceMaximumSpeechRate)
        return u
    }

    // speak `text` starting at character `start`
    func speak(from start: Int) {
        baseOffset = max(0, min(start, ns.length))
        if isPaused { isPaused = false; applyPauseStyle() }
        if synth.isSpeaking {
            restarting = true                  // ignore the resulting didCancel
            synth.stopSpeaking(at: .immediate)
        }
        guard baseOffset < ns.length else { idle = true; return }
        speakEnd = ns.length
        idle = false
        offsets.removeAll()
        lastUtt = nil
        for (off, str, v) in segments(from: baseOffset)
        where !str.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            let u = utterance(str, voice: v)
            offsets[ObjectIdentifier(u)] = off
            lastUtt = u
            synth.speak(u)
        }
        if lastUtt == nil { idle = true }
    }

    // map a click index back to the start of its word, then read from there
    func startFromClick(_ idx: Int) {
        var i = min(idx, ns.length)
        let ws = CharacterSet.whitespacesAndNewlines
        while i > 0, let u = UnicodeScalar(ns.character(at: i - 1)), !ws.contains(u) { i -= 1 }
        speak(from: i)
    }

    func start() {
        installSignalHandler()
        synth.delegate = self
        startSpool()
        AVSpeechSynthesizer.requestPersonalVoiceAuthorization { _ in
            DispatchQueue.main.async { if self.ns.length > 0 { self.speak(from: 0) } }
        }
    }

    func speechSynthesizer(_ s: AVSpeechSynthesizer, didStart u: AVSpeechUtterance) {
        restarting = false
    }

    func speechSynthesizer(_ s: AVSpeechSynthesizer, willSpeakRangeOfSpeechString r: NSRange, utterance u: AVSpeechUtterance) {
        guard let ts = textView.textStorage else { return }
        let loc = r.location + (offsets[ObjectIdentifier(u)] ?? baseOffset)
        spokenIndex = loc                       // remember where we are, for speed-change restarts
        guard loc + r.length <= ts.length else { return }
        let here = NSRange(location: loc, length: r.length)
        let full = NSRange(location: 0, length: ts.length)
        ts.beginEditing()
        // clear previous highlight (fill + underline), then repaint the spoken trail
        ts.removeAttribute(.backgroundColor, range: full)
        ts.removeAttribute(.underlineStyle, range: full)
        ts.removeAttribute(.underlineColor, range: full)
        ts.addAttribute(.foregroundColor, value: spokenColor, range: NSRange(location: 0, length: loc + r.length))
        // current word: crisp solid fill + 2px brand-magenta rule (brand active indicator)
        ts.addAttribute(.backgroundColor, value: hiBack, range: here)
        ts.addAttribute(.underlineStyle, value: NSUnderlineStyle.thick.rawValue, range: here)
        ts.addAttribute(.underlineColor, value: hiRule, range: here)
        ts.endEditing()
        textView.scrollRangeToVisible(here)
        if dinoMode { animateFace(ns.substring(with: here)) }
    }

    // Lip sync off the word callbacks. AVSpeechSynthesizer hands us a range when it
    // STARTS a word but never says how long the word will take — so each callback
    // measures the previous word and feeds a running chars-per-second estimate. That
    // self-corrects within a sentence and survives a mid-read speed change.
    func animateFace(_ word: String) {
        guard let f = face else { return }
        let now = CACurrentMediaTime()
        if lastWordAt > 0, lastWordLen > 0 {
            let d = now - lastWordAt
            if d > 0.04, d < 2.0 { charsPerSec = charsPerSec * 0.7 + (Double(lastWordLen) / d) * 0.3 }
        }
        lastWordAt = now
        lastWordLen = max(1, word.count)

        faceSeq = visemes(for: word) + [0]        // trailing shut, so the gap between words reads
        let est = min(1.6, Double(word.count) / max(4.0, charsPerSec))
        let step = max(0.045, est / Double(faceSeq.count))
        faceStep = 0
        f.level = faceSeq[0]
        faceTimer?.invalidate()
        faceTimer = Timer.scheduledTimer(withTimeInterval: step, repeats: true) { [weak self] t in
            guard let self = self, let f = self.face, !self.isPaused else { t.invalidate(); return }
            self.faceStep += 1
            guard self.faceStep < self.faceSeq.count else { f.level = 0; t.invalidate(); return }
            f.level = self.faceSeq[self.faceStep]
        }
    }

    func restFace() {
        faceTimer?.invalidate()
        faceTimer = nil
        face?.level = 0
    }

    func finish() {
        restFace()
        guard !restarting else { return }
        idle = true
        if !spool.isEmpty {
            // live mode: more may have streamed in behind us; only the spool watcher closes us
            if ns.length > speakEnd && !isPaused { speak(from: speakEnd) }
            return
        }
        NSApp.terminate(nil)
    }
    // Mid-queue utterances hand off to the next voice; only the last one ends the run.
    func speechSynthesizer(_ s: AVSpeechSynthesizer, didFinish u: AVSpeechUtterance) { if u === lastUtt { finish() } }
    func speechSynthesizer(_ s: AVSpeechSynthesizer, didCancel u: AVSpeechUtterance) { if u === lastUtt { finish() } }
    func windowWillClose(_ n: Notification) { synth.stopSpeaking(at: .immediate); NSApp.terminate(nil) }
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let controller = Controller(text: text)
controller.buildWindow()
controller.start()
app.run()
