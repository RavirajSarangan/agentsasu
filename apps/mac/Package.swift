// swift-tools-version:5.10
// Sasu's native core, built step by step to replace the Python core (see README).
import PackageDescription

let package = Package(
    name: "SasuMac",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "sasu-core-swift", targets: ["sasu-core-swift"]),
        .library(name: "SasuKit", targets: ["SasuKit"]),
    ],
    targets: [
        .target(name: "SasuKit", linkerSettings: [.linkedLibrary("sqlite3")]),
        .executableTarget(name: "sasu-core-swift", dependencies: ["SasuKit"]),
    ]
)
