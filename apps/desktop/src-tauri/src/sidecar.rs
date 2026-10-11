//! Runs sasu-core (Python) and owns the only trusted channel to it: its stdin.
//!
//! Line 1 on stdin is the config (token, data dir, vault key) so no secret is in argv
//! or env. Later lines are control messages (lock/unlock, Touch ID results, kill
//! switch). The core prints `{"port": N}` first on stdout and exits when stdin closes.
//!
//! Dev: `uv run --project <repo>/core python -m sasu_core`. Phase 8 swaps in the
//! PyInstaller binary bundled as a Tauri sidecar.

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::BTreeSet;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};
use tauri::{AppHandle, Emitter};

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Endpoint {
    pub port: u16,
    pub token: String,
}

#[derive(Deserialize)]
struct Handshake {
    port: u16,
}

#[derive(Clone)]
pub struct CoreSecrets {
    pub token: String,
    pub data_dir: PathBuf,
    pub vault_key: String,
}

#[derive(Default, Clone)]
pub struct Core {
    endpoint: Arc<Mutex<Option<Endpoint>>>,
    child: Arc<Mutex<Option<Child>>>,
    stdin: Arc<Mutex<Option<ChildStdin>>>,
    /// Lock reasons we have sent, replayed if the core restarts.
    locks: Arc<Mutex<BTreeSet<String>>>,
    /// Data dir, so keys can be replayed to a restarted core.
    data_dir: Arc<Mutex<Option<PathBuf>>>,
    stopping: Arc<AtomicBool>,
}

const MAX_QUICK_RESTARTS: u32 = 5;

impl Core {
    pub fn endpoint(&self) -> Option<Endpoint> {
        self.endpoint.lock().unwrap().clone()
    }

    pub fn locks(&self) -> BTreeSet<String> {
        self.locks.lock().unwrap().clone()
    }

    /// Sends one trusted control message to the core.
    pub fn control(&self, msg: Value) {
        if let Some(t) = msg.get("type").and_then(Value::as_str) {
            if let Some(reason) = msg.get("reason").and_then(Value::as_str) {
                let mut locks = self.locks.lock().unwrap();
                match t {
                    "lock" => {
                        locks.insert(reason.to_owned());
                    }
                    "unlock" => {
                        locks.remove(reason);
                    }
                    _ => {}
                }
            }
        }
        self.write_line(&msg);
    }

    fn write_line(&self, msg: &Value) {
        if let Some(stdin) = self.stdin.lock().unwrap().as_mut() {
            let _ = writeln!(stdin, "{msg}").and_then(|_| stdin.flush());
        }
    }

    pub fn data_dir(&self) -> Option<PathBuf> {
        self.data_dir.lock().unwrap().clone()
    }

    pub fn start(&self, app: AppHandle, secrets: CoreSecrets) {
        *self.data_dir.lock().unwrap() = Some(secrets.data_dir.clone());
        let core = self.clone();
        thread::spawn(move || {
            let mut quick_failures = 0;
            loop {
                // A fresh token every launch of the core.
                let secrets = CoreSecrets { token: crate::secrets::random_hex32(), ..secrets.clone() };
                let started = Instant::now();
                if let Err(e) = core.run_once(&app, &secrets) {
                    eprintln!("[sasu] core failed to start: {e}");
                }
                *core.endpoint.lock().unwrap() = None;
                *core.stdin.lock().unwrap() = None;
                let _ = app.emit("core-exited", ());
                if core.stopping.load(Ordering::SeqCst) {
                    return;
                }
                quick_failures = if started.elapsed() < Duration::from_secs(10) { quick_failures + 1 } else { 0 };
                if quick_failures >= MAX_QUICK_RESTARTS {
                    eprintln!("[sasu] core keeps crashing; giving up");
                    return;
                }
                thread::sleep(Duration::from_millis(500 * 2u64.pow(quick_failures)));
            }
        });
    }

