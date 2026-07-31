# Android Render Showcase

This is a complete Termin project for repeatable Android rendering checks. The
scene exercises the default RenderingManager topology, PBR meshes, directional
shadows, point lighting, bloom, Android Surface lifecycle, Vulkan presentation,
and the packaged native scene-UI contract.

`UI/native_runtime_hud.uiscript` is compiled into a `ui_document` package
resource. `Native Runtime HUD/UIComponent` instantiates it, while the default
pipeline paints it through `UIWidgetPass`. The document deliberately contains
an overlay, wrapped labels, and an `IconButton`. Layout values are logical UI
units. The root respects Android safe insets, the button has a 48-by-48 minimum
touch target, and responsive variants widen/reflow the HUD at medium/expanded
widths and switch it to a horizontal row in landscape. No `tcgui`, Python
scene-UI module, platform-name selector, or project-local density calculation
is part of this path.

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

The debug APK is written below `dist/android/apk`. The packaged UI dependency
list should contain only native widget types used by
`UI/native_runtime_hud.uiscript`.

## Install and run

```bash
adb install -r \
  test-projects/android-render-showcase/dist/android/apk/AndroidRenderShowcase-debug.apk

adb shell am start -W \
  -n org.termin.testprojects.androidshowcase/org.termin.android.TerminActivity
```

To enable the native frame profiler explicitly for a development smoke, pass
the activity extra and inspect the periodic completed-frame report:

```bash
adb shell am force-stop org.termin.testprojects.androidshowcase
adb shell am start -W \
  --ez termin.profiler true \
  -n org.termin.testprojects.androidshowcase/org.termin.android.TerminActivity
adb logcat -d -s TerminAndroid:I | grep 'profiler: completed='
```

Without the extra, packaged applications keep native profiling disabled. The
extra is ignored by non-debug variants.

## Native UI emulator/device gates

Use a named arm64 target (`adb devices -l`) and record its serial, logical
resolution, density, font scale, and safe inset/navigation mode. Run these
named scenarios and retain both screenshots and filtered logcat with the build
artifact:

1. `android-native-ui-portrait`: launch in portrait. The HUD starts 12 logical
   units inside the safe rect, the two-line hint is readable without clipping,
   and the blue `UI` button is at least 48 logical units on both axes. Save
   `android-native-ui-portrait.png`.
2. `android-native-ui-landscape`: rotate to landscape. The same retained
   title/hint/button handles form one horizontal row, remain inside display
   cutout and system-bar insets, and do not unexpectedly cover the center of
   the scene. Save `android-native-ui-landscape.png`.
3. `android-native-ui-input`: tap the blue `UI` button, then drag over it. The
   button handles the pointer stream and the orbit camera does not move. Drag
   in uncovered scene space; the camera must orbit.
4. `android-native-ui-resize`: rotate portrait → landscape → portrait. The HUD
   returns to its original geometry and button active state without stale
   pre-rotation bounds or rematerialization.
5. `android-native-ui-runtime-closure`: keep the application in the foreground
   for at least 120 frames. The label/button/overlay remain visible and logcat
   contains no missing component, pass, widget factory, UI asset, shader, or
   Vulkan errors.

Reference captures from the `SM-A546E` arm64 device gate (1080 by 2340
physical pixels, density 2.812, font scale 1.1) are retained in
[`docs/android-native-ui-portrait.png`](docs/android-native-ui-portrait.png)
and
[`docs/android-native-ui-landscape.png`](docs/android-native-ui-landscape.png).
They demonstrate the compact portrait stack and the landscape row after safe
insets have been applied.

Suggested capture:

```bash
adb logcat -c
adb devices -l
adb shell wm size
adb shell wm density
adb shell settings get system font_scale
adb shell am start -W \
  -n org.termin.testprojects.androidshowcase/org.termin.android.TerminActivity
adb exec-out screencap -p > android-native-ui-portrait.png
adb shell settings put system user_rotation 1
adb exec-out screencap -p > android-native-ui-landscape.png
adb shell settings put system user_rotation 0
adb logcat -d -v threadtime \
  TerminAndroid:I TerminTcLog:I '*:S'
```

If automatic rotation is enabled, use the emulator/device rotation control
instead of changing `user_rotation`. Restore the original rotation setting
after the capture. Some devices (including OnePlus 5 on Android 10) retain the
application-requested orientation when only the setting is changed. For those,
use the WindowManager override documented in the
[adaptive UI regression matrix](../../docs/adaptive-ui-regression-matrix.md),
then restore free rotation immediately after the gate.
