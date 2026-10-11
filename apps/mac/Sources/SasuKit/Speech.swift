import CSherpaOnnx
import Foundation

/// C strings that must outlive a sherpa-onnx config.
final class CStrings {
    private var ptrs: [UnsafeMutablePointer<CChar>] = []
    func callAsFunction(_ s: String) -> UnsafePointer<CChar> {
        let p = strdup(s)!
        ptrs.append(p)
        return UnsafePointer(p)
    }
    deinit { ptrs.forEach { free($0) } }
}

public let sampleRate: Int32 = 16_000

/// Whisper speech-to-text (sherpa-onnx), same settings as the Python core's `from_whisper`.
public final class Recognizer: @unchecked Sendable {
    private let ptr: OpaquePointer
    private let strings = CStrings()
    private let lock = NSLock()

    /// `model` is "tiny" or "turbo"; `language` "" = auto-detect, or "en" / "ta".
    public init?(modelsDir: String, model: String, language: String = "", threads: Int32) {
        var c = SherpaOnnxOfflineRecognizerConfig()
        c.feat_config.sample_rate = sampleRate
        c.feat_config.feature_dim = 80
        c.model_config.whisper.encoder = strings("\(modelsDir)/\(model)-encoder.int8.onnx")
        c.model_config.whisper.decoder = strings("\(modelsDir)/\(model)-decoder.int8.onnx")
        c.model_config.whisper.language = strings(language)
        c.model_config.whisper.task = strings("transcribe")
        c.model_config.whisper.tail_paddings = -1
        c.model_config.tokens = strings("\(modelsDir)/\(model)-tokens.txt")
        c.model_config.num_threads = threads
        c.model_config.provider = strings("cpu")
        c.model_config.model_type = strings("whisper")
        c.decoding_method = strings("greedy_search")
        guard let p = SherpaOnnxCreateOfflineRecognizer(&c) else { return nil }
        ptr = p
    }

    deinit { SherpaOnnxDestroyOfflineRecognizer(ptr) }

    /// (text, raw language code like "en", "ta", "ja").
    public func decode(_ samples: [Float]) -> (String, String) {
        lock.withLock {
            let stream = SherpaOnnxCreateOfflineStream(ptr)
            defer { SherpaOnnxDestroyOfflineStream(stream) }
            samples.withUnsafeBufferPointer { SherpaOnnxAcceptWaveformOffline(stream, sampleRate, $0.baseAddress, Int32($0.count)) }
            SherpaOnnxDecodeOfflineStream(ptr, stream)
            guard let r = SherpaOnnxGetOfflineStreamResult(stream) else { return ("", "") }
            defer { SherpaOnnxDestroyOfflineRecognizerResult(r) }
            let text = r.pointee.text.map { String(cString: $0) } ?? ""
            let lang = r.pointee.lang.map { String(cString: $0) } ?? ""
            return (text.trimmingCharacters(in: .whitespacesAndNewlines), lang.trimmingCharacters(in: CharacterSet(charactersIn: "<|>")).lowercased())
        }
    }
}

/// Voice activity detection (Silero), same thresholds as the Python pipeline.
public final class VAD: @unchecked Sendable {
    private let ptr: OpaquePointer
    private let strings = CStrings()
    public let window: Int

    public init?(modelsDir: String, minSilence: Float = 0.4) {
        var c = SherpaOnnxVadModelConfig()
        c.silero_vad.model = strings("\(modelsDir)/silero_vad.onnx")
        c.silero_vad.threshold = 0.5
        c.silero_vad.min_silence_duration = minSilence
        c.silero_vad.min_speech_duration = 0.25
        c.silero_vad.max_speech_duration = 15
        c.silero_vad.window_size = 512
        c.sample_rate = sampleRate
        c.num_threads = 1
        c.provider = strings("cpu")
        guard let p = SherpaOnnxCreateVoiceActivityDetector(&c, 30) else { return nil }
        ptr = p
        window = 512
    }

    deinit { SherpaOnnxDestroyVoiceActivityDetector(ptr) }

    public func accept(_ samples: [Float]) {
        samples.withUnsafeBufferPointer { SherpaOnnxVoiceActivityDetectorAcceptWaveform(ptr, $0.baseAddress, Int32($0.count)) }
    }

    public func flush() { SherpaOnnxVoiceActivityDetectorFlush(ptr) }
    public func reset() { SherpaOnnxVoiceActivityDetectorReset(ptr) }
    public var speechDetected: Bool { SherpaOnnxVoiceActivityDetectorDetected(ptr) != 0 }

    /// Finished speech segments, oldest first.
    public func popSegments() -> [[Float]] {
        var out: [[Float]] = []
        while SherpaOnnxVoiceActivityDetectorEmpty(ptr) == 0 {
            if let seg = SherpaOnnxVoiceActivityDetectorFront(ptr) {
                out.append(Array(UnsafeBufferPointer(start: seg.pointee.samples, count: Int(seg.pointee.n))))
                SherpaOnnxDestroySpeechSegment(seg)
            }
            SherpaOnnxVoiceActivityDetectorPop(ptr)
        }
        return out
    }
}

/// Speaker embeddings for voiceprints (WeSpeaker ResNet34).
public final class SpeakerEmbedder: @unchecked Sendable {
    private let ptr: OpaquePointer
    private let strings = CStrings()
    private let lock = NSLock()

    public init?(modelsDir: String, threads: Int32 = 2) {
        var c = SherpaOnnxSpeakerEmbeddingExtractorConfig()
        c.model = strings("\(modelsDir)/wespeaker_en_voxceleb_resnet34.onnx")
        c.num_threads = threads
        c.provider = strings("cpu")
        guard let p = SherpaOnnxCreateSpeakerEmbeddingExtractor(&c) else { return nil }
        ptr = p
    }

    deinit { SherpaOnnxDestroySpeakerEmbeddingExtractor(ptr) }

    /// nil for clips under 0.5 s (too short to tell who's speaking), like the Python core.
    public func embed(_ samples: [Float]) -> [Float]? {
        guard samples.count >= Int(sampleRate) / 2 else { return nil }
        return lock.withLock {
            let ex = ptr
            guard let stream = SherpaOnnxSpeakerEmbeddingExtractorCreateStream(ex) else { return nil }
            defer { SherpaOnnxDestroyOnlineStream(stream) }
            samples.withUnsafeBufferPointer { SherpaOnnxOnlineStreamAcceptWaveform(stream, sampleRate, $0.baseAddress, Int32($0.count)) }
            SherpaOnnxOnlineStreamInputFinished(stream)
            guard SherpaOnnxSpeakerEmbeddingExtractorIsReady(ex, stream) != 0,
                  let v = SherpaOnnxSpeakerEmbeddingExtractorComputeEmbedding(ex, stream) else { return nil }
            defer { SherpaOnnxSpeakerEmbeddingExtractorDestroyEmbedding(v) }
            return Array(UnsafeBufferPointer(start: v, count: Int(SherpaOnnxSpeakerEmbeddingExtractorDim(ex))))
        }
    }
}

public func isTamil(_ s: String) -> Bool { s.unicodeScalars.contains { (0x0B80...0x0BFF).contains($0.value) } }

/// Same as the pipeline's `_lang`: trust "en"/"ta", otherwise judge by script.
public func speechLang(raw: String, text: String) -> String {
    ["en", "ta"].contains(raw) ? raw : isTamil(text) ? "ta" : "en"
}
