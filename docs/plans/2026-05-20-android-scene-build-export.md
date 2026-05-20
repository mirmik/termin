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

## Temporary Limitations

Mesh and material resources are currently emitted as diagnostic placeholders.
This is deliberate for the first end-to-end build path: package export, APK
assembly, install, and runtime loading can be verified before the real resource
graph is complete.

The next migration step is replacing placeholders with actual exported
resources:

- collect mesh/material/shader refs from the live scene and saved assets;
- serialize real `TcMesh` data into runtime mesh artifacts;
- serialize `TcMaterial` phases/properties into runtime material artifacts;
- collect shader variants from drawable/material usage;
- compile/copy matching SPIR-V artifacts into the runtime package.

## Editor Integration

The editor button should remain thin:

```text
Project -> Build -> Android
```

It should save the scene, call `build_android_project(...)`, and display the
build log/diagnostics. Resource traversal and Gradle invocation should stay out
of the UI layer.
