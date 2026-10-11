import Foundation

/// Speech with the Mac's built-in voices, like tts/macos.py: Tamil script → Vani, the rest →
/// Tara (girl) or Rishi (boy). A Tanglish reply switches voice per run of script.
public final class Speaker: @unchecked Sendable {
    public var style = "girl"
    public var enabled = true
    public var rate = 195
    private var current: Process?
    private let lock = NSLock()

    public init() {}

    static let voices = ["girl": ["ta": "Vani", "en": "Tara"], "boy": ["ta": "Vani", "en": "Rishi"]]

    /// [(lang, chunk)]: sentence-ish runs in one script. Same as `split_runs`.
    public static func splitRuns(_ text: String) -> [(String, String)] {
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        let re = FastPath.re(#"(?<=[.!?।])\s+"#)
        var parts: [String] = []
        var last = t.startIndex
        for m in re.matches(in: t, range: NSRange(t.startIndex..., in: t)) {
            guard let r = Range(m.range, in: t) else { continue }
            parts.append(String(t[last..<r.lowerBound]))
            last = r.upperBound
        }
        parts.append(String(t[last...]))
        var runs: [(String, String)] = []
        for p in parts where !p.isEmpty {
            let lang = isTamil(p) ? "ta" : "en"
            if let l = runs.last, l.0 == lang { runs[runs.count - 1].1 += " " + p } else { runs.append((lang, p)) }
        }
        return runs
    }

    public func say(_ text: String) async {
        guard enabled else { return }
        for (lang, chunk) in Self.splitRuns(text) {
            let voice = Self.voices[style]?[lang] ?? "Tara"
            let p = Process()
            p.executableURL = URL(fileURLWithPath: "/usr/bin/say")
            p.arguments = ["-v", voice, "-r", String(rate), chunk]
            p.standardOutput = FileHandle.nullDevice
            p.standardError = FileHandle.nullDevice
            guard (try? p.run()) != nil else { return }
            lock.withLock { current = p }
            await withCheckedContinuation { (c: CheckedContinuation<Void, Never>) in
                DispatchQueue.global().async { p.waitUntilExit(); c.resume() }
            }
            let stopped = lock.withLock { () -> Bool in
                defer { current = nil }
                return p.terminationReason == .uncaughtSignal
            }
            if stopped { return }
        }
    }

    /// Barge-in: cut Sasu off immediately.
    public func stop() {
        lock.withLock { if let p = current, p.isRunning { p.terminate() } }
    }
}
