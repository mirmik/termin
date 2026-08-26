# Termin CLI

`termin` is the central SDK command hub installed into `sdk/bin`.
It is intentionally small: it resolves a subcommand and delegates to a
dedicated executable.

## Commands

```bash
termin init [--name NAME]
termin editor [project]
termin launcher
termin shaderc ...
termin profiles [--project path/to/project]
termin profile PROFILE [--project path/to/project]
termin build PROFILE [--project path/to/project] [--dry-run]
termin run PROFILE [--project path/to/project] [run options]
termin play [SCENE] [--project path/to/project] [play options]
termin show MODEL.glb [--width PX] [--height PX] [--title TEXT] [--backend NAME]
termin stdlib [sync] [--project path/to/project] [--clean] [--dry-run]
termin runner ...
termin builder ...
```

`termin init` initializes a starter project directly in the current directory.
The project name defaults to the directory name and can be overridden with
`--name`. Existing unrelated files are preserved, while `.terminproj`,
`scene.scene`, and `project_settings` conflicts are rejected without
overwriting them:

```bash
mkdir MyGame
cd MyGame
termin init
termin editor .
```

A project is added or moved to the top of the launcher's recent-project list
only after the editor has validated and opened it. Selecting a project in the
launcher does not update the list by itself.

## Adding the checkout SDK to Bash PATH

From a source checkout, run:

```bash
task sdk:path
```

The helper writes one managed, idempotent block to `~/.bashrc` using the
checkout's absolute `sdk/bin` path. It preserves the rest of the file and
updates the same block when run again. Open a new Bash shell afterwards, or
apply it immediately with `source ~/.bashrc`. Set `TERMIN_BASHRC` to target a
different Bash startup file.

Unknown commands are resolved in a git-like form:

1. `termin_<command>` next to the `termin` executable;
2. `termin-<command>` next to the `termin` executable;
3. the same names in `PATH`.

`termin build PROFILE` currently delegates to:

```bash
termin_builder build PROFILE
```

`termin run PROFILE` delegates to:

```bash
termin_runner run PROFILE
```

`termin play [SCENE]` delegates to the project playback runner:

```bash
termin_runner play [SCENE]
```

Source playback synchronizes the SDK's standard resource library into
`<project>/stdlib` before loading the scene. Projects that intentionally do not
use or manage the standard library can skip this step explicitly:

```bash
termin play --project . --no-stdlib-sync
```

The flag affects source-project playback only; packaged `termin run` bundles
use the resources exported into the bundle.

`termin show MODEL.glb` opens a standalone model window and does not require a
Termin project. The viewer preserves the GLB node hierarchy, presents static
mesh geometry with base-color factors and base-color textures, converts glTF's
Y-up coordinates to Termin's Z-up convention, and frames the complete model
automatically. Meshes without an assigned GLB material use a cyan, flat-lit
preview material so their form remains readable.

- drag with the left mouse button to orbit;
- drag with the middle or right mouse button to pan;
- scroll the wheel up to zoom in and down to zoom out.

The current command is a static asset preview: skins are shown in their bind
pose and animations are not played. It intentionally uses the lightweight
retained graphics path rather than the project/player PBR scene pipeline.
`--frames N` closes after a finite number of rendered frames and is useful for
SDK smoke checks. `--backend vulkan|opengl|d3d11` overrides the normal platform
backend selection when a specific graphics path needs to be tested.

The command delegates to the dedicated model-viewer package:

```bash
termin_show MODEL.glb
python -m termin.model_viewer MODEL.glb
```

Packaged build commands use the standalone `termin-project-build` package
(`termin.project_build`). The old broad-copy `termin.project_builder` path and
`build.json` player contract were removed.

`termin stdlib` currently delegates to:

```bash
termin_stdlib sync
```

## Build Profiles

Build profiles are project data. The default location is:

```text
project_settings/build_profiles.json
```

Current schema (v1 is deliberately rejected):

