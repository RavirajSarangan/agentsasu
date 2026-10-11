import Foundation

/// One request from start to finish.
public final class Turn: @unchecked Sendable {
    public let id: String
    public let lang: String
    public var role: String
    public var untrustedSeen = false
    public var planApproved = false
    public var untrustedTexts: [String] = []
    public var calls: [[String: Any]] = []

    public init(id: String = Turn.newID(), lang: String, role: String = "owner") {
        self.id = id
        self.lang = lang
        self.role = role
    }

    public static func newID(_ n: Int = 12) -> String {
        String(UUID().uuidString.lowercased().replacingOccurrences(of: "-", with: "").prefix(n))
    }
}

public func detectLang(_ text: String) -> String {
    text.unicodeScalars.contains { (0x0B80...0x0BFF).contains($0.value) } ? "ta" : "en"
}

/// The approval question for a call. Same wording as brain/agent.py `confirm_text`.
public func confirmText(_ tool: String, _ a: Args) -> String {
    let n = list(a, "paths").count
    switch tool {
    case "files_move":
        let d = name(s(a, "destination"))
        return "Move \(n) item(s) to \(d.isEmpty ? "that folder" : d)?"
    case "files_trash": return "Throw away \(n) item(s)? (You can say “Sasu undo”.)"
    case "files_rename": return "Rename \(name(s(a, "path"))) to \(s(a, "new_name"))?"
    case "files_new_folder": return "Create the folder \(name(s(a, "path")))?"
    case "apps_quit": return "Quit \(s(a, "app"))?"
    case "system_wifi": return "Turn Wi-Fi \(b(a, "on") ? "on" : "off")?"
    case "shell_run": return "Run this command: \(String(s(a, "command").prefix(160)))"
    default:
        let shown = a.keys.sorted().map { "\($0)=\(String(PyJSON.dumps(a[$0]).prefix(60)))" }.joined(separator: ", ")
        return "Allow \(tool)(\(shown))?"
    }
}

/// Runs one tool call: trap files → leak guard → policy → role → approval → run → journal → audit.
public final class Executor: @unchecked Sendable {
    public typealias Emit = ([String: Any?]) -> Void
    public typealias Approve = (_ prompt: String, _ risk: Decision, _ lang: String, _ confirmed: Bool) async -> Bool

    let emit: Emit
    let approve: Approve
    let audit: AuditLog
    let journal: UndoJournal
    let holding: String
    let runner: Runner
    let canaries: Canaries?
    let onAlarm: ((String, String) async -> Void)?

    public init(emit: @escaping Emit, approve: @escaping Approve, audit: AuditLog, journal: UndoJournal, holding: String, runner: Runner, canaries: Canaries? = nil, onAlarm: ((String, String) async -> Void)? = nil) {
        Tools.ensure()
        self.emit = emit
        self.approve = approve
        self.audit = audit
        self.journal = journal
        self.holding = holding
        self.runner = runner
        self.canaries = canaries
        self.onAlarm = onAlarm
    }

    public func decision(_ name: String, _ args: Args, _ turn: Turn) -> Decision {
        guard let tool = Tools.registry[name] else { return .deny }
        if turn.role == "guest", !Roles.guestTools.contains(name) { return .deny }
        var d = tool.decision(args)
        if turn.untrustedSeen, d != .safe { d = d.bumped }
        return Roles.allowed(role: turn.role, tool: name, args: args, decision: d)
    }

    static func risk(_ d: Decision) -> String { d == .deny ? "safe" : d.rawValue }

    private func alarm(_ kind: String, _ detail: String, _ name: String, _ args: Args, _ cid: String) async -> String {
        audit.append("alarm", ["alarm": kind, "detail": detail, "tool": name, "args": args])
        emit(["type": "tool_start", "id": cid, "name": name, "args": args, "risk": "dangerous"])
        emit(["type": "tool_end", "id": cid, "ok": false, "summary": "Blocked: " + detail])
        emit(["type": "alarm", "kind": kind, "detail": detail])
        await onAlarm?(kind, detail)
        return "BLOCKED for security. Stop and tell the user briefly that you were stopped."
    }

