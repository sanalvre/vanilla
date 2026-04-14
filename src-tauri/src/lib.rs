/// Vanilla — Tauri application library
///
/// Handles:
/// - Plugin registration (shell, fs, dialog)
/// - Sidecar process management (Python FastAPI)
/// - File watching via events emitted to the frontend
/// - Tauri command handlers

use tauri::Manager;

/// Emit a vault:file-changed event to the frontend when files change.
/// The frontend will forward this to the Python sidecar via HTTP.
#[tauri::command]
async fn start_watching(_app: tauri::AppHandle, vault_path: String) -> Result<String, String> {
    // File watching is handled via tauri-plugin-fs watch API on the frontend.
    // This command is a placeholder for any Rust-side watch initialization.
    // The actual watch is started from TypeScript using @tauri-apps/plugin-fs.
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

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            start_watching,
            get_app_data_dir,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
