import Foundation

/// JSON text formatted exactly like Python's `json.dumps(v, sort_keys=True, ensure_ascii=False)`.
/// The audit log hashes this text, so both cores must produce the same bytes.
public enum PyJSON {
    public static func dumps(_ value: Any?) -> String {
        switch value {
        case nil, is NSNull:
            return "null"
        case let b as Bool:
            return b ? "true" : "false"
        case let i as Int:
            return String(i)
        case let d as Double:
            return d.rounded() == d && abs(d) < 1e16 ? String(format: "%.1f", d) : "\(d)"
        case let s as String:
            return quote(s)
        case let a as [Any?]:
            return "[" + a.map(dumps).joined(separator: ", ") + "]"
        case let a as [Any]:
            return "[" + a.map { dumps($0) }.joined(separator: ", ") + "]"
        case let o as [String: Any?]:
            return object(o.keys, { o[$0] ?? nil })
        case let o as [String: Any]:
            return object(o.keys, { o[$0] })
        default:
            return quote(String(describing: value!))
        }
    }

    /// Keys sorted by code point, like Python's sort_keys.
    static func object<K: Collection>(_ keys: K, _ value: (String) -> Any?) -> String where K.Element == String {
        let sorted = keys.sorted { Array($0.unicodeScalars.map(\.value)).lexicographicallyPrecedes(Array($1.unicodeScalars.map(\.value))) }
        return "{" + sorted.map { quote($0) + ": " + dumps(value($0)) }.joined(separator: ", ") + "}"
    }

    public static func quote(_ s: String) -> String {
        var out = "\""
        for u in s.unicodeScalars {
            switch u {
            case "\"": out += "\\\""
            case "\\": out += "\\\\"
            case "\n": out += "\\n"
            case "\r": out += "\\r"
            case "\t": out += "\\t"
            case "\u{08}": out += "\\b"
            case "\u{0C}": out += "\\f"
            default:
                if u.value < 0x20 {
                    out += String(format: "\\u%04x", u.value)
                } else {
                    out.unicodeScalars.append(u)
                }
            }
        }
        return out + "\""
    }
}
