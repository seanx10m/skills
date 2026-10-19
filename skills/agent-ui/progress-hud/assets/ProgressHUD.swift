// ProgressHUD - a floating, always-on-top macOS HUD that renders a generic
// progress feed written by whatever long-running work is happening.
//
// It is a DUMB renderer: it polls JSON feed file(s) and draws them. Producers (a
// Workflow, /goal, /loop, a big refactor) write the feed via the `progress-hud`
// CLI. See ~/.claude/skills/progress-hud/SKILL.md.
//
// Two run modes, chosen by argv:
//   ProgressHUD <feedPath> <pidPath> [stackIndex]   - single-effort card (default)
//   ProgressHUD --bundle <pidPath>                  - one window, one row per
//                                                      session feed under sessions/
//
// Feed  ~/.progress-hud/sessions/<sid>.json (or current.json when run bare):
//   { "title": str, "done": int, "total": int,
//     "phase": str, "detail": str,
//     "state": "running"|"done"|"stalled", "updatedAt": epoch_seconds }
// Config ~/.progress-hud/config.json:  { "alpha": 0.35..1.0, "bundle": bool }
// Mascot ~/.progress-hud/mascot.gif:   optional animated sprite, square-cropped + rounded.
// Singleton via pidfile (per-session pid, or bundle.pid in bundle mode).
//
// Drag anywhere to move. Gear = settings (transparency). "-" = compact pill. "x" = quit.

import AppKit

// ---- paths & state dir --------------------------------------------------
let fm = FileManager.default
let hudDir = fm.homeDirectoryForCurrentUser.appendingPathComponent(".progress-hud")
try? fm.createDirectory(at: hudDir, withIntermediateDirectories: true)
let sessionsDir = hudDir.appendingPathComponent("sessions")

let cliArgs = CommandLine.arguments
let bundleMode = cliArgs.count > 1 && cliArgs[1] == "--bundle"

let configURL = hudDir.appendingPathComponent("config.json")
let mascotURL = hudDir.appendingPathComponent("mascot.gif")

// ---- feed model ---------------------------------------------------------
struct Feed {
    var title = "…"; var done = 0; var total = 0
    var phase = ""; var detail = ""; var folder = ""
    var state = "running"; var updatedAt = 0.0
}

func readFeed(from url: URL) -> Feed? {
    guard let d = try? Data(contentsOf: url),
          let any = try? JSONSerialization.jsonObject(with: d),
          let o = any as? [String: Any] else { return nil }
    var f = Feed()
    f.title  = o["title"]  as? String ?? f.title
    f.done   = (o["done"]  as? NSNumber)?.intValue ?? 0
    f.total  = (o["total"] as? NSNumber)?.intValue ?? 0
    f.phase  = o["phase"]  as? String ?? ""
    f.detail = o["detail"] as? String ?? ""
    f.folder = o["folder"] as? String ?? ""
    f.state  = o["state"]  as? String ?? "running"
    f.updatedAt = (o["updatedAt"] as? NSNumber)?.doubleValue ?? 0
    return f
}

func loadConfig() -> [String: Any] {
    guard let d = try? Data(contentsOf: configURL),
          let any = try? JSONSerialization.jsonObject(with: d),
          let o = any as? [String: Any] else { return [:] }
    return o
}
func setConfig(_ key: String, _ val: Any) {   // merge, don't clobber other keys
    var c = loadConfig(); c[key] = val
    if let d = try? JSONSerialization.data(withJSONObject: c) { try? d.write(to: configURL) }
}
func loadAlpha() -> CGFloat {
    let a = (loadConfig()["alpha"] as? NSNumber)?.doubleValue ?? 0.92
    return CGFloat(min(1.0, max(0.35, a)))
}
func loadMascotEnabled() -> Bool { loadConfig()["mascot"] as? Bool ?? true }

