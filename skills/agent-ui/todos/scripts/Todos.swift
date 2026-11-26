// todos: a small always-on-top, non-activating panel. Reads every *.json goal file in one
// directory (one per agent or project), stacks them, and animates step changes.
// Click a goal's title to fold it to one line (Harvey ball + title + %). Double-click empty space
// to toggle dense mode (only active steps, plus a "+N more" row that expands the goal). Drag anywhere to move; the position is remembered.
import AppKit
import SwiftUI

struct Step: Codable, Identifiable, Equatable { let id: String; let label: String; var state: String }
struct Goal: Codable, Equatable {
    let title: String
    var steps: [Step]?
    var percent: Double?        // used until the goal has steps
    var owner: String?          // who keeps it updated, e.g. "agent-1"
}
struct GoalFile: Identifiable, Equatable { let id: String; var goal: Goal }

func pct(_ g: Goal) -> Double {
    if let s = g.steps, !s.isEmpty {
        let w = s.reduce(0.0) { $0 + ($1.state == "done" ? 1 : $1.state == "active" ? 0.0 : 0) }
        return w / Double(s.count)
    }
    return min(max((g.percent ?? 0) / 100, 0), 1)
}

final class Model: ObservableObject {
    @Published var files: [GoalFile] = []
    @Published var flash: Set<String> = []
    @Published var folded: Set<String> = Set(UserDefaults.standard.stringArray(forKey: "Todos.folded") ?? [])
    @Published var dense: Bool = UserDefaults.standard.bool(forKey: "Todos.dense")
    let dir: URL
    var stamps: [String: Data] = [:]
    init(dir: URL) { self.dir = dir; load(); Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in self?.load() } }
    var reduceMotion: Bool { NSWorkspace.shared.accessibilityDisplayShouldReduceMotion }
    func load() {
        let urls = ((try? FileManager.default.contentsOfDirectory(at: dir, includingPropertiesForKeys: nil)) ?? [])
            .filter { $0.pathExtension == "json" }.sorted { $0.lastPathComponent < $1.lastPathComponent }
        var next: [GoalFile] = []; var changed: Set<String> = []; var any = false
        for u in urls {
            let key = u.deletingPathExtension().lastPathComponent
            guard let d = try? Data(contentsOf: u), let g = try? JSONDecoder().decode(Goal.self, from: d) else {
                if let old = files.first(where: { $0.id == key }) { next.append(old) }; continue
            }
            if stamps[key] != d { any = true
                if let old = files.first(where: { $0.id == key })?.goal {
                    let o = Dictionary(uniqueKeysWithValues: (old.steps ?? []).map { ($0.id, $0.state) })
                    for s in g.steps ?? [] where o[s.id] != s.state { changed.insert(key + "/" + s.id) }
                    if old.percent != g.percent { changed.insert(key) }
                }
                stamps[key] = d
            }
            next.append(GoalFile(id: key, goal: g))
        }
        if !any && next.map(\.id) == files.map(\.id) { return }
        withAnimation(reduceMotion ? nil : .spring(response: 0.45, dampingFraction: 0.75)) { files = next; flash = changed }
        if !changed.isEmpty {
            NSSound(named: "Tink")?.play()
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.6) { withAnimation(.easeOut(duration: 0.6)) { self.flash = [] } }
        }
    }
    func toggleFold(_ id: String) {
        withAnimation(reduceMotion ? nil : .easeInOut(duration: 0.22)) { if folded.contains(id) { folded.remove(id) } else { folded.insert(id) } }
        UserDefaults.standard.set(Array(folded), forKey: "Todos.folded")
    }
    @Published var expanded: Set<String> = []   // goals opened past dense mode via "+N more"
    func toggleExpanded(_ id: String) {
        withAnimation(reduceMotion ? nil : .easeInOut(duration: 0.22)) { if expanded.contains(id) { expanded.remove(id) } else { expanded.insert(id) } }
    }
    func toggleDense() {
        withAnimation(reduceMotion ? nil : .easeInOut(duration: 0.22)) { dense.toggle(); expanded = [] }
        UserDefaults.standard.set(dense, forKey: "Todos.dense")
    }
    // Whole-panel collapse: the panel shrinks to a pill of Harvey balls, one per goal.
    @Published var collapsed: Bool = UserDefaults.standard.bool(forKey: "Todos.collapsed")
    func toggleCollapsed() {
        withAnimation(reduceMotion ? nil : .spring(response: 0.32, dampingFraction: 0.86)) { collapsed.toggle() }
        UserDefaults.standard.set(collapsed, forKey: "Todos.collapsed")
    }
}

