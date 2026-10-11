import CryptoKit
import Foundation
import SQLite3

/// Append-only, hash-chained audit log; the same SQLite file and format as security/audit.py.
/// Every row stores sha256(prev | at(6 decimals) | kind | data).
public final class AuditLog {
    public struct Entry { public let id: Int64; public let at: Double; public let kind: String; public let data: String; public let hash: String }
    public struct Status: Equatable { public let ok: Bool; public let entries: Int; public let brokenAt: Int64? }

    public static let genesis = String(repeating: "0", count: 64)
    private static let schema = """
    CREATE TABLE IF NOT EXISTS audit (
      id    INTEGER PRIMARY KEY AUTOINCREMENT,
      at    REAL NOT NULL,
      kind  TEXT NOT NULL,
      data  TEXT NOT NULL,
      prev  TEXT NOT NULL,
      hash  TEXT NOT NULL
    );
    CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit
      BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
    CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit
      BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
    """

    private var db: OpaquePointer?
    private let lock = NSLock()

    public init(path: String) throws {
        guard sqlite3_open(path, &db) == SQLITE_OK else { throw AuditError.open(path) }
        guard sqlite3_exec(db, Self.schema, nil, nil, nil) == SQLITE_OK else { throw AuditError.sql(lastError) }
        chmod(path, 0o600)  // owner-only: other local users can't read history
    }

    deinit { sqlite3_close(db) }

    public static func digest(prev: String, at: Double, kind: String, data: String) -> String {
        let text = "\(prev)|\(String(format: "%.6f", at))|\(kind)|\(data)"
        return SHA256.hash(data: Data(text.utf8)).map { String(format: "%02x", $0) }.joined()
    }

    @discardableResult
    public func append(_ kind: String, _ data: [String: Any?] = [:]) -> Entry {
        let body = PyJSON.dumps(Redact.object(data))
        lock.lock()
        defer { lock.unlock() }
        let prev = query("SELECT hash FROM audit ORDER BY id DESC LIMIT 1").first?[0] as? String ?? Self.genesis
        let at = Date().timeIntervalSince1970
        let hash = Self.digest(prev: prev, at: at, kind: kind, data: body)
        var stmt: OpaquePointer?
        sqlite3_prepare_v2(db, "INSERT INTO audit (at, kind, data, prev, hash) VALUES (?, ?, ?, ?, ?)", -1, &stmt, nil)
        sqlite3_bind_double(stmt, 1, at)
        for (i, s) in [kind, body, prev, hash].enumerated() { sqlite3_bind_text(stmt, Int32(i + 2), s, -1, SQLITE_TRANSIENT) }
        sqlite3_step(stmt)
        sqlite3_finalize(stmt)
        return Entry(id: sqlite3_last_insert_rowid(db), at: at, kind: kind, data: body, hash: hash)
    }

    public func recent(limit: Int = 100) -> [Entry] {
        lock.lock()
        defer { lock.unlock() }
        return query("SELECT id, at, kind, data, hash FROM audit ORDER BY id DESC LIMIT \(max(1, min(limit, 1000)))").map {
            Entry(id: $0[0] as! Int64, at: $0[1] as! Double, kind: $0[2] as! String, data: $0[3] as! String, hash: $0[4] as! String)
        }
    }

    public func verify() -> Status {
        lock.lock()
        defer { lock.unlock() }
        var prev = Self.genesis
        var count = 0
        for r in query("SELECT id, at, kind, data, prev, hash FROM audit ORDER BY id") {
            count += 1
            let (id, at, kind, data, storedPrev, stored) = (r[0] as! Int64, r[1] as! Double, r[2] as! String, r[3] as! String, r[4] as! String, r[5] as! String)
            if storedPrev != prev || Self.digest(prev: prev, at: at, kind: kind, data: data) != stored {
                return Status(ok: false, entries: count, brokenAt: id)
            }
            prev = stored
        }
        return Status(ok: true, entries: count, brokenAt: nil)
    }

    private var lastError: String { String(cString: sqlite3_errmsg(db)) }

    private func query(_ sql: String) -> [[Any?]] {
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else { return [] }
        defer { sqlite3_finalize(stmt) }
        var rows: [[Any?]] = []
        while sqlite3_step(stmt) == SQLITE_ROW {
            rows.append((0..<sqlite3_column_count(stmt)).map { i -> Any? in
                switch sqlite3_column_type(stmt, i) {
                case SQLITE_INTEGER: return sqlite3_column_int64(stmt, i)
                case SQLITE_FLOAT: return sqlite3_column_double(stmt, i)
                case SQLITE_TEXT: return String(cString: sqlite3_column_text(stmt, i))
                default: return nil
                }
            })
        }
        return rows
    }
}

public enum AuditError: Error { case open(String), sql(String) }

private let SQLITE_TRANSIENT = unsafeBitCast(-1, to: sqlite3_destructor_type.self)
