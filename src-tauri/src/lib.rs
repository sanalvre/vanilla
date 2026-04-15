/// Vanilla — Tauri application library
///
/// Handles:
/// - Sidecar lifecycle: spawn the Python FastAPI process, read its port
///   from stdout, emit "sidecar-ready" event to frontend
/// - Plugin registration (shell, fs, dialog)
/// - Tauri command handlers

use tauri::Manager;
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandEvent;

/// Emit a vault:file-changed event to the frontend when files change.
#[tauri::command]
async fn start_watching(_app: tauri::AppHandle, vault_path: String) -> Result<String, String> {
    Ok(format!("Watch registered for: {}", vault_path))
}

/// Get the app's data directory path (for SQLite, config, etc.)
#[tauri::command]
fn get_app_data_dir(app: tauri::AppHandle) -> Result<String, String> {
    let path = app
        .path()
        .app_data_dir()
        .map_err(|e| format!("Failed to get app data dir: {}", e))?;
    Ok(path.to_string_lossy().to_string())
}

/// Spawn the Python sidecar and emit the port to the frontend.
///
/// The sidecar prints "VANILLA_PORT:<port>" to stdout on startup.
/// We capture that, then emit "sidecar-ready" with the port number so
/// the frontend can build its API base URL dynamically.
fn spawn_sidecar(app: &tauri::AppHandle) {
    let app_handle = app.clone();

    tauri::async_runtime::spawn(async move {
        let shell = app_handle.shell();

        let sidecar_result = shell.sidecar("vanilla-sidecar");
        let sidecar_cmd = match sidecar_result {
            Ok(cmd) => cmd,
            Err(e) => {
                eprintln!("[sidecar] Failed to create sidecar command: {}", e);
                return;
            }
        };

        let spawn_result = sidecar_cmd.spawn();
        let (mut rx, _child) = match spawn_result {
            Ok(result) => result,
            Err(e) => {
                eprintln!("[sidecar] Failed to spawn sidecar: {}", e);
                return;
            }
        };

        // Read events from the sidecar process
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(bytes) => {
                    let line = String::from_utf8_lossy(&bytes);
                    let line = line.trim();

                    // Parse port from "VANILLA_PORT:<port>"
                    if let Some(port_str) = line.strip_prefix("VANILLA_PORT:") {
                        if let Ok(port) = port_str.trim().parse::<u16>() {
                            println!("[sidecar] Listening on port {}", port);
                            // Notify the frontend
                            if let Err(e) = app_handle.emit("sidecar-ready", port) {
                                eprintln!("[sidecar] Failed to emit sidecar-ready: {}", e);
                            }
                        }
                    } else if !line.is_empty() {
                        // Forward other sidecar logs (useful for debugging)
                        println!("[sidecar] {}", line);
                    }
                }
                CommandEvent::Stderr(bytes) => {
                    let line = String::from_utf8_lossy(&bytes);
                    eprintln!("[sidecar-err] {}", line.trim());
                }
                CommandEvent::Terminated(status) => {
                    eprintln!(
                        "[sidecar] Process terminated with code {:?}",
                        status.code
                    );
                    break;
                }
                _ => {}
            }
        }
    });
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            start_watching,
            get_app_data_dir,
        ])
        .setup(|app| {
            // Spawn the Python sidecar when the app window opens.
            // In dev mode (npm run tauri dev), skip this — the dev server
            // uses a manually started sidecar via VANILLA_DEV=1.
            #[cfg(not(debug_assertions))]
            spawn_sidecar(&app.handle().clone());

            // In debug builds, still spawn the sidecar so `tauri dev` works
            // end-to-end, but only if we detect it's not already running.
            #[cfg(debug_assertions)]
            {
                // Spawn unconditionally in debug too — Vite handles HMR,
                // the sidecar handles API. User can override by setting
                // VANILLA_NO_SIDECAR=1 if they want to manage it manually.
                if std::env::var("VANILLA_NO_SIDECAR").is_err() {
                    spawn_sidecar(&app.handle().clone());
                }
            }

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
