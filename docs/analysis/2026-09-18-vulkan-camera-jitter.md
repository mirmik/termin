# Vulkan editor camera jitter investigation

Tracking: Kanboard #2438. Status: localized to the XWayland Vulkan FIFO path
on this machine; native Wayland removes the symptom. The SDK now prefers the
native Wayland connection when available; rebuilt-SDK verification is recorded
below.

## Observations

- Recording: `/home/mirmik/Видео/Screencast_20260918_202048.mp4`, approximately
  15 seconds, 2560×1440, nominal 120 FPS, variable frame timestamps.
- User reports jitter during pan/orbit and possibly zoom in PhysicsTest.
- User's same-machine comparison: Vulkan jitters, OpenGL does not. Moving
  desktop windows, including the editor window, does not jitter.
- Follow-up A/B/A test: Vulkan VSync was enabled; disabling it removed the
  jumps, and enabling it again restored them. This establishes a repeatable
  dependency on synchronized presentation, not yet the exact faulty layer.
- Consecutive-frame optical flow of the scene shows repeated forward jumps
  followed immediately by backward movement. One rounded horizontal sequence
  is `+7, +7, +35, -19, +6` pixels. This is more than uneven frame pacing.
- The recording rules out a defect confined to the physical monitor. It does
  not distinguish application rendering from presentation/compositor behavior.

## Controlled GPU snapshots

Used a temporary copy of `tests/fixtures/windows-d3d11-scene` in an isolated
MCP editor on NVIDIA GeForce RTX 5090, with Vulkan synchronization validation
enabled (`TGFX2_GPU_VALIDATION_REQUIRED=1`). Despite its historical filename,
the scene works with the Vulkan editor.

Two runs: 80 headless frames, then 40 windowed frames. The windowed framebuffer
was 2560×1358. Sent a pan button press at viewport center, then monotonically
increasing pointer X by 2 pixels per iteration. Each iteration:

1. Dispatch pointer move and update editor camera.
2. Record the camera's global position.
3. `native_viewport.rendering_manager.render_all(True)`.
4. In a separate context frame, `blit(display.color_tex, snapshots[i])` into
   a unique RGBA16F GPU texture.
5. Render the editor GUI, including presentation in the windowed run.

Only after recording the entire sequence did the test wait for the GPU and
read snapshots back. There was no synchronous readback between frames.

Results:

| Run | Camera position increments | Median feature X displacement per frame |
| --- | --- | --- |
| Headless, 80 frames | Constant `(0.01630449, 0.00961620, -0.00013716)` | approximately +1.88…+2.00 px |
| Windowed, 40 frames | Constant `(0.00648635, 0.00382558, -0.00005456)` | approximately +1.98…+2.00 px |

No backward steps in either run; no GPU validation errors reported.
This checks the viewport texture before final window composition, **not the
images actually displayed by the compositor**. The test also changes timing,
uses a simpler scene and synthetic input, and runs with validation enabled;
it cannot exonerate all scene rendering or input paths.

Temporary scripts/data/logs are under `/tmp/termin-jitter/`: `analyze.py`,
`motion.csv`, `record-loop.py`, `record-window.py`, `readback.py`,
`readback-window.py`, `poses.npy`, `window-poses.npy`, `gpu-*.npy`,
`window-gpu-*.npy`, and `editor-{validation,window}.log`.
These are diagnostic artifacts, not a permanent regression suite.

An earlier attempt to collect snapshots in a pre-render callback terminated
the isolated test editor with SIGSEGV. Its cause was not diagnosed and is not
evidence for the original jitter. The explicit-loop recordings above completed.

## Code audit

- Editor VSync selects `PresentationMode::VSync` at window construction;
  `pick_present_mode()` maps it strictly to `VK_PRESENT_MODE_FIFO_KHR`.
  Disabling VSync selects `VK_PRESENT_MODE_IMMEDIATE_KHR`. This setting does
  not alter camera math. Editor settings apply this choice after restart.
