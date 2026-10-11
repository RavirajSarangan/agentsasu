//! Window placement and behaviour.

use tauri::{AppHandle, Manager, PhysicalPosition, WebviewWindow, WindowEvent};

const MARGIN: f64 = 24.0;

/// Puts the robot in the bottom-right corner of the primary screen, above the Dock.
pub fn place_overlay(overlay: &WebviewWindow) -> tauri::Result<()> {
    let Some(monitor) = overlay.primary_monitor()? else { return Ok(()) };
    let area = monitor.work_area();
    let size = overlay.outer_size()?;
    let margin = (MARGIN * monitor.scale_factor()) as i32;
    let x = area.position.x + area.size.width as i32 - size.width as i32 - margin;
    let y = area.position.y + area.size.height as i32 - size.height as i32 - margin;
    overlay.set_position(PhysicalPosition::new(x, y))
}

pub fn show_panel(app: &AppHandle) {
    if let Some(panel) = app.get_webview_window("panel") {
        let _ = panel.show();
        let _ = panel.unminimize();
        let _ = panel.set_focus();
    }
}

pub fn toggle_overlay(app: &AppHandle) {
    if let Some(overlay) = app.get_webview_window("overlay") {
        let visible = overlay.is_visible().unwrap_or(true);
        let _ = if visible { overlay.hide() } else { overlay.show() };
    }
}

/// Closing the panel only hides it; the app lives in the tray.
pub fn keep_panel_alive(panel: &WebviewWindow) {
    let handle = panel.clone();
    panel.on_window_event(move |event| {
        if let WindowEvent::CloseRequested { api, .. } = event {
            api.prevent_close();
            let _ = handle.hide();
        }
    });
}