struct Harvey: View {   // filled pie for a folded goal
    let p: Double
    var body: some View {
        ZStack {
            Circle().strokeBorder(Color.primary.opacity(0.55), lineWidth: 1.2)
            Pie(p: p).fill(Color.primary.opacity(0.85)).padding(2.2)
        }.frame(width: 14, height: 14)
    }
}
struct Pie: Shape {
    var p: Double
    var animatableData: Double { get { p } set { p = newValue } }
    func path(in r: CGRect) -> Path {
        var path = Path(); let c = CGPoint(x: r.midX, y: r.midY)
        if p >= 0.999 { path.addEllipse(in: r); return path }
        path.move(to: c)
        path.addArc(center: c, radius: r.width / 2, startAngle: .degrees(-90), endAngle: .degrees(-90 + 360 * p), clockwise: false)
        path.closeSubpath(); return path
    }
}

struct PulseDot: View {
    @State private var on = false
    var body: some View {
        let rm = NSWorkspace.shared.accessibilityDisplayShouldReduceMotion
        ZStack {
            Circle().fill(Color.primary.opacity(0.25)).frame(width: 14, height: 14)
                .scaleEffect(rm ? 1 : (on ? 1.0 : 0.45)).opacity(rm ? 0 : (on ? 0 : 0.9))
            Circle().fill(Color.primary.opacity(0.85)).frame(width: 6, height: 6)
                .opacity(rm ? 1 : (on ? 0.55 : 1))
        }
        .onAppear { if !rm { withAnimation(.easeInOut(duration: 1.2).repeatForever(autoreverses: false)) { on = true } } }
    }
}

struct StepRow: View {
    let step: Step; let lit: Bool
    var body: some View {
        HStack(spacing: 8) {
            ZStack {
                Circle().strokeBorder(Color.secondary.opacity(0.5), lineWidth: 1.2).frame(width: 14, height: 14)
                if step.state == "done" {
                    Circle().fill(Color.primary).frame(width: 14, height: 14)
                    Image(systemName: "checkmark").font(.system(size: 8, weight: .bold)).foregroundColor(Color(NSColor.windowBackgroundColor))
                        .transition(.scale.combined(with: .opacity))
                } else if step.state == "active" { PulseDot() }
            }
            .scaleEffect(lit ? 1.25 : 1)
            Text(step.label).font(.system(size: 12, weight: step.state == "active" ? .semibold : .regular))
                .foregroundColor(step.state == "done" ? .secondary : .primary)
                .strikethrough(step.state == "done", color: .secondary)
            Spacer(minLength: 0)
        }
        .padding(.vertical, 3).padding(.horizontal, 6)
        .background(RoundedRectangle(cornerRadius: 6).fill(Color.accentColor.opacity(lit ? 0.18 : 0)))
    }
}

struct GoalBlock: View {
    @ObservedObject var m: Model; let f: GoalFile
    var body: some View {
        let g = f.goal, p = pct(g), folded = m.folded.contains(f.id)
        let steps = g.steps ?? []
        let doneN = steps.filter { $0.state == "done" }.count
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 8) {
                if folded { Harvey(p: p).scaleEffect(m.flash.contains(f.id) ? 1.25 : 1) }
                Text(g.title).font(.system(size: 13, weight: .semibold)).lineLimit(1)
                Spacer()
                Text(steps.isEmpty ? "\(Int((p * 100).rounded()))%" : "\(doneN)/\(steps.count)")
                    .font(.system(size: 11).monospacedDigit()).foregroundColor(.secondary)
            }
            .contentShape(Rectangle())
            .onTapGesture { m.toggleFold(f.id) }
            if !folded {
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        Capsule().fill(Color.secondary.opacity(0.18))
                        Capsule().fill(Color.primary.opacity(0.8)).frame(width: geo.size.width * p)
                    }
                }.frame(height: 4)
                if !steps.isEmpty {
                    let open = m.expanded.contains(f.id)
                    let shown = steps.filter { !m.dense || open || $0.state == "active" }
                    let hidden = steps.count - steps.filter { $0.state == "active" }.count
                    VStack(alignment: .leading, spacing: 0) {
                        ForEach(shown) { s in
                            StepRow(step: s, lit: m.flash.contains(f.id + "/" + s.id))
                        }
                        // Dense mode never silently drops steps: a quiet row says how many are tucked away.
                        if m.dense && hidden > 0 {
                            Text(open ? "Show less" : "+\(hidden) more")
                                .font(.system(size: 11)).foregroundColor(.secondary)
                                .padding(.vertical, 3).padding(.horizontal, 6)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .contentShape(Rectangle())
                                .onTapGesture { m.toggleExpanded(f.id) }
                        }
                    }
                }
            }
        }
    }
}