- FIFO is specified to append presentation requests at the tail and consume
  them from the head at vertical blanking; reversed frames are not normal
  FIFO behavior. See the [Khronos present-mode reference](https://docs.vulkan.org/refpages/latest/refpages/source/VkPresentModeKHR.html).
- `OrbitCameraPan` holds the initial view/projection/target and computes pan
  from a fixed anchor. It does not feed the previous pan result back into the
  next calculation.
- Ordinary SDL motion uses queued event coordinates; routing to the captured
  camera controller did not reveal a duplicate or stale-coordinate path.
- Camera transform and cached last pose update together. No alternating
  camera-state buffer was found.
- Scene, UI and presentation textures are reused, but the inspected Vulkan
  paths contain read/write layout barriers and use the same graphics queue.
  Reuse alone is not proof of a race.
- Main scene/grid camera uniforms use the fenced frame ring.
- Persistent mapped LightingUBO and SkyboxPass parameters remain separate
  lifetime concerns already tracked in #2246; concrete consumers were added
  there. Their connection to this jitter is unproven.

## Investigation plan before the presentation reproduction

1. FIFO/VSync versus Immediate A/B/A is now complete: only FIFO jitters.
   Preserve this exact comparison for subsequent reproductions.
2. Log input sequence and camera pose while reproducing the actual drag.
3. Add matching frame serials to scene and final UI output, and record the
   actual displayed output. Find the first stage where serials/poses reverse.
4. If GPU snapshots remain ordered while displayed frames reverse, compare
   SDL X11/Wayland presentation under the same device/driver/settings.

Do not use a per-frame `wait_idle()` as a fix. It can hide a lifetime bug and
changes queue timing. The final fix needs a reproduction at the responsible
layer and a regression test.

## Environment and interpretation after VSync comparison

The session environment identifies Wayland (`XDG_SESSION_TYPE=wayland`), with
both Wayland and X11 display endpoints available. At this stage the actual SDL
video driver had not been queried; the desktop session alone does not establish
native Wayland versus XWayland. `/proc/driver/nvidia/version`
reports NVIDIA open kernel module 595.84. No global graphics settings were
changed during this investigation.

Immediate mode is a user-verified workaround, not a root-cause fix. Its timing
also differs from FIFO, so a race exposed by FIFO remains possible. A FIFO
presentation/driver/compositor defect was the leading hypothesis at this stage.
Generic reports of NVIDIA FIFO stutter on other systems do not establish that
this is the same issue; in particular Windows/DXGI reports are not evidence
for this Linux case.

## Isolated presentation reproduction and correction

The actual default SDL driver was queried inside a running probe:
`SDL_GetCurrentVideoDriver()` returned `x11`. The desktop is KWin 5.27.11 on
Wayland, so this connects through XWayland. Selecting `SDL_VIDEODRIVER=wayland`
successfully initialized the native Wayland driver.

The user's editor settings also revealed `fpsLimit=0`. Earlier controlled
editor runs had used the default 60 FPS limit, an important reproduction
difference.

A separate Python presentation probe prepared 256 immutable images before
the measurement. Each image contains an 8-bit black/white serial, its bitwise
complement, and a moving bar. After startup there are no scene/camera updates
or texture uploads, only `BackendWindow.present(textures[serial % 256])`.
This still exercises the production output transform and Vulkan swapchain.

FFmpeg X11 window capture at 120 FPS produced:

| XWayland mode | Software FPS limit | Captured samples | Valid barcode samples | Backward transitions |
| --- | --- | --- | --- | --- |
| FIFO | 60 | 719 | 719 | 0 |
| FIFO | unlimited | 959 | 958 | 137 |
| IMMEDIATE | unlimited | 959 | 956 | 0 |

Complement rows reject incomplete/mixed captures. Signed modulo-256
differences handle serial wrap; adjacent captures more than 20 ms apart are
excluded from transition counts. In the FIFO reproduction, typical changes
were `+1, -3, +5`; measured presentation rate was about 120.3 FPS. The immediate
control ran around 4250 FPS, still with zero backward transitions among the
qualified samples. This captures the X11 window's published content, not
physical scanout, and does not establish which driver/compositor component
is responsible internally.

Finally, a temporary copy of the user's **PhysicsTest** scene was opened with
native Wayland, Vulkan, VSync enabled, and unlimited FPS. The user exercised
pan/orbit and confirmed twice that the jitter was absent. The original project
and global desktop settings were not changed.

Correction in `SDLWindowSystem`: before SDL video initialization, prefer
`wayland,x11` at default hint priority when `WAYLAND_DISPLAY` is nonempty and
no video-driver hint is already set. Explicit `SDL_VIDEODRIVER`, host hints,
and already initialized SDL remain authoritative. X11 remains available when
native Wayland cannot initialize. The selected SDL driver is now logged.
This avoids the failing XWayland path without disabling VSync, changing camera
math, or adding GPU waits. It does not claim to repair XWayland/NVIDIA internals.

The reusable diagnostic is now available through the public task interface:

```bash
TERMIN_BACKEND=vulkan SDL_VIDEODRIVER=x11 task smoke:present-order -- \
  --mode vsync --seconds 15 --fps 0 --output /tmp/termin-present-fifo
```

Repeat with `--mode immediate` or `SDL_VIDEODRIVER=wayland`. The task reports
the actual SDL driver and applied presentation mode, and optionally writes a
CSV of submission times and a `.ready` JSON startup marker. It does not capture
or assert displayed order automatically. Barcode geometry and modulo decoding
limits are documented in `--help`. The immutable images use about 313 MiB.

## Rebuilt-SDK verification

- `task build` completed successfully, including isolated SDK launcher/import
  verification.
- With no `SDL_VIDEODRIVER` override, the Vulkan FIFO probe logged `wayland`
  and presented 240 frames in two seconds. Explicit `SDL_VIDEODRIVER=x11`
  still selected X11 and completed successfully.
- The permanent `task smoke:present-order` passed its help check, X11 Vulkan
  run, and native Wayland OpenGL run (120 frames in two seconds at 60 FPS).
- The rebuilt editor opened the isolated PhysicsTest copy without a driver
  override, logged `wayland`, loaded the scene, entered its unlimited-FPS
  loop with VSync enabled, and shut down cleanly. Visual acceptance is the
  user's earlier manual confirmation on the same native Wayland path.
- `task test:cpp -- --full` exercised 273 tests with three failures:
  offscreen window-manager event-count assertion (#2440), the already known
  NVIDIA OpenGL 3.3 interface-link check (#2253), and missing profiler UI font
  (#2441). Vulkan window/swapchain and both presentation-mode smokes passed.
- A control full run with `SDL_VIDEODRIVER=x11` and `TERMIN_SDK` set repeated
  the first two failures and passed the profiler test. It also exposed a
  separate OpenGL bound-resource smoke failure (#2442), absent in the first
  run. Both full-suite exit statuses were nonzero; these are not claimed as
  green runs. Logs are `/tmp/termin-jitter/tests-cpp{,-x11}.log`.

No per-frame GPU waits or camera changes were introduced. Explicit X11 still
uses the affected presentation path; identifying its internal driver/compositor
defect would require a separate platform investigation.
