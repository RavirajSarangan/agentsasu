import Foundation

/// Least-privilege rules every tool call is checked against. Same as security/policy.py.
/// Tiers: safe (run), confirm (owner yes), dangerous (Touch ID), deny (never).
public enum Decision: String, Comparable, Codable {
    case safe, confirm, dangerous, deny

    var order: Int { ["safe": 0, "confirm": 1, "dangerous": 2, "deny": 3][rawValue]! }
    public static func < (a: Decision, b: Decision) -> Bool { a.order < b.order }

    /// One tier stricter: used when a call follows untrusted content (prompt injection).
    public var bumped: Decision { self == .safe ? .confirm : self == .confirm ? .dangerous : self }
}

public func strictest(_ ds: Decision...) -> Decision { ds.max() ?? .safe }

public enum Policy {
    public static let home = Paths.resolve(NSHomeDirectory())

    static let denyPaths: [String] = [
        home + "/.ssh", home + "/.gnupg", home + "/.aws",
        home + "/Library/Keychains", home + "/Library/Cookies",
        home + "/Library/Application Support/dev.sasu.desktop",  // our own vault + audit
        "/System", "/private/etc", "/etc", "/private/var/db",
    ]

    static let safeCommands: Set<String> = ["ls", "pwd", "whoami", "date", "cal", "uptime", "df", "du", "echo", "cat", "head", "tail", "wc", "file", "which", "sw_vers", "system_profiler", "pmset", "open", "say", "mdfind", "find", "grep", "sort", "uniq", "diskutil", "networksetup", "ping", "git"]
    static let confirmCommands: Set<String> = ["mv", "cp", "mkdir", "touch", "zip", "unzip", "tar", "kill", "killall", "osascript", "brew", "npm", "pnpm", "pip", "uv", "defaults", "curl", "wget"]
    static let dangerousCommands: Set<String> = ["rm", "rmdir", "chmod", "chown", "launchctl", "shutdown", "reboot", "dd", "diskutil eraseDisk", "srm", "trash"]
    static let denyCommands: Set<String> = ["sudo", "su", "doas", "passwd", "security", "csrutil", "nvram", "spctl", "mkfs", "fdisk", "visudo", "crontab"]
    static let shells: Set<String> = ["sh", "bash", "zsh", "fish", "python", "python3", "node", "perl", "ruby"]

    static func inside(_ path: String, _ root: String) -> Bool { path == root || path.hasPrefix(root + "/") }

    public static func path(_ raw: String, write: Bool) -> Decision {
        let p = Paths.resolve(Paths.expandUser(raw))
        if denyPaths.contains(where: { inside(p, $0) }) { return .deny }
        if !inside(p, home) { return write ? .dangerous : .confirm }
        return write ? .confirm : .safe
    }

    /// Classify a shell command line. Anything we can't parse safely is dangerous.
    public static func shell(_ command: String) -> Decision {
        if ["`", "$(", "<(", ">("].contains(where: command.contains) { return .dangerous }
        guard let tokens = try? Shlex.split(command) else { return .dangerous }
        if tokens.isEmpty { return .deny }
        var decision = Decision.safe
        var segmentStart = true
        for (i, tok) in tokens.enumerated() {
            if [";", "&&", "||", "|", "&"].contains(tok) {
                if tok == "|", i + 1 < tokens.count, shells.contains(tokens[i + 1]) { return .deny }  // curl … | sh
                segmentStart = true
                continue
            }
            if [">", ">>", "<"].contains(tok) {
                decision = strictest(decision, .confirm)
                continue
            }
            if !segmentStart {
                if ["-rf", "-fr", "-r", "-R"].contains(tok), decision == .dangerous {
                    let next = i + 1 < tokens.count ? tokens[i + 1] : ""
                    if ["/", "~", "/*", "~/", NSHomeDirectory()].contains(next) { return .deny }
                }
                continue
            }
            segmentStart = false
            let name = (tok as NSString).lastPathComponent
            if denyCommands.contains(name) { return .deny }
            if shells.contains(name) || dangerousCommands.contains(name) {
                decision = strictest(decision, .dangerous)
            } else if confirmCommands.contains(name) {
                decision = strictest(decision, .confirm)
            } else if !safeCommands.contains(name) {
                decision = strictest(decision, .dangerous)
            }
        }
        return decision
    }
}

/// Python's `shlex.shlex(s, posix=True, punctuation_chars=";&|<>")` with whitespace_split.
public enum Shlex {
    public struct Unbalanced: Error {}

