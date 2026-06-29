# Project Build Manifest

Status 2026-06-29: the historical broad-copy
`build.json`/`assets/manifest.json` project build contract was removed. Project
builds now use the standalone `termin-project-build` package
(`termin.project_build`) and produce runtime packages plus
target-specific artifacts.

## Ownership

- Editor: invokes desktop, Android, or Quest/OpenXR build actions.
- CLI/build tool: resolves project profiles and delegates to
  `termin.project_build.profile_build`.
- Runtime package exporter: writes the shared `package/` contract.
- Player/runtime hosts: consume `app.json` or platform-native package wiring.

The removed `termin.project_builder` package must not be reintroduced as a
compatibility path. Build code should live under `termin.project_build`, outside
the editor-private `termin-app` package.

## Runtime Package

All supported targets start from a runtime package:

```text
package/
  manifest.json
  scene.json
  meshes/
  materials/
  shaders/
  pipelines/
  python/
```

`package/manifest.json` is the resource contract consumed by the Python player
runtime package loader and the C++ runtime loader. The exporter records resource
entries such as `shader`, `mesh`, `material`, `pipeline`, and `foliage_data`,
plus shader artifact target requirements when a profile requests explicit
shader targets.

## Desktop Bundle

Desktop builds wrap the runtime package in a relocatable bundle:

```text
dist/<app>/
  <app>
  app.json
  lib/
  package/
    manifest.json
    scene.json
    ...
  share/
```

`app.json` is the desktop bundle entry manifest. Paths are relative to the
bundle root and point at `package/manifest.json` and `package/scene.json`.

The editor `Build` action writes this desktop bundle. The editor `Run Build`
action launches the bundle-local player executable when present, otherwise it
falls back to:

```bash
python -m termin.player --bundle dist/<app>/app.json
```

## Source Playback

Source-project playback remains separate from build output:

```bash
python -m termin.player <project> --scene Scenes/Main.scene
termin play Scenes/Main.scene
```

Source playback may scan project assets and load project modules directly.
Packaged builds must not depend on source tree scanning or the removed
`build.json` format.
