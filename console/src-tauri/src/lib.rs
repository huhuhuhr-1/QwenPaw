mod backend;
mod tray;

use tauri::{RunEvent, WindowEvent};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let build_result = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            backend::backend_port,
            backend::backend_startup_error,
            backend::restart_backend,
        ])
        .manage(backend::BackendState::default())
        .setup(|app| {
            backend::setup(app)?;
            tray::setup_tray(app)?;
            Ok(())
        })
        .on_window_event(|window, event| {
            // Hide the window instead of closing it so the backend keeps
            // running. Use the tray menu "Quit" to actually stop and exit.
            if let WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .build(tauri::generate_context!());

    match build_result {
        Ok(app) => {
            app.run(|app_handle, event| {
                if let RunEvent::ExitRequested { .. } = event {
                    backend::stop(app_handle);
                }
            });
        }
        Err(err) => {
            eprintln!("[QwenPaw Desktop] Fatal startup error: {err}");
            std::process::exit(1);
        }
    }
}