```json
{
  "version": 2,
  "profiles": {
    "dev": {
      "target": {"kind": "desktop", "os": "linux", "arch": "x86_64"},
      "configuration": "dev",
      "output_dir": "dist/dev",
      "content": {
        "entry_scene": "Scenes/Main.scene",
        "scenes": ["Scenes/Main.scene"],
        "modules": [],
        "python": {"requirements": []},
        "resources": {"policy": "strict", "include": []}
      },
      "runtime": {"backends": ["vulkan", "opengl"]}
    },
    "quest": {
      "target": {"kind": "quest_openxr", "abi": "arm64-v8a", "ndk_api": 26},
      "configuration": "debug",
      "output_dir": "dist/quest",
      "content": {
        "entry_scene": "Scenes/Main.scene",
        "scenes": ["Scenes/Main.scene"]
      }
    }
  }
}
```

Supported build targets:

- `desktop` - writes a relocatable desktop runtime bundle.
- `android` - exports the shared runtime package and assembles an Android APK.
- `quest_openxr` - exports the shared runtime package and assembles a
  Quest/OpenXR APK.

Desktop profiles must set `runtime.backends` to an ordered list of `vulkan`,
`opengl`, and `d3d11`. The list is both the set of shipped shader artifact
families and the packaged player backend priority. Linux-friendly profiles
normally use `["vulkan", "opengl"]`; Windows/D3D-first profiles can use
`["d3d11", "vulkan", "opengl"]`. D3D11 artifacts require `fxc`, so they are
opt-in instead of an implicit Linux build requirement.

`termin_builder` resolves the project and profile, then delegates to the
canonical Python backend:

```bash
python -m termin.project_build.profile_build build \
  --project-root PROJECT \
  --profiles-path project_settings/build_profiles.json \
  --profile PROFILE
```

The same typed request compiler powers `profiles`, `profile`, `build --dry-run`,
normal builds, and `termin_runner run --profile`. Unknown fields and targets
fail before build work starts. Local SDK/compiler/Gradle paths are toolchain
inputs and are never serialized into the portable profile.

Inspect the canonical local capability report without starting a build:

```bash
python -m termin.project_build.profile_build capabilities \
  --project-root PROJECT \
  --profiles-path project_settings/build_profiles.json \
  --profile PROFILE \
  --json
```

The JSON is the same `inspect_profile_capabilities()` report available to the
editor. Tool paths merge per field as installation defaults < shared user
settings < environment < invocation arguments. Shared settings are stored in
`~/.config/termin/settings.json` on Linux and
`%APPDATA%/termin/settings.json` on Windows. Supported environment overrides
are `TERMIN_SDK`, `TERMIN_ROOT`, `TERMIN_ANDROID_SDK_ROOT`, `ANDROID_HOME`
(with `ANDROID_SDK_ROOT` as the secondary standard name), `ANDROID_NDK_HOME`
(with `ANDROID_NDK_ROOT` as the secondary name), `JAVA_HOME`, `TERMIN_SHADERC`,
`TERMIN_FXC`, `TERMIN_ANDROID_BUILD_SCRIPT`,
`TERMIN_QUEST_OPENXR_BUILD_SCRIPT`, `GRADLE_BIN` and `ADB`. The `build` and
`capabilities` subcommands also accept corresponding
explicit path options; these have highest precedence.

The native editor consumes the same file through **Game > Build Profiles...**.
The adjacent Build/Run/Install/Launch commands always act on the selected
profile. Build and Run use the same normalized request and target dispatch as
the CLI; Install and Launch are enabled only for Android-family profiles when
their exact APK/ADB prerequisites are available. Action output is mirrored to
the Build Profiles Output tab and the editor console.

Workstation-specific paths are configured under
**Edit > Settings... > Build Toolchain**, not in `build_profiles.json`. The
editor stores Termin SDK/source roots, the Termin Android SDK slice, Google
Android SDK, Android NDK, JDK, `termin_shaderc`, FXC, Android/Quest build
scripts, Gradle and ADB in the shared
Termin user settings. The rest of the editor preferences use that same
canonical config file. Environment variables override these saved fallbacks
without making the project dirty. Changing the settings refreshes the selected
profile's action capabilities; the same values are used by a bare `termin build`
when no matching explicit argument is provided.

