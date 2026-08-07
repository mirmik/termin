# Quest OpenXR render-path alignment

Date: 2026-08-06

Status: architecture accepted and implemented; Quest device acceptance pending.

The resulting contract is documented in
`docs/architecture/xr-multiview-rendering.md`. The implementation replaces the
two independent eye executions described below with one explicit, layered
`xr_multiview` graph. The sections describing the old path are retained as the
investigation record.

## Motivation

The investigation of intermittent square artifacts on Quest 2 showed that the
showcase is not merely exercising an ordinary Vulkan renderer on another
display. Its current OpenXR path combines several unusual choices that mature
Quest integrations commonly avoid. Any one of them can be valid with complete
synchronization and layout management, but their combination leaves Termin on
a lightly tested path through the Adreno tiled renderer.

The artifact investigation is documented in
`docs/analysis/2026-08-06-quest-adreno-tile-artifacts.md`. Ending and reopening
the opaque render pass between draws suppressed the artifact, but that
diagnostic workaround was rejected and removed. The purpose of this document
is to identify the larger architectural differences worth addressing instead.

## Current stereo path

The current runtime creates one independent color swapchain per view. It also
creates one engine-owned `D32F` depth texture and shares that same image between
both eyes:

- `termin-openxr/src/openxr_android_runtime_smoke.cpp`, color swapchains around
  lines 1196--1239;
- the single depth texture around lines 1241--1249.

For each XR frame the runtime opens one `RenderContext2` frame, then executes
the complete scene/framegraph once for the left eye and once for the right eye.
Both executions are recorded before the single `end_frame()` submission.

Before each eye, the runtime forcibly changes the tracked layout of both the
acquired color image and the shared depth image to
`VK_IMAGE_LAYOUT_UNDEFINED`. This is CPU-side layout bookkeeping, not a
completion dependency between the previous eye's depth writes and reuse of the
same image by the next eye.

The effective structure is:

```text
begin Vulkan frame / command stream

left eye:
    mark external color-left and shared-depth undefined
    execute complete framegraph

right eye:
    mark external color-right and the same shared-depth undefined
    execute complete framegraph

submit both eyes
release both OpenXR swapchain images
```

This deserves priority in the next investigation. Reusing one depth attachment
for two eye executions whose commands have not yet been submitted is a more
specific explanation for eye-dependent tile corruption than materials or
mesh sharing. Declaring the old layout undefined permits contents to be
discarded; it must not be treated as a substitute for a correctly scoped
execution and memory dependency.

## Final transfer into the XR image

The general framegraph renders through intermediate resources. Its
`PresentToScreenPass` then calls the generic `RenderContext2::blit`, which maps
to `VulkanCommandList::copy_texture`.

The current generic copy operation finishes by putting both source and
destination into `VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL`. That default is
convenient for ordinary engine textures that will be sampled next, but the
destination here is an external OpenXR color swapchain image.

For a Vulkan OpenXR session, after `xrWaitSwapchainImage` the runtime guarantees
a color image layout compatible with `VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL`.
At `xrReleaseSwapchainImage` the application is responsible for returning the
image to a compatible color-attachment layout and queue ownership. Releasing
the image in an incompatible layout permits undefined runtime behavior:

<https://registry.khronos.org/OpenXR/specs/1.1/man/html/XR_KHR_vulkan_enable-swapchain-image-state.html>

A diagnostic change restored the external image's caller-owned layout after
the transfer, but the visible artifact still occurred. Therefore this is a
real contract problem to fix, not a proven complete explanation of the tile
artifact.

## Submission and release contract

After recording both eyes, the runtime submits the shared command stream and
immediately calls `xrReleaseSwapchainImage` for each acquired swapchain. The
intended ordering relies on the OpenXR runtime and the Vulkan queue supplied in
the graphics binding. Termin does not currently express a named completion
contract at the release site.

