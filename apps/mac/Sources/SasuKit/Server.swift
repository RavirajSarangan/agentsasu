import Foundation
import Network

public let sasuVersion = "0.4.0"

/// The local server the UI talks to: 127.0.0.1 only, a secret token, allowed origins.
/// Phase 1 of the Swift core: transport, security checks and audit; commands come next.
public final class CoreServer {
    public static let appOrigins: Set<String> = ["tauri://localhost", "http://tauri.localhost", "https://tauri.localhost"]
    public static let devOrigins: Set<String> = ["http://localhost:1420", "http://127.0.0.1:1420"]
    static let maxMessage = 16_384

    let token: String
    let audit: AuditLog
    public var executor: Executor!
    let journal: UndoJournal
    private var current: Task<Void, Never>?
    private let pendingLock = NSLock()
    private var pending: [String: (kind: String, cont: CheckedContinuation<Bool, Never>)] = [:]
    let origins: Set<String>
    let queue = DispatchQueue(label: "sasu.core.server")
    private var listener: NWListener?
    private var clients: [ObjectIdentifier: Client] = [:]
    public private(set) var locks: Set<String> = []

    public init(token: String, audit: AuditLog, dev: Bool, dataDir: String, runner: Runner = ProcessRunner()) throws {
        self.token = token
        self.audit = audit
        self.origins = dev ? Self.appOrigins.union(Self.devOrigins) : Self.appOrigins
        journal = try UndoJournal(path: dataDir + "/undo.sqlite")
        let canaries = Canaries(stateFile: dataDir + "/canaries.json")
        executor = Executor(
            emit: { [weak self] e in self?.emit(e) },
            approve: { [weak self] prompt, risk, lang, confirmed in await self?.approve(prompt, risk, lang, confirmed) ?? false },
            audit: audit, journal: journal, holding: dataDir + "/bin", runner: runner, canaries: canaries,
            onAlarm: { [weak self] kind, _ in if kind == "canary" { self?.control(["type": "lock", "reason": "canary"]) } }
        )
    }

    func emit(_ event: [String: Any?]) {
        let text = PyJSON.compact(event)
        queue.async { [self] in broadcast(text) }
    }

    // MARK: approvals — owner "yes", then Touch ID for dangerous steps

    private func wait(_ id: String, _ kind: String, timeout: Double) async -> Bool {
        await withCheckedContinuation { cont in
            pendingLock.withLock { pending[id] = (kind, cont) }
            DispatchQueue.global().asyncAfter(deadline: .now() + timeout) { [weak self] in self?.resolve(id, kind, false) }
        }
    }

    @discardableResult
    func resolve(_ id: String, _ kind: String, _ ok: Bool) -> Bool {
        let p = pendingLock.withLock { () -> (kind: String, cont: CheckedContinuation<Bool, Never>)? in
            guard let p = pending[id], p.kind == kind else { return nil }
            pending[id] = nil
            return p
        }
        p?.cont.resume(returning: ok)
        return p != nil
    }

    func denyAll() {
        let all = pendingLock.withLock { () -> [CheckedContinuation<Bool, Never>] in
            defer { pending.removeAll() }
            return pending.values.map(\.cont)
        }
        all.forEach { $0.resume(returning: false) }
    }

    func approve(_ prompt: String, _ risk: Decision, _ lang: String, _ confirmed: Bool) async -> Bool {
        if risk == .safe { return true }
        if !confirmed {
            let cid = Turn.newID()
            emit(["type": "confirm_request", "id": cid, "prompt": prompt, "lang": lang, "risk": Executor.risk(risk)])
            let ok = await wait(cid, "confirm", timeout: 30)
            audit.append("approval", ["id": cid, "step": "confirm", "risk": risk.rawValue, "prompt": prompt, "ok": ok])
            if !ok { return false }
        }
        if risk != .dangerous { return true }
        let aid = Turn.newID()
        emit(["type": "auth_required", "id": aid, "reason": prompt, "risk": Executor.risk(risk)])
        let ok = await wait(aid, "auth", timeout: 60)
        audit.append("approval", ["id": aid, "step": "touch_id", "risk": risk.rawValue, "prompt": prompt, "ok": ok])
        return ok
    }

