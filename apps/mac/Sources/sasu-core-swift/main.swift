// sasu-core-swift — the native Sasu core (phase 1: server, security checks, audit).
//
// App mode (`--stdin-config`): line 1 on stdin is the JSON config (token, data dir,
// vault key), so no secret is ever in argv or the environment. Later lines are trusted
// control messages. The first stdout line is the handshake `{"port": N}`. The process
// exits when stdin closes, so it never outlives the app.
//
// Tools: `--verify-audit <file>` prints the chain status; `--redact` redacts stdin.
import Foundation
import SasuKit

setvbuf(stdout, nil, _IOLBF, 0)
let args = CommandLine.arguments

func fail(_ msg: String) -> Never {
    FileHandle.standardError.write(Data("[core-swift] \(msg)\n".utf8))
    exit(2)
}

if let i = args.firstIndex(of: "--verify-audit"), i + 1 < args.count {
    guard let log = try? AuditLog(path: args[i + 1]) else { fail("can't open \(args[i + 1])") }
    let s = log.verify()
    print(PyJSON.compact(["ok": s.ok, "entries": s.entries, "broken_at": s.brokenAt.map { Int($0) } as Any?]))
    exit(s.ok ? 0 : 1)
}

// Pure decision functions, one JSON request per line (for the parity tests).
if args.contains("--eval") {
    while let line = readLine() {
        guard let q = (try? JSONSerialization.jsonObject(with: Data(line.utf8))) as? [String: Any] else { print("null"); continue }
        let a = q["args"] as? [String: Any] ?? [:]
        switch q["fn"] as? String {
        case "shell": print(PyJSON.quote(Policy.shell(q["cmd"] as? String ?? "").rawValue))
        case "path": print(PyJSON.quote(Policy.path(q["path"] as? String ?? "", write: q["write"] as? Bool ?? false).rawValue))
        case "role":
            let d = Decision(rawValue: q["decision"] as? String ?? "safe") ?? .safe
            print(PyJSON.quote(Roles.allowed(role: q["role"] as? String ?? "", tool: q["tool"] as? String ?? "", args: a, decision: d).rawValue))
        case "leak": print(LeakGuard.leaks(tool: q["tool"] as? String ?? "", args: a, untrusted: q["untrusted"] as? [String] ?? []) ? "true" : "false")
        case "canary": print(Canaries(stateFile: q["state"] as? String ?? "").trippedBy(a).map(PyJSON.quote) ?? "null")
        case "fast":
            if let f = FastPath.parse(q["text"] as? String ?? "") {
                print(PyJSON.compact(["calls": f.calls.map { [$0.0, $0.1] as [Any?] }, "say_en": f.sayEn, "say_ta": f.sayTa, "kind": f.kind]))
            } else {
                print("null")
            }
        case "wake":
            let r = Wake.find(q["text"] as? String ?? "", names: q["names"] as? [String] ?? [])
            print(PyJSON.compact(["heard": r.0, "rest": r.1]))
        case "stop":
            print(Wake.isStop(q["text"] as? String ?? "") ? "true" : "false")
        case "transcribe", "segments", "embed":
            let dir = q["models"] as? String ?? ""
            guard let wav = readWav(q["wav"] as? String ?? "") else { print("null"); continue }
            switch q["fn"] as? String {
            case "transcribe":
                let key = "\(q["model"] ?? "tiny"):\(q["lang"] ?? "")"
                let rec = VoiceEval.recognizers[key] ?? Recognizer(modelsDir: dir, model: q["model"] as? String ?? "tiny", language: q["lang"] as? String ?? "", threads: 4)
                VoiceEval.recognizers[key] = rec
                let r = rec?.decode(wav) ?? ("", "")
                print(PyJSON.compact(["text": r.0, "lang": r.1]))
            case "segments":
                guard let vad = VAD(modelsDir: dir) else { print("null"); continue }
                let padded = [Float](repeating: 0, count: 9600) + wav + [Float](repeating: 0, count: 32000)
                var segs: [Int] = []
                var i = 0
                while i + vad.window <= padded.count {
                    vad.accept(Array(padded[i..<(i + vad.window)]))
                    segs += vad.popSegments().map(\.count)
                    i += vad.window
                }
                print(PyJSON.compact(["lengths": segs]))
            default:
                VoiceEval.embedder = VoiceEval.embedder ?? SpeakerEmbedder(modelsDir: dir)
                print(VoiceEval.embedder?.embed(wav).map { PyJSON.dumps($0.map { Double($0) }) } ?? "null")
            }
        case "listen":
            // A scripted session: clips are cut into speech segments by the VAD and fed in
            // order; other steps change the mode, like the real app would.
            let dir = q["models"] as? String ?? ""
            guard let listener = VoiceEval.listener(dir), let vad = VAD(modelsDir: dir) else { print("null"); continue }
            let rec = EvalRecorder()
            listener.delegate = rec
            listener.mode = .idle
            listener.nextLang = nil
            listener.followUp = false
            listener.wakeNames = q["names"] as? [String] ?? []
            let steps = q["steps"] as? [[String: Any]] ?? []
            let done = DispatchSemaphore(value: 0)
            Task {
                for step in steps {
                    if let m = step["mode"] as? String, let mode = Listener.Mode(rawValue: m) { listener.mode = mode }
                    if let sp = step["speaking"] as? Bool { listener.setSpeaking(sp) }
                    if let f = step["follow_up"] as? Bool { listener.followUp = f }
                    if let w = step["wav"] as? String, let audio = readWav(w) {
                        vad.reset()
                        let x = [Float](repeating: 0, count: 9600) + audio + [Float](repeating: 0, count: 32000)
                        var i = 0
                        while i + vad.window <= x.count {
                            vad.accept(Array(x[i..<(i + vad.window)]))
                            for seg in vad.popSegments() { await listener.handle(seg) }
                            i += vad.window
                        }
                    }
                    rec.withLock { rec.log.append(["mode": listener.mode.rawValue]) }
                }
                done.signal()
            }
            done.wait()
            print(PyJSON.compact(["log": rec.log]))
        case "identify":
            let dir = q["models"] as? String ?? ""
            guard let vault = VoiceprintVault(path: q["vault"] as? String ?? "", keyHex: q["key"] as? String ?? ""),
                  let profiles = try? vault.loadProfiles() else { print("null"); continue }
            VoiceEval.embedder = VoiceEval.embedder ?? SpeakerEmbedder(modelsDir: dir)
            guard let wav = readWav(q["wav"] as? String ?? ""), let e = VoiceEval.embedder?.embed(wav) else { print("null"); continue }
            let (who, score) = identify(profiles, e)
            print(PyJSON.compact(["name": who?.name, "role": who?.role, "score": score]))
        case "call", "undo":
            // One executor call (or an undo) in a sandbox data dir, with a scripted yes/no.
            let dir = q["data_dir"] as? String ?? NSTemporaryDirectory()
            let log = AuditLog.shared(dir)
            let journal = try! UndoJournal(path: dir + "/undo.sqlite")
            let box = EvalBox()
            let answer = q["approve"] as? Bool ?? false
            let runner = FakeRunner(config: ["log": dir + "/calls.jsonl", "default": q["default"] as? String ?? ""])
            let ex = Executor(
                emit: { e in box.withLock { box.events.append((e["type"] as? String) ?? "") } },
                approve: { prompt, risk, _, _ in box.withLock { box.prompts.append([prompt, risk.rawValue]) }; return answer },
                audit: log, journal: journal, holding: dir + "/bin", runner: runner,
                canaries: Canaries(stateFile: dir + "/canaries.json"))
            let done = DispatchSemaphore(value: 0)
            Task {
                if q["fn"] as? String == "undo" {
                    let (ok, items) = await ex.undo(turn: q["turn"] as? String ?? "")
                    box.withLock { box.out = ["ok": ok, "items": items] }
                } else {
                    let turn = Turn(id: q["turn"] as? String ?? Turn.newID(), lang: "en", role: q["role"] as? String ?? "owner")
                    turn.untrustedSeen = q["untrusted_seen"] as? Bool ?? false
                    let r = await ex.call(q["tool"] as? String ?? "", a, turn)
                    box.withLock { box.out = ["result": r, "approvals": box.prompts, "events": box.events] }
                }
                done.signal()
            }
            done.wait()
            print(PyJSON.compact(box.out))
        default: print("null")
        }
    }
    exit(0)
}