// ---- shared drawing helpers (used by both the single card and bundle rows) ----
func fillPill(_ r: NSRect, _ c: NSColor) {
    let p = NSBezierPath(roundedRect: r, xRadius: r.height / 2, yRadius: r.height / 2)
    c.setFill(); p.fill()
}
func drawText(_ s: String, in r: NSRect, size: CGFloat, weight: NSFont.Weight, color: NSColor, align: NSTextAlignment) {
    let para = NSMutableParagraphStyle(); para.alignment = align; para.lineBreakMode = .byTruncatingTail
    let attrs: [NSAttributedString.Key: Any] = [
        .font: NSFont.systemFont(ofSize: size, weight: weight),
        .foregroundColor: color, .paragraphStyle: para,
    ]
    var rr = r
    let h = ceil(NSString(string: s).size(withAttributes: attrs).height)
    rr.origin.y += max(0, (r.height - h) / 2)
    NSString(string: s).draw(in: rr, withAttributes: attrs)
}
let green = NSColor(calibratedRed: 0.20, green: 0.80, blue: 0.42, alpha: 1)
let amber = NSColor(calibratedRed: 0.95, green: 0.62, blue: 0.15, alpha: 1)

func isStalled(_ f: Feed) -> Bool {
    f.state == "stalled" ||
    (f.state == "running" && f.updatedAt > 0 && Date().timeIntervalSince1970 - f.updatedAt > 90)
}
func progressFraction(_ f: Feed) -> CGFloat {
    if f.state == "done" { return 1 }
    return f.total <= 0 ? 0 : min(1, max(0, CGFloat(f.done) / CGFloat(f.total)))
}

// ---- single-effort HUD view ----------------------------------------------
final class HUDView: NSView, NSWindowDelegate {
    var feed = Feed()
    var live = false          // did we ever see a feed?
    var compact = false
    var showSettings = false
    var mascotEnabled = true

    var mascotBox: NSView?
    var settingsView: NSView?

    // scale drives every visual dimension so content grows with the frame;
    // the OS (native .resizable + contentAspectRatio) owns the actual drag,
    // we just read the resulting frame size back in windowDidResize.
    var scale: CGFloat = 1.0

    func windowDidResize(_ notification: Notification) {
        guard let w = window, !compact else { return }
        scale = max(0.5, min(3.5, w.frame.width / Card.w))
        frame = NSRect(origin: .zero, size: w.frame.size)
        layoutSubviewsHUD()
        needsDisplay = true
    }

    override var isFlipped: Bool { true }

    var stalled: Bool { isStalled(feed) }
    var isDone: Bool { feed.state == "done" }
    var barColor: NSColor { stalled ? amber : green }

    var fraction: CGFloat { progressFraction(feed) }
    var percentInt: Int { Int((fraction * 100).rounded()) }
    var hasMascot: Bool { mascotBox != nil && mascotEnabled }

    func updateMascotVisibility() { mascotBox?.isHidden = compact || showSettings || !mascotEnabled }

