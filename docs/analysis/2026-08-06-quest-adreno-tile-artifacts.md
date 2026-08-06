# Quest 2 Vulkan tile-artifact investigation

Date: 2026-08-06

Status: diagnostic workaround reproduced, but intentionally not retained;
underlying driver/engine fault not yet proved.

## Summary

The Quest OpenXR showcase intermittently rendered small, screen-aligned square
or stair-step regions containing color from nearby objects. The corruption was
different in the left and right eye and was transient, but it was present in
captured digital frames. This excludes the headset display matrix, lenses and
binocular perception as the source.

A clean A/B test found that ending and reopening the opaque Vulkan render pass
between every draw suppresses the artifact. Removing those boundaries, without
enabling capture or changing the scene, makes the artifact return. The
experimental `ColorPass.max_draws_per_render_pass` implementation was useful
for localization but was rejected as a production design and reverted.

This result localizes the failure to work whose lifetime crosses draw calls
inside a long render pass on the Quest/Adreno tiled renderer. It does not by
itself prove whether the final cause is an Adreno driver defect, an engine
synchronization/layout error not reported by validation, or marginal hardware.
The unusual stereo and external-image path that may expose such a failure is
analyzed separately in
`docs/analysis/2026-08-06-quest-openxr-render-path.md`.

## Observed symptom

- The defect consists of regular, axis-aligned square groups rather than
  isolated pixels or triangles.
- A group can visually contain color belonging to a nearby object and can move
  between surfaces as objects move.
- Left- and right-eye corruption is not identical.
- The defect is intermittent. A bad region can remain visible for a fraction
  of a second and disappear before a manually triggered capture.
- It was reproduced on the Quest 2 running the native OpenXR Vulkan showcase.
- Core, synchronization, GPU-assisted and best-practices Vulkan validation did
  not report an error explaining the corruption.

Representative investigation frames were captured under the temporary
`test-projects/quest-openxr-showcase/diagnostic-captures/` tree, including:

- `2026-08-06-rolling-capture-1/rolling-trigger-2680-15517199868786/history-000-frame-1971-left.png`
- `2026-08-06-rolling-capture-1/rolling-trigger-2680-15517199868786/history-029-frame-2232-right.png`
- `2026-08-06-rolling-capture-1/rolling-trigger-2680-15517199868786/history-043-frame-2358-left.png`

The complete capture directory was about 289 MiB. It was diagnostic output,
not repository source, and was removed during cleanup.

## Hypotheses tested

### Display panel, optics or binocular fusion

Rejected. Similar defects were visible in exported eye images. Binocular fusion
did explain one false observation about which physical cube carried a defect,
but not the defect itself.

### A particular cube, material or shader

Rejected as the primary cause.

- The blue cube was disabled and artifacts still occurred.
- Controller proxy geometry could be hidden or assigned simple and diagnostic
  PBR materials, with inconsistent correlation to the defect.
- Diagnostic PBR and Cook--Torrance produced byte-identical vertex and fragment
  SPIR-V in the relevant comparison.
- Adding all five material texture bindings to the diagnostic shader did not
  transfer the failure reliably.
- Removing the stale `u_diffuse_mul` material field did not suppress it.

These experiments were useful for excluding material data but their scene and
material edits must not remain in the final patch.

### Dynamic UBO ring and draw transforms

Not supported by the experiments. Moving controller draws influenced where the
artifact was noticed, but a moving PBR draw using a clean material did not
reliably reproduce it. A no-ring diagnostic path did not establish the ring as
the cause. The `enable_ring_ubo` switch added only for that experiment should be
removed.

### Framegraph aliasing and later passes

The framegraph debugger and rolling capture were extended to inspect internal
pass boundaries. Captures showed the problem in application-produced imagery,
but did not isolate it to a particular material or later compositing pass.
Continuous capture also materially changed timing and could suppress the
artifact, so capture-enabled performance or absence-of-artifact results are not
valid controls.

### One long opaque render pass

Supported by the final clean A/B:

1. Rolling capture was disabled before launch.
2. With nine opaque draws and `max_draws_per_render_pass = 1`, eight intermediate
   render-pass boundaries were emitted. Repeated attempts found no visible
   artifacts.
3. The project was rebuilt with `max_draws_per_render_pass = 0`. No other
   experimental condition changed. The artifacts returned.
4. The value was restored to `1` for a final confirmation run, then the
   experimental implementation was removed from the source tree.

Ending the pass stores color and depth attachments from tile-local memory;
reopening it without clears loads them again. The workaround therefore forces
attachment materialization and resets the hardware render-pass lifetime after
each draw.

## Performance cost

Measurements were taken after warm-up at the requested 72 Hz, with rolling
capture disabled.

| Configuration | XR render time | Opaque `ColorPass` per eye | Observed FPS |
| --- | ---: | ---: | ---: |
| Unlimited render pass (`0`) | about 1.75--1.90 ms | about 0.50--0.54 ms | 71.7--71.9 |
| One draw per render pass (`1`) | about 2.06--2.20 ms | about 0.55--0.60 ms | 71.5--71.9 |

The measured cost is approximately 0.3--0.4 ms per stereo XR frame in this
small scene. It does not currently reduce the 72 Hz presentation rate, but it
does consume GPU/bandwidth headroom and will scale poorly with draw count on a
tiled GPU. It is a targeted compatibility switch, not a desirable global
default.

## Code disposition

No rendering or diagnostic code from this investigation was retained. In
particular, cleanup removed:

- The experimental `ColorPass.max_draws_per_render_pass` API and the
  Quest-specific pipeline created to exercise it.
- The OpenXR rolling history, raw-frame dump, capture markers, freeze/resume
  behavior and controller-A capture action.
- The `termin_image` dependency added solely to encode diagnostic PNG files.
- The public active-command-list accessor added solely for the rolling capture.
- Framegraph-capture request extensions used only by that OpenXR experiment,
  unless they are redesigned, wired into the actual network debugger and
  covered by tests as a separate change.
- The `enable_ring_ubo` diagnostic device switch.
- The `PBRNoTextures` shader and all diagnostic material substitutions.
- Disabled shadows, editor-camera serialization noise and diagnostic scene
  geometry changes.
- The bulk `diagnostic-captures` directory after representative evidence has
  been described here.

Independent Vulkan correctness findings were also reverted so they can be
reviewed and applied as focused changes rather than inherited from a chaotic
diagnostic session. They are recorded in
`docs/analysis/2026-08-06-quest-vulkan-followups.md` and on the project board.

### Fix separately

The runtime currently submits rendering and releases OpenXR swapchain images
without an explicit application-side completion object handed to OpenXR. A
diagnostic `wait_idle()` before release is conservative but stalls the entire
graphics queue and did not cure this artifact. Do not hide it inside the tile
workaround. Define a proper per-submission fence/completion contract for the
OpenXR path, test it independently, and then remove the global idle wait.

The Android log also repeatedly reports that the native UI font resolves to a
host SDK path. This is unrelated to the tile corruption but is a genuine
runtime-package closure bug and should be tracked separately.

## Follow-up

The workaround should remain project/platform scoped until it is tested on
more Qualcomm devices. If deeper localization becomes worthwhile, binary-search
the boundary positions or group draws by count and record which exact pair of
adjacent draws requires a break. A driver/vendor report should include the
representative eye frames, device/OS build, Vulkan driver properties and the
minimal `0` versus `1` A/B.
