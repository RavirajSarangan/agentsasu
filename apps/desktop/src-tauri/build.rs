fn main() {
    // App commands must be granted per window in capabilities/ (least privilege).
    tauri_build::try_build(tauri_build::Attributes::new().app_manifest(tauri_build::AppManifest::new().commands(&[
        "core_endpoint",
        "show_panel",
        "permissions_status",
        "request_permission",
        "open_privacy_pane",
        "auth_available",
        "authorize_action",
        "test_touch_id",
        "shell_security",
        "set_disabled",
        "haptic",
        "fly_to_app",
        "fly_home",
        "api_keys",
        "set_api_key",
        "remove_api_key",
        "open_help",
        "unlock_secure",
    ])))
    .expect("failed to run tauri-build");
}