    override func draw(_ dirty: NSRect) {
        let b = bounds
        let s = scale   // one factor drives every dimension below, so content scales with the frame
        NSGraphicsContext.current?.cgContext.setShouldAntialias(true)

        let card = NSBezierPath(roundedRect: b,
                                xRadius: compact ? b.height/2 : 14*s,
                                yRadius: compact ? b.height/2 : 14*s)
        NSColor(calibratedWhite: 0.07, alpha: 0.95).setFill(); card.fill()
        NSColor(calibratedWhite: 1, alpha: 0.10).setStroke(); card.lineWidth = 1; card.stroke()

        if compact {
            drawText("\(percentInt)%", in: b, size: 13, weight: .bold, color: .white, align: .center)
            let track = NSRect(x: 10, y: b.height - 7, width: b.width - 20, height: 3)
            fillPill(track, NSColor(calibratedWhite: 1, alpha: 0.15))
            fillPill(NSRect(x: track.minX, y: track.minY, width: track.width * fraction, height: track.height), barColor)
            return
        }

        if showSettings { return }   // settings overlay draws the rest

        let textX: CGFloat = hasMascot ? 64*s : 16*s
        let textW = b.width - textX - 74*s

        // title: folder name (muted) as a prefix, then the effort title (white)
        let titleRect = NSRect(x: textX, y: 12*s, width: textW, height: 18*s)
        let tpara = NSMutableParagraphStyle(); tpara.lineBreakMode = .byTruncatingTail
        let tfont = NSFont.systemFont(ofSize: 13*s, weight: .semibold)
        let atitle = NSMutableAttributedString()
        if !feed.folder.isEmpty {
            atitle.append(NSAttributedString(string: feed.folder + "  ", attributes: [
                .font: tfont, .paragraphStyle: tpara,
                .foregroundColor: NSColor(calibratedWhite: 0.50, alpha: 1)]))
        }
        atitle.append(NSAttributedString(string: feed.title, attributes: [
            .font: tfont, .paragraphStyle: tpara, .foregroundColor: NSColor.white]))
        var tr = titleRect
        tr.origin.y += max(0, (titleRect.height - ceil(atitle.size().height)) / 2)
        atitle.draw(in: tr)
        // sub-line: done/total · %  (+ state)
        let stateTag = isDone ? "  ✓ done" : (stalled ? "  · stalled" : "")
        let sub = live
            ? (feed.total > 0 ? "\(feed.done)/\(feed.total) · \(percentInt)%\(stateTag)"
                              : "\(percentInt)%\(stateTag)")
            : "waiting for progress feed…"
        drawText(sub, in: NSRect(x: textX, y: 32*s, width: textW, height: 14*s),
                 size: 11*s, weight: .regular, color: NSColor(calibratedWhite: 0.72, alpha: 1), align: .left)
        // detail line: "phase · detail"
        let dl = [feed.phase, feed.detail].filter { !$0.isEmpty }.joined(separator: " · ")
        if !dl.isEmpty {
            drawText(dl, in: NSRect(x: textX, y: 50*s, width: textW, height: 14*s),
                     size: 11*s, weight: .regular, color: NSColor(calibratedWhite: 0.55, alpha: 1), align: .left)
        }
        // progress bar (bottom, clear of the detail line)
        let track = NSRect(x: 16*s, y: b.height - 16*s, width: b.width - 32*s, height: 8*s)
        fillPill(track, NSColor(calibratedWhite: 1, alpha: 0.13))
        if fraction > 0 {
            fillPill(NSRect(x: track.minX, y: track.minY, width: max(8, track.width * fraction), height: track.height), barColor)
        }
        // buttons
        drawGlyph("⚙", at: settingsRect)
        drawGlyph("–", at: minRect)
        drawGlyph("×", at: closeRect)
    }

    // button rects (expanded) - sized/positioned by scale so they grow with the card
    var settingsRect: NSRect { NSRect(x: bounds.width - 66*scale, y: 10*scale, width: 18*scale, height: 18*scale) }
    var minRect: NSRect      { NSRect(x: bounds.width - 44*scale, y: 10*scale, width: 18*scale, height: 18*scale) }
    var closeRect: NSRect    { NSRect(x: bounds.width - 24*scale, y: 10*scale, width: 18*scale, height: 18*scale) }

    private func drawGlyph(_ s: String, at r: NSRect) {
        let bg = NSBezierPath(roundedRect: r, xRadius: 5*scale, yRadius: 5*scale)
        NSColor(calibratedWhite: 1, alpha: 0.08).setFill(); bg.fill()
        drawText(s, in: r.offsetBy(dx: 0, dy: -1), size: 13*scale, weight: .medium,
                 color: NSColor(calibratedWhite: 0.85, alpha: 1), align: .center)
    }

    // ---- interaction ----
    override func mouseDown(with e: NSEvent) {
        let pt = convert(e.locationInWindow, from: nil)
        if compact { toggleCompact(); return }
        if showSettings { window?.performDrag(with: e); return }  // slider handles its own clicks
        if settingsRect.contains(pt) { toggleSettings(); return }
        if minRect.contains(pt)      { toggleCompact();  return }
        if closeRect.contains(pt)    { quit();           return }
        window?.performDrag(with: e)
    }

    var onQuit: (() -> Void)?
    func quit() { onQuit?(); NSApp.terminate(nil) }