The OpenXR specification says that release occurs once the application is done
submitting commands that reference the image, while the Vulkan graphics
binding also gives the runtime access to the application-provided queue and
requires external synchronization of that queue. This does not justify adding
an unconditional `vkDeviceWaitIdle`; it does mean that ownership, queue access,
submission ordering and any required fence must be explicit in Termin's
abstraction rather than accidental properties of the current smoke loop.

The separate Vulkan follow-up list is in
`docs/analysis/2026-08-06-quest-vulkan-followups.md`.

## Framegraph reuse between eyes

Each eye runs the normal multi-pass framegraph independently. Intermediate
targets, canonical resource aliases and cached layout state are reused across
the two executions inside one recording frame. This is legal only if every
inter-eye hazard is represented correctly. It is substantially less common
than rendering both views as layers of one multiview pass and expands the
number of layout transitions, transfers and alias boundaries exercised per XR
frame.

This also explains why generic engine facilities can behave differently on
Quest even when the scene itself is small. The interesting workload is not the
number of cubes; it is two complete, stateful framegraph executions sharing
backend resources before submission on a tile-based GPU.

## Relation to draw calls and instancing

Rendering the cubes through instancing could suppress the observed problem by
reducing descriptor changes, dynamic UBO slices, buffer binds and draw
boundaries. It would also be a normal performance improvement for repeated
geometry.

However, disappearance under instancing would not identify the root cause:
instancing changes command count, state transitions, scheduling and timing at
once. Giving every draw a private copy of the mesh would test a different
hypothesis—incorrect sharing or caching of vertex/index buffers—but that is
less consistent with screen-aligned tile blocks and the successful STORE/LOAD
experiment.

A useful controlled matrix is:

1. one shared mesh, several direct draws;
2. independent mesh buffers, several otherwise identical direct draws;
3. one shared mesh and one instanced draw;
4. multi-draw indirect, if the direct-versus-instanced result warrants it.

This should follow the more direct per-eye depth test rather than precede it.

## Conventional target architecture

The preferred direction is a deliberate OpenXR renderer rather than a series
of special cases around the desktop framegraph:

1. Create a two-layer color swapchain, or otherwise model both views as layers
   of one stereo render target when supported by the runtime.
2. Use Vulkan native multiview so a scene draw is broadcast to both view
   layers. Khronos describes native multiview as the industry-standard
   high-performance OpenXR stereo path:
   <https://docs.vulkan.org/tutorial/latest/OpenXR_Vulkan_Spatial_Computing/08_Slang_Spatial_Shaders/02_native_multiview.html>.
3. Provide matching independent depth layers. Never reuse one mutable depth
   image between eyes without an explicit dependency and a measured reason.
4. Model external image initial/final layout and queue ownership as part of the
   render-target contract. Generic `copy_texture` policy must not choose an XR
   image's release state.
5. Prefer rendering the final framegraph result directly into the XR target
   when compatible. If an intermediate and transfer are required, represent
   the transfer and final external layout explicitly.
6. Define submission completion and `xrReleaseSwapchainImage` ordering in the
   OpenXR backend contract.
7. Add instancing/batching independently as a normal scene-rendering
   optimization, not as the correctness fix for this artifact.

## Recommended next tests

Before a larger multiview migration, run small binary tests in this order:

1. Allocate one depth image per eye, preserve truthful layouts, and change
   nothing else.
2. Restore each XR color image to `COLOR_ATTACHMENT_OPTIMAL` immediately before
   release and assert its tracked state.
3. Make the submission/release contract explicit and verify it with Vulkan
   synchronization validation.
4. Disable framegraph physical aliasing for the XR target without changing pass
   structure.
5. Compare separate direct draws with one instanced cube draw.
6. Prototype a two-layer multiview color/depth target.

For every test, keep rolling capture disabled during the visual A/B: continuous
capture previously changed timing enough to suppress the artifact. Record
device/runtime versions, both-eye behavior, frame timing and whether the
artifact survives repeated fresh launches.

## Completion criterion

This analysis is resolved when the Quest path has a documented stereo target
contract, independent per-view depth storage, specification-compliant external
image transitions and explicit submission/release ordering; and when a
multiview decision has been implemented or rejected with device measurements.
