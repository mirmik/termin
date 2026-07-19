# Termin CLI

`termin` is the central SDK command hub installed into `sdk/bin`.
It is intentionally small: it resolves a subcommand and delegates to a
dedicated executable.

## Commands

```bash
termin editor [project]
termin launcher
termin shaderc ...
termin profiles [--project path/to/project]
termin profile PROFILE [--project path/to/project]
termin build PROFILE [--project path/to/project] [--dry-run]
termin run PROFILE [--project path/to/project] [run options]
termin play [SCENE] [--project path/to/project] [play options]
termin stdlib [sync] [--project path/to/project] [--clean] [--dry-run]
termin runner ...
termin builder ...
```

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
    libpython3.10.so*
    libtermin_*.so*
    python3.10/
      site-packages/
        termin/
        tcgui/
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
does not call `scene.before_render()` or `RenderingManager.render_all`. Use
`--no-assets` and `--no-modules` for narrow smoke tests that do not need project
asset discovery or module loading.

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