// Right-click the panel or the pill: the only way to collapse (no chrome, one item).
// The titles and icons are the standard collapse pair (Collapse =
// rectangle.compress.vertical, Expand = rectangle.expand.vertical). A click on the pill also expands.
struct PanelMenu: View {
    @ObservedObject var m: Model
    var body: some View {
        Button(m.collapsed ? "Expand" : "Collapse", systemImage: m.collapsed ? "rectangle.expand.vertical" : "rectangle.compress.vertical") { m.toggleCollapsed() }
    }
}

struct CollapsedPill: View {
    @ObservedObject var m: Model
    var body: some View {
        HStack(spacing: 6) {
            if m.files.isEmpty { Harvey(p: 0) }
            ForEach(m.files) { f in
                let active = (f.goal.steps ?? []).contains { $0.state == "active" }
                Harvey(p: pct(f.goal))
                    .scaleEffect(m.flash.contains(where: { $0 == f.id || $0.hasPrefix(f.id + "/") }) ? 1.3 : 1)
                    .overlay(active ? PulseDot().scaleEffect(0.6).offset(x: 6, y: -6) : nil)
                    .help(f.goal.title)
            }
        }
        .padding(.horizontal, 10).padding(.vertical, 8)
        .contentShape(Rectangle())
        .onTapGesture { m.toggleCollapsed() }
        .help("Expand")
        .contextMenu { PanelMenu(m: m) }
    }
}

struct FloaterView: View {
    @ObservedObject var m: Model
    var body: some View {
        Group {
            if m.collapsed {
                CollapsedPill(m: m)
                    .background(VisualEffect().clipShape(Capsule()))
                    .overlay(Capsule().strokeBorder(Color.primary.opacity(0.08)))
                    .transition(.opacity)
            } else {
                VStack(alignment: .leading, spacing: 0) {
                    VStack(alignment: .leading, spacing: 12) {
                        if m.files.isEmpty { Text("No todos yet").font(.system(size: 12)).foregroundColor(.secondary) }
                        ForEach(m.files) { f in GoalBlock(m: m, f: f) }
                    }
                    .padding(12)
                }
                .frame(width: 260)
                .background(VisualEffect().clipShape(RoundedRectangle(cornerRadius: 12)))
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Color.primary.opacity(0.08)))
                .contentShape(Rectangle())
                .onTapGesture(count: 2) { m.toggleDense() }
                .contextMenu { PanelMenu(m: m) }
                .transition(.opacity)
            }
        }
    }
}

struct VisualEffect: NSViewRepresentable {
    func makeNSView(context: Context) -> NSVisualEffectView { let v = NSVisualEffectView(); v.material = .hudWindow; v.blendingMode = .behindWindow; v.state = .active; return v }
    func updateNSView(_ v: NSVisualEffectView, context: Context) {}
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    var panel: NSPanel!
    func applicationDidFinishLaunching(_ n: Notification) {
        let dir = URL(fileURLWithPath: CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : FileManager.default.currentDirectoryPath)
        let m = Model(dir: dir)
        let host = NSHostingView(rootView: FloaterView(m: m))
        host.frame.size = host.fittingSize
        panel = NSPanel(contentRect: host.frame, styleMask: [.nonactivatingPanel, .borderless], backing: .buffered, defer: false)
        panel.level = .floating; panel.isOpaque = false; panel.backgroundColor = .clear; panel.hasShadow = true
        panel.isMovableByWindowBackground = true
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.contentView = host
        let name = "Todos:" + dir.path
        if !panel.setFrameUsingName(name) { place() }
        panel.setFrameAutosaveName(name)
        panel.orderFrontRegardless()
        Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self] _ in
            guard let self else { return }
            let s = host.fittingSize
            var f = self.panel.frame
            if abs(s.height - f.height) > 1 || abs(s.width - f.width) > 1 {
                // Keep the top edge, and the side nearest the screen edge, fixed.
                let rightSide = f.midX > (self.panel.screen?.visibleFrame.midX ?? 0)
                f.origin.y += f.height - s.height
                if rightSide { f.origin.x += f.width - s.width }
                f.size = s; self.panel.setFrame(f, display: true)
            }
        }
    }
    // corner from GOAL_FLOATER_CORNER: br (default), bl, tr, tl. Used only until you drag it once.
    func place() {
        guard let vf = NSScreen.main?.visibleFrame else { return }
        let s = panel.frame.size
        let c = ProcessInfo.processInfo.environment["GOAL_FLOATER_CORNER"] ?? "br"
        let x = c.hasSuffix("l") ? vf.minX + 16 : vf.maxX - s.width - 16
        let y = c.hasPrefix("t") ? vf.maxY - s.height - 16 : vf.minY + 16
        panel.setFrameOrigin(NSPoint(x: x, y: y))
    }
}

@main struct Main {
    static func main() {
        let app = NSApplication.shared
        app.setActivationPolicy(.accessory)
        let d = AppDelegate(); app.delegate = d
        app.run()
    }
}
