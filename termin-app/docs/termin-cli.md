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

## Running Profiles

The default run mode starts a desktop build already produced by the matching
build profile:

```bash
termin run dev --project path/to/project
```

This resolves `output_dir` from the profile and launches:

```bash
python -m termin.player --build <output_dir>/build.json
```

By default `run` does not rebuild implicitly. Pass `--build-if-missing` to build
when `build.json` is absent, or `--rebuild` to rebuild before every launch.
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
