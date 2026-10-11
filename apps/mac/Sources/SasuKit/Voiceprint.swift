import CryptoKit
import Foundation

/// Voiceprints and the encrypted vault. Same math and file format as security/voiceprint.py.
public func normalized(_ v: [Float]) -> [Double] {
    let d = v.map(Double.init)
    let n = sqrt(d.reduce(0) { $0 + $1 * $1 })
    return n == 0 ? d : d.map { $0 / n }
}

public func cosine(_ a: [Double], _ b: [Double]) -> Double {
    guard a.count == b.count else { return 0 }
    let na = sqrt(a.reduce(0) { $0 + $1 * $1 }), nb = sqrt(b.reduce(0) { $0 + $1 * $1 })
    guard na > 0, nb > 0 else { return 0 }
    return zip(a, b).reduce(0) { $0 + ($1.0 / na) * ($1.1 / nb) }
}

public struct Voiceprint {
    public static let defaultThreshold = 0.68  // same voice ≈0.80, other voices 0.46–0.62
    public var centroid: [Double]
    public var threshold: Double

    public static func enroll(_ samples: [[Float]], threshold: Double = defaultThreshold) -> Voiceprint? {
        guard samples.count >= 3, let dim = samples.first?.count else { return nil }
        let normed = samples.map(normalized)
        let mean = (0..<dim).map { i in normed.reduce(0) { $0 + $1[i] } / Double(normed.count) }
        let n = sqrt(mean.reduce(0) { $0 + $1 * $1 })
        return Voiceprint(centroid: mean.map { $0 / n }, threshold: threshold)
    }

    /// (matches, score rounded to 4 decimals like Python).
    public func verify(_ embedding: [Float]) -> (Bool, Double) {
        let score = cosine(centroid, embedding.map(Double.init))
        return (score >= threshold, (score * 10_000).rounded() / 10_000)
    }
}

public struct Profile {
    public var name: String
    public var role: String  // owner | family | kid
    public var voiceprint: Voiceprint
}

/// The best-matching enrolled person above their threshold, and the best score seen.
public func identify(_ profiles: [Profile], _ embedding: [Float]) -> (Profile?, Double) {
    var best: Profile?
    var bestScore = 0.0
    for p in profiles {
        let (ok, score) = p.voiceprint.verify(embedding)
        if score > bestScore {
            bestScore = score
            best = ok ? p : nil
        }
    }
    return (best, bestScore)
}

/// AES-256-GCM file: 12-byte nonce + ciphertext + 16-byte tag, AAD "sasu-voiceprint-v1".
public struct VoiceprintVault {
    static let aad = Data("sasu-voiceprint-v1".utf8)
    public let path: String
    let key: SymmetricKey

    public init?(path: String, keyHex: String) {
        guard keyHex.count == 64 else { return nil }
        var bytes: [UInt8] = []
        var i = keyHex.startIndex
        while i < keyHex.endIndex {
            let j = keyHex.index(i, offsetBy: 2)
            guard let b = UInt8(keyHex[i..<j], radix: 16) else { return nil }
            bytes.append(b)
            i = j
        }
        self.path = path
        key = SymmetricKey(data: bytes)
    }

    public func loadProfiles() throws -> [Profile] {
        guard let raw = FileManager.default.contents(atPath: path) else { return [] }
        guard raw.count > 28 else { throw CryptoKitError.incorrectParameterSize }
        let box = try AES.GCM.SealedBox(nonce: AES.GCM.Nonce(data: raw.prefix(12)), ciphertext: raw.dropFirst(12).dropLast(16), tag: raw.suffix(16))
        let plain = try AES.GCM.open(box, using: key, authenticating: Self.aad)
        guard let body = try JSONSerialization.jsonObject(with: plain) as? [String: Any] else { return [] }
        func vp(_ o: [String: Any]) -> Voiceprint {
            Voiceprint(centroid: (o["centroid"] as? [Double]) ?? [], threshold: (o["threshold"] as? Double) ?? Voiceprint.defaultThreshold)
        }
        guard let list = body["profiles"] as? [[String: Any]] else {
            return [Profile(name: "Owner", role: "owner", voiceprint: vp(body))]  // single-owner file (v0.3)
        }
        return list.map { Profile(name: $0["name"] as? String ?? "?", role: $0["role"] as? String ?? "guest", voiceprint: vp($0)) }
    }

    public func saveProfiles(_ profiles: [Profile]) throws {
        let body: [String: Any] = ["profiles": profiles.map { ["name": $0.name, "role": $0.role, "centroid": $0.voiceprint.centroid, "threshold": $0.voiceprint.threshold] as [String: Any] }]
        let sealed = try AES.GCM.seal(try JSONSerialization.data(withJSONObject: body), using: key, authenticating: Self.aad)
        let tmp = path + ".tmp"
        FileManager.default.createFile(atPath: tmp, contents: Data(sealed.nonce) + sealed.ciphertext + sealed.tag, attributes: [.posixPermissions: 0o600])
        _ = try FileManager.default.replaceItemAt(URL(fileURLWithPath: path), withItemAt: URL(fileURLWithPath: tmp))
    }
}
