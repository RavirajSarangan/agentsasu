//! Touch ID / login password for dangerous actions (LocalAuthentication).
//!
//! The result goes straight to the core over stdin, so no web content can forge it.

#[cfg(target_os = "macos")]
pub fn available() -> bool {
    use objc2_local_authentication::{LAContext, LAPolicy};
    let ctx = unsafe { LAContext::new() };
    unsafe { ctx.canEvaluatePolicy_error(LAPolicy::DeviceOwnerAuthentication) }.is_ok()
}

#[cfg(not(target_os = "macos"))]
pub fn available() -> bool {
    false
}

/// Blocks until the owner passes or cancels. Call off the main thread.
#[cfg(target_os = "macos")]
pub fn authenticate(reason: &str) -> bool {
    use objc2::runtime::Bool;
    use objc2_foundation::{NSError, NSString};
    use objc2_local_authentication::{LAContext, LAPolicy};
    use std::sync::mpsc;
    use std::time::Duration;

    let (tx, rx) = mpsc::channel::<bool>();
    let ctx = unsafe { LAContext::new() };
    let reply = block2::RcBlock::new(move |ok: Bool, _err: *mut NSError| {
        let _ = tx.send(ok.as_bool());
    });
    let reason = NSString::from_str(reason);
    unsafe { ctx.evaluatePolicy_localizedReason_reply(LAPolicy::DeviceOwnerAuthentication, &reason, &reply) };
    let ok = rx.recv_timeout(Duration::from_secs(120)).unwrap_or(false);
    drop(ctx);
    ok
}

#[cfg(not(target_os = "macos"))]
pub fn authenticate(_reason: &str) -> bool {
    false
}