    func toggleCompact() {
        compact.toggle()
        if compact { showSettings = false; settingsView?.isHidden = true }
        updateMascotVisibility()
        guard let w = window else { return }
        var f = w.frame
        // expanding restores the user's scaled size, not the base Card.w/h
        let newW: CGFloat = compact ? 92 : Card.w * scale
        let newH: CGFloat = compact ? 34 : Card.h * scale
        f.origin.y += f.height - newH
        f.size = NSSize(width: newW, height: newH)
        // the pill isn't user-resizable and isn't Card's aspect ratio - drop the
        // lock while compact so our own setFrame isn't fighting it, restore after
        w.styleMask = compact ? w.styleMask.subtracting(.resizable) : w.styleMask.union(.resizable)
        w.contentAspectRatio = compact ? .zero : NSSize(width: Card.w, height: Card.h)
        w.setFrame(f, display: true, animate: true)
        layoutSubviewsHUD()
        needsDisplay = true
    }

    func toggleSettings() {
        showSettings.toggle()
        buildSettingsIfNeeded()
        settingsView?.isHidden = !showSettings
        updateMascotVisibility()
        needsDisplay = true
    }

    // build the settings overlay (transparency dial + Claudina toggle) lazily
    private func buildSettingsIfNeeded() {
        if settingsView != nil { return }
        let v = NSView(frame: bounds); v.wantsLayer = true
        v.layer?.cornerRadius = 14; v.layer?.masksToBounds = true
        v.layer?.backgroundColor = NSColor(calibratedWhite: 0.10, alpha: 1).cgColor

        let label = NSTextField(labelWithString: "Transparency")
        label.font = NSFont.systemFont(ofSize: 12, weight: .semibold)
        label.textColor = .white
        label.frame = NSRect(x: 16, y: 12, width: 200, height: 16)
        v.addSubview(label)

        let slider = NSSlider(value: Double(window?.alphaValue ?? 0.92),
                              minValue: 0.35, maxValue: 1.0,
                              target: self, action: #selector(alphaChanged(_:)))
        slider.frame = NSRect(x: 16, y: 32, width: bounds.width - 32, height: 20)
        slider.isContinuous = true
        v.addSubview(slider)

        let mcbBg = NSView(frame: NSRect(x: 12, y: bounds.height - 36, width: 180, height: 28))
        mcbBg.wantsLayer = true
        mcbBg.layer?.cornerRadius = 7
        mcbBg.layer?.backgroundColor = NSColor(calibratedWhite: 1, alpha: 0.08).cgColor
        v.addSubview(mcbBg)

        let mcb = NSButton(checkboxWithTitle: "Show Claudina", target: self, action: #selector(mascotToggled(_:)))
        mcb.state = mascotEnabled ? .on : .off
        mcb.controlSize = .large
        mcb.attributedTitle = NSAttributedString(
            string: "Show Claudina",
            attributes: [.foregroundColor: NSColor.white, .font: NSFont.systemFont(ofSize: 13, weight: .semibold)])
        mcb.frame = NSRect(x: 8, y: 3, width: 168, height: 22)
        mcbBg.addSubview(mcb)

        let close = NSButton(title: "Done", target: self, action: #selector(closeSettings))
        close.bezelStyle = .rounded
        close.frame = NSRect(x: bounds.width - 66, y: bounds.height - 32, width: 54, height: 22)
        v.addSubview(close)

        addSubview(v)
        settingsView = v
    }

    @objc func alphaChanged(_ s: NSSlider) {
        let a = CGFloat(s.doubleValue)
        window?.alphaValue = a
        setConfig("alpha", Double(a))       // <- sets the DEFAULT for next launch
    }
    @objc func mascotToggled(_ b: NSButton) {
        mascotEnabled = (b.state == .on)
        setConfig("mascot", mascotEnabled) // persist Claudina on/off
        updateMascotVisibility(); needsDisplay = true
    }
    @objc func closeSettings() { if showSettings { toggleSettings() } }

    // position mascot + settings overlay after resize
    func layoutSubviewsHUD() {
        settingsView?.frame = bounds
        if let box = mascotBox {
            box.frame = NSRect(x: 12*scale, y: 14*scale, width: 44*scale, height: 44*scale)   // top-left
            box.layer?.cornerRadius = 8*scale
            (box.subviews.first)?.frame = box.bounds   // gif is pre-cropped tight to Claudina
        }
    }
}

enum Card { static let w: CGFloat = 360; static let h: CGFloat = 92 }

// ---- bundle view: one window, one row per active session feed -----------
// note: no per-row settings/compact/close - one shared × quits the viewer,
// underlying sessions keep running regardless. Add per-row controls if that's
// ever actually wanted.
final class BundleView: NSView {
    struct Row { let id: String; let feed: Feed }
    var rows: [Row] = []
    var onQuit: (() -> Void)?

    override var isFlipped: Bool { true }
    static let rowH: CGFloat = 56
    static let headerH: CGFloat = 22

    var closeRect: NSRect { NSRect(x: bounds.width - 26, y: 4, width: 18, height: 18) }

    override func draw(_ dirty: NSRect) {
        let b = bounds
        let card = NSBezierPath(roundedRect: b, xRadius: 14, yRadius: 14)
        NSColor(calibratedWhite: 0.07, alpha: 0.95).setFill(); card.fill()
        NSColor(calibratedWhite: 1, alpha: 0.10).setStroke(); card.lineWidth = 1; card.stroke()

        drawText("📊 \(rows.count) running", in: NSRect(x: 14, y: 2, width: b.width - 40, height: 18),
                 size: 12, weight: .semibold, color: NSColor(calibratedWhite: 0.75, alpha: 1), align: .left)
        let bg = NSBezierPath(roundedRect: closeRect, xRadius: 5, yRadius: 5)
        NSColor(calibratedWhite: 1, alpha: 0.08).setFill(); bg.fill()
        drawText("×", in: closeRect.offsetBy(dx: 0, dy: -1), size: 13, weight: .medium,
                 color: NSColor(calibratedWhite: 0.85, alpha: 1), align: .center)

        for (i, row) in rows.enumerated() {
            let top = Self.headerH + CGFloat(i) * Self.rowH
            let f = row.feed
            let stalled = isStalled(f)
            let isDone = f.state == "done"
            let barColor = stalled ? amber : green
            let frac = progressFraction(f)
            let pct = Int((frac * 100).rounded())

            let titleRect = NSRect(x: 16, y: top + 4, width: b.width - 32, height: 16)
            let tpara = NSMutableParagraphStyle(); tpara.lineBreakMode = .byTruncatingTail
            let tfont = NSFont.systemFont(ofSize: 12, weight: .semibold)
            let atitle = NSMutableAttributedString()
            if !f.folder.isEmpty {
                atitle.append(NSAttributedString(string: f.folder + "  ", attributes: [
                    .font: tfont, .paragraphStyle: tpara,
                    .foregroundColor: NSColor(calibratedWhite: 0.50, alpha: 1)]))
            }
            atitle.append(NSAttributedString(string: f.title, attributes: [
                .font: tfont, .paragraphStyle: tpara, .foregroundColor: NSColor.white]))
            atitle.draw(in: titleRect)

            let stateTag = isDone ? "  ✓ done" : (stalled ? "  · stalled" : "")
            let sub = f.total > 0 ? "\(f.done)/\(f.total) · \(pct)%\(stateTag)" : "\(pct)%\(stateTag)"
            let dl = [f.phase, f.detail].filter { !$0.isEmpty }.joined(separator: " · ")
            drawText([sub, dl].filter { !$0.isEmpty }.joined(separator: "  ·  "),
                     in: NSRect(x: 16, y: top + 21, width: b.width - 32, height: 14),
                     size: 10.5, weight: .regular, color: NSColor(calibratedWhite: 0.62, alpha: 1), align: .left)

            let track = NSRect(x: 16, y: top + 42, width: b.width - 32, height: 6)
            fillPill(track, NSColor(calibratedWhite: 1, alpha: 0.13))
            if frac > 0 {
                fillPill(NSRect(x: track.minX, y: track.minY, width: max(6, track.width * frac), height: track.height), barColor)
            }
            if i < rows.count - 1 {
                NSColor(calibratedWhite: 1, alpha: 0.06).setStroke()
                let sep = NSBezierPath()
                sep.move(to: NSPoint(x: 12, y: top + Self.rowH - 1))
                sep.line(to: NSPoint(x: b.width - 12, y: top + Self.rowH - 1))
                sep.lineWidth = 1; sep.stroke()
            }
        }
    }

    override func mouseDown(with e: NSEvent) {
        let pt = convert(e.locationInWindow, from: nil)
        if closeRect.contains(pt) { onQuit?(); NSApp.terminate(nil); return }
        window?.performDrag(with: e)
    }
}

// ---- app ------------------------------------------------------------------
let app = NSApplication.shared
app.setActivationPolicy(.accessory)

// atexit/signal need C function pointers, which can't capture a local `let` -
// route pid cleanup through a global instead.
var gPidURL = hudDir.appendingPathComponent("pid")
atexit { try? FileManager.default.removeItem(at: gPidURL) }
for sig in [SIGTERM, SIGINT] {
    signal(sig) { _ in try? FileManager.default.removeItem(at: gPidURL); exit(0) }
}

func makePanel(w: CGFloat, h: CGFloat, resizable: Bool) -> NSPanel {
    // .titled (not .borderless) so AppKit builds a real NSThemeFrame - that's what
    // actually gives edge/corner drag-to-resize for free. .fullSizeContentView +
    // a hidden/transparent title bar keeps the borderless *look*.
    var mask: NSWindow.StyleMask = [.titled, .fullSizeContentView, .nonactivatingPanel]
    if resizable { mask.insert(.resizable) }
    let panel = NSPanel(contentRect: NSRect(x: 0, y: 0, width: w, height: h),
                        styleMask: mask, backing: .buffered, defer: false)
    panel.isFloatingPanel = true
    panel.hidesOnDeactivate = false
    panel.isOpaque = false
    panel.backgroundColor = .clear
    panel.hasShadow = true
    panel.titlebarAppearsTransparent = true
    panel.titleVisibility = .hidden
    panel.standardWindowButton(.closeButton)?.isHidden = true
    panel.standardWindowButton(.miniaturizeButton)?.isHidden = true
    panel.standardWindowButton(.zoomButton)?.isHidden = true
    panel.isMovableByWindowBackground = true
    panel.level = NSWindow.Level(rawValue: Int(CGWindowLevelForKey(.overlayWindow)))
    panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary]
    panel.alphaValue = loadAlpha()
    return panel
}

if bundleMode {
    let pidURL = cliArgs.count > 2 ? URL(fileURLWithPath: cliArgs[2]) : hudDir.appendingPathComponent("bundle.pid")
    gPidURL = pidURL

    let panel = makePanel(w: Card.w, h: BundleView.headerH + BundleView.rowH, resizable: false)
    let view = BundleView(frame: NSRect(x: 0, y: 0, width: Card.w, height: BundleView.headerH + BundleView.rowH))
    panel.contentView = view
    view.onQuit = { try? fm.removeItem(at: pidURL) }

    func positionTop(_ h: CGFloat) {
        guard let vis = NSScreen.main?.visibleFrame else { return }
        var f = panel.frame
        f.origin = NSPoint(x: vis.midX - Card.w / 2, y: vis.maxY - h - 12)
        f.size = NSSize(width: Card.w, height: h)
        panel.setFrame(f, display: true)
    }
    positionTop(view.frame.height)
    panel.orderFrontRegardless()

    try? String(ProcessInfo.processInfo.processIdentifier).write(to: pidURL, atomically: true, encoding: .utf8)

    var everSawRows = false
    var doneSince: [String: Date] = [:]
    func refresh() {
        var out: [BundleView.Row] = []
        if let files = try? fm.contentsOfDirectory(at: sessionsDir, includingPropertiesForKeys: nil) {
            for file in files where file.pathExtension == "json" {
                guard let f = readFeed(from: file) else { continue }
                let id = file.deletingPathExtension().lastPathComponent
                if f.state == "done" {
                    let since = doneSince[id] ?? Date()
                    doneSince[id] = since
                    if Date().timeIntervalSince(since) > 5 { continue }   // linger then drop, like the single card
                } else {
                    doneSince[id] = nil
                }
                out.append(.init(id: id, feed: f))
            }
        }
        out.sort { $0.id < $1.id }
        if !out.isEmpty { everSawRows = true }
        if out.isEmpty && everSawRows {
            try? fm.removeItem(at: pidURL); NSApp.terminate(nil); return
        }
        view.rows = out
        let h = BundleView.headerH + CGFloat(max(1, out.count)) * BundleView.rowH
        if abs(h - panel.frame.height) > 0.5 { positionTop(h); view.frame = NSRect(x: 0, y: 0, width: Card.w, height: h) }
        view.needsDisplay = true
    }
    refresh()
    Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { _ in refresh() }

} else {
    // argv: [feedPath] [pidPath] [stackIndex] - set by the CLI so one HUD per
    // session can run at once; falls back to the shared singleton paths when
    // launched bare (manual run / demo.sh).
    let feedURL    = cliArgs.count > 1 ? URL(fileURLWithPath: cliArgs[1]) : hudDir.appendingPathComponent("current.json")
    let pidURL     = cliArgs.count > 2 ? URL(fileURLWithPath: cliArgs[2]) : hudDir.appendingPathComponent("pid")
    let stackIndex = cliArgs.count > 3 ? (Int(cliArgs[3]) ?? 0) : 0
    gPidURL = pidURL

    let panel = makePanel(w: Card.w, h: Card.h, resizable: true)
    panel.contentAspectRatio = NSSize(width: Card.w, height: Card.h)
    panel.minSize = NSSize(width: Card.w * 0.5, height: Card.h * 0.5)
    panel.maxSize = NSSize(width: Card.w * 3.5, height: Card.h * 3.5)

    let hud = HUDView(frame: NSRect(x: 0, y: 0, width: Card.w, height: Card.h))
    panel.contentView = hud
    panel.delegate = hud
    hud.onQuit = { try? fm.removeItem(at: pidURL) }

    hud.mascotEnabled = loadMascotEnabled()

    // optional animated mascot "Claudina": dropped at ~/.progress-hud/mascot.gif
    if fm.fileExists(atPath: mascotURL.path), let img = NSImage(contentsOf: mascotURL) {
        let box = NSView(); box.wantsLayer = true
        box.layer?.cornerRadius = 8; box.layer?.masksToBounds = true
        box.layer?.backgroundColor = NSColor(calibratedWhite: 0, alpha: 0.25).cgColor
        let iv = NSImageView()
        iv.image = img; iv.animates = true
        iv.imageScaling = .scaleAxesIndependently   // fill the (zoomed) box, crop outer
        box.addSubview(iv)
        hud.addSubview(box)
        hud.mascotBox = box
    }

    if let vis = NSScreen.main?.visibleFrame {
        let yOffset = CGFloat(stackIndex) * (Card.h + 12)   // stack additional HUDs downward
        panel.setFrameOrigin(NSPoint(x: vis.midX - Card.w/2, y: vis.maxY - Card.h - 12 - yOffset))
    }
    hud.layoutSubviewsHUD()
    hud.updateMascotVisibility()
    panel.orderFrontRegardless()

    // ---- singleton pidfile + cleanup ----
    try? String(ProcessInfo.processInfo.processIdentifier)
        .write(to: pidURL, atomically: true, encoding: .utf8)

    // ---- poll the feed ----
    var doneSince: Date?
    func refresh() {
        if let f = readFeed(from: feedURL) {
            hud.feed = f; hud.live = true
            if hud.isDone {
                if doneSince == nil { doneSince = Date() }
                else if Date().timeIntervalSince(doneSince!) > 5 { hud.quit() }  // linger then exit
            } else { doneSince = nil }
        } else if hud.live {
            hud.quit()   // feed removed by `progress-hud stop` -> effort over
        }
        hud.needsDisplay = true
    }
    refresh()
    Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { _ in refresh() }
}

app.run()
