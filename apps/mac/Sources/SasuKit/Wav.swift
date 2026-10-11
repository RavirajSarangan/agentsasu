import Foundation

/// Reads 16-bit PCM mono WAV into floats in [-1, 1] (test and file input).
public func readWav(_ path: String) -> [Float]? {
    guard let d = FileManager.default.contents(atPath: path), d.count > 44,
          String(decoding: d[0..<4], as: UTF8.self) == "RIFF" else { return nil }
    var i = 12
    while i + 8 <= d.count {
        let id = String(decoding: d[i..<(i + 4)], as: UTF8.self)
        let size = Int(d[i + 4]) | Int(d[i + 5]) << 8 | Int(d[i + 6]) << 16 | Int(d[i + 7]) << 24
        if id == "data" {
            let end = min(d.count, i + 8 + size)
            return stride(from: i + 8, to: end - 1, by: 2).map { Float(Int16(bitPattern: UInt16(d[$0]) | UInt16(d[$0 + 1]) << 8)) / 32768 }
        }
        i += 8 + size + (size % 2)
    }
    return nil
}
