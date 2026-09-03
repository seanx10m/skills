import Foundation
import UserNotifications
import AppKit

// Headless notifier for the ⚡️ /notify skill.
//   POST mode  (args present): <title> <subtitle> <body> [termBundleId]
//     - robot = app bundle icon (left). termBundleId stored in userInfo for click.
//   CLICK mode (no args, relaunched by a notification tap):
//     - spin up a tiny NSApplication, receive the tap, activate the origin
//       terminal app (iTerm / Warp / …) so you land back in that terminal.
//
// Posting keeps the proven semaphore/CLI path (no runloop). The async
// UNUserNotificationCenter calls would silently drop the banner if we exited
// early, so we WAIT on each. Not authorized -> exit non-zero so notify.sh falls
// back to osascript. Build: build.sh (swiftc -> bundle -> codesign).

func wait(_ timeout: Double, _ work: (@escaping () -> Void) -> Void) {
    let sem = DispatchSemaphore(value: 0)
    work { sem.signal() }
    _ = sem.wait(timeout: .now() + timeout)
}

final class ClickDelegate: NSObject, NSApplicationDelegate, UNUserNotificationCenterDelegate {
    func applicationDidFinishLaunching(_ n: Notification) {
        // watchdog: nothing to handle (bare launch) -> don't linger
        DispatchQueue.main.asyncAfter(deadline: .now() + 5) { exit(0) }
    }
    func userNotificationCenter(_ c: UNUserNotificationCenter,
                                didReceive r: UNNotificationResponse,
                                withCompletionHandler done: @escaping () -> Void) {
        if let bid = r.notification.request.content.userInfo["termbid"] as? String, !bid.isEmpty {
            activateApp(bid)
        }
        done()
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) { exit(0) }
    }
}

func activateApp(_ bid: String) {
    if let app = NSRunningApplication.runningApplications(withBundleIdentifier: bid).first {
        app.activate(options: [.activateAllWindows])
    } else if let url = NSWorkspace.shared.urlForApplication(withBundleIdentifier: bid) {
        let cfg = NSWorkspace.OpenConfiguration(); cfg.activates = true
        NSWorkspace.shared.openApplication(at: url, configuration: cfg) { _, _ in }
    }
}

let args = CommandLine.arguments

// directly-testable jump: `ClaudeNotify --activate <bundleid>` (used to verify the
// focus half in isolation from macOS notification-tap delivery)
if args.count > 2 && args[1] == "--activate" {
    activateApp(args[2])
    usleep(300_000)
    exit(0)
}

if args.count > 1 && !args[1].isEmpty {
    // ---------------- POST MODE ----------------
    let center = UNUserNotificationCenter.current()
    let title    = args[1]
    let subtitle = args.count > 2 ? args[2] : ""
    let body     = args.count > 3 ? args[3] : ""
    let termbid  = args.count > 4 ? args[4] : ""

    wait(5) { d in center.requestAuthorization(options: [.alert, .sound]) { _, _ in d() } }
    var status: UNAuthorizationStatus = .notDetermined
    wait(5) { d in center.getNotificationSettings { s in status = s.authorizationStatus; d() } }
    guard status == .authorized else {
        FileHandle.standardError.write("ClaudeNotify: not authorized (status \(status.rawValue))\n".data(using: .utf8)!)
        exit(2)
    }

    let content = UNMutableNotificationContent()
    content.title = title
    if !subtitle.isEmpty { content.subtitle = subtitle }
    content.body = body
    // silent: /sound's afplay hook is the one source of truth for which sound plays,
    // so the banner doesn't fight it with macOS's own default notification sound.
    content.sound = nil
    if !termbid.isEmpty { content.userInfo = ["termbid": termbid] }

    let req = UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: nil)
    var addErr: Error?
    wait(5) { d in center.add(req) { e in addErr = e; d() } }
    usleep(400_000)  // let usernoted flush the XPC delivery before process exit
    if let e = addErr {
        FileHandle.standardError.write("ClaudeNotify: add failed: \(e)\n".data(using: .utf8)!)
        exit(3)
    }
    exit(0)
} else {
    // ---------------- CLICK MODE ----------------
    let app = NSApplication.shared
    let delegate = ClickDelegate()
    app.delegate = delegate
    UNUserNotificationCenter.current().delegate = delegate   // set BEFORE run so the tap is delivered
    app.setActivationPolicy(.accessory)   // no Dock icon / no focus steal
    app.run()
}
