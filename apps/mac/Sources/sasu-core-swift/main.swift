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
let server = CoreServer(token: token, audit: audit, dev: dev)
guard let port = try? server.start() else { fail("can't listen on 127.0.0.1") }
audit.append("start", ["version": sasuVersion, "demo": false, "dev": dev, "core": "swift"])
print("{\"port\": \(port)}")

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