    // MARK: turns

    static let undoPattern = #"^(?:hey\s+)?(?:sasu[,\s]*)?(?:undo(?: that| it)?|cancel that|திருப்பி\s*மாத்து|thiruppi\s*maathu)[.!]?$"#

    private var activeTurn: Int = 0  // generation number of the running turn, 0 = none
    private var generation = 0

    func start(_ work: @escaping () async -> Void) {
        stopTurn()
        generation += 1
        let gen = generation
        pendingLock.withLock { activeTurn = gen }
        current = Task { [weak self] in
            await work()
            self?.pendingLock.withLock { if self?.activeTurn == gen { self?.activeTurn = 0 } }
        }
    }

    /// Stops the running turn. Returns false if nothing was running (like Python's `_stop`).
    @discardableResult
    func stopTurn() -> Bool {
        denyAll()
        let running = pendingLock.withLock { () -> Bool in
            defer { activeTurn = 0 }
            return activeTurn != 0
        }
        current?.cancel()
        current = nil
        return running
    }

    func speak(_ text: String, _ lang: String) async {
        let words = text.split(separator: " ", omittingEmptySubsequences: false).map(String.init)
        emit(["type": "say_start", "text": words.first ?? "", "lang": lang])
        for w in words.dropFirst() {
            try? await Task.sleep(nanoseconds: 30_000_000)
            emit(["type": "say_chunk", "text": " " + w])
        }
        emit(["type": "say_end"])
    }

    func textTurn(_ raw: String) async {
        let text = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        let lang = detectLang(text)
        if FastPath.match(Self.undoPattern, text) != nil { return await undoTurn(nil) }
        guard let fast = FastPath.parse(text) else {
            emit(["type": "transcript", "text": text, "lang": lang])
            emit(["type": "error", "code": "not_implemented", "message": "The Swift core can't answer that yet."])
            emit(["type": "turn_done", "ok": false])
            return
        }
        let turn = Turn(lang: lang)
        audit.append("command", ["source": "owner", "text": text, "turn": turn.id, "fast": fast.kind])
        emit(["type": "transcript", "text": text, "lang": lang])
        var ok = true
        var content = ""
        for (name, args) in fast.calls {
            let r = await executor.call(name, args, turn)
            ok = ok && r.hasPrefix("OK")
            content += r
        }
        let reply = !ok ? (lang != "ta" ? "That didn't work." : "அது சரியா வேலை செய்யல.")
            : fast.kind == "battery" ? batteryReply(content, lang)
            : (lang == "ta" ? fast.sayTa : fast.sayEn)
        await speak(reply, lang)
        let actions = journal.pending(turn: turn.id)
        if !actions.isEmpty {
            emit(["type": "undo_available", "turn_id": turn.id, "actions": actions.map { Tools.describe(kind: $0.kind, data: $0.data) }])
        }
        emit(["type": "turn_done", "ok": ok])
    }

    func undoTurn(_ id: String?) async {
        guard let tid = id ?? journal.lastTurn() else {
            await speak("There's nothing to undo.", "en")
            emit(["type": "turn_done", "ok": true])
            return
        }
        let (ok, items) = await executor.undo(turn: tid)
        let summary = items.isEmpty ? "nothing to undo" : items.joined(separator: "; ")
        audit.append("undo", ["turn": tid, "ok": ok, "summary": summary])
        emit(["type": "undone", "turn_id": tid, "ok": ok, "summary": summary])
        await speak(ok ? "Undone: \(summary)." : "Partly undone: \(summary).", "en")
        emit(["type": "turn_done", "ok": ok])
    }

