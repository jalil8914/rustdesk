mod keyboard;
/// cbindgen:ignore
pub mod platform;
#[cfg(not(any(target_os = "android", target_os = "ios")))]
pub use platform::{
    clip_cursor, get_cursor, get_cursor_data, get_cursor_pos, get_focused_display,
    set_cursor_pos, start_os_service,
};
#[cfg(not(any(target_os = "ios")))]
/// cbindgen:ignore
mod server;
#[cfg(not(any(target_os = "ios")))]
pub use self::server::*;
mod client;
mod lan;
#[cfg(not(any(target_os = "ios")))]
mod rendezvous_mediator;
#[cfg(not(any(target_os = "ios")))]
pub use self::rendezvous_mediator::*;
/// cbindgen:ignore
pub mod common;
#[cfg(not(any(target_os = "ios")))]
pub mod ipc;
#[cfg(not(any(
    target_os = "android",
    target_os = "ios",
    feature = "flutter"
)))]
pub mod ui;
mod version;
pub use version::*;
#[cfg(any(target_os = "android", target_os = "ios", feature = "flutter"))]
mod bridge_generated;
#[cfg(any(target_os = "android", target_os = "ios", feature = "flutter"))]
pub mod flutter;
#[cfg(any(target_os = "android", target_os = "ios", feature = "flutter"))]
pub mod flutter_ffi;
use common::*;
mod auth_2fa;
#[cfg(not(target_os = "ios"))]
mod clipboard;
#[cfg(not(any(target_os = "android", target_os = "ios")))]
pub mod core_main;
mod custom_server;
mod lang;
#[cfg(not(any(target_os = "android", target_os = "ios")))]
mod port_forward;

#[cfg(all(feature = "flutter", feature = "plugin_framework"))]
#[cfg(not(any(target_os = "android", target_os = "ios")))]
pub mod plugin;

#[cfg(not(any(target_os = "android", target_os = "ios")))]
mod tray;

#[cfg(not(any(target_os = "android", target_os = "ios")))]
mod whiteboard;

#[cfg(not(any(target_os = "android", target_os = "ios")))]
mod updater;

mod ui_cm_interface;
mod ui_interface;
mod ui_session_interface;

mod hbbs_http;

#[cfg(any(target_os = "windows", target_os = "linux", target_os = "macos"))]
pub mod clipboard_file;

pub mod privacy_mode;

#[cfg(windows)]
pub mod virtual_display_manager;

mod kcp_stream;

/// Apply the Aqsacloud defaults.
///
/// Called from BOTH entry points. core_main() only runs on desktop; Flutter
/// mobile loads the library directly, so anything set only there leaves Android
/// and iOS showing "RustDesk" with an unconfigured server.
///
/// Every value is set only when unset, so a custom.txt config or a user's own
/// choice in Settings still wins.
/// True when this binary is running as the customer-facing support client.
///
/// The support client is the same executable under a different filename, so a
/// second full build of the matrix is not needed - the portable packer records
/// whatever name it is given and the name survives extraction.
fn is_support_client() -> bool {
    std::env::current_exe()
        .ok()
        .and_then(|p| {
            p.file_stem()
                .map(|s| s.to_string_lossy().to_lowercase())
        })
        .map_or(false, |name| name.contains("support"))
}

pub fn apply_branding() {
    // MUST stay within [a-zA-Z0-9-] - see validate_install_app_name in
    // platform/windows.rs. The name is interpolated UNQUOTED into ~25 shell
    // commands, so a space silently breaks Windows install.
    if hbb_common::config::APP_NAME.read().unwrap().eq("RustDesk") {
        *hbb_common::config::APP_NAME.write().unwrap() = "Aqsacloud".to_owned();
    }
    if hbb_common::config::PROD_RENDEZVOUS_SERVER
        .read()
        .unwrap()
        .is_empty()
    {
        *hbb_common::config::PROD_RENDEZVOUS_SERVER.write().unwrap() =
            "remote.aqsacloud.com".to_owned();
    }
    // RS_PUB_KEY is a const inside the hbb_common submodule and cannot be
    // patched from this repo, so the key is injected as a runtime setting.
    // DEFAULT_SETTINGS is the lowest-priority source in Config::get_option, so
    // a value the user sets in the GUI still overrides it.
    //
    // custom-rendezvous-server is seeded too: the Network dialog reads the
    // option, so without it the ID server box renders empty.
    {
        let mut settings = hbb_common::config::DEFAULT_SETTINGS.write().unwrap();
        settings
            .entry("custom-rendezvous-server".to_owned())
            .or_insert_with(|| "remote.aqsacloud.com".to_owned());
        settings
            .entry("key".to_owned())
            .or_insert_with(|| "ZcB8ewCtyWslUP911rTiyQ9B8LcO2brghndeO3UmImo=".to_owned());
    }

    // Customer-facing support client: receive connections only.
    //
    // is_incoming_only() reads exactly this key, and the Flutter layer keys the
    // narrow single-pane window, the hidden connect field and the suppressed
    // install prompt off it. Set here so it lands before any UI reads it, on
    // both the desktop and mobile entry points.
    if is_support_client() {
        hbb_common::config::HARD_SETTINGS
            .write()
            .unwrap()
            .insert("conn-type".to_owned(), "incoming".to_owned());
    }
}
