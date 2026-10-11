//! "The robot goes where it works": glide the overlay next to the app Sasu is acting on,
//! then home again. Window bounds come from System Events (needs Accessibility).

use std::sync::Mutex;
use std::time::Duration;
use tauri::{Manager, PhysicalPosition, WebviewWindow};

#[derive(Default)]
pub struct Home(Mutex<Option<PhysicalPosition<i32>>>);

const STEPS: i32 = 22;

fn ease_out(t: f64) -> f64 {
    1.0 - (1.0 - t).powi(3)
}

fn glide(win: &WebviewWindow, to: PhysicalPosition<i32>) {
    let Ok(from) = win.outer_position() else { return };
    for i in 1..=STEPS {
        let t = ease_out(i as f64 / STEPS as f64);
        let x = from.x as f64 + (to.x - from.x) as f64 * t;
        let y = from.y as f64 + (to.y - from.y) as f64 * t;
        let _ = win.set_position(PhysicalPosition::new(x.round() as i32, y.round() as i32));
        std::thread::sleep(Duration::from_millis(16));
    }
}

/// App names are passed to AppleScript, so only allow plain names.
fn safe_app_name(app: &str) -> bool {
    !app.is_empty() && app.len() <= 64 && app.chars().all(|c| c.is_alphanumeric() || " .-_&'".contains(c)) && !app.contains('"')
}

/// Front window of `app` as (x, y, w, h) in points.
fn window_bounds(app: &str) -> Option<(f64, f64, f64, f64)> {
    if !safe_app_name(app) {
        return None;
    }
    let script = format!(
        r#"tell application "System Events" to tell process "{app}" to get {{position, size}} of front window"#
    );
    let out = std::process::Command::new("osascript").args(["-e", &script]).output().ok()?;
    if !out.status.success() {
        return None;
    }
    let nums: Vec<f64> = String::from_utf8_lossy(&out.stdout).split(',').filter_map(|s| s.trim().parse().ok()).collect();
    match nums.as_slice() {
        [x, y, w, h] => Some((*x, *y, *w, *h)),
        _ => None,
    }
}

pub fn to_app(app: tauri::AppHandle, name: String) {
    std::thread::spawn(move || {
        let Some(win) = app.get_webview_window("overlay") else { return };
        let Some((x, y, w, _h)) = window_bounds(&name) else { return };
        let scale = win.scale_factor().unwrap_or(2.0);
        let size = win.outer_size().ok();
        let home = app.state::<Home>();
        {
            let mut saved = home.0.lock().unwrap();
            if saved.is_none() {
                *saved = win.outer_position().ok();
            }
        }
        // Sit just inside the app window's top-right corner, clamped to the screen.
        let (ow, oh) = size.map(|s| (s.width as i32, s.height as i32)).unwrap_or((270, 380));
        let mut tx = ((x + w) * scale) as i32 - ow + (40.0 * scale) as i32;
        let mut ty = (y * scale) as i32 + (10.0 * scale) as i32;
        if let Ok(Some(mon)) = win.current_monitor() {
            let a = mon.work_area();
            tx = tx.clamp(a.position.x, a.position.x + a.size.width as i32 - ow);
            ty = ty.clamp(a.position.y, a.position.y + a.size.height as i32 - oh);
        }
        glide(&win, PhysicalPosition::new(tx, ty));
    });
}

pub fn home(app: tauri::AppHandle) {
    std::thread::spawn(move || {
        let Some(win) = app.get_webview_window("overlay") else { return };
        let target = app.state::<Home>().0.lock().unwrap().take();
        if let Some(pos) = target {
            std::thread::sleep(Duration::from_millis(900));
            glide(&win, pos);
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn app_names_are_sanitised() {
        assert!(safe_app_name("Safari"));
        assert!(safe_app_name("Visual Studio Code"));
        assert!(!safe_app_name(r#"Safari" to do shell script "rm -rf ~"#));
        assert!(!safe_app_name(""));
        assert!(!safe_app_name("a;b"));
    }

    #[test]
    fn easing_ends_at_one() {
        assert!((ease_out(1.0) - 1.0).abs() < 1e-9);
        assert!(ease_out(0.5) > 0.5);
    }
}
