//! Trackpad haptics for moments that matter (confirm, Touch ID, success).

use tauri::AppHandle;

pub fn play(app: &AppHandle, kind: &str) {
    #[cfg(target_os = "macos")]
    {
        use objc2_app_kit::{NSHapticFeedbackManager, NSHapticFeedbackPattern, NSHapticFeedbackPerformanceTime, NSHapticFeedbackPerformer};
        let pattern = match kind {
            "alignment" => NSHapticFeedbackPattern::Alignment,
            "level" => NSHapticFeedbackPattern::LevelChange,
            _ => NSHapticFeedbackPattern::Generic,
        };
        let _ = app.run_on_main_thread(move || {
            let performer = NSHapticFeedbackManager::defaultPerformer();
            performer.performFeedbackPattern_performanceTime(pattern, NSHapticFeedbackPerformanceTime::Now);
        });
    }
    #[cfg(not(target_os = "macos"))]
    let _ = (app, kind);
}
