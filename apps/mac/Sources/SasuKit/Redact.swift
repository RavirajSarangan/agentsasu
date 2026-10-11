import Foundation

/// Strip secrets before anything is logged or sent to an AI. Same rules as security/redact.py.
public enum Redact {
    public static let mask = "«redacted»"

    private static let patterns: [NSRegularExpression] = [
        #"sk-ant-[A-Za-z0-9_\-]{20,}"#,
        #"sk-(?:proj-)?[A-Za-z0-9_\-]{20,}"#,
        #"AKIA[0-9A-Z]{16}"#,
        #"gh[pousr]_[A-Za-z0-9]{36,}"#,
        #"xox[abprs]-[A-Za-z0-9\-]{10,}"#,
        #"AIza[0-9A-Za-z_\-]{35}"#,
        #"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"#,
        #"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----"#,
        #"\b(?:\d[ -]?){13,19}\b"#,
    ].map { try! NSRegularExpression(pattern: $0) }

    private static let assignment = try! NSRegularExpression(
        pattern: #"\b(password|passwd|pwd|secret|token|api[_-]?key)\b(\s*[:=]\s*)("[^"]*"|'[^']*'|\S+)"#,
        options: [.caseInsensitive]
    )

    public static func text(_ s: String) -> String {
        var out = s
        for p in patterns {
            out = p.stringByReplacingMatches(in: out, range: NSRange(out.startIndex..., in: out), withTemplate: mask)
        }
        return assignment.stringByReplacingMatches(
            in: out, range: NSRange(out.startIndex..., in: out), withTemplate: "$1$2" + mask
        )
    }

    public static func object(_ v: Any?) -> Any? {
        switch v {
        case let s as String: return text(s)
        case let a as [Any?]: return a.map(object)
        case let o as [String: Any?]: return o.mapValues(object)
        default: return v
        }
    }
}
