import Foundation

/// What the listener heard.
public struct Heard {
    public let text: String
    public let lang: String
    public let embedding: [Float]?
    public let seconds: Double
}

public protocol ListenerDelegate: AnyObject {
    func onWake(commandFollows: Bool) async
    func onCommand(_ heard: Heard) async
    func onStop() async
    func onCaption(_ text: String, lang: String) async
    func onEnrollSample(_ embedding: [Float]) async
}

/// The listening state machine: one speech segment at a time. Same logic as
/// voice/pipeline.py `_segment` (modes idle, command, speaking, meeting, enroll).
public final class Listener: @unchecked Sendable {
    public enum Mode: String { case idle, command, speaking, meeting, enroll }

    let modelsDir: String
    let tiny: Recognizer
    let turbo: Recognizer
    let speaker: SpeakerEmbedder
    private var forced: [String: Recognizer] = [:]
    private let forcedLock = NSLock()

    public weak var delegate: ListenerDelegate?
    public var mode: Mode = .idle
    public var armedAt = Date.distantPast
    public var armTimeout = 8.0
    public var followUp = false
    public var followTimeout = 6.0
    public var wakeNames: [String] = []
    public var preferLang = "en"
    public var nextLang: String?

    public init?(modelsDir: String) {
        guard let tiny = Recognizer(modelsDir: modelsDir, model: "tiny", threads: 2),
              let turbo = Recognizer(modelsDir: modelsDir, model: "turbo", threads: 8),
              let speaker = SpeakerEmbedder(modelsDir: modelsDir) else { return nil }
        self.modelsDir = modelsDir
        self.tiny = tiny
        self.turbo = turbo
        self.speaker = speaker
    }

    public func arm(_ timeout: Double = 8) {
        mode = .command
        armedAt = Date()
        armTimeout = timeout
    }

    public func setSpeaking(_ on: Bool) {
        if mode == .meeting { return }
        if on {
            mode = .speaking
        } else if mode == .speaking {
            if followUp {
                followUp = false
                arm(followTimeout)
            } else {
                mode = .idle
            }
        }
    }

    func recognizer(_ model: String, _ lang: String) -> Recognizer? {
        forcedLock.withLock {
            let key = "\(model):\(lang)"
            if let r = forced[key] { return r }
            let r = Recognizer(modelsDir: modelsDir, model: model, language: lang, threads: model == "tiny" ? 2 : 8)
            forced[key] = r
            return r
        }
    }

    func decodeAs(_ model: String, _ lang: String, _ samples: [Float]) -> String {
        recognizer(model, lang)?.decode(samples).0 ?? ""
    }

    /// Like the pipeline's `_decode`: turbo guesses of a third language are re-decoded
    /// in the preferred language, because Sasu only speaks English and Tamil.
    func decode(_ rec: Recognizer, _ samples: [Float]) -> (String, String) {
        let (text, raw) = rec.decode(samples)
        if rec === turbo, !raw.isEmpty, !["en", "ta"].contains(raw), !isTamil(text) {
            let lang = ["en", "ta"].contains(preferLang) ? preferLang : "en"
            return (decodeAs("turbo", lang, samples), lang)
        }
        return (text, speechLang(raw: raw, text: text))
    }

    static func wordCount(_ s: String) -> Int { s.split(whereSeparator: { $0.isWhitespace }).count }

    public func handle(_ samples: [Float]) async {
        let secs = Double(samples.count) / Double(sampleRate)
        switch mode {
        case .meeting:
            let (text, lang) = decode(turbo, samples)
            if !text.isEmpty { await delegate?.onCaption(text, lang: lang) }
            return
        case .speaking:
            if secs < 3, Wake.isStop(decode(tiny, samples).0) { await delegate?.onStop() }
            return
        case .enroll:
            if let e = speaker.embed(samples) { await delegate?.onEnrollSample(e) }
            return
        case .command:
            mode = .idle
            var text: String, lang: String
            if nextLang == "ta" {
                nextLang = nil
                (text, lang) = (decodeAs("turbo", "ta", samples), "ta")
            } else {
                (text, lang) = decode(turbo, samples)
            }
            if text.isEmpty { return arm(armTimeout) }
            let (heard, rest) = Wake.find(text, names: wakeNames)
            if heard, Self.wordCount(rest) == 0 {
                arm()  // "Hey Sasu" again: still listening, not a command
                await delegate?.onWake(commandFollows: false)
                return
            }
            await delegate?.onCommand(Heard(text: heard && !rest.isEmpty ? rest : text, lang: lang, embedding: speaker.embed(samples), seconds: secs))
            return
        case .idle:
            break
        }
        // idle: the wake word, possibly with the command in the same breath
        if secs > 12 { return }
        var text: String, lang: String, rest: String
        if secs > 1.8 {
            (text, lang) = decode(turbo, samples)  // long enough to hold a command: one accurate pass
            let w = Wake.find(text, names: wakeNames)
            guard w.0 else { return }
            rest = w.1
        } else {
            var (quick, qlang) = decode(tiny, samples)
            var w = Wake.find(quick, names: wakeNames)
            if !w.0 {
                // Short Tamil "சாசு" is often mis-detected as another language: try as Tamil.
                quick = decodeAs("tiny", "ta", samples)
                w = Wake.find(quick, names: wakeNames)
                qlang = "ta"
            }
            if !w.0, secs >= 1.0 {
                // tiny mishears some voices on segments this long; one accurate pass first.
                (quick, qlang) = decode(turbo, samples)
                w = Wake.find(quick, names: wakeNames)
            }
            guard w.0 else { return }
            if qlang == "ta" || isTamil(quick) { nextLang = "ta" }
            (text, lang, rest) = (quick, nextLang == "ta" ? "ta" : "en", w.1)
            if Self.wordCount(rest) >= 2 {
                (text, lang) = decode(turbo, samples)
                rest = Wake.find(text, names: wakeNames).1
            }
        }
        _ = text
        if Self.wordCount(rest) >= 1 {
            nextLang = nil  // the command came in the same breath; don't force the next one
            let emb = speaker.embed(samples)
            await delegate?.onWake(commandFollows: true)
            await delegate?.onCommand(Heard(text: rest, lang: lang, embedding: emb, seconds: secs))
        } else {
            arm()
            await delegate?.onWake(commandFollows: false)
        }
    }
}
