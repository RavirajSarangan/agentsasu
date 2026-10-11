import Foundation

public typealias Args = [String: Any]

public struct ToolResult {
    public var ok: Bool
    public var summary: String
    public var content: String = ""
    public var app: String? = nil
}

public struct ToolContext {
    public let turnID: String
    public let journal: UndoJournal
    public let holding: String
    public let runner: Runner
    public var home: String = NSHomeDirectory()

    func run(_ args: [String], timeout: Double = 15, stdin: String? = nil) async -> Proc {
        await runner.run(args, timeout: timeout, stdin: stdin)
    }
}

public struct Tool {
    public let name: String
    public let risk: Decision
    public let decide: ((Args) -> Decision)?
    public let untrustedOutput: Bool
    public let run: (Args, ToolContext) async -> ToolResult

    public func decision(_ args: Args) -> Decision {
        decide.map { strictest(risk, $0(args)) } ?? risk
    }
}

struct Inverse {
    let describe: ([String: Any]) -> String
    let run: ([String: Any], ToolContext) async -> Void
}

func s(_ a: Args, _ k: String) -> String { (a[k] as? String) ?? (a[k].map { "\($0)" } ?? "") }
func i(_ a: Args, _ k: String) -> Int { (a[k] as? Int) ?? Int(s(a, k)) ?? (a[k] as? Double).map { Int($0) } ?? 0 }
func b(_ a: Args, _ k: String) -> Bool { (a[k] as? Bool) ?? false }
func list(_ a: Args, _ k: String) -> [String] { (a[k] as? [Any])?.map { "\($0)" } ?? [] }
func name(_ path: String) -> String { (path as NSString).lastPathComponent }

/// Same as Python's `_free_name`: "a.pdf" → "a (1).pdf" if taken.
func freeName(_ target: String) -> String {
    let fm = FileManager.default
    if !fm.fileExists(atPath: target) { return target }
    let dir = (target as NSString).deletingLastPathComponent
    let file = name(target)
    let ext = (file as NSString).pathExtension
    let stem = ext.isEmpty ? file : (file as NSString).deletingPathExtension
    for n in 1..<1000 {
        let cand = dir + "/" + stem + " (\(n))" + (ext.isEmpty ? "" : "." + ext)
        if !fm.fileExists(atPath: cand) { return cand }
    }
    return target
}

func resolved(_ p: String) -> String { Paths.resolve(Paths.expandUser(p)) }

func readDecision(_ a: Args) -> Decision {
    let p = [s(a, "path"), s(a, "folder")].first { !$0.isEmpty } ?? "~"
    return Policy.path(p, write: false)
}

func writeAll(_ keys: String...) -> (Args) -> Decision {
    { a in
        var paths: [String] = []
        for k in keys {
            if let v = a[k] as? [Any] { paths += v.map { "\($0)" } } else if !s(a, k).isEmpty { paths.append(s(a, k)) }
        }
        return paths.isEmpty ? .deny : paths.reduce(Decision.confirm) { strictest($0, Policy.path($1, write: true)) }
    }
}

public enum Tools {
    nonisolated(unsafe) public private(set) static var registry: [String: Tool] = [:]
    nonisolated(unsafe) static var inverses: [String: Inverse] = [:]

    static func add(_ name: String, risk: Decision = .safe, decide: ((Args) -> Decision)? = nil, untrusted: Bool = false, _ run: @escaping (Args, ToolContext) async -> ToolResult) {
        registry[name] = Tool(name: name, risk: risk, decide: decide, untrustedOutput: untrusted, run: run)
    }

    static func inverse(_ kind: String, _ describe: @escaping ([String: Any]) -> String, _ run: @escaping ([String: Any], ToolContext) async -> Void) {
        inverses[kind] = Inverse(describe: describe, run: run)
    }

    public static func describe(kind: String, data: [String: Any]) -> String { inverses[kind]?.describe(data) ?? kind }

