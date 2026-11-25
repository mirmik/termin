# Termin Az/Z positioner in Avalonia

This .NET 8 / Avalonia 11.3.9 sample models the AntennaBench positioning preview.
An amber platform rotates about world +Z and a blue carriage moves along its
parent's local +Z. The carriage keeps its horizontal offset from the turntable
axis, so it also inherits the turn. The sliders set azimuth in degrees and lift
in meters. Drag to orbit, scroll to zoom, or start the 33 ms scan.

## Run against the installed SDK

Use an SDK from this checkout with the full C# profile and built-in shader
artifacts. Use Windows x64 with D3D11 or Linux x64 with Vulkan. The sample build
also needs .NET 8, CMake, Python 3.10+, and the platform C++ toolchain.

| Platform | SDK build |
| --- | --- |
| Windows | `task build -- --sdl --no-vulkan --no-opengl` |
| Linux | `task build -- --vulkan --no-opengl` |

Run from the repository root in a desktop session.

```sh
task smoke:avalonia-positioner -- --interactive
task smoke:avalonia-positioner
```

For unattended Linux runs use
`xvfb-run -a task smoke:avalonia-positioner`. Pass
`--capture-dir <directory>` after `--` to save the pixel checkpoints.
Use `--sdk-root <directory>` to select another full SDK installation.
On Windows the smoke can be built under SSH with `--build-only` and started in
the interactive desktop with `--run-only`.

## Embedding contract

- Build the mesh and material once and attach them through `MeshComponent` and
  `MeshRenderer` on a Termin `Scene`. Parent the carriage under azimuth with
  `Entity.SetParent`. Apply scan samples as a local Z-axis quaternion on the
  turntable and a local Z translation on the carriage. Update world transforms
  before rendering. Keep the orbit camera separate from the scan hierarchy.
- The scene renders through a viewport and a pipeline with an explicit
  `DisplayLinear` color export. The pipeline uses the target's RGBA16F format
  through `ResourceSpec.set_format("render_target")`. D3D11 requires matching
  formats for this copy.
- The sample's small native bridge creates an offscreen display on the active
  device and reads the composed frame. It submits the display composite before
  readback on Vulkan, converts linear RGB to sRGB, and writes opaque BGRA8888
  into the caller's buffer in top-to-bottom row order. The Avalonia host locks a
  `WriteableBitmap`, supplies its native pointer and row stride, unlocks it and
  invalidates the `Image`.
- Render and resize on the UI thread in this sample. Size both the output and
  bitmap in physical pixels. Unregister the display and free its viewport,
  target and pipeline before releasing the graphics host. The sample owns the
  full process runtime and shuts it down when closing the viewport. An app
  sharing the runtime should own its initialization and shutdown at app scope.

The development runner loads the full managed binding and matching native
libraries, shader resources and font from an installed SDK. The published
Windows plot package covers the `plot-d3d11` profile. The supported offscreen
C/C# API is tracked in #3910 and the app-local full runtime for both RIDs is
tracked in #3911.

## Smoke evidence

The smoke checks the carriage's world position and the pixels rendered by
Avalonia after a 90° parent turn, a 1 m lift and a camera orbit. It also checks
resize and closing and reopening the window. The scan measures the UI-thread
time to render, copy and update the bitmap for 32 frames with a 33 ms scheduling
interval at 686 × 556 pixels.

| Environment | p50 | p95 |
| --- | ---: | ---: |
| Linux x64, Vulkan llvmpipe, Xvfb | 3.60 ms | 3.92 ms |
| Windows x64, D3D11, VirtIO VM | 6.81 ms | 7.71 ms |

These measurements cover the sample geometry and viewport size. Avalonia
compositor latency and performance on the deployment hardware require separate
measurements with the actual AntennaBench scene.