if args.contains("--redact") {
    while let line = readLine(strippingNewline: false) { print(Redact.text(line), terminator: "") }
    exit(0)
}

guard args.contains("--stdin-config"), let first = readLine(),
      let cfg = (try? JSONSerialization.jsonObject(with: Data(first.utf8))) as? [String: Any],
      let token = cfg["token"] as? String, token.count >= 32,
      let dataDir = cfg["data_dir"] as? String,
      let vaultKey = cfg["vault_key"] as? String, vaultKey.count == 64
else { fail("usage: sasu-core-swift --stdin-config  (config JSON on the first stdin line)") }
let dev = cfg["dev"] as? Bool ?? false

try? FileManager.default.createDirectory(atPath: dataDir, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
guard let audit = try? AuditLog(path: dataDir + "/audit.sqlite") else { fail("can't open the audit log") }
// Tests can swap in a recording runner through the trusted stdin config (never the network).
let runner: Runner = (cfg["fake_runner"] as? [String: Any]).map { FakeRunner(config: $0) } ?? ProcessRunner()
guard let server = try? CoreServer(token: token, audit: audit, dev: dev, dataDir: dataDir, runner: runner) else { fail("can't open the undo journal") }
guard let port = try? server.start() else { fail("can't listen on 127.0.0.1") }
server.baseURLOverrides = cfg["brain_base_urls"] as? [String: String] ?? [:]
server.configureVoice(dataDir: dataDir, vaultKey: vaultKey, modelsDir: cfg["models_dir"] as? String ?? dataDir + "/models", tts: cfg["tts"] as? Bool ?? true)
audit.append("start", ["version": sasuVersion, "demo": false, "dev": dev, "core": "swift"])
print("{\"port\": \(port)}")
server.bootVoice(mic: cfg["mic"] as? Bool ?? true)

// Trusted control channel; EOF means the app went away.
Thread.detachNewThread {
    while let line = readLine() {
        if let msg = (try? JSONSerialization.jsonObject(with: Data(line.utf8))) as? [String: Any] {
            server.control(msg)
        } else {
            FileHandle.standardError.write(Data("[core-swift] ignored bad control line\n".utf8))
        }
    }
    server.drain()  // finish control messages that arrived just before EOF
    audit.append("stop")
    exit(0)
}
dispatchMain()

/// Shared state for one --eval executor call (safe across the background task).
final class EvalBox: NSLock, @unchecked Sendable {
    var prompts: [[String]] = []
    var events: [String] = []
    var out: [String: Any?] = [:]
}

/// Models kept loaded across --eval lines (they take seconds to load).
enum VoiceEval {
    nonisolated(unsafe) static var recognizers: [String: Recognizer?] = [:]
    nonisolated(unsafe) static var embedder: SpeakerEmbedder?
    nonisolated(unsafe) static var listeners: [String: Listener] = [:]

    static func listener(_ dir: String) -> Listener? {
        if let l = listeners[dir] { return l }
        let l = Listener(modelsDir: dir)
        listeners[dir] = l
        return l
    }
}

/// Records what the listener reports, for the parity tests.
final class EvalRecorder: NSLock, ListenerDelegate, @unchecked Sendable {
    var log: [[String: Any?]] = []
    func add(_ e: [String: Any?]) { withLock { log.append(e) } }
    func onWake(commandFollows: Bool) async { add(["event": "wake", "follows": commandFollows]) }
    func onCommand(_ h: Heard) async { add(["event": "command", "text": h.text, "lang": h.lang, "voiceprint": h.embedding != nil]) }
    func onStop() async { add(["event": "stop"]) }
    func onCaption(_ text: String, lang: String) async { add(["event": "caption", "text": text, "lang": lang]) }
    func onEnrollSample(_ embedding: [Float]) async { add(["event": "enroll"]) }
}
