# Aqsacloud branding

Everything separating this fork from upstream RustDesk, and — more importantly —
the constraints that are **not** obvious from reading the code.

Read [Landmines](#landmines) before merging any upstream release. Every entry
there is something that broke a real build.

---

## Landmines

Non-negotiable constraints. Each one caused a failure that looked like something
else entirely.

### 1. `APP_NAME` must match `[a-zA-Z0-9-]+` — no spaces

`src/core_main.rs` sets it to `Aqsacloud`. It was briefly `Aqsacloud Desk`, which
broke Windows install with no useful error.

`crate::get_app_name()` is interpolated **unquoted** into ~25 shell commands in
`src/platform/windows.rs`:

```
sc create Aqsacloud Desk binpath= "..." start= auto    # "Desk" parses as a stray arg
sc stop/delete Aqsacloud Desk
reg add HKEY_CLASSES_ROOT\.aqsacloud desk /f           # ext = app_name.to_lowercase()
```

The service is never created and install dies, while the UI still reports
"ready". Upstream documents the rule in `validate_install_app_name()` — which is
only referenced from tests, so nothing enforces it at runtime.

Hyphens are legal: `Aqsacloud-Desk` would work if a two-word name is ever wanted.

### 2. These names must NOT be rebranded

| File | Field | Why |
|---|---|---|
| `Cargo.toml` | `[package] name = "rustdesk"` | `default-run` and every `target/release/rustdesk*` path in CI depend on it |
| `flutter/pubspec.yaml` | `name: flutter_hbb` | Every `import 'package:flutter_hbb/...'` breaks |
| `flutter/linux/CMakeLists.txt` | `BINARY_NAME "rustdesk"` | Linux packaging paths |
| `Cargo.toml` | `[lib] name = "librustdesk"` | Android loads `librustdesk.so` by name |

`description`, `authors`, and `APPLICATION_ID` are safe to brand.

### 3. `libs/hbb_common` is a git submodule

It points at `rustdesk/hbb_common` and **cannot be patched from this repo**.

That is why the server key is injected at runtime rather than set at
`config::RS_PUB_KEY`, which is a `const` inside the submodule. See
[Server configuration](#server-configuration).

Changing anything in there means forking it and repointing `.gitmodules`.

### 4. `build.py` must stay mode `100755`

The workflow calls `./build.py` directly for the macOS and packaging jobs. If the
executable bit is lost the job dies with `./build.py: Permission denied`.

This is easy to drop when committing through the GitHub Git Data API, which
requires an explicit `mode` per tree entry. Always read the existing tree and
carry modes forward rather than hardcoding `100644`.

### 5. Renaming the macOS `PRODUCT_NAME` renames the `.app` bundle

`flutter/macos/Runner/Configs/AppInfo.xcconfig` sets `PRODUCT_NAME = Aqsacloud Desk`,
so `flutter build macos` emits `Aqsacloud Desk.app`. Three places assumed
`RustDesk.app` and now discover the bundle instead:

- `build.py` — globs `build/macos/Build/Products/Release/*.app`
- `.github/workflows/flutter-build.yml` — the unsigned `create-dmg` step
- `.github/workflows/flutter-build.yml` — the codesign + signed `create-dmg` step

Quote the path: the branded name contains a space.

### 6. Do not "fix" `lazy_static` by downgrading it

`lazy_static 1.5.0` is **not yanked**. `hbb_common` requires `"1.5"`, so pinning
1.4.0 makes `Cargo.lock` unsatisfiable under `--locked` and breaks every Rust job.

The real cause of `no matching package named lazy_static found` was the
`crates.io-index` override — see below.

### 7. The arch containers must not force the git crates.io index

The `run-on-arch` jobs used to write:

```
[source.crates-io]
registry = 'https://github.com/rust-lang/crates.io-index'
```

That overrides the sparse protocol with the legacy git index, whose clone inside
the container image is stale. Crates published after that snapshot are invisible,
which surfaces as "no matching package" for versions that plainly exist.

Removed from all three container jobs. If armv7 sciter starts failing again with
a missing-crate error, check whether an upstream merge reintroduced it.

### 8. The installer must rename the binary

`copy_raw_cmd()` XCOPYs the source folder verbatim, so the executable installs
under its **cargo** name, `rustdesk.exe`. But `get_install_info()` derives

```
exe = <path>\<get_app_name()>.exe      ->  C:\Program Files\Aqsacloud\Aqsacloud.exe
```

and that path is used for the desktop shortcut, the `sc create` binpath, and the
"am I already installed?" check. Without a rename that file never exists, so:

- the desktop shortcut does nothing
- the service cannot be registered
- the installed copy keeps offering to install itself

Upstream cannot hit this: `RustDesk` matches `rustdesk.exe` case-insensitively
on Windows. Any rebranded name diverges from the cargo binary name and breaks
the assumption.

`rename_exe_cmd()` exists for this. **Both** install paths must call it -
`install_me()` and the MSI/update path around `run_after_install`. Only the
latter did upstream.

### 9. Recolouring a surface means auditing everything on it

Upstream paints several panels with saturated fills - a magenta-to-salmon
gradient on the install card, cyan-to-blue on the connection-manager header -
and hardcodes `Colors.white` for the text, buttons, links and icons sitting on
them.

Swapping the fill for a theme colour without touching the contents leaves white
text on a light background: invisible, and only in the light theme, so it does
not show up in dark-mode testing. This was hit three separate times.

When changing a container's background, grep the whole widget for
`Colors.white` and `Colors.white70` before moving on. Two rules:

- text and icons **on a themed surface** follow
  `Theme.of(context).textTheme.titleLarge?.color`
- text and icons **on a solid accent fill** (buttons, badges) keep white, or use
  a dark tone against the brand orange - `Color(0xFF3A2600)`

Also check the language files: several upstream strings bake the product name
into the copy rather than deriving it, so a rename leaves them stale.

---

## Server configuration

Set in `src/core_main.rs`, immediately after `crate::load_custom_client()`.

| Setting | Value | Mechanism |
|---|---|---|
| App name | `Aqsacloud` | `config::APP_NAME` |
| ID server | `remote.aqsacloud.com` | `PROD_RENDEZVOUS_SERVER` **and** `DEFAULT_SETTINGS["custom-rendezvous-server"]` |
| Public key | `ZcB8ew...ImIo=` | `DEFAULT_SETTINGS["key"]` |

Two things worth understanding:

**Why `DEFAULT_SETTINGS` and not `RS_PUB_KEY`.** The latter is a `const` in the
hbb_common submodule. `Config::get_option` resolves
`OVERWRITE_SETTINGS` → `CONFIG2.options` → `DEFAULT_SETTINGS`, so seeding the
lowest tier gives a shipping default the user can still override in Settings.
`common.rs::get_key()` falls back to `RS_PUB_KEY` only when the option is empty.

**Why both server keys.** `PROD_RENDEZVOUS_SERVER` works as a connection
fallback, but the Network settings dialog reads the `custom-rendezvous-server`
option — without it the ID server box renders empty and looks unconfigured.

The ID server is a **hostname, never a bare IP**. It is compiled into every
client, so a hardcoded address would strand every install if the server moved;
a hostname makes that a DNS change. The Cloudflare record must stay **DNS only**
(grey cloud) - the proxy handles HTTP/HTTPS, while this speaks raw TCP/UDP on
21115-21119. Verify with `nslookup remote.aqsacloud.com 1.1.1.1`: it must return
the origin IP, not a Cloudflare address.

The Key shown in Settings is the server's **public** key. It is meant to be in
every client and is not a secret.

---

## Update check — disabled

`src/common.rs::check_software_update()` has an empty body.

Upstream posts to `https://api.rustdesk.com/version/latest`; the response carries
a URL pointing at **upstream's** releases. If their version number exceeds ours,
the app raises an Update button that would replace this client with stock
RustDesk.

With the check disabled, `SOFTWARE_UPDATE_URL` stays empty, which also keeps the
Update button hidden on the home page. Distribute updates from our own releases.

Upstream gates this behind `is_custom_client()` — a flag set by their licensing
flow, which this build does not satisfy, so the check was live.

---

## Icons — 7 distinct slots

Missing any of these leaves an upstream mark somewhere visible. The tray and
taskbar were missed on the first pass precisely because they are not under `res/`.

| Slot | Files | Drives |
|---|---|---|
| `res/` | `icon.png`, `mac-icon.png`, `128x128.png`, `128x128@2x.png`, `64x64.png`, `32x32.png`, `icon.ico`, `tray-icon.ico`, `mac-tray-{dark,light}-x2.png`, `logo.svg`, `scalable.svg` | Linux/macOS packaging |
| `flutter/windows/runner/resources/app_icon.ico` | multi-res ICO | **Window + taskbar** |
| `flutter/assets/icon.png` | 512px, transparent | **Tab bar + system tray** |
| `flutter/assets/icon.svg` | vector | tab-bar fallback |
| Android mipmaps | `ic_launcher`, `ic_launcher_round`, `ic_launcher_foreground`, `ic_stat_logo` × 5 densities | Launcher, notifications |
| iOS AppIcon | 15 sizes, **opaque** (iOS rejects alpha) | Home screen |

`flutter/assets/icon.png` **did not exist upstream**. `src/tray.rs::load_icon_from_asset()`
reads `data\flutter_assets\assets\icon.png` and falls back to `res/tray-icon.ico`
only when absent — so creating it is what fixes the tray.

Android notification icons (`ic_stat_logo`) must be white-on-transparent `LA`
mode; Android masks them to a silhouette.

### Regenerating icons

`scripts/genicons.py` builds every raster from measured geometry rather than
upscaling the 226×57 source logo, which is far too small for the 1024px slots.

The mark is a stroked cloud — the union of two circles plus a connecting body,
in a 40×30 box:

```
big lobe   : center (15.0, 15.0)  r 15.0
small lobe : center (29.5, 20.0)  r 10.0
body       : x 15.0 .. 29.5, top y 15.0
baseline   : y 30.0        <- all three MUST bottom out here or the flat edge steps
stroke     : 3.6
colors     : #F5A623 on #050A14
```

Omitting the connecting body makes it read as two stuck-together circles rather
than a cloud.

---

## UI changes

Palette lives in `flutter/lib/common.dart` (`MyTheme`), so most surfaces inherit
it. Mobile picks up the colours for free; only desktop layout was restructured.

| File | Change |
|---|---|
| `common.dart` | `accent`/`accent50`/`accent80`/`idColor`/`button` → `#F5A623`; dark `scaffoldBackgroundColor` → `#050A14`, `background` → `#0D1626` |
| `desktop_home_page.dart` | 52px icon rail; ID as 31px hero card + copy button; password card; left pane 300px |
| `connection_page.dart` | Connect panel filled card, full-width (max 640); divider removed |
| `desktop_setting_page.dart` | Pill nav (4px accent bar removed); About debranded + footer card |
| `desktop_tab_page.dart` | `showTitle: true` |
| `tabbar_widget.dart` | Wordmark "Aqsacloud" |
| `remote_toolbar.dart` | `_ToolbarTheme` constants only — radius 14, brand navy, no logic touched |
| `peer_card.dart` | `peerCardUiType` default `grid` → `list` |

Notes for future edits:

- **Prefer theme lookups to literals.** Cards use `colorScheme.background` and
  panes use `scaffoldBackgroundColor` so the light theme still works.
- **`_ListView.isHideSingleItem()`** already hides tab chips while only Home is
  open. Forcing them hidden permanently would strand the user in Settings with no
  route back.
- **Links inside `SelectionArea` do not fire.** Text selection swallows the tap —
  the About footer link is a sibling, not a child.
- **`translate('Slogan_tip')`** carries upstream's slogan in every language file.
  The About slogan is a literal for that reason.

---

## Build and CI

| Workflow | Trigger | Purpose |
|---|---|---|
| `brand-build.yml` | push to `aqsacloud/main` | Full matrix; publishes release `aqsacloud-N` |
| `flutter-analyze.yml` | push to `aqsacloud/dev` | Dart errors in ~4 min instead of 40 |

Work on `aqsacloud/dev`, let the gate pass, then merge to `aqsacloud/main`.

The gate generates FRB bindings first — `flutter/lib` imports
`generated_bridge.dart`, which is not committed, so analyze fails without it.

**The gate only covers Dart.** Rust and workflow changes are validated only by a
full build.

### Android signing

Four repo secrets: `ANDROID_SIGNING_KEY` (base64 keystore), `ANDROID_ALIAS`,
`ANDROID_KEY_STORE_PASSWORD`, `ANDROID_KEY_PASSWORD`.

Without them Gradle silently falls back to the **debug** key, and Play Protect
blocks the install with "App blocked to protect your device". Those secrets also
gate the APK artifact upload, so unsigned runs publish APKs only to the release.

Keystore: `aqsacloud-release.jks`, alias `aqsacloud`, RSA 2048, valid to 2053.
**Losing it means never being able to update installed apps.** Back it up.

### Known-failing / limitations

- **macOS DMGs are unsigned** — needs `MACOS_P12_BASE64` and a paid Apple
  certificate. Users must right-click → Open.
- **iOS `.ipa` is unsigned** — `flutter build ipa --no-codesign` cannot export a
  real IPA, so `Runner.app` is wrapped in the standard `Payload/` layout. It
  needs re-signing (AltStore/Sideloadly) to install.

---

## Merging upstream

The branding is concentrated deliberately. Files that conflict most:

```
src/core_main.rs                  flutter/lib/common.dart
src/common.rs                     flutter/lib/desktop/pages/*.dart
Cargo.toml                        .github/workflows/flutter-build.yml
```

Checklist after any upstream merge:

1. `APP_NAME` still `Aqsacloud`, still no spaces
2. `Cargo.toml [package] name` still `rustdesk`
3. `build.py` still mode `100755`
4. `check_software_update()` still empty
5. No `crates.io-index` override reintroduced in `flutter-build.yml`
6. macOS `.app` discovery still present in `build.py` and both `create-dmg` steps
7. `flutter/assets/icon.png` still present
8. Run the analyze gate, then a full build, then install and check the tray icon,
   About page, and that install completes

`master` tracks upstream and is the merge point.