    /// Spawns the core and blocks until it exits.
    fn run_once(&self, app: &AppHandle, secrets: &CoreSecrets) -> std::io::Result<()> {
        let mut child = core_command()?
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()?;
        let stdout = child.stdout.take().expect("piped stdout");
        let mut stdin = child.stdin.take().expect("piped stdin");
        let config = json!({
            "token": secrets.token,
            "data_dir": secrets.data_dir,
            "vault_key": secrets.vault_key,
            "dev": cfg!(debug_assertions),
        });
        writeln!(stdin, "{config}")?;
        stdin.flush()?;
        *self.stdin.lock().unwrap() = Some(stdin);
        *self.child.lock().unwrap() = Some(child);

        let mut lines = BufReader::new(stdout).lines();
        match lines.next() {
            Some(Ok(first)) => match serde_json::from_str::<Handshake>(&first) {
                Ok(h) => {
                    println!("[sasu] core ready on 127.0.0.1:{}", h.port);
                    for reason in self.locks() {
                        self.write_line(&json!({"type": "lock", "reason": reason}));
                    }
                    for msg in crate::keys::control_messages(&secrets.data_dir) {
                        self.write_line(&msg);
                    }
                    let ep = Endpoint { port: h.port, token: secrets.token.clone() };
                    *self.endpoint.lock().unwrap() = Some(ep);
                    let _ = app.emit("core-ready", ());
                }
                Err(_) => eprintln!("[sasu] unexpected handshake from core"),
            },
            _ => eprintln!("[sasu] core closed stdout before handshake"),
        }
        for line in lines.map_while(Result::ok) {
            println!("[core] {line}");
        }

        if let Some(mut child) = self.child.lock().unwrap().take() {
            let status = child.wait()?;
            eprintln!("[sasu] core exited: {status}");
        }
        Ok(())
    }

    pub fn stop(&self) {
        self.stopping.store(true, Ordering::SeqCst);
        *self.stdin.lock().unwrap() = None; // closing stdin asks the core to exit
        if let Some(mut child) = self.child.lock().unwrap().take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

fn core_dir() -> PathBuf {
    std::env::var_os("SASU_CORE_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../../core"))
}

/// GUI apps on macOS get a minimal PATH, so look in the usual install spots too.
fn find_uv() -> PathBuf {
    let home = std::env::var("HOME").unwrap_or_default();
    let candidates = [
        format!("{home}/.local/bin/uv"),
        format!("{home}/.cargo/bin/uv"),
        "/opt/homebrew/bin/uv".into(),
        "/usr/local/bin/uv".into(),
    ];
    candidates.into_iter().map(PathBuf::from).find(|p| p.exists()).unwrap_or_else(|| PathBuf::from("uv"))
}

fn core_command() -> std::io::Result<Command> {
    let dir = core_dir()
        .canonicalize()
        .map_err(|e| std::io::Error::new(e.kind(), format!("core dir {:?}: {e}", core_dir())))?;
    let mut cmd = Command::new(find_uv());
    cmd.args(["run", "--quiet", "--project"])
        .arg(&dir)
        .args(["python", "-m", "sasu_core", "--stdin-config"])
        .current_dir(&dir);
    if std::env::var("SASU_DEMO").is_ok_and(|v| v == "1") {
        cmd.arg("--demo");
    }
    Ok(cmd)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn handshake_has_only_a_port() {
        let h: Handshake = serde_json::from_str(r#"{"port": 51234}"#).unwrap();
        assert_eq!(h.port, 51234);
    }

    #[test]
    fn core_dir_points_at_python_project() {
        assert!(core_dir().join("pyproject.toml").exists());
    }

    #[test]
    fn lock_reasons_are_tracked_for_replay() {
        let core = Core::default();
        core.control(json!({"type": "lock", "reason": "screen"}));
        core.control(json!({"type": "lock", "reason": "disabled"}));
        core.control(json!({"type": "unlock", "reason": "screen"}));
        assert_eq!(core.locks().into_iter().collect::<Vec<_>>(), vec!["disabled".to_string()]);
    }
}
