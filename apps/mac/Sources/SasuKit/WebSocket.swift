import CryptoKit
import Foundation

/// Minimal RFC 6455 framing: what Sasu's UI needs (text, ping/pong, close), no extensions.
public enum WebSocket {
    static let guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

    public static func accept(key: String) -> String {
        Data(Insecure.SHA1.hash(data: Data((key + guid).utf8))).base64EncodedString()
    }

    public enum Opcode: UInt8 { case continuation = 0, text = 1, binary = 2, close = 8, ping = 9, pong = 10 }

    public struct Frame { public let fin: Bool; public let opcode: Opcode; public let payload: Data }

    /// Server → client frames are never masked.
    public static func encode(_ opcode: Opcode, _ payload: Data) -> Data {
        var out = Data([0x80 | opcode.rawValue])
        let n = payload.count
        if n < 126 {
            out.append(UInt8(n))
        } else if n <= 0xFFFF {
            out.append(126)
            out.append(contentsOf: [UInt8(n >> 8), UInt8(n & 0xFF)])
        } else {
            out.append(127)
            out.append(contentsOf: (0..<8).reversed().map { UInt8((UInt64(n) >> (UInt64($0) * 8)) & 0xFF) })
        }
        out.append(payload)
        return out
    }

    public static func text(_ s: String) -> Data { encode(.text, Data(s.utf8)) }

    public enum DecodeError: Error { case unmasked, tooLarge, badOpcode }

    /// Parse one frame from the front of `buffer`. Returns nil if more bytes are needed.
    public static func decode(_ buffer: inout Data, maxPayload: Int = 1 << 20) throws -> Frame? {
        let b = [UInt8](buffer.prefix(14))
        guard b.count >= 2 else { return nil }
        guard let op = Opcode(rawValue: b[0] & 0x0F) else { throw DecodeError.badOpcode }
        guard b[1] & 0x80 != 0 else { throw DecodeError.unmasked }  // clients must mask
        var len = Int(b[1] & 0x7F)
        var offset = 2
        if len == 126 {
            guard b.count >= 4 else { return nil }
            len = Int(b[2]) << 8 | Int(b[3])
            offset = 4
        } else if len == 127 {
            guard b.count >= 10 else { return nil }
            len = (2..<10).reduce(0) { $0 << 8 | Int(b[$1]) }
            offset = 10
        }
        guard len <= maxPayload else { throw DecodeError.tooLarge }
        guard buffer.count >= offset + 4 + len else { return nil }
        let start = buffer.startIndex
        let mask = [UInt8](buffer[(start + offset)..<(start + offset + 4)])
        var payload = [UInt8](buffer[(start + offset + 4)..<(start + offset + 4 + len)])
        for i in payload.indices { payload[i] ^= mask[i % 4] }
        buffer = Data(buffer[(start + offset + 4 + len)...])
        return Frame(fin: b[0] & 0x80 != 0, opcode: op, payload: Data(payload))
    }
}

/// Same limit as the Python core: 30 messages per 10 s.
public final class RateLimiter {
    private var hits: [Double] = []
    private let limit: Int
    private let window: Double

    public init(limit: Int = 30, window: Double = 10) {
        self.limit = limit
        self.window = window
    }

    public func allow(now: Double = ProcessInfo.processInfo.systemUptime) -> Bool {
        hits.removeAll { now - $0 > window }
        guard hits.count < limit else { return false }
        hits.append(now)
        return true
    }
}

/// Constant-time comparison for secrets.
public func secureEquals(_ a: String, _ b: String) -> Bool {
    let x = Array(a.utf8), y = Array(b.utf8)
    var diff = x.count ^ y.count
    for i in 0..<max(x.count, y.count) {
        diff |= Int((i < x.count ? x[i] : 0) ^ (i < y.count ? y[i] : 0))
    }
    return diff == 0
}
