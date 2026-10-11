//! Secrets the core needs, created here and handed over on stdin only.

use std::io::Read;
use std::path::Path;

const SERVICE: &str = "dev.sasu.desktop";
const VAULT_ACCOUNT: &str = "voiceprint-vault-key";

/// 32 random bytes from the OS, hex-encoded.
pub fn random_hex32() -> String {
    let mut buf = [0u8; 32];
    std::fs::File::open("/dev/urandom")
        .and_then(|mut f| f.read_exact(&mut buf))
        .expect("OS randomness unavailable");
    buf.iter().map(|b| format!("{b:02x}")).collect()
}

/// Key that encrypts the owner's voiceprint at rest.
///
/// Release builds keep it in the macOS Keychain. Debug builds are re-signed on every
/// compile, which would make the Keychain prompt each time, so they keep a 0600 file
/// in the app data dir instead.
pub fn vault_key(data_dir: &Path) -> String {
    let dev_file = data_dir.join(".vault-key-dev");
    if cfg!(debug_assertions) || !cfg!(target_os = "macos") {
        return file_key(&dev_file);
    }
    keychain_key(&dev_file)
}

/// A key a dev build left in a file (so the release app can still read your data).
fn dev_key(path: &Path) -> Option<String> {
    let key = std::fs::read_to_string(path).ok()?;
    let key = key.trim();
    (key.len() == 64 && key.chars().all(|c| c.is_ascii_hexdigit())).then(|| key.to_owned())
}

#[cfg(target_os = "macos")]
fn keychain_key(dev_file: &Path) -> String {
    use security_framework::passwords::{get_generic_password, set_generic_password};
    if let Ok(bytes) = get_generic_password(SERVICE, VAULT_ACCOUNT) {
        if let Ok(key) = String::from_utf8(bytes) {
            if key.len() == 64 {
                return key;
            }
        }
    }
    // First release launch after using a dev build: move the key into the Keychain.
    let migrated = dev_key(dev_file);
    let key = migrated.clone().unwrap_or_else(random_hex32);
    match set_generic_password(SERVICE, VAULT_ACCOUNT, key.as_bytes()) {
        Ok(()) if migrated.is_some() => {
            let _ = std::fs::remove_file(dev_file);
        }
        Ok(()) => {}
        Err(e) => eprintln!("[sasu] keychain write failed: {e}"),
    }
    key
}

#[cfg(not(target_os = "macos"))]
fn keychain_key(_dev_file: &Path) -> String {
    random_hex32()
}

fn file_key(path: &Path) -> String {
    if let Ok(key) = std::fs::read_to_string(path) {
        if key.trim().len() == 64 {
            return key.trim().to_owned();
        }
    }
    let key = random_hex32();
    if let Some(dir) = path.parent() {
        let _ = std::fs::create_dir_all(dir);
    }
    let _ = std::fs::write(path, &key);
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o600));
    }
    let _ = SERVICE;
    let _ = VAULT_ACCOUNT;
    key
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn random_is_hex_and_unique() {
        let (a, b) = (random_hex32(), random_hex32());
        assert_eq!(a.len(), 64);
        assert!(a.chars().all(|c| c.is_ascii_hexdigit()));
        assert_ne!(a, b);
    }

    #[test]
    fn file_key_is_stable_and_private() {
        let dir = std::env::temp_dir().join(format!("sasu-test-{}", random_hex32()));
        let path = dir.join("k");
        let k1 = file_key(&path);
        assert_eq!(k1, file_key(&path));
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            assert_eq!(std::fs::metadata(&path).unwrap().permissions().mode() & 0o777, 0o600);
        }
        let _ = std::fs::remove_dir_all(dir);
    }
}
