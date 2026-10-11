// swift-tools-version:5.10
// Sasu's native core, built step by step to replace the Python core (see README).
import Foundation
import PackageDescription

// The speech engine (sherpa-onnx) is fetched by scripts/fetch-sherpa.sh into vendor/.
let vendorLib = URL(fileURLWithPath: #filePath).deletingLastPathComponent().appendingPathComponent("vendor/sherpa-onnx/lib").path

let package = Package(
    name: "SasuMac",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "sasu-core-swift", targets: ["sasu-core-swift"]),
        .library(name: "SasuKit", targets: ["SasuKit"]),
    ],
    targets: [
        .target(name: "CSherpaOnnx"),
        .target(
            name: "SasuKit",
            dependencies: ["CSherpaOnnx"],
            linkerSettings: [
                .linkedLibrary("sqlite3"),
                .linkedLibrary("sherpa-onnx-c-api"),
                .unsafeFlags(["-L", vendorLib, "-Xlinker", "-rpath", "-Xlinker", vendorLib]),
            ]
        ),
        .executableTarget(name: "sasu-core-swift", dependencies: ["SasuKit"]),
    ]
)
