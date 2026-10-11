import Foundation

/// Instant commands parsed locally in English, Tanglish and Tamil. Same as fastpath.py.
public struct Fast {
    public var calls: [(String, [String: Any])]
    public var sayEn: String
    public var sayTa: String
    public var kind: String
}

public enum FastPath {
    static let sites: [String: String] = [
        "google": "google.com", "youtube": "youtube.com", "gmail": "mail.google.com", "github": "github.com",
        "whatsapp": "web.whatsapp.com", "instagram": "instagram.com", "facebook": "facebook.com",
        "netflix": "netflix.com", "chatgpt": "chatgpt.com", "maps": "maps.google.com",
        "linkedin": "linkedin.com", "x": "x.com", "twitter": "x.com",
    ]
    static let apps: [String: String] = [
        "safari": "Safari", "chrome": "Google Chrome", "google chrome": "Google Chrome", "spotify": "Spotify",
        "music": "Music", "finder": "Finder", "notes": "Notes", "calendar": "Calendar", "mail": "Mail",
        "messages": "Messages", "whatsapp app": "WhatsApp", "vs code": "Visual Studio Code",
        "vscode": "Visual Studio Code", "code": "Visual Studio Code", "terminal": "Terminal",
        "settings": "System Settings", "system settings": "System Settings", "photos": "Photos",
        "camera": "Photo Booth", "calculator": "Calculator", "reminders": "Reminders", "slack": "Slack",
        "zoom": "zoom.us", "word": "Microsoft Word", "excel": "Microsoft Excel", "teams": "Microsoft Teams",
        "figma": "Figma",
    ]

    nonisolated(unsafe) static var cache: [String: NSRegularExpression] = [:]
    static let cacheLock = NSLock()

    static func re(_ p: String) -> NSRegularExpression {
        cacheLock.lock()
        defer { cacheLock.unlock() }
        if let r = cache[p] { return r }
        let r = try! NSRegularExpression(pattern: p, options: [.caseInsensitive])
        cache[p] = r
        return r
    }

    static func match(_ p: String, _ s: String) -> [String?]? {
        guard let m = re(p).firstMatch(in: s, range: NSRange(s.startIndex..., in: s)) else { return nil }
        return (0..<m.numberOfRanges).map { i in Range(m.range(at: i), in: s).map { String(s[$0]) } }
    }

    static func has(_ s: String, _ pats: String...) -> Bool { pats.contains { match($0, s) != nil } }

    static func sub(_ p: String, _ s: String, _ with: String) -> String {
        re(p).stringByReplacingMatches(in: s, range: NSRange(s.startIndex..., in: s), withTemplate: with)
    }