    @discardableResult
    public func call(_ name: String, _ args: Args, _ turn: Turn) async -> String {
        let cid = Turn.newID(8)
        if let why = canaries?.trippedBy(args) { return await alarm("canary", why, name, args, cid) }
        if LeakGuard.leaks(tool: name, args: args, untrusted: turn.untrustedTexts) {
            return await alarm("leak", "tried to send out text it had just read", name, args, cid)
        }
        let d = decision(name, args, turn)
        guard let tool = Tools.registry[name], d != .deny else {
            let why = turn.role == "guest" ? "guest" : turn.role != "owner" ? turn.role : "policy"
            audit.append("rejected", ["reason": why, "tool": name, "args": args])
            emit(["type": "tool_start", "id": cid, "name": name, "args": args, "risk": "dangerous"])
            emit(["type": "tool_end", "id": cid, "ok": false, "summary": "Blocked for safety"])
            return "BLOCKED: this action is not allowed. Tell the user briefly."
        }
        if d != .safe {
            let covered = turn.planApproved && d == .confirm
            if !covered, !(await approve(confirmText(name, args), d, turn.lang, turn.planApproved)) {
                audit.append("tool", ["tool": name, "args": args, "decision": d.rawValue, "ok": false, "summary": "declined"])
                return "The user said no. Don't do it; acknowledge briefly."
            }
        }
        emit(["type": "tool_start", "id": cid, "name": name, "args": args, "risk": Self.risk(d)])
        let ctx = ToolContext(turnID: turn.id, journal: journal, holding: holding, runner: runner)
        let res = await tool.run(args, ctx)
        emit(["type": "tool_end", "id": cid, "ok": res.ok, "summary": String(res.summary.prefix(120))])
        if let app = res.app { emit(["type": "focus_app", "app": app]) }
        audit.append("tool", ["tool": name, "args": args, "decision": d.rawValue, "ok": res.ok, "summary": res.summary])
        turn.calls.append(["tool": name, "args": args])
        var content = res.content
        if tool.untrustedOutput, !content.isEmpty {
            turn.untrustedSeen = true
            turn.untrustedTexts.append(String(content.prefix(20_000)))
            if let c = canaries, c.tokens.contains(where: { content.contains($0) }) {
                _ = await alarm("canary", "read a trap file", name, args, cid)
                return "BLOCKED for security. Stop and tell the user briefly that you were stopped."
            }
            content = "<untrusted>\n" + content.replacingOccurrences(of: "</untrusted>", with: "</ untrusted>") + "\n</untrusted>"
        }
        return "\(res.ok ? "OK" : "FAILED"): \(res.summary)\n\(content)".trimmingCharacters(in: .whitespacesAndNewlines)
    }

    /// Reverse a turn newest-first. Same as undo.py `undo_turn`.
    public func undo(turn tid: String) async -> (Bool, [String]) {
        let ctx = ToolContext(turnID: tid, journal: journal, holding: holding, runner: runner)
        var done: [Int64] = []
        var items: [String] = []
        for action in journal.pending(turn: tid).reversed() {
            if await Tools.undoStep(kind: action.kind, data: action.data, ctx: ctx) {
                done.append(action.id)
                items.append(Tools.describe(kind: action.kind, data: action.data))
            }
        }
        journal.markUndone(done)
        return (true, items)
    }
}

public func batteryReply(_ content: String, _ lang: String) -> String {
    guard let m = FastPath.match(#"Battery: (\d+)%"#, content), let pct = m[1] else {
        return lang != "ta" ? "I couldn't read the battery." : "Battery பார்க்க முடியல."
    }
    let low = content.lowercased()
    let charging = low.contains("charging") && !low.contains("discharging")
    return lang == "ta" ? "Battery \(pct) சதவீதம்\(charging ? ", charge ஆகுது" : "")." : "Battery is at \(pct) percent\(charging ? ", charging" : "")."
}
