# Adaptive Native UI Regression Matrix

The adaptive native UI contract is guarded by the central test runner and by
named platform scenarios. The automated reference is the real
`android-render-showcase` HUD, not a separately maintained copy.

## Automated Linux and Windows coverage

Run the matrix through the repository entry point:

```bash
task test --
```

The relevant CTest registrations are:

- `termin_gui_native_adaptive_layout_matrix_test` loads
  `UI/native_runtime_hud.uiscript` and checks density `1.0`, `1.5`, `2.0`, and
  `3.0`; font scale `1.0`, `1.3`, and `1.5`; compact, medium, expanded,
  portrait, and landscape logical viewports; physical safe insets; minimum
  touch targets; retained button state; and physical-to-logical hit testing.
  Failures include the case name, density, font scale, viewport, and failed
  widget contract.
- `termin_gui_native_renderer_pixel_smoke` checks pixel rounding, clips, text,
  and logical geometry at the same density scale set.
- `termin_gui_native_widgets_test` covers Box/Grid/Scroll/Wrap constrained
  reflow, wrapped text, font-driven remeasure, and scroll content extent.
- `termin_gui_native_uiscript_test` covers responsive boundary selection,
  tree/state preservation, grid overrides, and malformed declarations.
- `termin_gui_native_window_adapter_test` is the backend-neutral desktop
  `2.0 -> 1.5 -> 1.0` runtime display-scale test. It must run on Windows as
  part of the central suite; a live Windows pass additionally moves the same
  window between monitors with different DPI and confirms stable logical
  geometry and pointer targeting.

## Android device gate

Use the scenarios under “Native UI emulator/device gates” in
`test-projects/android-render-showcase/README.md`.
Record the device model, physical extent, density, font scale, safe-inset mode,
portrait and landscape captures, frame count, and filtered logcat.

Reference device evidence:

- Samsung SM-A546E: 1080 by 2340, density 2.812, font scale 1.1; portrait,
  landscape, safe insets, button/camera input separation, and runtime package
  closure passed. Reference captures live beside the showcase README.
- OnePlus 5 / Android 10: 1080 by 1920, 420 dpi, font scale 1.0; forced
  portrait -> landscape -> portrait reflow, state restoration, scene/HUD
  composition, and sustained runtime passed without native UI, shader,
  Vulkan, stale-resource, or Android runtime errors.

For devices that ignore the raw `user_rotation` setting, use WindowManager's
explicit override and always restore the original automatic mode:

```bash
adb shell wm set-fix-to-user-rotation enabled
adb shell wm set-user-rotation lock 1
# capture the settled landscape frame
adb shell wm set-user-rotation lock 0
adb shell wm set-fix-to-user-rotation disabled
adb shell wm set-user-rotation free
```

The task is not a complete cross-platform gate until both the Android run and
the named Windows central/live-DPI scenario have been recorded on their target
platforms. A skipped platform must remain visible rather than being treated as
a pass.
