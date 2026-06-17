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
termin play PROFILE [--project path/to/project] [run options]
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

`termin run PROFILE` and `termin play PROFILE` currently delegate to:

```bash
termin_runner run PROFILE
```

`termin stdlib` currently delegates to:

```bash
termin_stdlib sync
```

## Build Profiles

Build profiles are project data. The default location is:

```text
project_settings/build_profiles.json
```

Initial schema:

```json
{
  "profiles": {
    "dev": {
      "target": "desktop",
      "entry_scene": "Main.scene",
      "output_dir": "dist/dev"
    },
    "quest": {
      "target": "quest_openxr",
      "entry_scene": "Main.scene",
      "output_dir": "dist/quest"
    }
  }
}
```

`target: "desktop"` executes the desktop build backend. Use `--dry-run` to
check profile loading without running the backend.

Desktop builds are written as runtime bundles:

```text
dist/<app>/
  app.json
  bin/
    termin_player
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

`app.json` is the bundle entry manifest. Paths inside it are relative to the
bundle root, so the directory can be moved without keeping the original project
path.

Project `.pymodule` descriptors are copied into `package/python`. The generated
`package/python/modules.json` records module descriptors, package files, and
Python requirements for the desktop runtime host. Cache directories such as
`__pycache__` are not copied into the bundle.

Desktop bundles also include a player MCP diagnostics contract in
`app.json` under `runtime.mcp`. It is disabled by default and can be enabled at
run time with `--mcp`, `TERMIN_PLAYER_MCP=1`, or by setting
`runtime.mcp.enabled` in the manifest. The player MCP server exposes the shared
MCP transport, an `execute_python_script` tool against the running player
thread, and a `capture_player_screenshot` tool that reads the player render
surface into a PNG. The script namespace includes `runtime`/`player`, `scene`,
`window`, `surface`, `display`, `viewport`, `camera`, `project_path`,
`scene_name`, `asset_manifest_path`, `build_json_path`, `delta_time`, and
`request_quit`.

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

Legacy builds resolve `output_dir` from the profile and launch:

```bash
python -m termin.player --build <output_dir>/build.json
```

Packaged desktop bundles launch through the bundle-local C++ host:

```bash
dist/<app>/bin/termin_player
```

The host embeds CPython from `dist/<app>/lib/python3.10`, adds bundled
`site-packages` and `package/python` to `sys.path`, and calls
`termin.player --bundle dist/<app>/app.json`.
`--backend <name>` is consumed by the C++ host and translated to
`TERMIN_BACKEND` before CPython is initialized; display options such as
`--width`, `--height`, and `--title` are forwarded to the Python player.

By default `run` does not rebuild implicitly. Pass `--build-if-missing` to build
when build output is absent, or `--rebuild` to rebuild before every launch.
Pass `--dry-run` to inspect the resolved player command without starting a
window.

`run` is intentionally not build-only. Source project mode launches the profile
entry scene directly through the player, which keeps room for editor-like
Play Mode flows:

```bash
termin run dev --mode project
```

Useful run options:

```bash
termin run dev --backend opengl --width 1600 --height 900 --title Chess
termin run dev --mode project --scene scene2.scene
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
