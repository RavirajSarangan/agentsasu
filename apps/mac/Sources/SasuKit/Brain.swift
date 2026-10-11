import Foundation

/// The shared AI contract (tools, roles, providers, prompt), generated from Python.
public enum BrainContract {
    nonisolated(unsafe) public static let doc: [String: Any] =
        (try? JSONSerialization.jsonObject(with: Data(brainContractJSON.utf8))) as? [String: Any] ?? [:]

    public static var tools: [[String: Any]] { doc["tools"] as? [[String: Any]] ?? [] }
    public static var guestTools: Set<String> { Set(doc["guest_tools"] as? [String] ?? []) }
    public static var kidTools: Set<String> { Set(doc["kid_tools"] as? [String] ?? []) }
    static var providers: [String: [String: Any]] { doc["providers"] as? [String: [String: Any]] ?? [:] }

    public static func schemas(only: Set<String>?) -> [[String: Any]] {
        tools.filter { t in only.map { $0.contains(((t["function"] as? [String: Any])?["name"] as? String) ?? "") } ?? true }
    }

    public static func systemPrompt(fun: Bool, now: Date = Date()) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "EEEE dd MMMM yyyy, HH:mm"
        let base = (doc["system"] as? String ?? "")
            .replacingOccurrences(of: "{home}", with: NSHomeDirectory())
            .replacingOccurrences(of: "{now}", with: f.string(from: now))
        return fun ? base + (doc["fun"] as? String ?? "") : base
    }
}

public struct ProviderSpec {
    public let id: String
    public let label: String
    public var baseURL: String
    public let defaultModel: String
    public let prefer: String
    public let needsKey: Bool

    public static func get(_ id: String) -> ProviderSpec? {
        guard let p = BrainContract.providers[id] else { return nil }
        return ProviderSpec(id: id, label: p["label"] as? String ?? id, baseURL: p["base_url"] as? String ?? "",
                            defaultModel: p["default_model"] as? String ?? "", prefer: p["prefer"] as? String ?? "",
                            needsKey: p["needs_key"] as? Bool ?? true)
    }
}

/// The user's choice if available, else the newest model matching the provider's
/// preference. Same as providers.py `pick_model`.
public func pickModel(_ spec: ProviderSpec, _ available: [String], preferred: String? = nil) -> String {
    if let p = preferred, available.contains(p) { return p }
    let matches = available.compactMap { name -> ([Double], String)? in
        guard let m = FastPath.match(spec.prefer, name), let v = m.count > 1 ? m[1] : nil else { return nil }
        return (v.split(whereSeparator: { $0 == "." || $0 == "-" }).compactMap { Double($0) }, name)
    }
    if let best = matches.max(by: { $0.0.lexicographicallyPrecedes($1.0) }) { return best.1 }
    return available.contains(spec.defaultModel) || available.isEmpty ? spec.defaultModel : available[0]
}

public struct LLMError: Error, CustomStringConvertible {
    public let description: String
}

/// One OpenAI-compatible client for every provider. Same requests as providers.py.
public final class ChatClient: @unchecked Sendable {
    public let spec: ProviderSpec
    public let model: String
    let key: String?
    let session: URLSession

    public init(spec: ProviderSpec, key: String?, model: String) {
        self.spec = spec
        self.key = key
        self.model = model
        let cfg = URLSessionConfiguration.ephemeral
        cfg.timeoutIntervalForRequest = 60
        session = URLSession(configuration: cfg)
    }

    func request(_ path: String, body: Any? = nil) -> URLRequest {
        var r = URLRequest(url: URL(string: spec.baseURL + path)!)
        if let key, !key.isEmpty { r.setValue("Bearer \(key)", forHTTPHeaderField: "Authorization") }
        if let body {
            r.httpMethod = "POST"
            r.setValue("application/json", forHTTPHeaderField: "Content-Type")
            r.httpBody = try? JSONSerialization.data(withJSONObject: body)
        }
        return r
    }

