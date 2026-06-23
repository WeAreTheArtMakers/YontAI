use std::{
    fs,
    net::{SocketAddr, TcpStream},
    process::{Child, Command, Stdio},
    sync::Mutex,
    time::Duration,
};
use tauri::Manager;

struct BackendProcess(Mutex<Option<Child>>);

fn backend_is_alive() -> bool {
    let address = SocketAddr::from(([127, 0, 0, 1], 8765));
    TcpStream::connect_timeout(&address, Duration::from_millis(250)).is_ok()
}

fn spawn_backend() -> Option<Child> {
    if backend_is_alive() {
        eprintln!("Backend already running on port 8765");
        return None;
    }

    // Try multiple possible locations for the script
    let possible_paths = vec![
        // Development mode
        std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()?
            .parent()?
            .parent()?
            .join("start-backend.sh"),
        // Bundle mode - in Resources
        std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()?
            .parent()?
            .parent()?
            .join("Resources")
            .join("start-backend.sh"),
        // Current directory
        std::env::current_dir().ok()?.join("start-backend.sh"),
    ];

    let mut script_path = None;
    for path in possible_paths {
        if path.exists() {
            eprintln!("Found backend script at: {}", path.display());
            script_path = Some(path);
            break;
        }
    }

    let script = script_path?;
    let project_root = script.parent()?;

    eprintln!("Starting backend from: {}", script.display());
    eprintln!("Working directory: {}", project_root.display());

    // Make script executable
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        if let Ok(metadata) = fs::metadata(&script) {
            let mut perms = metadata.permissions();
            perms.set_mode(0o755);
            let _ = fs::set_permissions(&script, perms);
        }
    }

    Command::new("sh")
        .arg(&script)
        .current_dir(project_root)
        .env("YONTAI_RELOAD", "0")
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|error| {
            eprintln!("YontAI backend could not be started: {error}");
            error
        })
        .ok()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .manage(BackendProcess(Mutex::new(None)))
        .setup(|app| {
            let state = app.state::<BackendProcess>();
            if let Ok(mut child_slot) = state.0.lock() {
                *child_slot = spawn_backend();
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                let state = window.state::<BackendProcess>();
                {
                    if let Ok(mut child_slot) = state.0.lock() {
                        if let Some(mut child) = child_slot.take() {
                            let _ = child.kill();
                        }
                    };
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("failed to run YontAI desktop app");
}
