//! 2026-05-28 系统托盘：关闭窗口时隐藏而非退出，保持后台服务运行
//!
//! 关闭窗口 → 隐藏，Python 后端继续运行。托盘菜单提供
//! "Show Window" 恢复窗口、"Quit" 停止后端并退出。

use tauri::{
    menu::{MenuBuilder, MenuItemBuilder, PredefinedMenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Manager,
};

/// Create the system tray icon during app startup.
///
/// The tray menu has two items:
/// - **Show Window**: restores the hidden window (idempotent).
/// - **Quit**: kills the Python backend process and exits the app.
pub(crate) fn setup_tray(app: &tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    let handle = app.handle();

    let show_item = MenuItemBuilder::with_id("show", "Show Window").build(handle)?;
    let separator = PredefinedMenuItem::separator(handle)?;
    let quit_item = MenuItemBuilder::with_id("quit", "Quit").build(handle)?;

    let menu = MenuBuilder::new(handle)
        .items(&[&show_item, &separator, &quit_item])
        .build()?;

    let icon = app
        .default_window_icon()
        .cloned()
        .expect("default window icon required for tray");

    let _tray = TrayIconBuilder::new()
        .icon(icon)
        .tooltip("QwenPaw Desktop")
        .menu(&menu)
        .show_menu_on_left_click(true)
        .on_menu_event(move |app_handle: &AppHandle, event| match event.id().as_ref() {
            "show" => {
                if let Some(window) = app_handle.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
            "quit" => {
                crate::backend::stop(app_handle);
                app_handle.exit(0);
            }
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                let handle = tray.app_handle();
                if let Some(window) = handle.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
        })
        .build(handle)?;

    Ok(())
}