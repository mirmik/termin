# Android Render Showcase

This is a complete Termin project for repeatable Android rendering checks. The
scene exercises the default RenderingManager topology, PBR meshes, directional
shadows, point lighting, bloom, Android Surface lifecycle, and Vulkan
presentation.

## Open in the editor

```bash
./sdk/bin/termin_editor \
  test-projects/android-render-showcase/AndroidRenderShowcase.terminproj
```

## Inspect the build profile

```bash
./sdk/bin/termin_builder profile android-debug \
  --project test-projects/android-render-showcase

./sdk/bin/termin_builder build android-debug \
  --dry-run \
  --project test-projects/android-render-showcase
```

## Build

The local toolchain must provide the Termin Android SDK slice, Android SDK/NDK,
and Gradle. These paths are local context and are deliberately not stored in
the portable profile.

```bash
./sdk/bin/termin_builder build android-debug \
  --project test-projects/android-render-showcase
```

The debug APK is written below `dist/android/apk`.

## Install and run

```bash
adb install -r \
  test-projects/android-render-showcase/dist/android/apk/AndroidRenderShowcase-debug.apk

adb shell am start -W \
  -n org.termin.testprojects.androidshowcase/org.termin.android.TerminActivity
```

For a rendering smoke, keep the application in the foreground for at least
120 frames and check logcat for `RenderingManager`, `ShadowPass`, shader, and
Vulkan errors.
