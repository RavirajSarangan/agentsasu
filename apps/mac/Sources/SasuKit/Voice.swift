@preconcurrency import AVFoundation
import Foundation

/// Live voice: microphone (or fed audio) → voice activity → Listener. Like VoicePipeline.
public final class VoiceRuntime: @unchecked Sendable {
    public let listener: Listener
    let vad: VAD
    private var engine: AVAudioEngine?
    private let stream: AsyncStream<[Float]>
    private let input: AsyncStream<[Float]>.Continuation
    private var loop: Task<Void, Never>?
    private var lastLevel = Date.distantPast
    public var onLevel: ((Double) -> Void)?
    public var onTimeout: (() async -> Void)?

    public init?(modelsDir: String) {
        guard let listener = Listener(modelsDir: modelsDir), let vad = VAD(modelsDir: modelsDir) else { return nil }
        self.listener = listener
        self.vad = vad
        (stream, input) = AsyncStream.makeStream(of: [Float].self, bufferingPolicy: .bufferingNewest(400))
    }

    public static func modelsReady(_ dir: String) -> Bool {
        ["silero_vad.onnx", "wespeaker_en_voxceleb_resnet34.onnx", "tiny-encoder.int8.onnx", "tiny-decoder.int8.onnx",
         "tiny-tokens.txt", "turbo-encoder.int8.onnx", "turbo-decoder.int8.onnx", "turbo-tokens.txt"]
            .allSatisfy { FileManager.default.fileExists(atPath: dir + "/" + $0) }
    }

    /// Start processing; `mic: false` only processes fed audio (tests, files).
    public func start(mic: Bool) throws {
        loop = Task { [weak self] in await self?.run() }
        guard mic else { return }
        let engine = AVAudioEngine()
        let node = engine.inputNode
        let hw = node.outputFormat(forBus: 0)
        guard let want = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: Double(sampleRate), channels: 1, interleaved: false),
              let converter = AVAudioConverter(from: hw, to: want) else { throw VoiceError.audioFormat }
        let input = self.input
        node.installTap(onBus: 0, bufferSize: 4096, format: hw) { buffer, _ in
            let ratio = want.sampleRate / hw.sampleRate
            guard let out = AVAudioPCMBuffer(pcmFormat: want, frameCapacity: AVAudioFrameCount(Double(buffer.frameLength) * ratio) + 32) else { return }
            var fed = false
            converter.convert(to: out, error: nil) { _, status in
                if fed { status.pointee = .noDataNow; return nil }
                fed = true
                status.pointee = .haveData
                return buffer
            }
            if let ch = out.floatChannelData?[0], out.frameLength > 0 {
                input.yield(Array(UnsafeBufferPointer(start: ch, count: Int(out.frameLength))))
            }
        }
        try engine.start()
        self.engine = engine
    }

    public func stop() {
        engine?.inputNode.removeTap(onBus: 0)
        engine?.stop()
        loop?.cancel()
        input.finish()
    }

    /// Push audio as if it came from the mic.
    public func feed(_ samples: [Float]) {
        var i = 0
        while i < samples.count {
            input.yield(Array(samples[i..<min(samples.count, i + 1024)]))
            i += 1024
        }
    }

    private func run() async {
        var buffer: [Float] = []
        for await chunk in stream {
            let l = listener
            if [.command, .enroll].contains(l.mode), Date().timeIntervalSince(lastLevel) > 0.08 {
                lastLevel = Date()
                let rms = sqrt(chunk.reduce(0) { $0 + Double($1 * $1) } / Double(max(1, chunk.count)))
                onLevel?(min(1, sqrt(rms) * 2.2))
            }
            if l.mode == .command, Date().timeIntervalSince(l.armedAt) > l.armTimeout, !vad.speechDetected {
                l.mode = .idle
                await onTimeout?()
            }
            buffer += chunk
            while buffer.count >= vad.window {
                vad.accept(Array(buffer[0..<vad.window]))
                buffer.removeFirst(vad.window)
            }
            for seg in vad.popSegments() { await l.handle(seg) }
        }
    }
}

public enum VoiceError: Error { case audioFormat }