`build-sdk-android.sh` resolves the NDK independently in this order: explicit
`--ndk`, `ANDROID_NDK_HOME`, `ANDROID_NDK_ROOT`, then
`Build/androidNdkRoot` from the shared settings file.

The v2 model already reserves explicit scene, module, Python-requirement and
resource roots. Builds currently reject non-trivial roots with a structured
`profile.feature_pending` diagnostic until their dependency-closure stages are
implemented; they are never silently ignored.

The backend-only `python -m termin.project_build.profile_build desktop ...`
entrypoint also accepts repeated `--shader-target` values for direct desktop
package experiments.

Desktop builds are written as runtime bundles:

```text
dist/<app>/
  <app>
  app.json
  lib/
    libpython3.14t.so*
    libtermin_*.so*
    python3.14t/
      site-packages/
        termin/
        tgfx/
        ...
  package/
    manifest.json
    scene.json
    python/
      modules.json
      *.pymodule
      <module packages>/
    meshes/
    materials/
    shaders/
    pipelines/
  share/
    termin/
```

Windows bundles use the runtime layout expected by `termin_player.exe`:

```text
dist/<app>/
  <app>.exe
  app.json
  *.dll
  python/
    DLLs/
      _ctypes.pyd
      ...
    Lib/
      site-packages/
        termin/
        ...
```

`app.json` is the bundle entry manifest. Paths inside it are relative to the
bundle root, so the directory can be moved without keeping the original project
path.

Project `.pymodule` descriptors are copied into `package/python`. The generated
`package/python/modules.json` records module descriptors, package files, and
Python requirements for the desktop runtime host. Cache directories such as
`__pycache__` are not copied into the bundle. Requirement packages are copied
from the project `.venv` when present, then from the build backend environment.

Desktop bundles also include a player MCP diagnostics contract in
`app.json` under `runtime.mcp`. It is disabled by default and can be enabled at
run time with `--mcp`, `TERMIN_PLAYER_MCP=1`, or by setting
`runtime.mcp.enabled` in the manifest. The player MCP server exposes the shared
MCP transport, an `execute_python_script` tool against the running player
thread, and a `capture_player_screenshot` tool that reads the player render
surface into a PNG. The script namespace includes `runtime`/`player`, `scene`,
`window`, `surface`, `display`, `viewport`, `camera`, `project_path`,
`scene_name`, `delta_time`, and `request_quit`.

Desktop builds currently package the SDK CPython runtime, Termin Python
packages, Termin native libraries, project Python modules, recursive Python
package requirements discovered from module descriptors, built-in shader
resources, and precompiled runtime shader artifacts. Linux system libraries are
not vendored yet: SDL2, Vulkan/OpenGL, X11/Wayland/audio, libc/libstdc++, and
their transitive dependencies are still resolved from the host OS.

## Running Profiles

The default run mode starts a desktop build already produced by the matching
build profile:

```bash
termin run dev --project path/to/project
```

`run` is a desktop packaged-runtime command today. Android and Quest/OpenXR
profiles are build-only from `termin build`; install/launch on devices still
goes through the dedicated deploy helpers until `termin deploy PROFILE` becomes
the canonical device command.

Enable player MCP for a run:

```bash
termin run dev --project path/to/project --mcp
termin run dev --project path/to/project --mcp --mcp-port 9001
```

The default player MCP session file is:

```text
/tmp/termin-player-mcp.json
```

Player screenshots captured through MCP default to:

```text
/tmp/termin-player-screenshots/
```

Packaged desktop bundles launch through the bundle-local C++ host:

```bash
dist/<app>/<app>
```

