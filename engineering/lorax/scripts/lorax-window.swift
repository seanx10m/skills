// lorax-window - a small always-on-top panel that plays the lorax animation.
// Modeled on progress-hud: borderless, floating, joins all Spaces, accessory app.
// Usage: LoraxWindow <path-to-html> [width] [height]
import AppKit
import WebKit

let args = CommandLine.arguments
guard args.count > 1 else {
    FileHandle.standardError.write("usage: LoraxWindow <html> [w] [h]\n".data(using: .utf8)!)
    exit(2)
}
let htmlPath = args[1]
let W = args.count > 2 ? (Double(args[2]) ?? 220) : 220
let H = args.count > 3 ? (Double(args[3]) ?? 130) : 130

let pidDir = (NSHomeDirectory() as NSString).appendingPathComponent(".lorax")
let pidFile = (pidDir as NSString).appendingPathComponent("pid")

func clearPid() { try? FileManager.default.removeItem(atPath: pidFile) }

// Singleton. A stale pid from a crashed run must not lock us out forever, so
// the file is only honored when that process is actually alive.
func claimPid() -> Bool {
    try? FileManager.default.createDirectory(atPath: pidDir, withIntermediateDirectories: true)
    if let s = try? String(contentsOfFile: pidFile, encoding: .utf8),
       let old = Int32(s.trimmingCharacters(in: .whitespacesAndNewlines)),
       old > 0, kill(old, 0) == 0 {
        return false
    }
    try? "\(getpid())".write(toFile: pidFile, atomically: true, encoding: .utf8)
    return true
}

guard claimPid() else { exit(0) }   // another panel is up; not an error
for sig in [SIGINT, SIGTERM, SIGHUP] { signal(sig, { _ in clearPid(); exit(0) }) }

final class Panel: NSWindow {
    override var canBecomeKey: Bool { true }   // needed for Esc
}

// A visible, generous resize handle in the bottom-left corner. The webview
// swallows the borderless window's own 3px edge-drag region, so without this
// the panel is effectively unresizable.
final class GripView: NSView {
    private var startFrame = NSRect.zero
    private var startMouse = NSPoint.zero

    override var mouseDownCanMoveWindow: Bool { false }   // beats isMovableByWindowBackground
    override func resetCursorRects() { addCursorRect(bounds, cursor: .crosshair) }

    override func draw(_ dirty: NSRect) {
        let b = bounds
        NSColor(white: 0, alpha: 0.42).setFill()
        NSBezierPath(roundedRect: NSRect(x: b.minX + 2, y: b.minY + 2,
                                         width: b.width - 4, height: b.height - 4),
                     xRadius: 3, yRadius: 3).fill()
        NSColor(white: 1, alpha: 0.75).setStroke()
        // three diagonals parallel to the corner, like the classic grow box
        for i in 0..<3 {
            let o = CGFloat(4 + i * 4)
            let p = NSBezierPath()
            p.lineWidth = 1
            p.move(to: NSPoint(x: b.minX + 4, y: b.minY + o))
            p.line(to: NSPoint(x: b.minX + o, y: b.minY + 4))
            p.stroke()
        }
    }

    override func mouseDown(with e: NSEvent) {
        guard let w = window else { return }
        startFrame = w.frame
        startMouse = NSEvent.mouseLocation
    }

    override func mouseDragged(with e: NSEvent) {
        guard let w = window else { return }
        let m = NSEvent.mouseLocation
        var f = startFrame
        f.size.width  = max(w.minSize.width,  startFrame.width  - (m.x - startMouse.x))
        f.size.height = max(w.minSize.height, startFrame.height - (m.y - startMouse.y))
        f.origin.x = startFrame.maxX - f.size.width      // top-right stays pinned
        f.origin.y = startFrame.maxY - f.size.height
        w.setFrame(f, display: true)
    }
}

final class App: NSObject, NSApplicationDelegate, WKScriptMessageHandler {
    var win: Panel!
    var web: WKWebView!

    func applicationDidFinishLaunching(_ n: Notification) {
        let cfg = WKWebViewConfiguration()
        cfg.userContentController.add(self, name: "lorax")

        let screen = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
        // Top right. AppKit's origin is bottom-left, so the top edge is maxY.
        let rect = NSRect(x: screen.maxX - CGFloat(W) - 24,
                          y: screen.maxY - CGFloat(H) - 24,
                          width: CGFloat(W), height: CGFloat(H))

        win = Panel(contentRect: rect,
                    styleMask: [.borderless, .resizable],
                    backing: .buffered, defer: false)
        win.level = .floating
        win.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        win.isOpaque = false
        win.backgroundColor = .black
        win.hasShadow = true
        win.isMovableByWindowBackground = true   // drag anywhere; clicks still reach the page
        win.isReleasedWhenClosed = false
        win.minSize = NSSize(width: 160, height: 90)   // below this the in-page X becomes unreachable; Esc still works

        web = WKWebView(frame: win.contentLayoutRect, configuration: cfg)
        web.autoresizingMask = [.width, .height]
        web.setValue(false, forKey: "drawsBackground")
        if #available(macOS 13.3, *) { web.isInspectable = false }
        web.enclosingScrollView?.hasVerticalScroller = false
        win.contentView = web

        let grip = GripView(frame: NSRect(x: 0, y: 0, width: 20, height: 20))
        grip.autoresizingMask = [.maxXMargin, .maxYMargin]   // pinned bottom-left
        web.addSubview(grip)

        let url = URL(fileURLWithPath: htmlPath)
        web.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())

        // Enter like a notification: slide down from just off the top edge while
        // fading up. Same gesture as a macOS toast, which is what this is.
        let end = rect
        var start = rect
        start.origin.y += 18
        win.setFrame(start, display: false)
        win.alphaValue = 0
        win.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: false)
        NSAnimationContext.runAnimationGroup { ctx in
            ctx.duration = 0.34
            ctx.timingFunction = CAMediaTimingFunction(name: .easeOut)
            win.animator().setFrame(end, display: true)
            win.animator().alphaValue = 1
        }
    }

    // "done" = the show ended; leave it up so the user can hit SEE MORE.
    // "close" = the in-page x was clicked.
    func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) {
        if (m.body as? String) == "close" { quit() }
    }

    func quit() {
        clearPid()
        var up = win.frame
        up.origin.y += 14
        NSAnimationContext.runAnimationGroup({ ctx in
            ctx.duration = 0.18
            ctx.timingFunction = CAMediaTimingFunction(name: .easeIn)
            win.animator().setFrame(up, display: true)
            win.animator().alphaValue = 0
        }, completionHandler: { NSApp.terminate(nil) })
    }

    func applicationWillTerminate(_ n: Notification) { clearPid() }
}

final class KeyCatcher: NSObject {
    static func install(_ app: App) {
        NSEvent.addLocalMonitorForEvents(matching: .keyDown) { e in
            if e.keyCode == 53 { app.quit(); return nil }   // Esc
            return e
        }
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)          // no dock icon, no menu bar
let delegate = App()
app.delegate = delegate
KeyCatcher.install(delegate)
app.run()
