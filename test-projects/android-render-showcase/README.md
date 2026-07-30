# Android Render Showcase

This is a complete Termin project for repeatable Android rendering checks. The
scene exercises the default RenderingManager topology, PBR meshes, directional
shadows, point lighting, bloom, Android Surface lifecycle, Vulkan presentation,
and the packaged native scene-UI contract.

`UI/native_runtime_hud.uiscript` is compiled into a `ui_document` package
resource. `Native Runtime HUD/UIComponent` instantiates it, while the default
pipeline paints it through `UIWidgetPass`. The document deliberately contains
an overlay, labels, and an `IconButton`. No `tcgui` or Python scene-UI module is
part of this path.

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

## Native UI device gates

Run these named scenarios and retain the filtered logcat output with the build
artifact:

1. `android-native-ui-input`: launch in portrait, tap the blue `UI` button, then
   drag over it. The button handles the pointer stream and the orbit camera does
   not move. Drag in uncovered scene space; the camera must orbit.
2. `android-native-ui-resize`: rotate portrait → landscape → portrait. The HUD
   remains 20 px from the top-left corner and neither labels nor button retain
   stale pre-rotation bounds.
3. `android-native-ui-runtime-closure`: keep the application in the foreground
   for at least 120 frames. The label/button/overlay remain visible and logcat
   contains no missing component, pass, widget factory, UI asset, shader, or
   Vulkan errors.

Suggested capture:

```bash
adb logcat -c
adb shell am start -W \
  -n org.termin.testprojects.androidshowcase/org.termin.android.TerminActivity
adb logcat -d -v threadtime \
  TerminAndroid:I TerminTcLog:I '*:S'
```
