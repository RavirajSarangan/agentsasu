mod auth;
mod fly;
mod haptics;
mod keys;
mod permissions;
mod secrets;
mod session;
mod sidecar;
mod tray;
mod windows;

use serde_json::json;
use sidecar::{Core, CoreSecrets, Endpoint};
use tauri::{AppHandle, Emitter, Manager, RunEvent};
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};

#[tauri::command]
fn core_endpoint(core: tauri::State<'_, Core>) -> Option<Endpoint> {
    core.endpoint()
}

#[tauri::command]
fn show_panel(app: AppHandle) {
    windows::show_panel(&app);
}

#[tauri::command]
fn permissions_status() -> permissions::Permissions {
    permissions::status()
}

#[tauri::command]
fn request_permission(kind: String) -> Result<(), String> {
    permissions::request(&kind)
}

#[tauri::command]
fn open_privacy_pane(kind: String) -> Result<(), String> {
    permissions::open_pane(&kind)
}

#[tauri::command]
fn auth_available() -> bool {
    auth::available()
}

/// Touch ID for a dangerous action the core is waiting on. The verdict goes to the
/// core over stdin; the UI only learns whether it passed.
#[tauri::command]
async fn authorize_action(core: tauri::State<'_, Core>, id: String, reason: String) -> Result<bool, String> {
    let reason = format!("Sasu wants to: {reason}");
    let ok = tauri::async_runtime::spawn_blocking(move || auth::authenticate(&reason))
        .await
        .map_err(|e| e.to_string())?;
    core.control(json!({"type": "auth_result", "id": id, "ok": ok}));
    Ok(ok)
}

/// Touch ID check with no action attached (setup assistant test).
#[tauri::command]
async fn test_touch_id() -> Result<bool, String> {
    tauri::async_runtime::spawn_blocking(|| auth::authenticate("test Touch ID for Sasu"))
        .await
        .map_err(|e| e.to_string())
}

#[derive(serde::Serialize)]
struct ShellSecurity {
    locks: Vec<String>,
    touch_id: bool,
}

#[tauri::command]
fn shell_security(core: tauri::State<'_, Core>) -> ShellSecurity {
    ShellSecurity { locks: core.locks().into_iter().collect(), touch_id: auth::available() }
}

/// Turning Sasu back on needs the owner (Touch ID or password).
#[tauri::command]
async fn set_disabled(app: AppHandle, core: tauri::State<'_, Core>, disabled: bool) -> Result<bool, String> {
    if !disabled {
        let ok = tauri::async_runtime::spawn_blocking(|| auth::authenticate("turn Sasu back on"))
            .await
            .map_err(|e| e.to_string())?;
        if !ok && auth::available() {
            return Ok(false);
        }
    }
    tray::set_disabled(&app, &core, disabled);
    Ok(true)
}

#[tauri::command]
fn haptic(app: AppHandle, kind: String) {
    haptics::play(&app, &kind);
}

#[tauri::command]
fn fly_to_app(app: AppHandle, name: String) {
    fly::to_app(app, name);
}

#[tauri::command]
fn fly_home(app: AppHandle) {
    fly::home(app);
}

#[tauri::command]
fn api_keys(core: tauri::State<'_, Core>) -> Vec<String> {
    core.data_dir().map(|d| keys::configured(&d)).unwrap_or_default()
}

/// Saves a provider key and hands it to the running core over stdin.
#[tauri::command]
fn set_api_key(core: tauri::State<'_, Core>, provider: String, key: String) -> Result<(), String> {
    let dir = core.data_dir().ok_or("core not started")?;
    keys::set(&dir, &provider, &key)?;
    core.control(json!({"type": "secret", "provider": provider, "key": key.trim()}));
    Ok(())
}

#[tauri::command]
fn remove_api_key(core: tauri::State<'_, Core>, provider: String) -> Result<(), String> {
    let dir = core.data_dir().ok_or("core not started")?;
    keys::remove(&dir, &provider)?;
    core.control(json!({"type": "secret", "provider": provider, "key": ""}));
    Ok(())
}