    static func undoStep(kind: String, data: [String: Any], ctx: ToolContext) async -> Bool {
        guard let inv = inverses[kind] else { return false }
        await inv.run(data, ctx)
        return true
    }

    // MARK: - registration

    static let registered: Bool = {
        apps(); system(); media(); files(); misc()
        return true
    }()

    public static func ensure() { _ = registered }

    static func apps() {
        func isRunning(_ ctx: ToolContext, _ app: String) async -> Bool {
            (await ctx.run(applescript("return application (item 1 of argv) is running") + [app])).out.trimmingCharacters(in: .whitespacesAndNewlines) == "true"
        }
        add("apps_open") { a, ctx in
            let app = s(a, "app").trimmingCharacters(in: .whitespaces)
            let was = await isRunning(ctx, app)
            guard (await ctx.run(["open", "-a", app])).ok else { return ToolResult(ok: false, summary: "Couldn't find an app called \(app)") }
            ctx.journal.record(turn: ctx.turnID, kind: "app_open", ["app": app, "was_running": was])
            return ToolResult(ok: true, summary: "\(app) opened", app: app)
        }
        inverse("app_open", { "opened \($0["app"] ?? "")" }) { d, ctx in
            if !((d["was_running"] as? Bool) ?? false) { _ = await ctx.run(applescript("tell application (item 1 of argv) to quit") + ["\(d["app"] ?? "")"]) }
        }
        add("apps_quit", risk: .confirm) { a, ctx in
            let app = s(a, "app").trimmingCharacters(in: .whitespaces)
            guard (await ctx.run(applescript("tell application (item 1 of argv) to quit") + [app])).ok else { return ToolResult(ok: false, summary: "Couldn't quit \(app)") }
            ctx.journal.record(turn: ctx.turnID, kind: "app_quit", ["app": app])
            return ToolResult(ok: true, summary: "\(app) quit")
        }
        inverse("app_quit", { "quit \($0["app"] ?? "")" }) { d, ctx in _ = await ctx.run(["open", "-a", "\(d["app"] ?? "")"]) }
        add("apps_list") { _, ctx in
            let p = await ctx.run(applescript(#"tell application "System Events" to get name of every process whose background only is false"#))
            let names = p.out.split(separator: ",").map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }.filter { !$0.isEmpty }
            return ToolResult(ok: p.ok, summary: "\(names.count) apps open", content: names.joined(separator: ", "))
        }
    }

    static func system() {
        func volume(_ ctx: ToolContext) async -> Int {
            Int((await ctx.run(applescript("return output volume of (get volume settings)"))).out.trimmingCharacters(in: .whitespacesAndNewlines)) ?? 50
        }
        func setVolume(_ ctx: ToolContext, _ level: Int) async {
            _ = await ctx.run(applescript("set volume output volume (item 1 of argv as integer)") + [String(level)])
        }
        add("system_volume") { a, ctx in
            let level = max(0, min(100, i(a, "level")))
            let prev = await volume(ctx)
            await setVolume(ctx, level)
            ctx.journal.record(turn: ctx.turnID, kind: "volume", ["prev": prev, "level": level])
            return ToolResult(ok: true, summary: "Volume \(level)")
        }
        add("system_volume_step") { a, ctx in
            let prev = await volume(ctx)
            let level = max(0, min(100, prev + i(a, "delta")))
            await setVolume(ctx, level)
            ctx.journal.record(turn: ctx.turnID, kind: "volume", ["prev": prev, "level": level])
            return ToolResult(ok: true, summary: "Volume \(level)")
        }
        inverse("volume", { "volume \($0["prev"] ?? "") → \($0["level"] ?? "")" }) { d, ctx in await setVolume(ctx, (d["prev"] as? Int) ?? 50) }

        let darkGet = applescript(#"tell application "System Events" to tell appearance preferences to return dark mode"#)
        let darkSet = applescript(#"tell application "System Events" to tell appearance preferences to set dark mode to (item 1 of argv is "true")"#)
        add("system_dark_mode") { a, ctx in
            let on = b(a, "on")
            let prev = (await ctx.run(darkGet)).out.trimmingCharacters(in: .whitespacesAndNewlines) == "true"
            _ = await ctx.run(darkSet + [on ? "true" : "false"])
            ctx.journal.record(turn: ctx.turnID, kind: "dark_mode", ["prev": prev, "on": on])
            return ToolResult(ok: true, summary: "Dark mode \(on ? "on" : "off")")
        }
        inverse("dark_mode", { "dark mode \(($0["on"] as? Bool) == true ? "on" : "off")" }) { d, ctx in
            _ = await ctx.run(darkSet + [((d["prev"] as? Bool) ?? false) ? "true" : "false"])
        }

        add("system_wifi", risk: .confirm) { a, ctx in
            let on = b(a, "on")
            let ports = (await ctx.run(["networksetup", "-listallhardwareports"])).out
            let dev = FastPath.match(#"Hardware Port: Wi-Fi\s*\nDevice: (\w+)"#, ports)?[1] ?? "en0"
            let prev = (await ctx.run(["networksetup", "-getairportpower", dev])).out.contains("On")
            guard (await ctx.run(["networksetup", "-setairportpower", dev, on ? "on" : "off"])).ok else { return ToolResult(ok: false, summary: "Couldn't change Wi-Fi") }
            ctx.journal.record(turn: ctx.turnID, kind: "wifi", ["prev": prev, "on": on, "device": dev])
            return ToolResult(ok: true, summary: "Wi-Fi \(on ? "on" : "off")")
        }
        inverse("wifi", { "Wi-Fi \(($0["on"] as? Bool) == true ? "on" : "off")" }) { d, ctx in
            _ = await ctx.run(["networksetup", "-setairportpower", "\(d["device"] ?? "en0")", ((d["prev"] as? Bool) ?? false) ? "on" : "off"])
        }

        add("system_info") { _, ctx in
            let date = (await ctx.run(["date", "+%A %d %B %Y, %H:%M"])).out.trimmingCharacters(in: .whitespacesAndNewlines)
            let batt = (await ctx.run(["pmset", "-g", "batt"])).out
            let m = FastPath.match(#"(\d+)%;\s*([\w ]+);"#, batt)
            let battery = m.map { "\($0[1] ?? "")% (\(($0[2] ?? "").trimmingCharacters(in: .whitespaces)))" } ?? "unknown"
            let ver = (await ctx.run(["sw_vers", "-productVersion"])).out.trimmingCharacters(in: .whitespacesAndNewlines)
            return ToolResult(ok: true, summary: "System info", content: "Time: \(date)\nBattery: \(battery)\nmacOS \(ver)")
        }
    }

    static func media() {
        let actions = ["play": "play", "pause": "pause", "playpause": "playpause", "next": "next track", "previous": "previous track"]
        add("media_control") { a, ctx in
            let player = s(a, "player").isEmpty ? "Spotify" : s(a, "player")
            guard let action = actions[s(a, "action")], ["Music", "Spotify"].contains(player) else { return ToolResult(ok: false, summary: "Unknown player or action") }
            // Fixed script per allow-listed player: app terms must be known at compile time.
            let p = await ctx.run(applescript("tell application \"\(player)\" to \(action)"))
            return ToolResult(ok: p.ok, summary: p.ok ? "\(player): \(s(a, "action"))" : "\(player) didn't respond", app: player)
        }
        add("media_now_playing") { _, ctx in
            for player in ["Spotify", "Music"] {
                let p = await ctx.run(applescript("if application \"\(player)\" is running then tell application \"\(player)\" to return (name of current track) & \" — \" & (artist of current track)"))
                let t = p.out.trimmingCharacters(in: .whitespacesAndNewlines)
                if p.ok, !t.isEmpty { return ToolResult(ok: true, summary: t, content: "\(player): \(t)") }
            }
            return ToolResult(ok: true, summary: "Nothing playing")
        }
    }

    static func files() {
        let fm = FileManager.default
        add("files_find", decide: readDecision, untrusted: true) { a, ctx in
            let folder = resolved(s(a, "folder").isEmpty ? "~" : s(a, "folder"))
            let query = s(a, "query").trimmingCharacters(in: .whitespaces)
            let kind = s(a, "kind").trimmingCharacters(in: .whitespaces)
            var hits: [String]
            if !kind.isEmpty {
                let out = (await ctx.run(["mdfind", "-onlyin", folder, "kind:\(kind)"])).out
                hits = out.split(separator: "\n").map(String.init).filter { query.isEmpty || query == "*" || name($0).lowercased().contains(query.lowercased()) }
            } else {
                hits = (await ctx.run(["mdfind", "-onlyin", folder, "-name", query])).out.split(separator: "\n").map(String.init)
            }
            hits = Array(hits.filter { Policy.path($0, write: false) != .deny }.prefix(40))
            return ToolResult(ok: true, summary: "\(hits.count) found", content: hits.joined(separator: "\n"))
        }
        add("files_list", decide: readDecision, untrusted: true) { a, _ in
            let folder = resolved(s(a, "folder"))
            var isDir: ObjCBool = false
            guard fm.fileExists(atPath: folder, isDirectory: &isDir), isDir.boolValue else { return ToolResult(ok: false, summary: "Not a folder") }
            let items = ((try? fm.contentsOfDirectory(atPath: folder)) ?? []).map { folder + "/" + $0 }
            let mtime = { (p: String) in ((try? fm.attributesOfItem(atPath: p))?[.modificationDate] as? Date) ?? .distantPast }
            let lines = items.sorted { mtime($0) > mtime($1) }.prefix(80).filter { !name($0).hasPrefix(".") }.map { p -> String in
                var d: ObjCBool = false
                fm.fileExists(atPath: p, isDirectory: &d)
                return "\(d.boolValue ? "📁" : "📄") \(name(p))"
            }
            return ToolResult(ok: true, summary: "\(lines.count) items", content: lines.joined(separator: "\n"))
        }
        add("files_read", decide: readDecision, untrusted: true) { a, _ in
            let path = resolved(s(a, "path"))
            var d: ObjCBool = false
            guard fm.fileExists(atPath: path, isDirectory: &d), !d.boolValue, let fh = FileHandle(forReadingAtPath: path) else { return ToolResult(ok: false, summary: "No such file") }
            let data = (try? fh.read(upToCount: 20_000)) ?? Data()
            try? fh.close()
            if data.contains(0) { return ToolResult(ok: false, summary: "That's not a text file") }
            return ToolResult(ok: true, summary: "Read \(name(path))", content: String(decoding: data, as: UTF8.self))
        }
        add("files_move", risk: .confirm, decide: writeAll("paths", "destination")) { a, ctx in
            let dest = resolved(s(a, "destination"))
            if !fm.fileExists(atPath: dest) {
                try? fm.createDirectory(atPath: dest, withIntermediateDirectories: true)
                ctx.journal.record(turn: ctx.turnID, kind: "mkdir", ["path": dest])
            }
            var moved = 0
            for raw in list(a, "paths") {
                let src = resolved(raw)
                guard fm.fileExists(atPath: src) else { continue }
                let target = freeName(dest + "/" + name(src))
                guard (try? fm.moveItem(atPath: src, toPath: target)) != nil else { continue }
                ctx.journal.record(turn: ctx.turnID, kind: "move", ["src": src, "dst": target])
                moved += 1
            }
            return ToolResult(ok: moved > 0, summary: "Moved \(moved) item(s) to \(name(dest))")
        }
        inverse("move", { "moved \(name("\($0["src"] ?? "")"))" }) { d, _ in
            try? FileManager.default.moveItem(atPath: "\(d["dst"] ?? "")", toPath: freeName("\(d["src"] ?? "")"))
        }
        inverse("mkdir", { "created folder \(name("\($0["path"] ?? "")"))" }) { d, _ in
            let p = "\(d["path"] ?? "")"
            if ((try? FileManager.default.contentsOfDirectory(atPath: p)) ?? ["x"]).isEmpty { try? FileManager.default.removeItem(atPath: p) }
        }
        add("files_rename", risk: .confirm, decide: writeAll("path")) { a, ctx in
            let src = resolved(s(a, "path"))
            let newName = s(a, "new_name").trimmingCharacters(in: .whitespaces)
            guard fm.fileExists(atPath: src), !newName.isEmpty, !newName.contains("/"), ![".", ".."].contains(newName) else { return ToolResult(ok: false, summary: "Can't rename that") }
            let target = freeName((src as NSString).deletingLastPathComponent + "/" + newName)
            guard (try? fm.moveItem(atPath: src, toPath: target)) != nil else { return ToolResult(ok: false, summary: "Can't rename that") }
            ctx.journal.record(turn: ctx.turnID, kind: "move", ["src": src, "dst": target])
            return ToolResult(ok: true, summary: "Renamed to \(name(target))")
        }
        add("files_new_folder", risk: .confirm, decide: writeAll("path")) { a, ctx in
            let path = resolved(s(a, "path"))
            if fm.fileExists(atPath: path) { return ToolResult(ok: true, summary: "\(name(path)) already exists") }
            try? fm.createDirectory(atPath: path, withIntermediateDirectories: true)
            ctx.journal.record(turn: ctx.turnID, kind: "mkdir", ["path": path])
            return ToolResult(ok: true, summary: "Created \(name(path))")
        }
        add("files_trash", risk: .confirm, decide: writeAll("paths")) { a, ctx in
            let bin = ctx.holding + "/" + ctx.turnID
            try? fm.createDirectory(atPath: bin, withIntermediateDirectories: true)
            var n = 0
            for raw in list(a, "paths") {
                let src = resolved(raw)
                guard fm.fileExists(atPath: src) else { continue }
                let held = bin + "/" + String(UUID().uuidString.lowercased().replacingOccurrences(of: "-", with: "").prefix(8)) + "-" + name(src)
                guard (try? fm.moveItem(atPath: src, toPath: held)) != nil else { continue }
                ctx.journal.record(turn: ctx.turnID, kind: "trash", ["src": src, "held": held])
                n += 1
            }
            return ToolResult(ok: n > 0, summary: "Threw away \(n) item(s) — undoable")
        }
        inverse("trash", { "threw away \(name("\($0["src"] ?? "")"))" }) { d, _ in
            try? FileManager.default.moveItem(atPath: "\(d["held"] ?? "")", toPath: freeName("\(d["src"] ?? "")"))
        }
        add("files_reveal", decide: { Policy.path(s($0, "path").isEmpty ? "~" : s($0, "path"), write: false) }) { a, ctx in
            let path = resolved(s(a, "path"))
            guard fm.fileExists(atPath: path) else { return ToolResult(ok: false, summary: "No such file") }
            let p = await ctx.run(["open", "-R", path])
            return ToolResult(ok: p.ok, summary: "Showing \(name(path))", app: "Finder")
        }
    }

    static func misc() {
        add("web_open") { a, ctx in
            var url = s(a, "url").trimmingCharacters(in: .whitespaces)
            let lower = url.lowercased()
            if FastPath.match(#"^[a-zA-Z][a-zA-Z0-9+.-]*:"#, url) != nil, !lower.hasPrefix("http://"), !lower.hasPrefix("https://") {
                return ToolResult(ok: false, summary: "Only web links can be opened")
            }
            if !lower.hasPrefix("http://"), !lower.hasPrefix("https://") { url = "https://" + url }
            let comps = URLComponents(string: url)
            let host = comps?.host?.lowercased() ?? ""
            guard ["http", "https"].contains(comps?.scheme?.lowercased() ?? ""), !host.isEmpty, host.contains(".") || host == "localhost" else {
                return ToolResult(ok: false, summary: "Only web links can be opened")
            }
            let p = await ctx.run(["open", url])
            return ToolResult(ok: p.ok, summary: "Opened \(comps?.host ?? host)")
        }
        add("clipboard_get", untrusted: true) { _, ctx in
            let p = await ctx.run(["pbpaste"])
            return ToolResult(ok: p.ok, summary: "Read clipboard", content: String(p.out.prefix(5000)))
        }
        add("clipboard_set") { a, ctx in
            let prev = (await ctx.run(["pbpaste"])).out
            _ = await ctx.run(["pbcopy"], timeout: 5, stdin: s(a, "text"))
            ctx.journal.record(turn: ctx.turnID, kind: "clipboard", ["prev": String(prev.prefix(20_000))])
            return ToolResult(ok: true, summary: "Copied")
        }
        inverse("clipboard", { _ in "copied text" }) { d, ctx in _ = await ctx.run(["pbcopy"], timeout: 5, stdin: "\(d["prev"] ?? "")") }

        add("reminders_add") { a, ctx in
            let title = String(s(a, "title").trimmingCharacters(in: .whitespaces).prefix(200))
            let p = await ctx.run(applescript(#"tell application "Reminders" to return id of (make new reminder with properties {name:(item 1 of argv)})"#) + [title])
            guard p.ok else { return ToolResult(ok: false, summary: "Reminders didn't respond (allow Automation for Sasu)") }
            ctx.journal.record(turn: ctx.turnID, kind: "reminder", ["id": p.out.trimmingCharacters(in: .whitespacesAndNewlines), "title": title])
            return ToolResult(ok: true, summary: "Reminder: \(title)", app: "Reminders")
        }
        inverse("reminder", { "added reminder “\($0["title"] ?? "")”" }) { d, ctx in
            _ = await ctx.run(applescript(#"tell application "Reminders" to delete (first reminder whose id is (item 1 of argv))"#) + ["\(d["id"] ?? "")"])
        }
        add("notes_add") { a, ctx in
            let title = String(s(a, "title").trimmingCharacters(in: .whitespaces).prefix(200))
            let body = String(s(a, "body").prefix(10_000))
            let p = await ctx.run(applescript(#"tell application "Notes" to return id of (make new note with properties {name:(item 1 of argv), body:(item 2 of argv)})"#) + [title, body])
            guard p.ok else { return ToolResult(ok: false, summary: "Notes didn't respond (allow Automation for Sasu)") }
            ctx.journal.record(turn: ctx.turnID, kind: "note", ["id": p.out.trimmingCharacters(in: .whitespacesAndNewlines), "title": title])
            return ToolResult(ok: true, summary: "Note: \(title)", app: "Notes")
        }
        inverse("note", { "created note “\($0["title"] ?? "")”" }) { d, ctx in
            _ = await ctx.run(applescript(#"tell application "Notes" to delete note id (item 1 of argv)"#) + ["\(d["id"] ?? "")"])
        }

        add("shell_run", risk: .confirm, decide: { Policy.shell(s($0, "command")) }, untrusted: true) { a, ctx in
            let p = await ctx.run(["/bin/zsh", "-c", s(a, "command")], timeout: 30)
            return ToolResult(ok: p.ok, summary: "exit \(p.code)", content: String((p.out + (p.err.isEmpty ? "" : "\n" + p.err)).prefix(6000)))
        }
        add("messages_send", risk: .confirm) { a, ctx in
            let to = s(a, "to").trimmingCharacters(in: .whitespaces)
            guard FastPath.match(#"^(?:\+?[\d\s()-]{6,20}|[^@\s]+@[^@\s]+\.[a-z]{2,})$"#, to) != nil else { return ToolResult(ok: false, summary: "That doesn't look like a phone number or email") }
            let script = applescript(#"tell application "Messages""#, "set svc to 1st account whose service type = iMessage", "send (item 1 of argv) to participant (item 2 of argv) of svc", "end tell")
            let p = await ctx.run(script + [String(s(a, "text").prefix(1000)), to])
            return ToolResult(ok: p.ok, summary: p.ok ? "Message sent" : "Messages couldn't send it (allow Automation for Sasu)", app: "Messages")
        }
        add("type_text", risk: .confirm) { a, ctx in
            let text = String(s(a, "text").prefix(5000))
            let app = (await ctx.run(applescript(#"tell application "System Events" to return name of first process whose frontmost is true"#))).out.trimmingCharacters(in: .whitespacesAndNewlines)
            let prev = (await ctx.run(["pbpaste"])).out
            _ = await ctx.run(["pbcopy"], timeout: 5, stdin: text)
            let p = await ctx.run(applescript(#"tell application "System Events" to keystroke "v" using command down"#))
            try? await Task.sleep(nanoseconds: 250_000_000)
            _ = await ctx.run(["pbcopy"], timeout: 5, stdin: prev)
            guard p.ok else { return ToolResult(ok: false, summary: "Couldn't type (allow Accessibility for Sasu)") }
            return ToolResult(ok: true, summary: "Typed \(text.count) characters into \(app.isEmpty ? "the front app" : app)", app: app.isEmpty ? nil : app)
        }
        windows()
    }

    static func windows() {
        let desktop = applescript(#"tell application "Finder" to get bounds of window of desktop"#)
        let get = applescript(#"tell application "System Events" to tell process (item 1 of argv) to get {position, size} of front window"#)
        let set = applescript(#"tell application "System Events" to tell process (item 1 of argv)"#, "set position of front window to {(item 2 of argv) as integer, (item 3 of argv) as integer}", "set size of front window to {(item 4 of argv) as integer, (item 5 of argv) as integer}", "end tell")
        func nums(_ s: String) -> [Int] {
            s.replacingOccurrences(of: "{", with: "").replacingOccurrences(of: "}", with: "").split(separator: ",").compactMap { Double($0.trimmingCharacters(in: .whitespacesAndNewlines)).map { Int($0) } }
        }
        func setFrame(_ ctx: ToolContext, _ app: String, _ f: [Int]) async -> Bool {
            (await ctx.run(set + [app] + f.map(String.init))).ok
        }
        add("windows_arrange") { a, ctx in
            let apps = list(a, "apps").map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }.prefix(3)
            let layout = s(a, "layout").isEmpty ? "split" : s(a, "layout")
            guard !apps.isEmpty else { return ToolResult(ok: false, summary: "Which apps?") }
            let bounds = nums((await ctx.run(desktop)).out)
            let (w, h) = bounds.count == 4 ? (bounds[2], bounds[3]) : (1440, 900)
            let top = 25, height = h - 25, n = apps.count
            let frames: [[Int]] = (0..<n).map { k in
                if layout == "full" || n == 1 { return [0, top, w, height] }
                if layout == "stack" { return [0, top + k * (height / n), w, height / n] }
                return [k * (w / n), top, w / n, height]
            }
            var done = 0
            for (app, f) in zip(apps, frames) {
                _ = await ctx.run(["open", "-a", app])
                let prev = nums((await ctx.run(get + [app])).out)
                if await setFrame(ctx, app, f) {
                    done += 1
                    if prev.count == 4 { ctx.journal.record(turn: ctx.turnID, kind: "window", ["app": app, "prev": prev]) }
                }
            }
            if done == 0 { return ToolResult(ok: false, summary: "Couldn't move the windows (allow Accessibility for Sasu)") }
            return ToolResult(ok: true, summary: "Arranged \(apps.joined(separator: " and "))", app: apps.first)
        }
        inverse("window", { "moved \($0["app"] ?? "")'s window" }) { d, ctx in
            _ = await setFrame(ctx, "\(d["app"] ?? "")", (d["prev"] as? [Int]) ?? [])
        }
    }
}
