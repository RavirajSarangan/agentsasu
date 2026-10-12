import Foundation

/// Values of every string anywhere inside a JSON-like value.
func strings(_ v: Any?) -> [String] {
    switch v {
    case let s as String: return [s]
    case let a as [Any?]: return a.flatMap(strings)
    case let o as [String: Any?]: return o.values.flatMap(strings)
    default: return []
    }
}

/// What each kind of person may ask for. Same as security/roles.py.
public enum Roles {
    public static let guestTools: Set<String> = ["system_info", "media_control", "media_now_playing", "system_volume", "system_volume_step"]
    public static let kidTools: Set<String> = ["media_control", "media_now_playing", "system_volume", "system_volume_step", "system_info", "web_open"]
    static let kidSites: Set<String> = ["youtube.com", "www.youtube.com", "youtubekids.com", "www.youtubekids.com", "m.youtube.com"]

    public static func allowed(role: String, tool: String, args: [String: Any?], decision: Decision) -> Decision {
        if role == "owner" || decision == .deny { return decision }
        if role == "family" { return tool == "shell_run" || decision == .dangerous ? .deny : decision }
        if role == "kid" {
            guard kidTools.contains(tool) else { return .deny }
            if tool == "web_open" {
                let url = (args["url"] as? String) ?? ""
                let host = URL(string: url.contains("://") ? url : "https://" + url)?.host?.lowercased() ?? ""
                if !kidSites.contains(host) { return .deny }
            }
            return decision
        }
        return guestTools.contains(tool) ? decision : .deny
    }
}

/// Untrusted text read during a turn can't be smuggled out. Same as security/leakguard.py.
public enum LeakGuard {
    static let window = 32
    static let outbound: Set<String> = ["web_open", "web_search", "clipboard_set", "shell_run", "notes_add", "reminders_add", "screen_set_value"]

    static func norm(_ s: String) -> String { s.split(whereSeparator: { $0.isWhitespace }).joined(separator: " ") }

    public static func leaks(tool: String, args: [String: Any?], untrusted: [String]) -> Bool {
        guard outbound.contains(tool), !untrusted.isEmpty else { return false }
        let sources = untrusted.filter { $0.count >= window }.map(norm)
        for raw in strings(args) {
            let text = norm(raw)
            let decoded = norm(text.replacingOccurrences(of: "+", with: " ").removingPercentEncoding ?? text)
            for candidate in Set([text, decoded]) {
                let c = Array(candidate)
                var i = 0
                while i <= c.count - window {
                    let chunk = String(c[i..<(i + window)])
                    if sources.contains(where: { $0.contains(chunk) }) { return true }
                    i += 4
                }
            }
        }
        return false
    }
}

/// Trap files: if a call touches one or sends its marker, something is wrong. Same as canary.py.
public struct Canaries {
    public var paths: [String] = []
    public var tokens: [String] = []

    public init(stateFile: String) {
        guard let data = FileManager.default.contents(atPath: stateFile),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return }
        paths = obj["paths"] as? [String] ?? []
        tokens = obj["tokens"] as? [String] ?? []
    }

    public func trippedBy(_ args: [String: Any?]) -> String? {
        let resolvedTraps = paths.map(Paths.resolve)
        for value in strings(args) {
            for t in tokens where value.contains(t) || value.contains(String(t.reversed())) {
                return "tried to send a trap file's secret"
            }
            let r = Paths.resolve(Paths.expandUser(value))
            if resolvedTraps.contains(r) { return "touched trap file \((r as NSString).lastPathComponent)" }
        }
        return nil
    }
}