    /// Starts listening on 127.0.0.1 and returns the port.
    public func start(port: UInt16 = 0) throws -> UInt16 {
        let params = NWParameters.tcp
        params.requiredLocalEndpoint = .hostPort(host: "127.0.0.1", port: NWEndpoint.Port(rawValue: port) ?? .any)
        params.allowLocalEndpointReuse = true
        let listener = try NWListener(using: params)
        let ready = DispatchSemaphore(value: 0)
        var failure: Error?
        listener.stateUpdateHandler = { state in
            switch state {
            case .ready: ready.signal()
            case let .failed(e): failure = e; ready.signal()
            default: break
            }
        }
        listener.newConnectionHandler = { [weak self] conn in self?.accept(conn) }
        listener.start(queue: queue)
        ready.wait()
        if let failure { throw failure }
        self.listener = listener
        return listener.port?.rawValue ?? 0
    }

    // MARK: control (trusted stdin channel)

    /// Waits until every queued control message has been handled (before exiting).
    public func drain() { queue.sync {} }

    public func control(_ msg: [String: Any]) {
        queue.async { [self] in
            switch msg["type"] as? String {
            case "lock":
                if let r = msg["reason"] as? String {
                    if stopTurn() {
                        broadcast(#"{"type":"error","code":"locked","message":"Sasu is locked"}"#)
                        broadcast(#"{"type":"turn_done","ok":false}"#)
                    }
                    locks.insert(r)
                    audit.append("lock", ["reason": r])
                    broadcast(PyJSON.compact(["type": "locked", "reasons": locks.sorted()]))
                }
            case "unlock":
                if let r = msg["reason"] as? String, locks.remove(r) != nil {
                    audit.append("unlock", ["reason": r])
                    broadcast(locks.isEmpty ? #"{"type":"unlocked"}"# : PyJSON.compact(["type": "locked", "reasons": locks.sorted()]))
                }
            case "secret":
                // Keys are held in memory only and never logged; phase 1 only notes presence.
                audit.append("key", ["provider": msg["provider"] as? String ?? "", "present": !((msg["key"] as? String) ?? "").isEmpty])
            case "auth_result":
                if let id = msg["id"] as? String { resolve(id, "auth", (msg["ok"] as? Bool) ?? false) }
            case "cancel":
                audit.append("cancel", ["source": "kill_switch"])
                if stopTurn() {
                    broadcast(#"{"type":"error","code":"cancelled","message":"Stopped"}"#)
                    broadcast(#"{"type":"turn_done","ok":false}"#)
                }
            default:
                break
            }
        }
    }

    // MARK: connections

    private func accept(_ conn: NWConnection) {
        let client = Client(conn: conn, server: self)
        clients[ObjectIdentifier(client)] = client
        conn.stateUpdateHandler = { [weak self, weak client] state in
            if case .cancelled = state, let client { self?.clients.removeValue(forKey: ObjectIdentifier(client)) }
            if case .failed = state { conn.cancel() }
        }
        conn.start(queue: queue)
        client.readRequest()
    }

    func broadcast(_ text: String) {
        for c in clients.values where c.isWebSocket { c.send(WebSocket.text(text)) }
    }

    func handleHTTP(_ req: HTTPRequest, _ client: Client) {
        let (path, query) = req.pathAndQuery
        if path == "/ws", req.header("upgrade")?.lowercased() == "websocket" {
            let origin = req.header("origin")
            if let origin, !origins.contains(origin) {
                audit.append("rejected", ["reason": "origin", "origin": origin])
                return client.respond(403, "Forbidden")
            }
            guard secureEquals(query["t"] ?? "", token) else {
                audit.append("rejected", ["reason": "bad_token", "origin": origin ?? ""])
                return client.respond(403, "Forbidden")
            }
            guard let key = req.header("sec-websocket-key") else { return client.respond(400, "Bad Request") }
            client.upgrade(acceptKey: WebSocket.accept(key: key))
            client.send(WebSocket.text(PyJSON.compact(["type": "ready", "version": sasuVersion, "demo": false])))
            if !locks.isEmpty { client.send(WebSocket.text(PyJSON.compact(["type": "locked", "reasons": locks.sorted()]))) }
            return
        }
        switch path {
        case "/api/health":
            client.respond(200, #"{"ok":true}"#, json: true)
        case "/api/audit":
            guard secureEquals(req.header("authorization") ?? "", "Bearer \(token)") else { return client.respond(401, #"{"detail":"Unauthorized"}"#, json: true) }
            let limit = Int(query["limit"] ?? "") ?? 100
            let rows = audit.recent(limit: limit).map { e -> String in
                #"{"id":\#(e.id),"at":\#(e.at),"kind":\#(PyJSON.quote(e.kind)),"data":\#(e.data),"hash":"\#(e.hash)"}"#
            }
            client.respond(200, "[" + rows.joined(separator: ",") + "]", json: true)
        case "/api/security":
            guard secureEquals(req.header("authorization") ?? "", "Bearer \(token)") else { return client.respond(401, #"{"detail":"Unauthorized"}"#, json: true) }
            let s = audit.verify()
            client.respond(200, PyJSON.compact(["chain": ["ok": s.ok, "entries": s.entries, "broken_at": s.brokenAt.map { Int($0) } as Any?], "locks": locks.sorted(), "core": "swift"]), json: true)
        default:
            client.respond(404, #"{"detail":"Not Found"}"#, json: true)
        }
    }

    func handleText(_ text: String, _ client: Client) {
        guard text.utf8.count <= Self.maxMessage, client.limiter.allow() else {
            audit.append("rejected", ["reason": "rate_or_size"])
            return client.send(WebSocket.text(#"{"type":"error","code":"rate_limited","message":"Too many commands"}"#))
        }
        guard let obj = (try? JSONSerialization.jsonObject(with: Data(text.utf8))) as? [String: Any], let type = obj["type"] as? String else {
            return client.send(WebSocket.text(#"{"type":"error","code":"bad_command","message":"Expected a JSON object with a type"}"#))
        }
        if ["text_command", "undo"].contains(type), !locks.isEmpty {
            audit.append("rejected", ["reason": "locked", "command": type])
            return client.send(WebSocket.text(#"{"type":"error","code":"locked","message":"Sasu is locked"}"#))
        }
        switch type {
        case "text_command":
            let text = obj["text"] as? String ?? ""
            start { [weak self] in await self?.textTurn(text) }
        case "undo":
            let id = obj["turn_id"] as? String
            start { [weak self] in await self?.undoTurn(id) }
        case "confirm_response":
            resolve(obj["id"] as? String ?? "", "confirm", obj["approved"] as? Bool ?? false)
        case "cancel":
            audit.append("cancel", ["source": "ui"])
            if stopTurn() {
                broadcast(#"{"type":"error","code":"cancelled","message":"Stopped"}"#)
                broadcast(#"{"type":"turn_done","ok":false}"#)
            }
        case "lock":
            control(["type": "lock", "reason": "user"])
        default:
            client.send(WebSocket.text(PyJSON.compact(["type": "error", "code": "not_implemented", "message": "The Swift core can't do \"\(type)\" yet"])))
        }
    }
}

extension PyJSON {
    /// Compact JSON (pydantic's `model_dump_json` style) for wire messages.
    public static func compact(_ value: [String: Any?]) -> String {
        dumps(value).replacingOccurrences(of: "\", \"", with: "\",\"")
            .replacingOccurrences(of: "\": ", with: "\":")
            .replacingOccurrences(of: ", \"", with: ",\"")
    }
}

// MARK: - HTTP plumbing

struct HTTPRequest {
    let method: String
    let target: String
    let headers: [String: String]

    func header(_ name: String) -> String? { headers[name.lowercased()] }

    var pathAndQuery: (String, [String: String]) {
        let parts = target.split(separator: "?", maxSplits: 1).map(String.init)
        var q: [String: String] = [:]
        if parts.count == 2 {
            for pair in parts[1].split(separator: "&") {
                let kv = pair.split(separator: "=", maxSplits: 1).map { String($0).replacingOccurrences(of: "+", with: " ").removingPercentEncoding ?? String($0) }
                if let k = kv.first { q[k] = kv.count > 1 ? kv[1] : "" }
            }
        }
        return (parts.first ?? "/", q)
    }

    static func parse(_ data: Data) -> HTTPRequest? {
        guard let text = String(data: data, encoding: .utf8) else { return nil }
        var lines = text.components(separatedBy: "\r\n")
        let first = lines.removeFirst().split(separator: " ")
        guard first.count >= 2 else { return nil }
        var headers: [String: String] = [:]
        for line in lines where !line.isEmpty {
            guard let i = line.firstIndex(of: ":") else { continue }
            headers[line[..<i].lowercased()] = line[line.index(after: i)...].trimmingCharacters(in: .whitespaces)
        }
        return HTTPRequest(method: String(first[0]), target: String(first[1]), headers: headers)
    }
}

final class Client {
    let conn: NWConnection
    unowned let server: CoreServer
    let limiter = RateLimiter()
    private(set) var isWebSocket = false
    private var buffer = Data()
    private var fragments = Data()

    init(conn: NWConnection, server: CoreServer) {
        self.conn = conn
        self.server = server
    }

    func send(_ data: Data) { conn.send(content: data, completion: .contentProcessed { _ in }) }

    func respond(_ status: Int, _ body: String, json: Bool = false) {
        let reason = [200: "OK", 400: "Bad Request", 401: "Unauthorized", 403: "Forbidden", 404: "Not Found"][status] ?? "Error"
        let head = "HTTP/1.1 \(status) \(reason)\r\nContent-Type: \(json ? "application/json" : "text/plain")\r\nContent-Length: \(body.utf8.count)\r\nConnection: close\r\n\r\n"
        conn.send(content: Data((head + body).utf8), completion: .contentProcessed { [conn] _ in conn.cancel() })
    }

    func upgrade(acceptKey: String) {
        isWebSocket = true
        let head = "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: \(acceptKey)\r\n\r\n"
        send(Data(head.utf8))
        readFrames()
    }

    func readRequest() {
        conn.receive(minimumIncompleteLength: 1, maximumLength: 65_536) { [self] data, _, done, error in
            if let data { buffer.append(data) }
            if let end = buffer.range(of: Data("\r\n\r\n".utf8)) {
                let head = buffer[..<end.lowerBound]
                buffer = Data(buffer[end.upperBound...])
                guard let req = HTTPRequest.parse(Data(head)) else { return respond(400, "Bad Request") }
                server.handleHTTP(req, self)
            } else if buffer.count > 32_768 || done || error != nil {
                conn.cancel()
            } else {
                readRequest()
            }
        }
    }

    private func readFrames() {
        conn.receive(minimumIncompleteLength: 1, maximumLength: 65_536) { [self] data, _, done, error in
            if let data { buffer.append(data) }
            do {
                while let frame = try WebSocket.decode(&buffer) {
                    handle(frame)
                }
            } catch {
                send(WebSocket.encode(.close, Data([0x03, 0xEA])))  // 1002 protocol error
                conn.cancel()
                return
            }
            if done || error != nil { conn.cancel() } else { readFrames() }
        }
    }

    private func handle(_ frame: WebSocket.Frame) {
        switch frame.opcode {
        case .ping: send(WebSocket.encode(.pong, frame.payload))
        case .close: send(WebSocket.encode(.close, frame.payload.prefix(2))); conn.cancel()
        case .text, .continuation:
            fragments.append(frame.payload)
            if fragments.count > CoreServer.maxMessage * 4 { fragments.removeAll(); return }
            if frame.fin {
                let text = String(decoding: fragments, as: UTF8.self)
                fragments.removeAll()
                server.handleText(text, self)
            }
        default: break
        }
    }
}
