import Foundation
import SQLite3

/// Every change a tool makes, with what's needed to reverse it. Same file as undo.py.
public final class UndoJournal {
    public struct Action { public let id: Int64; public let turnID: String; public let kind: String; public let data: [String: Any] }

    private var db: OpaquePointer?
    private let lock = NSLock()

    public init(path: String) throws {
        guard sqlite3_open(path, &db) == SQLITE_OK else { throw AuditError.open(path) }
        sqlite3_exec(db, "CREATE TABLE IF NOT EXISTS actions (id INTEGER PRIMARY KEY AUTOINCREMENT, turn_id TEXT, at REAL, kind TEXT, data TEXT, undone INTEGER DEFAULT 0)", nil, nil, nil)
        chmod(path, 0o600)
    }

    deinit { sqlite3_close(db) }

    public func record(turn: String, kind: String, _ data: [String: Any?]) {
        lock.lock()
        defer { lock.unlock() }
        var stmt: OpaquePointer?
        sqlite3_prepare_v2(db, "INSERT INTO actions (turn_id, at, kind, data) VALUES (?, ?, ?, ?)", -1, &stmt, nil)
        sqlite3_bind_text(stmt, 1, turn, -1, transient)
        sqlite3_bind_double(stmt, 2, Date().timeIntervalSince1970)
        sqlite3_bind_text(stmt, 3, kind, -1, transient)
        sqlite3_bind_text(stmt, 4, PyJSON.dumps(data), -1, transient)
        sqlite3_step(stmt)
        sqlite3_finalize(stmt)
    }

    public func pending(turn: String) -> [Action] {
        lock.lock()
        defer { lock.unlock() }
        var stmt: OpaquePointer?
        sqlite3_prepare_v2(db, "SELECT id, turn_id, kind, data FROM actions WHERE turn_id = ? AND undone = 0 ORDER BY id", -1, &stmt, nil)
        sqlite3_bind_text(stmt, 1, turn, -1, transient)
        defer { sqlite3_finalize(stmt) }
        var out: [Action] = []
        while sqlite3_step(stmt) == SQLITE_ROW {
            let data = String(cString: sqlite3_column_text(stmt, 3))
            let obj = (try? JSONSerialization.jsonObject(with: Data(data.utf8))) as? [String: Any] ?? [:]
            out.append(Action(id: sqlite3_column_int64(stmt, 0), turnID: String(cString: sqlite3_column_text(stmt, 1)), kind: String(cString: sqlite3_column_text(stmt, 2)), data: obj))
        }
        return out
    }

    public func lastTurn() -> String? {
        lock.lock()
        defer { lock.unlock() }
        var stmt: OpaquePointer?
        sqlite3_prepare_v2(db, "SELECT turn_id FROM actions WHERE undone = 0 ORDER BY id DESC LIMIT 1", -1, &stmt, nil)
        defer { sqlite3_finalize(stmt) }
        return sqlite3_step(stmt) == SQLITE_ROW ? String(cString: sqlite3_column_text(stmt, 0)) : nil
    }

    public func markUndone(_ ids: [Int64]) {
        lock.lock()
        defer { lock.unlock() }
        for id in ids { sqlite3_exec(db, "UPDATE actions SET undone = 1 WHERE id = \(id)", nil, nil, nil) }
    }
}

private let transient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)