/// Security locks (panic word, trap file, away) only lift with Touch ID / password.
#[tauri::command]
async fn unlock_secure(core: tauri::State<'_, Core>, reason: String) -> Result<bool, String> {
    if !["panic", "canary", "away"].contains(&reason.as_str()) {
        return Err("unknown lock".into());
    }
    let why = format!("unlock Sasu ({reason})");
    let ok = tauri::async_runtime::spawn_blocking(move || auth::authenticate(&why))
        .await
        .map_err(|e| e.to_string())?;
    if ok {
        core.control(json!({"type": "unlock", "reason": reason}));
    }
    Ok(ok)
}

/// Opens one of a fixed set of help pages in the browser (no arbitrary URLs from the UI).
#[tauri::command]
fn open_help(page: String) -> Result<(), String> {
    let url = match page.as_str() {
        "gemini-key" => "https://aistudio.google.com/apikey",
        "groq-key" => "https://console.groq.com/keys",
        "anthropic-key" => "https://console.anthropic.com/settings/keys",
        "ollama" => "https://ollama.com/download",
        _ => return Err("unknown help page".into()),
    };
    std::process::Command::new("open").arg(url).spawn().map(|_| ()).map_err(|e| e.to_string())
}

/// ⌥Space = talk, ⌘⌥Z = undo last turn, ⌘⌥Esc = kill switch (goes to the core directly, even if the UI hangs).
fn register_hotkeys(app: &AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    let talk = Shortcut::new(Some(Modifiers::ALT), Code::Space);
    let stop = Shortcut::new(Some(Modifiers::SUPER | Modifiers::ALT), Code::Escape);
    let undo = Shortcut::new(Some(Modifiers::SUPER | Modifiers::ALT), Code::KeyZ);
    app.plugin(
        tauri_plugin_global_shortcut::Builder::new()
            .with_handler(move |app, shortcut, event| {
                if event.state() != ShortcutState::Pressed {
                    return;
                }
                if shortcut == &stop {
                    app.state::<Core>().control(json!({"type": "cancel"}));
                    let _ = app.emit_to("overlay", "hotkey-stop", ());
                } else if shortcut == &talk {
                    let _ = app.emit_to("overlay", "hotkey-talk", ());
                } else if shortcut == &undo {
                    let _ = app.emit_to("overlay", "hotkey-undo", ());
                }
            })
            .build(),
    )?;
    app.global_shortcut().register(talk)?;
    app.global_shortcut().register(stop)?;
    app.global_shortcut().register(undo)?;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_autostart::init(tauri_plugin_autostart::MacosLauncher::LaunchAgent, None))
        .manage(Core::default())
        .manage(fly::Home::default())
        .invoke_handler(tauri::generate_handler![
            core_endpoint,
            show_panel,
            permissions_status,
            request_permission,
            open_privacy_pane,
            auth_available,
            authorize_action,
            test_touch_id,
            shell_security,
            set_disabled,
            haptic,
            fly_to_app,
            fly_home,
            api_keys,
            set_api_key,
            remove_api_key,
            open_help,
            unlock_secure
        ])
        .setup(|app| {
            // Tray-only app: no Dock icon, the robot is the face of the app.
            #[cfg(target_os = "macos")]
            app.set_activation_policy(tauri::ActivationPolicy::Accessory);

            let handle = app.handle().clone();
            if let Some(overlay) = app.get_webview_window("overlay") {
                windows::place_overlay(&overlay)?;
            }
            if let Some(panel) = app.get_webview_window("panel") {
                windows::keep_panel_alive(&panel);
            }
            tray::create(&handle)?;
            if let Err(e) = register_hotkeys(&handle) {
                eprintln!("[sasu] hotkeys unavailable: {e}");
            }

            let data_dir = app.path().app_data_dir()?;
            std::fs::create_dir_all(&data_dir)?;
            let secrets = CoreSecrets {
                token: String::new(), // generated fresh for every core launch
                vault_key: secrets::vault_key(&data_dir),
                data_dir,
            };
            let core = app.state::<Core>().inner().clone();
            session::watch(handle.clone(), core.clone());
            core.start(handle, secrets);
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building Sasu");

    app.run(|app, event| {
        if let RunEvent::Exit = event {
            app.state::<Core>().stop();
        }
    });
}
