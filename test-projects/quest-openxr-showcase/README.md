# Quest OpenXR Showcase

This project is the interactive Quest acceptance scene for Termin's native
OpenXR runtime. It exercises the canonical `quest_openxr` profile, strict
runtime-package closure, stereo rendering, head tracking, controller grip
poses, trigger input, thumbstick locomotion and reusable direct grabbing.
The scene also exercises the native game-physics component path: the floor and
table are static colliders, while the three colored blocks are dynamic rigid
bodies that settle on the tabletop under gravity.

## Quest rendering budget

This showcase targets Quest-class standalone hardware. Dynamic shadows and
bloom are currently too expensive for its normal acceptance configuration and
should remain disabled. Enable either feature only for an explicit profiling or
quality experiment, and record GPU/frame timing before treating that setting as
a new project default.

The headset target uses the explicit `QuestMultiview` graph in
`Pipelines/QuestMultiview.pipeline`: layered opaque and transparent passes,
4x MSAA resolve, and direct layered tonemapping into one two-layer OpenXR
swapchain. The ordinary `Default` pipeline remains attached to the editor
target. Do not substitute it for the headset target; `xr_stereo` deliberately
rejects `single_view` pipelines.

The opaque multiview pass enables the explicit
`attachment_barrier_between_draws` compatibility option. It keeps one render
pass active while ordering framebuffer-local color/depth accesses between
draws, preventing the square tile corruption observed on the tested Quest 2
Adreno driver. Do not remove it without a headset A/B test; do not enable it
globally without evidence that another graph or device needs it.

The floating VR panel is rendered once by `UIWidgetPass` into the ordinary
`VR Panel Texture` target. The headset target exposes that color result to the
multiview graph as the named `PANEL_COLOR` texture, and the panel mesh samples
it like any other material texture. This keeps the UI graph and XR graph
literal: there is no hidden per-eye execution of the mono UI pass.

The right controller also owns a separate pointer entity. It currently follows
the grip pose because the Quest runtime leaves the separate aim action
inactive. Its `XrRayInteractorComponent` projects through the panel's
`WorldUiSurfaceComponent`; the surface maps the hit to the panel document's
physical presentation extent and feeds ordinary native pointer events back to
`UIComponent`. Pull the right index trigger to press the blue button or
toggle the checkbox. The `LineRenderer` ray ends at the panel while it is hit.

The ray is only a visualization of the independently tested pointer path. Its
remaining per-eye rendering defect belongs to the general `LineRenderer`
material/multiview work and does not affect panel hit testing or input.

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
7. `multiview-contract`: startup logs identify `QuestMultiview`; one layered
   color swapchain is created, both eyes remain distinct and stable, and no
   multiview capability, external texture state, or mono-pipeline rejection is
   reported.
8. `tile-integrity`: with 4x MSAA enabled, move the head and controllers around
   high-contrast object edges for at least one minute. No screen-aligned square
   or stair-step regions containing nearby object colors may appear in either
   eye.
9. `vr-panel`: the floating panel is visible in both eyes and shows its text,
   blue button and checkbox. It must not appear as a flat white/black surface or
   sample the headset swapchain in place of the panel texture.
10. `vr-panel-input`: the right-controller pointer follows the explicitly
    selected grip pose (the current Quest runtime leaves the separate aim action
    inactive), reaches the panel, and produces visible hover/pressed feedback.
    Trigger DOWN/UP on the checkbox toggles it; moving away or losing tracking
    cancels capture without leaving a widget pressed.

## Editor view

The scene also has a normal editor camera and texture target; the headset uses
the separate `xr_stereo` target bound explicitly to `XrOrigin`.

```bash
./sdk/bin/termin_editor \
  test-projects/quest-openxr-showcase/QuestOpenXRShowcase.terminproj
```