    static func clean(_ text: String) -> String {
        var t = sub(#"^\s*(?:hey|hi|ok|okay|he)?[\s,]*(?:sasu|saasu|sashu|சாசு)[\s,.!]*"#, text.trimmingCharacters(in: .whitespacesAndNewlines), "")
        let tamilDigits = Array("௦௧௨௩௪௫௬௭௮௯")
        t = String(t.map { c in tamilDigits.firstIndex(of: c).map { Character(String($0)) } ?? c })
        t = sub(#"[.!?,]+$"#, t, "").trimmingCharacters(in: .whitespacesAndNewlines)
        return sub(#"\s+"#, t, " ")
    }

    /// Python's str.title(): capitalise the first letter of every run of letters.
    static func title(_ s: String) -> String {
        var out = ""
        var prevLetter = false
        for c in s {
            out += prevLetter ? c.lowercased() : c.uppercased()
            prevLetter = c.isLetter
        }
        return out
    }

    static func clock(_ format: String) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = format
        return f.string(from: Date())
    }

    public static func parse(_ text: String) -> Fast? {
        let low = clean(text).lowercased()
        let words = low.split(whereSeparator: { $0.isWhitespace })
        if low.isEmpty || words.count > 9 { return nil }

        // music
        if has(low, #"\b(next|skip)\b( (song|track|paattu|one))?\b"#, #"அடுத்த\s*பாட்டு"#, #"next\s*podu"#) {
            return Fast(calls: [("media_control", ["action": "next"])], sayEn: "Next song.", sayTa: "அடுத்த பாட்டு.", kind: "music")
        }
        if has(low, #"\b(previous|last|before)\s+(song|track)\b"#, #"munnadi\s*paattu"#, "முந்தைய") {
            return Fast(calls: [("media_control", ["action": "previous"])], sayEn: "Going back.", sayTa: "முந்தைய பாட்டு.", kind: "music")
        }
        if has(low, #"\b(pause|stop)\b.*\b(music|song|spotify|paattu)\b"#, #"^(pause|pause it|stop music)$"#, #"paattu\s*niruthu"#, #"பாட்ட?ை?\s*நிறுத்து"#) {
            return Fast(calls: [("media_control", ["action": "pause"])], sayEn: "Paused.", sayTa: "நிறுத்திட்டேன்.", kind: "music")
        }
        if has(low, #"\bplay\b.*\b(music|song|songs|spotify|something)\b"#, "^play$", "^resume", #"(paattu|music|song)\s*(podu|potu|play pannu)"#, #"பாட்டு\s*போடு"#, #"^(பாட்டு|பாட்ட|paattu|music|songs?)$"#) {
            return Fast(calls: [("media_control", ["action": "play"])], sayEn: "Playing.", sayTa: "பாட்டு போடறேன்.", kind: "music")
        }

        // volume
        if let m = match(#"(?:volume|sound|சத்தம்)\D{0,8}?(\d{1,3})|(\d{1,3})\s*(?:%|percent)?\s*(?:volume|sound)"#, low),
           let n = Int(m[1] ?? m[2] ?? "") {
            let level = max(0, min(100, n))
            return Fast(calls: [("system_volume", ["level": level])], sayEn: "Volume \(level).", sayTa: "சத்தம் \(level).", kind: "volume")
        }
        if has(low, #"\b(louder|volume up|increase (the )?volume|turn it up)\b"#, #"(sound|volume|sa(?:t|th)+am)\s*(jaasti|athigam|ethu|kootu)"#, #"ச(த்)?தம்?\s*(அதிக|கூட்டு)"#) {
            return Fast(calls: [("system_volume_step", ["delta": 15])], sayEn: "Louder.", sayTa: "சத்தம் கூட்டிட்டேன்.", kind: "volume")
        }
        if has(low, #"\b(quieter|softer|volume down|lower (the )?volume|turn it down)\b"#, #"(sound|volume|sa(?:t|th)+am)\s*(konjam\s*)?(kammi|korai|kurai|kurey)"#, #"konjam\s*kammi"#, #"ச(த்)?தம்?\s*(குறை|கம்மி|க)"#) {
            return Fast(calls: [("system_volume_step", ["delta": -15])], sayEn: "Quieter.", sayTa: "சத்தம் குறைச்சிட்டேன்.", kind: "volume")
        }
        if has(low, #"^(mute|mute it|silence)$"#, #"\bmute\b"#) {
            return Fast(calls: [("system_volume", ["level": 0])], sayEn: "Muted.", sayTa: "சத்தம் இல்லாம பண்ணிட்டேன்.", kind: "volume")
        }

        // dark mode
        if has(low, #"\bdark mode\b"#), !has(low, #"\boff\b"#) {
            return Fast(calls: [("system_dark_mode", ["on": true])], sayEn: "Dark mode on.", sayTa: "Dark mode போட்டாச்சு.", kind: "dark")
        }
        if has(low, #"\blight mode\b"#, #"dark mode\s*off"#) {
            return Fast(calls: [("system_dark_mode", ["on": false])], sayEn: "Light mode on.", sayTa: "Light mode போட்டாச்சு.", kind: "dark")
        }

        // time / date / battery
        if has(low, #"\bwhat('?s| is)? the time\b"#, #"^time\??$"#, #"\btime (enna|ennachu)\b"#, #"mani\s*enna"#, #"மணி\s*என்ன"#) {
            let now = clock("h:mm a")
            return Fast(calls: [], sayEn: "It's \(now).", sayTa: "இப்போ மணி \(now).", kind: "time")
        }
        if has(low, #"\bwhat('?s| is)? (the )?(date|day)( today)?\b"#, #"inniku\s*(enna\s*)?(date|thethi)"#, #"இன்னைக்கு\s*என்ன\s*தேதி"#) {
            let today = clock("EEEE, d MMMM")
            return Fast(calls: [], sayEn: "Today is \(today).", sayTa: "இன்னைக்கு \(today).", kind: "date")
        }
        if has(low, #"\bbattery\b"#, #"charge\s*(evlo|evvalavu)"#, "சார்ஜ்") {
            return Fast(calls: [("system_info", [:])], sayEn: "", sayTa: "", kind: "battery")
        }

        // open app / site
        let m = match(#"^(?:please\s+|can you\s+)?(?:open|launch|start)\s+(?:up\s+)?(?:the\s+)?(.+?)(?:\s+app)?$"#, low)
            ?? match(#"^(.+?)(?:\s*-?\s*(?:ai|ah|a|ஐ|ஐ))?\s+(?:open|opan|thora|thira|திற)\s*(?:pannu|panu|pannunga|பண்ணு)?$"#, low)
        if let m, let raw = m[1] {
            let target = raw.trimmingCharacters(in: CharacterSet(charactersIn: " -"))
            if sites[target] != nil || has(target, #"\.(com|org|net|io|in|lk|uk|dev|app)\b"#) {
                let url = sites[target] ?? target
                return Fast(calls: [("web_open", ["url": url])], sayEn: "Opening \(sites[target] != nil ? title(target) : url).", sayTa: "\(target) திறக்கிறேன்.", kind: "open")
            }
            var app = apps[target]
            let n = target.split(whereSeparator: { $0.isWhitespace }).count
            if app == nil, n > 0, n <= 3, !has(target, #"\b(file|folder|my|the|all|every)\b"#) { app = title(target) }
            if let app {
                return Fast(calls: [("apps_open", ["app": app])], sayEn: "Opening \(app).", sayTa: "\(app) திறக்கிறேன்.", kind: "open")
            }
        }
        return nil
    }
}
