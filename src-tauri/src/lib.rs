/// Vanilla — Tauri application library
///
/// Handles:
/// - Plugin registration (shell, fs, dialog)
/// - Sidecar process management (Python FastAPI)
/// - File watching and event emission
/// - Tauri command handlers

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_dialog::init())
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
