# Quest OpenXR Showcase

This project is the interactive Quest acceptance scene for Termin's native
OpenXR runtime. It exercises the canonical `quest_openxr` profile, strict
runtime-package closure, stereo rendering, head tracking, controller grip
poses, trigger input, thumbstick locomotion and reusable direct grabbing.
The scene also exercises the native game-physics component path: the floor and
table are static colliders, while the three colored blocks are dynamic rigid
bodies that settle on the tabletop under gravity.

The cyan and magenta controller proxies follow the left and right grip poses.
Squeeze either index trigger while its proxy is close to a colored block to
grab it. The original hand-to-object offset is preserved; release the trigger
to return the block to physics from its current world pose. Loss of controller
tracking releases an object immediately as well.

## Prerequisites

Build the desktop SDK after engine changes, then the canonical Android SDK
slice. The Android build owns and installs `libopenxr_loader.so`; the Quest APK
does not compile a private second loader.

```bash
./build-sdk.sh
./build-sdk-android.sh --abi arm64-v8a --platform android-26
```

The local toolchain also needs Android SDK/NDK 27.2.12479018, Gradle 8.x and
ADB. Export the system Android SDK location (it is separate from Termin's
cross-compiled `sdk/android` tree):

```bash
export ANDROID_HOME="$HOME/Android/Sdk"
```

These machine paths belong to Termin settings or command-line overrides, not
to the portable project profile.

## Inspect and build

```bash
./sdk/bin/termin_builder capabilities quest-debug \
  --project test-projects/quest-openxr-showcase --json

./sdk/bin/termin_builder build quest-debug \
  --project test-projects/quest-openxr-showcase
```

The expected artifact is:

```text
test-projects/quest-openxr-showcase/dist/quest/apk/QuestOpenXRShowcase-quest-openxr-debug.apk
```

## Install, launch and logs

Select and record one named Quest device from `adb devices -l` before testing.

```bash
adb install -r \
  test-projects/quest-openxr-showcase/dist/quest/apk/QuestOpenXRShowcase-quest-openxr-debug.apk

adb shell am force-stop org.termin.testprojects.questopenxrshowcase
adb shell monkey -p org.termin.testprojects.questopenxrshowcase 1

adb logcat -c
adb logcat -s TerminOpenXR:I
```

Keep the proximity sensor active while launching; otherwise Quest pauses the
NativeActivity before the OpenXR session reaches the focused state.

## Device acceptance checklist

Record the headset model, Quest OS/runtime version, device serial, APK SHA-256
and filtered logcat together with the result.

1. `stereo/head`: both eyes show the table, three colored blocks, asymmetric
   cyan/magenta landmarks and floor without eye mismatch; head translation and
   rotation are stable; the initial forward direction faces the table.
2. `controllers`: cyan is the left controller and magenta is the right;
   position and orientation follow physical grip poses without swapping,
   mirroring or obvious one-frame jitter. Taking a controller out of tracking
   freezes no object and causes no pose jump on recovery.
3. `grab-left` and `grab-right`: approach each colored block, squeeze the index
   trigger, move and rotate the hand, then release. The block must not snap to
   the controller, must preserve its relative offset while held and must stay
   at the release pose without a discontinuity before gravity resumes. If it is
   released above the table or floor, it must fall and collide. Re-acquire it
   with either hand.
4. `ownership`: while one hand holds a block, the other cannot steal the same
   block. After release it can acquire it normally.
5. `locomotion`: left stick moves in head-yaw-relative X/Y; right stick turns
   continuously. Floor and landmarks make translation, direction and scale
   observable. Motion must not disturb controller-to-object alignment.
6. `runtime-closure`: remain focused for at least 300 frames. Logcat contains
   no missing component/resource/shader, OpenXR action, Vulkan or render-pipeline
   errors. It should report controller action-set initialization/attachment and
   grab/release events.

## Editor view

The scene also has a normal editor camera and texture target; the headset uses
the separate `xr_stereo` target bound explicitly to `XrOrigin`.

```bash
./sdk/bin/termin_editor \
  test-projects/quest-openxr-showcase/QuestOpenXRShowcase.terminproj
```