The host loads `app.json` and the runtime package through native
`termin::runtime::RuntimePackageLoader`. It embeds the bundle-local CPython
runtime only for project scripts/modules, adding bundled `site-packages` and
`package/python` to `sys.path`; Python `PlayerRuntime` does not manage packaged
execution.
`--backend <name>` is consumed by the C++ host and translated to
`TERMIN_BACKEND` before CPython is initialized; display options such as
`--width`, `--height`, and `--windowed` are consumed by the native host. If
`TERMIN_BACKEND` is not set explicitly, packaged player runs use
the first compiled backend listed in `package/manifest.json`
`target_requirements.shader_targets`. Source-scene `play` runs without a
package manifest keep the platform compiled default. By default the player
switches the window to borderless desktop fullscreen after creating it;
`--width` and `--height` define the normal-window size used when `--windowed`
is passed and the initial size before the OS applies fullscreen mode.

Backend selection is explicit after device creation. In particular, a Vulkan
device reported as a CPU renderer (for example Mesa Lavapipe) is not silently
replaced with OpenGL or another backend. Native editor startup logs the Vulkan
device and driver and shows a warning dialog; the same information is available
from **Help → About Termin**. Select an alternative explicitly with
`TERMIN_BACKEND=<name>` and restart the editor.

By default `run` does not rebuild implicitly and expects a packaged desktop
bundle. Pass `--build-if-missing` to build when packaged output is absent, or
`--rebuild` to rebuild before every launch. Pass `--dry-run` to inspect the
resolved player command without starting a window.

The removed `build.json` format is not a fallback for `run`.

`play` is intentionally separate from build output and build profiles. It
launches a source scene directly through `termin.player`, which keeps room for
editor-like Play Mode flows:

```bash
termin play
```

Scene selection order:

1. explicit positional scene, for example `termin play Scenes/Main.scene`;
2. explicit `--scene`, for compatibility with lower-level player options;
3. project-local `project_settings/.editor_state.json` `last_scene`;
4. first `.scene` file found under the project root.

Headless playback runs the same source scene update lifecycle without creating
a window, `RenderingManager`, display surfaces, or render passes. It is intended
for tests and simulation-only checks:

```bash
termin play --headless
termin play --headless --frames 10 --dt 0.0166667
```

In headless mode `termin.player` loads the scene without render scene
extensions and calls `scene.update(dt)` in a loop until the project requests
quit or the process is interrupted. `--frames` adds an explicit frame limit for
finite smoke checks. It attaches the collision world scene extension by default
so simulation-only physics can run without a window or `RenderingManager`. It
does not create `RenderingManager` or activate render lifecycle capabilities.
Serialized `render_mount` and `render_state` data is deliberately ignored, and
requesting either extension explicitly is an error because the headless host
does not create the services required to use them.

Drawable and other render-only components may remain in a source scene: their
serialized state is loaded, but their render lifecycle is inactive. Components
whose `start`, `update`, or `fixed_update` paths require a GPU, window, display
surface, or `RenderingManager` are not headless-compatible and must report that
missing service instead of waiting for a render callback. Run such a project
through a windowed or offscreen render host. `include_render_resources` only
controls registration of render asset/resource types; it does not create render
services. Use `--no-assets` and `--no-modules` for narrow smoke tests that do not
need project asset discovery or module loading.

`termin_runner run --mode project` remains only as a lower-level compatibility
path. The user-facing command for source project playback is `termin play`.

Useful run/play options:

```bash
termin run dev --backend opengl --width 1600 --height 900 --title Chess
termin run dev --windowed --width 1600 --height 900 --title Chess
termin play Scenes/scene2.scene
termin play --headless --frames 1 --no-assets --no-modules
```

## Standard Library

The SDK standard library is copied into a project with:

```bash
termin stdlib --project path/to/project
```

By default the command copies new files and updates changed files under
`<project>/stdlib`. Pass `--clean` to remove files from the project stdlib that
no longer exist in the SDK stdlib.

Stdlib shader assets use stable readable IDs in `.shader.meta` files, for
example `stdlib-blinn`. Runtime phase shader IDs are derived from those IDs,
for example `stdlib-blinn-shadow`.
