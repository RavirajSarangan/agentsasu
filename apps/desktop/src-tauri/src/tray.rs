use serde_json::json;
use tauri::menu::{CheckMenuItem, Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{AppHandle, Emitter, Manager, Wry};

use crate::sidecar::Core;
use crate::windows;

pub struct TrayState {
    disabled: CheckMenuItem<Wry>,
}

pub fn create(app: &AppHandle) -> tauri::Result<()> {
    let panel = MenuItem::with_id(app, "panel", "Open Sasu…", true, None::<&str>)?;
    let robot = MenuItem::with_id(app, "robot", "Show / Hide Robot", true, None::<&str>)?;
    let disabled = CheckMenuItem::with_id(app, "disabled", "Disable Sasu (mic off)", true, false, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quit Sasu", true, Some("CmdOrCtrl+Q"))?;
    let sep = PredefinedMenuItem::separator(app)?;
    let sep2 = PredefinedMenuItem::separator(app)?;
    let menu = Menu::with_items(app, &[&panel, &robot, &sep, &disabled, &sep2, &quit])?;
    app.manage(TrayState { disabled: disabled.clone() });

    let mut tray = TrayIconBuilder::with_id("sasu").tooltip("Sasu").menu(&menu).icon_as_template(true);
    tray = tray.icon(tauri::include_image!("icons/tray@2x.png"));
    tray.on_menu_event(|app, event| match event.id.as_ref() {
        "panel" => windows::show_panel(app),
        "robot" => windows::toggle_overlay(app),
        "disabled" => {
            let core = app.state::<Core>();
            let now_disabled = core.locks().contains("disabled");
            if now_disabled {
                // Re-enabling needs the owner; ask from the panel where Touch ID can show.
                let state = app.state::<TrayState>();
                let _ = state.disabled.set_checked(true);
                windows::show_panel(app);
                let _ = app.emit_to("panel", "request-enable", ());
            } else {
                set_disabled(app, &core, true);
            }
        }
        "quit" => {
            app.state::<Core>().stop();
            app.exit(0);
        }
        _ => {}
    })
    .build(app)?;
    Ok(())
}

pub fn set_disabled(app: &AppHandle, core: &Core, disabled: bool) {
    let kind = if disabled { "lock" } else { "unlock" };
    core.control(json!({"type": kind, "reason": "disabled"}));
    if let Some(state) = app.try_state::<TrayState>() {
        let _ = state.disabled.set_checked(disabled);
    }
    let _ = app.emit("disabled-changed", disabled);
}