    static let whitespace: Set<Character> = [" ", "\t", "\r", "\n"]
    static let punctuation: Set<Character> = [";", "&", "|", "<", ">"]
    static let quotes: Set<Character> = ["'", "\""]
    static let wordchars: Set<Character> = Set("abcdfeghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_ßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞ~-./*?=")

    public static func split(_ s: String) throws -> [String] {
        var chars = Array(s)[...]
        var pushback: [Character] = []
        func next() -> Character? {
            if !pushback.isEmpty { return pushback.removeLast() }
            return chars.popFirst()
        }
        func skipLine() { while let c = chars.popFirst(), c != "\n" {} }

        var out: [String] = []
        while true {
            var state: Character? = " "  // " " whitespace, "a" word, "c" punctuation, quote char, "\\"
            var escaped: Character = "a"
            var token = ""
            var quoted = false
            loop: while true {
                let c = next()
                switch state {
                case " ":
                    guard let c else { state = nil; break loop }
                    if whitespace.contains(c) {
                        if !token.isEmpty || quoted { break loop }
                    } else if c == "#" {
                        skipLine()
                    } else if c == "\\" {
                        escaped = "a"; state = "\\"
                    } else if wordchars.contains(c) {
                        token = String(c); state = "a"
                    } else if punctuation.contains(c) {
                        token = String(c); state = "c"
                    } else if quotes.contains(c) {
                        state = c
                    } else {
                        token = String(c); state = "a"  // whitespace_split
                    }
                case "a", "c":
                    guard let c else { state = nil; break loop }
                    if whitespace.contains(c) {
                        state = " "
                        if !token.isEmpty || quoted { break loop }
                    } else if c == "#" {
                        skipLine()
                        state = " "
                        if !token.isEmpty || quoted { break loop }
                    } else if state == "c" {
                        if punctuation.contains(c) {
                            token.append(c)
                        } else {
                            if !whitespace.contains(c) { pushback.append(c) }
                            state = " "
                            break loop
                        }
                    } else if quotes.contains(c) {
                        state = c
                    } else if c == "\\" {
                        escaped = "a"; state = "\\"
                    } else if wordchars.contains(c) || !punctuation.contains(c) {
                        token.append(c)
                    } else {
                        pushback.append(c)
                        state = " "
                        if !token.isEmpty || quoted { break loop }
                    }
                case "\\":
                    guard let c else { throw Unbalanced() }
                    if quotes.contains(escaped), c != "\\", c != escaped { token.append("\\") }
                    token.append(c)
                    state = escaped
                case let q?:  // inside a quote
                    quoted = true
                    guard let c else { throw Unbalanced() }
                    if c == q {
                        state = "a"
                    } else if c == "\\", q == "\"" {
                        escaped = q; state = "\\"
                    } else {
                        token.append(c)
                    }
                case nil:
                    break loop
                }
            }
            if token.isEmpty && !quoted && state == nil { return out }
            out.append(token)
            if state == nil { return out }
        }
    }
}

public enum Paths {
    public static func expandUser(_ p: String) -> String {
        if p == "~" { return NSHomeDirectory() }
        if p.hasPrefix("~/") { return NSHomeDirectory() + String(p.dropFirst(1)) }
        return p
    }

    /// Like Python's `Path.resolve()` (non-strict): absolute, symlinks of the existing
    /// prefix resolved (so /etc → /private/etc), the rest appended.
    public static func resolve(_ p: String) -> String {
        let abs = p.hasPrefix("/") ? p : FileManager.default.currentDirectoryPath + "/" + p
        var parts: [String] = []
        for comp in abs.split(separator: "/", omittingEmptySubsequences: true) {
            if comp == "." { continue }
            if comp == ".." { _ = parts.popLast(); continue }
            parts.append(String(comp))
        }
        var existing = parts.count
        while existing > 0, !FileManager.default.fileExists(atPath: "/" + parts[..<existing].joined(separator: "/")) {
            existing -= 1
        }
        let prefix = "/" + parts[..<existing].joined(separator: "/")
        var buf = [CChar](repeating: 0, count: Int(PATH_MAX))
        let real = realpath(prefix, &buf).map { String(cString: $0) } ?? prefix
        let rest = parts[existing...].joined(separator: "/")
        if rest.isEmpty { return real }
        return (real == "/" ? "" : real) + "/" + rest
    }
}
