# Termin OpenXR Android Runtime App

This Gradle project packages the Quest/OpenXR NativeActivity separately from
`termin-android`. Project builds normally reach it through a canonical
`quest_openxr` build profile.

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

The smoke app is an Android `NativeActivity` that starts an OpenXR session with Vulkan
(`XR_KHR_vulkan_enable`), lets tgfx2 create the runtime-compatible Vulkan device,
wraps OpenXR swapchain `VkImage`s as non-owning tgfx2 textures, creates a
minimal fallback `tc_scene` when no package is supplied, or loads the packaged
Termin scene and render engine when an asset root is present. The packaged path
uses the common native component/pass bootstrap. Its stereo fallback pipeline
composites `UIComponent` documents through `UIWidgetPass` after tonemapping and
before presentation, then submits the projection layer through `xrEndFrame`.

The canonical Android SDK build owns `libopenxr_loader.so`. Gradle copies that
installed loader with the other SDK shared libraries and deliberately does not
build a private loader from the Khronos source tree. Controller actions expose
left/right thumbsticks, primary trigger values, and aim/grip poses. Poses are
located for the predicted display time and converted into the selected
`XrOrigin` coordinate system before scene update.
