import Foundation

/// Spotting the robot's name in a rough transcript. Same rules as voice/wake.py.
/// Lengths and edit distances use Unicode code points, as Python does.
public enum Wake {
    static let latin = #"s[ae]{1,2}(?:s|z|sh)[uoa]|sh[ae]{1,2}s[uo]"#  // also "Shasu" (Tamil-accented)
    static let tamil = #"(?:சா|ச)(?:சு|சி|ஸு|ஸ|சூ|சோ)"#
    static let tamilShort = ["சாச", "சாஸ", "சச"]
    static let latinAliases: Set<String> = ["sauce", "sasse", "sassu", "saasu", "sasoo", "sassy", "sarsu"]
    static let stopWords = ["stop", "wait", "enough", "nil", "niruthu", "nirutthu", "நிறுத்து", "போதும்", "pothum"]
    static let notWake: Set<String> = ["season", "seasons", "sasha", "sausage", "sazon", "seashore", "seashell"]

    static func words(_ text: String) -> [String] {
        let re = FastPath.re(#"[a-zA-Z0-9]+|[\x{0B80}-\x{0BFF}]+"#)
        let lower = text.lowercased()
        return re.matches(in: lower, range: NSRange(lower.startIndex..., in: lower)).compactMap { Range($0.range, in: lower).map { String(lower[$0]) } }
    }

    static func len(_ s: String) -> Int { s.unicodeScalars.count }

    static func editDistance(_ a: String, _ b: String) -> Int {
        let x = Array(a.unicodeScalars), y = Array(b.unicodeScalars)
        var prev = Array(0...y.count)
        for i in 1...max(1, x.count) where !x.isEmpty {
            var cur = [i]
            for j in 1...max(1, y.count) where !y.isEmpty {
                cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x[i - 1] == y[j - 1] ? 0 : 1)))
            }
            prev = y.isEmpty ? [i] : cur
        }
        return x.isEmpty ? y.count : prev[y.count]
    }

    static func custom(_ ws: [String], _ names: [String]) -> (Bool, String) {
        for n in names {
            let target = n.lowercased().replacingOccurrences(of: " ", with: "")
            if target.isEmpty || target == "sasu" { continue }
            let isAscii = target.unicodeScalars.allSatisfy(\.isASCII)
            for i in ws.indices {
                for span in [1, 2] {
                    let chunk = ws[i..<min(ws.count, i + span)].joined()
                    let rest = ws[min(ws.count, i + span)...].joined(separator: " ")
                    if !isAscii {
                        if chunk == target { return (true, rest) }
                    } else if (len(target) >= 4 && abs(len(chunk) - len(target)) <= 1 && editDistance(chunk, target) <= 1) || (len(target) < 4 && chunk == target) {
                        return (true, rest)
                    }
                }
            }
        }
        return (false, "")
    }

    /// (heard the robot's name, what was said after it). "Sasu" always works.
    public static func find(_ text: String, names: [String] = []) -> (Bool, String) {
        let ws = words(text).filter { !notWake.contains($0) }
        if !names.isEmpty {
            let r = custom(ws, names)
            if r.0 { return r }
        }
        for (i, w) in ws.enumerated() {
            if FastPath.match(tamil, w) != nil || (tamilShort.contains { w.hasPrefix($0) } && len(w) <= 5) || latinAliases.contains(w) {
                return (true, ws[(i + 1)...].joined(separator: " "))
            }
        }
        for i in ws.indices {
            for span in [1, 2, 3] {
                let chunk = ws[i..<min(ws.count, i + span)].joined()
                if span > 1, len(chunk) > 12 { break }
                if FastPath.match(latin, chunk) != nil { return (true, ws[min(ws.count, i + span)...].joined(separator: " ")) }
            }
        }
        return (false, "")
    }

    public static func isStop(_ text: String) -> Bool {
        let toks = Set(words(text))
        return stopWords.contains { toks.contains($0) || text.contains($0) } && toks.count <= 4
    }
}
