# Android Scene Build Export

Goal: make the editor build a deployable Android package from a saved Termin
scene.

## Current Backend Shape

`termin.project_build.export_runtime_package(...)` writes the runtime package
contract consumed by `termin-runtime`:

- `manifest.json`
- `scene.json`
- `meshes/*.tmesh.json`
- `materials/*.tmat.json`
- `shaders/*.shader.json`
- `shaders/vulkan/*.spv`

`termin.project_build.build_android_project(...)` wraps that exporter and calls
the root `build-android-apk.sh` with `--assets-dir <runtime package>`. The APK is
copied to:

```text
<project>/dist/android/<project>/apk/<project>-debug.apk
```

## Current Limitations

Mesh and material resources are exported from the live runtime registries when
the exporter can resolve their UUIDs. If a referenced registry entry is missing,
the exporter emits a warning and writes a fallback artifact so the end-to-end
Android build remains installable.

The next migration step is replacing these registry-only assumptions with a
proper build resource graph:

- load or build missing mesh/material assets from project files;
- collect shader variants from drawable/material usage rather than only material
  phases currently present in memory;
- export texture bindings and material uniform values;
- report missing resources as build errors once the editor-side asset graph is
  reliable enough.

## Editor Integration

The editor button should remain thin:

```text
Project -> Build -> Android
```

It should save the scene, call `build_android_project(...)`, and display the
build log/diagnostics. Resource traversal and Gradle invocation should stay out
of the UI layer.