    public func listModels() async -> [String] {
        guard let (data, resp) = try? await session.data(for: request("/models")), (resp as? HTTPURLResponse)?.statusCode == 200,
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return [] }
        return (obj["data"] as? [[String: Any]] ?? []).map { (($0["id"] as? String) ?? "").replacingOccurrences(of: "models/", with: "", options: .anchored) }
    }

    public func complete(_ messages: [[String: Any]], tools: [[String: Any]]) async throws -> [String: Any] {
        var body: [String: Any] = ["model": model, "messages": messages, "temperature": 0.3]
        if !tools.isEmpty {
            body["tools"] = tools
            body["tool_choice"] = "auto"
        }
        let data: Data, resp: URLResponse
        do {
            (data, resp) = try await session.data(for: request("/chat/completions", body: body))
        } catch {
            throw LLMError(description: "Couldn't reach \(spec.label): \(type(of: error))")
        }
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        if code == 401 || code == 403 { throw LLMError(description: "\(spec.label) rejected the API key. Check it in Settings → AI brain.") }
        if code == 429 { throw LLMError(description: "\(spec.label) free limit reached — try again in a minute.") }
        if code >= 400 { throw LLMError(description: "\(spec.label) error \(code): \(String(decoding: data.prefix(200), as: UTF8.self))") }
        guard let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let choices = obj["choices"] as? [[String: Any]], let msg = choices.first?["message"] as? [String: Any] else {
            throw LLMError(description: "\(spec.label) returned no answer")
        }
        return msg
    }
}

/// The agent loop: model ↔ tools, every call through the Executor. Same as brain/agent.py.
public final class Agent: @unchecked Sendable {
    public static let maxSteps = 12
    let client: ChatClient
    let ex: Executor
    let emit: Executor.Emit
    let fun: Bool
    public var context = ""
    public var sentChars = 0

    public init(client: ChatClient, executor: Executor, emit: @escaping Executor.Emit, fun: Bool) {
        self.client = client
        ex = executor
        self.emit = emit
        self.fun = fun
    }

    static func args(_ raw: Any?) -> Args {
        if let d = raw as? Args { return d }
        guard let s = raw as? String, let d = try? JSONSerialization.jsonObject(with: Data((s.isEmpty ? "{}" : s).utf8)) as? Args else { return [:] }
        return d
    }

    public func run(_ text: String, _ turn: Turn, history: [[String: Any]]) async throws -> String {
        let only: Set<String>? = turn.role == "guest" ? BrainContract.guestTools : turn.role == "kid" ? BrainContract.kidTools : nil
        let tools = BrainContract.schemas(only: only)
        var messages: [[String: Any]] = [["role": "system", "content": BrainContract.systemPrompt(fun: fun) + context]] + history + [["role": "user", "content": text]]
        for step in 0..<Self.maxSteps {
            let outgoing = Redact.object(messages) as? [[String: Any]] ?? messages
            sentChars += PyJSON.dumps(outgoing).unicodeScalars.count + PyJSON.asciiLength(tools)
            let msg = try await client.complete(outgoing, tools: tools)
            let raw = msg["tool_calls"] as? [[String: Any]] ?? []
            if raw.isEmpty {
                let reply = ((msg["content"] as? String) ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
                return reply.isEmpty ? "Done." : reply
            }
            let calls = raw.map { c -> (String, Args) in
                let f = c["function"] as? [String: Any] ?? [:]
                return ((f["name"] as? String) ?? "", Self.args(f["arguments"]))
            }
            if step == 0, calls.count > 1, calls.contains(where: { [.confirm, .dangerous].contains(ex.decision($0.0, $0.1, turn)) }) {
                emit(["type": "plan_preview", "id": Turn.newID(8), "steps": calls.map { String(confirmText($0.0, $0.1).trimmingCharacters(in: CharacterSet(charactersIn: "?"))) }])
                let worst = calls.map { ex.decision($0.0, $0.1, turn) }.max() ?? .safe
                guard await ex.approve("Do these \(calls.count) things?", worst == .deny ? .safe : worst, turn.lang, false) else {
                    return turn.lang == "ta" ? "சரி, எதுவும் செய்யல." : "Okay, I won't do that."
                }
                turn.planApproved = true
            }
            messages.append(["role": "assistant", "content": (msg["content"] as? String) ?? "", "tool_calls": raw])
            for (c, call) in zip(raw, calls) {
                let result = await ex.call(call.0, call.1, turn)
                messages.append(["role": "tool", "tool_call_id": (c["id"] as? String) ?? call.0, "name": call.0, "content": result])
            }
        }
        return "That took too many steps, so I stopped. Try a simpler request?"
    }
}
