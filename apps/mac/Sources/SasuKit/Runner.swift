@preconcurrency import Dispatch
import Foundation

public struct Proc: Sendable {
    public let code: Int32
    public let out: String
    public let err: String
    public var ok: Bool { code == 0 }
}

/// Runs a program (never through a shell) with a timeout. Same contract as tools/runtime.py.
public protocol Runner: Sendable {
    func run(_ args: [String], timeout: Double, stdin: String?) async -> Proc
}

extension Runner {
    public func run(_ args: [String], timeout: Double = 15, stdin: String? = nil) async -> Proc {
        await run(args, timeout: timeout, stdin: stdin)
    }
}

/// osascript args. User data must go in argv (`item n of argv`), never in the script.
public func applescript(_ lines: String...) -> [String] {
    var a = ["osascript", "-e", "on run argv"]
    for l in lines { a += ["-e", l] }
    return a + ["-e", "end run"]
}

public struct ProcessRunner: Runner {
    public init() {}

    public func run(_ args: [String], timeout: Double, stdin: String?) async -> Proc {
        await withCheckedContinuation { cont in
            let p = Process()
            p.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            p.arguments = args
            p.environment = ["PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "HOME": NSHomeDirectory(), "LANG": "en_US.UTF-8"]
            let out = Pipe(), err = Pipe(), inp = Pipe()
            p.standardOutput = out
            p.standardError = err
            p.standardInput = stdin == nil ? FileHandle.nullDevice : inp
            do { try p.run() } catch {
                return cont.resume(returning: Proc(code: 127, out: "", err: "\(error)"))
            }
            if let stdin {
                inp.fileHandleForWriting.write(Data(stdin.utf8))
                try? inp.fileHandleForWriting.close()
            }
            let timer = DispatchWorkItem { if p.isRunning { p.terminate() } }
            DispatchQueue.global().asyncAfter(deadline: .now() + timeout, execute: timer)
            DispatchQueue.global().async {
                let o = out.fileHandleForReading.readDataToEndOfFile()
                let e = err.fileHandleForReading.readDataToEndOfFile()
                p.waitUntilExit()
                timer.cancel()
                let timedOut = p.terminationReason == .uncaughtSignal
                cont.resume(returning: Proc(code: timedOut ? 124 : p.terminationStatus, out: String(decoding: o, as: UTF8.self), err: timedOut ? "timed out" : String(decoding: e, as: UTF8.self)))
            }
        }
    }
}

/// Records commands instead of running them (tests). Configured from the trusted stdin
/// config, never from the network: {"log": path, "default": "50", "outputs": [[substring, out]]}.
public final class FakeRunner: Runner, @unchecked Sendable {
    let log: String
    let fallback: String
    let outputs: [(String, String)]
    let lock = NSLock()

    public init(config: [String: Any]) {
        log = config["log"] as? String ?? "/dev/null"
        fallback = config["default"] as? String ?? ""
        outputs = (config["outputs"] as? [[String]] ?? []).compactMap { $0.count == 2 ? ($0[0], $0[1]) : nil }
    }

    public func run(_ args: [String], timeout: Double, stdin: String?) async -> Proc { record(args, stdin) }

    private func record(_ args: [String], _ stdin: String?) -> Proc {
        lock.withLock {
            let line = PyJSON.dumps((args + [stdin ?? ""]) as [Any?]) + "\n"
            if let h = FileHandle(forWritingAtPath: log) {
                h.seekToEndOfFile()
                h.write(Data(line.utf8))
                try? h.close()
            } else {
                FileManager.default.createFile(atPath: log, contents: Data(line.utf8))
            }
            let joined = args.joined(separator: " ")
            return Proc(code: 0, out: outputs.first { joined.contains($0.0) }?.1 ?? fallback, err: "")
        }
    }
}
