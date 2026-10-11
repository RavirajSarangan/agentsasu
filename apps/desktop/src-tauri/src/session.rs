//! Goes deaf when the Mac is locked: screen lock, screensaver and fast user switching
//! all lock the core.

use crate::sidecar::Core;
use serde_json::json;
use tauri::{AppHandle, Emitter};

#[cfg(target_os = "macos")]
pub fn watch(app: AppHandle, core: Core) {
    use objc2_foundation::{NSDistributedNotificationCenter, NSNotification, NSString};
    use std::ptr::NonNull;
    use std::sync::atomic::{AtomicBool, Ordering};
    use std::sync::Arc;

    let screen_locked = Arc::new(AtomicBool::new(false));
    let center = NSDistributedNotificationCenter::defaultCenter();

    let events: [(&str, bool); 4] = [
        ("com.apple.screenIsLocked", true),
        ("com.apple.screensaver.didstart", true),
        ("com.apple.screenIsUnlocked", false),
        ("com.apple.screensaver.didstop", false),
    ];
    for (name, lock) in events {
        let (app, core, screen_locked) = (app.clone(), core.clone(), screen_locked.clone());
        let is_screen_lock = name == "com.apple.screenIsLocked";
        let is_saver_stop = name == "com.apple.screensaver.didstop";
        let block = block2::RcBlock::new(move |_n: NonNull<NSNotification>| {
            if lock {
                if is_screen_lock {
                    screen_locked.store(true, Ordering::SeqCst);
                }
                core.control(json!({"type": "lock", "reason": "screen"}));
                let _ = app.emit("session-locked", true);
            } else {
                // A screensaver that ends on a locked screen is not an unlock.
                if is_saver_stop && screen_locked.load(Ordering::SeqCst) {
                    return;
                }
                screen_locked.store(false, Ordering::SeqCst);
                core.control(json!({"type": "unlock", "reason": "screen"}));
                let _ = app.emit("session-locked", false);
            }
        });
        let observer = unsafe {
            center.addObserverForName_object_queue_usingBlock(Some(&NSString::from_str(name)), None, None, &block)
        };
        // Observers live for the whole app.
        std::mem::forget(observer);
    }

    // Fast user switching: another user took over the screen.
    use objc2_app_kit::{NSWorkspace, NSWorkspaceSessionDidBecomeActiveNotification, NSWorkspaceSessionDidResignActiveNotification};
    let ws_center = NSWorkspace::sharedWorkspace().notificationCenter();
    for (name, lock) in unsafe {
        [(NSWorkspaceSessionDidResignActiveNotification, true), (NSWorkspaceSessionDidBecomeActiveNotification, false)]
    } {
        let (app, core, screen_locked) = (app.clone(), core.clone(), screen_locked.clone());
        let block = block2::RcBlock::new(move |_n: NonNull<NSNotification>| {
            if lock {
                core.control(json!({"type": "lock", "reason": "screen"}));
                let _ = app.emit("session-locked", true);
            } else if !screen_locked.load(Ordering::SeqCst) {
                core.control(json!({"type": "unlock", "reason": "screen"}));
                let _ = app.emit("session-locked", false);
            }
        });
        let observer = unsafe { ws_center.addObserverForName_object_queue_usingBlock(Some(name), None, None, &block) };
        std::mem::forget(observer);
    }
}

#[cfg(not(target_os = "macos"))]
pub fn watch(_app: AppHandle, _core: Core) {}
