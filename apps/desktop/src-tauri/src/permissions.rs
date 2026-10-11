//! macOS privacy permissions Sasu needs, for the setup assistant.

use serde::Serialize;

#[derive(Serialize, Clone, Copy, PartialEq, Debug)]
#[serde(rename_all = "snake_case")]
pub enum Status {
    Granted,
    Denied,
    NotDetermined,
    /// macOS has no API to ask (e.g. Automation is per target app).
    Unknown,
}

#[derive(Serialize)]
pub struct Permissions {
    microphone: Status,
    accessibility: Status,
    screen_recording: Status,
    automation: Status,
}

#[cfg(target_os = "macos")]
mod mac {
    use super::Status;
    use objc2_av_foundation::{AVAuthorizationStatus, AVCaptureDevice, AVMediaTypeAudio};

    #[link(name = "ApplicationServices", kind = "framework")]
    extern "C" {
        fn AXIsProcessTrusted() -> bool;
    }
    #[link(name = "CoreGraphics", kind = "framework")]
    extern "C" {
        fn CGPreflightScreenCaptureAccess() -> bool;
        fn CGRequestScreenCaptureAccess() -> bool;
    }

    pub fn microphone() -> Status {
        let Some(audio) = (unsafe { AVMediaTypeAudio }) else { return Status::Unknown };
        match unsafe { AVCaptureDevice::authorizationStatusForMediaType(audio) } {
            AVAuthorizationStatus::Authorized => Status::Granted,
            AVAuthorizationStatus::NotDetermined => Status::NotDetermined,
            _ => Status::Denied,
        }
    }

    pub fn request_microphone() {
        let Some(audio) = (unsafe { AVMediaTypeAudio }) else { return };
        let handler = block2::RcBlock::new(|_granted: objc2::runtime::Bool| {});
        unsafe { AVCaptureDevice::requestAccessForMediaType_completionHandler(audio, &handler) };
    }

    pub fn accessibility() -> Status {
        if unsafe { AXIsProcessTrusted() } { Status::Granted } else { Status::Denied }
    }

    pub fn screen_recording() -> Status {
        if unsafe { CGPreflightScreenCaptureAccess() } { Status::Granted } else { Status::Denied }
    }

    pub fn request_screen_recording() {
        unsafe { CGRequestScreenCaptureAccess() };
    }
}

pub fn status() -> Permissions {
    #[cfg(target_os = "macos")]
    return Permissions {
        microphone: mac::microphone(),
        accessibility: mac::accessibility(),
        screen_recording: mac::screen_recording(),
        automation: Status::Unknown,
    };
    #[cfg(not(target_os = "macos"))]
    Permissions {
        microphone: Status::Unknown,
        accessibility: Status::Unknown,
        screen_recording: Status::Unknown,
        automation: Status::Unknown,
    }
}

/// Shows the system prompt where macOS has one; otherwise opens System Settings.
pub fn request(kind: &str) -> Result<(), String> {
    #[cfg(target_os = "macos")]
    match kind {
        "microphone" if mac::microphone() == Status::NotDetermined => {
            mac::request_microphone();
            return Ok(());
        }
        "screen_recording" if mac::screen_recording() != Status::Granted => {
            mac::request_screen_recording();
            return Ok(());
        }
        _ => {}
    }
    open_pane(kind)
}

pub fn open_pane(kind: &str) -> Result<(), String> {
    let anchor = match kind {
        "microphone" => "Privacy_Microphone",
        "accessibility" => "Privacy_Accessibility",
        "screen_recording" => "Privacy_ScreenCapture",
        "automation" => "Privacy_Automation",
        _ => return Err(format!("unknown permission {kind}")),
    };
    std::process::Command::new("open")
        .arg(format!("x-apple.systempreferences:com.apple.preference.security?{anchor}"))
        .spawn()
        .map(|_| ())
        .map_err(|e| e.to_string())
}
