# Termin OpenXR Android Smoke App

This Gradle project builds the experimental Quest/OpenXR smoke APK separately
from `termin-android`.

Build from the repository root:

```bash
./build-sdk-android.sh --abi arm64-v8a --platform android-26
./build-quest-openxr-apk.sh --application-id org.example.openxr \
  --gradle /path/to/gradle-8.x/bin/gradle
```

Pass `--variant debug` (the default) or `--variant release`. Release builds use
the shared Android signing contract documented in `docs/build-system.md` and
require all four `TERMIN_ANDROID_SIGNING_*` environment variables.

Project builds pass the canonical `project_settings/project.json` application
identity through `--application-id`, `--app-label`, `--version-code`, and
`--version-name`. Standalone smoke invocations may pass the same options
explicitly.

Install and launch on a connected headset:

```bash
./build-quest-openxr-apk.sh --application-id org.example.openxr \
  --gradle /path/to/gradle-8.x/bin/gradle --launch
```

`--launch` wakes the device through ADB before sending the launcher intent. The
Quest proximity sensor still has to keep the headset active; otherwise Android
will pause/stop the activity immediately after launch.

The smoke app does not use the Termin render engine yet. It is an Android
`NativeActivity` that starts an OpenXR session with Vulkan
(`XR_KHR_vulkan_enable`), lets tgfx2 create the runtime-compatible Vulkan device,
wraps OpenXR swapchain `VkImage`s as non-owning tgfx2 textures, creates a
minimal `tc_scene` entity with a `MeshComponent` backed by
`tc_primitive_unit_sphere()`, renders that sphere through tgfx2 command lists
with each eye's `xrLocateViews` pose/FOV, and submits the projection layer
through `xrEndFrame`.
