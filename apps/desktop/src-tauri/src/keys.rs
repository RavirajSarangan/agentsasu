//! AI provider API keys. Stored in the Keychain (release) or a 0600 file (debug, because
//! the Keychain re-prompts after every re-sign). Sent to the core only over stdin.

use serde_json::{json, Map, Value};
use std::path::{Path, PathBuf};

pub const PROVIDERS: [&str; 3] = ["gemini", "groq", "anthropic"];
const SERVICE: &str = "dev.sasu.desktop.ai";

fn dev_file(data_dir: &Path) -> PathBuf {
    data_dir.join(".ai-keys-dev.json")
}

fn read_dev(data_dir: &Path) -> Map<String, Value> {
    std::fs::read_to_string(dev_file(data_dir))
        .ok()
        .and_then(|s| serde_json::from_str::<Value>(&s).ok())
        .and_then(|v| v.as_object().cloned())
        .unwrap_or_default()
}

fn write_dev(data_dir: &Path, map: &Map<String, Value>) -> std::io::Result<()> {
    let path = dev_file(data_dir);
    std::fs::write(&path, Value::Object(map.clone()).to_string())?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o600))?;
    }
    Ok(())
}

fn valid(provider: &str) -> Result<(), String> {
    if PROVIDERS.contains(&provider) { Ok(()) } else { Err(format!("unknown provider {provider}")) }
}

pub fn set(data_dir: &Path, provider: &str, key: &str) -> Result<(), String> {
    valid(provider)?;
    let key = key.trim();
    if key.len() < 16 || key.len() > 512 || key.chars().any(char::is_whitespace) {
        return Err("that doesn't look like an API key".into());
    }
    if cfg!(debug_assertions) || !cfg!(target_os = "macos") {
        let mut map = read_dev(data_dir);
        map.insert(provider.into(), Value::String(key.into()));
        return write_dev(data_dir, &map).map_err(|e| e.to_string());
    }
    keychain::set(provider, key)
}

pub fn remove(data_dir: &Path, provider: &str) -> Result<(), String> {
    valid(provider)?;
    if cfg!(debug_assertions) || !cfg!(target_os = "macos") {
        let mut map = read_dev(data_dir);
        map.remove(provider);
        return write_dev(data_dir, &map).map_err(|e| e.to_string());
    }
    keychain::remove(provider)
}

fn get(data_dir: &Path, provider: &str) -> Option<String> {
    let dev = || read_dev(data_dir).get(provider).and_then(Value::as_str).map(str::to_owned);
    if cfg!(debug_assertions) || !cfg!(target_os = "macos") {
        return dev();
    }
    if let Some(k) = keychain::get(provider) {
        return Some(k);
    }
    // First release launch after a dev build: move the key into the Keychain.
    let k = dev()?;
    if keychain::set(provider, &k).is_ok() {
        let mut map = read_dev(data_dir);
        map.remove(provider);
        let _ = if map.is_empty() { std::fs::remove_file(dev_file(data_dir)) } else { write_dev(data_dir, &map) };
    }
    Some(k)
}

/// Which providers have a key (never the keys themselves).
pub fn configured(data_dir: &Path) -> Vec<String> {
    PROVIDERS.iter().filter(|p| get(data_dir, p).is_some()).map(|p| p.to_string()).collect()
}

/// Control messages that hand every stored key to a (re)started core.
pub fn control_messages(data_dir: &Path) -> Vec<Value> {
    PROVIDERS
        .iter()
        .filter_map(|p| get(data_dir, p).map(|k| json!({"type": "secret", "provider": p, "key": k})))
        .collect()
}

#[cfg(target_os = "macos")]
mod keychain {
    use super::SERVICE;
    use security_framework::passwords::{delete_generic_password, get_generic_password, set_generic_password};

    pub fn set(provider: &str, key: &str) -> Result<(), String> {
        set_generic_password(SERVICE, provider, key.as_bytes()).map_err(|e| e.to_string())
    }
    pub fn remove(provider: &str) -> Result<(), String> {
        delete_generic_password(SERVICE, provider).map_err(|e| e.to_string())
    }
    pub fn get(provider: &str) -> Option<String> {
        get_generic_password(SERVICE, provider).ok().and_then(|b| String::from_utf8(b).ok())
    }
}

#[cfg(not(target_os = "macos"))]
mod keychain {
    pub fn set(_: &str, _: &str) -> Result<(), String> {
        Err("keychain unavailable".into())
    }
    pub fn remove(_: &str) -> Result<(), String> {
        Ok(())
    }
    pub fn get(_: &str) -> Option<String> {
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_bad_input() {
        let dir = std::env::temp_dir();
        assert!(set(&dir, "evil", "x".repeat(40).as_str()).is_err());
        assert!(set(&dir, "gemini", "short").is_err());
        assert!(set(&dir, "gemini", "has spaces in it which is wrong").is_err());
    }

    #[test]
    fn dev_store_roundtrip_is_private() {
        let dir = std::env::temp_dir().join(format!("sasu-keys-{}", crate::secrets::random_hex32()));
        std::fs::create_dir_all(&dir).unwrap();
        set(&dir, "gemini", "AIzaSyExampleExampleExample000").unwrap();
        assert_eq!(configured(&dir), vec!["gemini".to_string()]);
        assert_eq!(control_messages(&dir)[0]["provider"], "gemini");
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let mode = std::fs::metadata(dev_file(&dir)).unwrap().permissions().mode();
            assert_eq!(mode & 0o777, 0o600);
        }
        remove(&dir, "gemini").unwrap();
        assert!(configured(&dir).is_empty());
        let _ = std::fs::remove_dir_all(dir);
    }
}
