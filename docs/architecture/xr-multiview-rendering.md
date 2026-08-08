# Explicit XR multiview rendering

Status: implemented and device-accepted for the Vulkan/OpenXR Quest path.

Termin models XR multiview as a separate, literal render-pipeline contract.
It is not a second interpretation of an ordinary mono graph. A graph declares
one of two execution models:

- `single_view` for the existing render path;
- `xr_multiview` for one invocation that renders two layered views.

An `xr_stereo` render target accepts only an `xr_multiview` pipeline. Socket
types are likewise distinct: `fbo` cannot be connected to `multiview_fbo`, and
the external headset target is an `external_xr_multiview_fbo`. This keeps the
graph's topology equal to the work submitted to the GPU.

## Frame contract

The OpenXR path owns one color swapchain with `arraySize = 2` and
`sampleCount = 1`. Each frame performs one acquire/wait, one graph execution,
one Vulkan submission, and one release. The two projection views reference
layers 0 and 1 of the same swapchain image.

The runtime supplies `StereoRenderViews`, containing ordinary left and right
`RenderCamera` values, to the render target context. Multiview passes require
that value explicitly. The legacy single camera remains populated only for
code that needs a representative position, such as transparent sorting.

External textures enter and leave the engine through an explicit access
contract. OpenXR declares the state after `xrWaitSwapchainImage` and the state
required before `xrReleaseSwapchainImage`; client code does not edit Vulkan's
tracked layout directly.

Named texture parameters on a render target remain part of the common pipeline
contract. Context providers for special targets, including `xr_stereo`, create
their platform-owned bindings first; the engine then resolves the target's
`pipeline_params` into those newly-created contexts without replacing provider
bindings. This lets an XR graph consume ordinary render-target output, such as
an offscreen UI panel, through an explicit named texture socket.

## Pass and resource contract

Layering belongs to texture/resource descriptors through `array_layers`.
Multiview render-pass state belongs to `MultiviewRenderPassDesc` and
`begin_multiview_pass`; it is intentionally absent from the ordinary
`RenderPassDesc` contract. Vulkan derives the view and correlation masks from
the declared view count. Backends without layered multiview support reject the
resource or pass explicitly.

The initial Quest graph is deliberately small:

```text
layered 8-bit UNORM matching the XR target + depth, 4x MSAA
  -> MultiviewColorPass (opaque)
  -> MultiviewColorPass (transparent)
  -> MultiviewResolvePass
  -> two-layer 8-bit UNORM OpenXR swapchain
```

These remain three logical framegraph passes, but they no longer imply three
physical GPU scopes. Adjacent raster passes may publish a
`tc_raster_pass_contract`; the executor groups compatible passes that target
the same canonical attachments and records them inside one backend render
scope. The opaque and transparent multiview passes therefore share one scope.
Their logical order, profiler sections and debugger identities remain intact.
A capture requested at an interior boundary, explicit per-pass synchronization,
or an incompatible load/attachment contract disables grouping for that frame.

An immediately following compatible `MultiviewResolvePass` publishes a
`tc_raster_resolve_contract` and is absorbed as the color attachment's resolve
target. Vulkan uses `pResolveAttachments`, D3D11 resolves after unbinding the
scope, OpenGL uses a framebuffer blit at scope end, and WebGPU uses
`resolveTarget`. If the multisampled color or depth is not read later, its
store operation is `DontCare`; the single-sample resolve remains stored. The
old standalone resolve command remains the ordinary fallback when the graph or
backend contract is incompatible.

Framebuffer clear metadata is also consumed by the first compatible physical
raster scope. In particular, the Quest MSAA color and depth attachments enter
that scope with `LoadOp::Clear`; they are not cleared in a preliminary render
pass and then reopened with `LoadOp::Load`. A resolve target is a complete image
write, so its external color clear is suppressed when that resolve is the
target's first graph access. A preceding read or partial write keeps the
standalone clear. Non-raster resources and incompatible/debug execution paths
retain the standalone clear fallback.

The Quest profile is intentionally an LDR forward path. It has no HDR
intermediate and no tonemap pass: the multisampled attachment inherits the
external target's 8-bit UNORM format, lighting is composed and blended there,
then resolved directly into the format-compatible OpenXR swapchain image. This
trades recoverable HDR highlights and HDR post-processing for lower attachment
storage and memory bandwidth. HDR pipelines remain valid elsewhere and
continue to use an explicit post-composition tonemap pass.

The Quest opaque pass explicitly enables
`attachment_barrier_between_draws`. On the tested Quest 2/Adreno driver this
maps to framebuffer-local color/depth ordering inside the same Vulkan render
pass and prevents tile corruption. It is visible graph configuration rather
than a hidden multiview behavior; the default remains disabled for passes and
platforms that do not need the compatibility ordering.

Shadows, bloom and World2D are outside the first contract. A mono UI pass may
render into an ordinary texture target before the XR target, then the multiview
graph may sample that texture on scene geometry through a named texture socket.
Rendering UI directly into the layered headset target would still require an
explicit multiview pass and typed graph sockets; the runtime must not silently
execute a mono pass once per eye.

## Shader ABI

Material vertex shaders are assembled with a pass-owned multiview output
adapter. `SV_ViewID` selects one of two per-view frame blocks. The two blocks
use the same `RenderCamera`-derived layout as the mono path, so material logic
does not acquire XR-specific camera classes or hidden globals. Tonemapping
samples the corresponding layer from a texture array and writes both external
layers in one multiview render pass.

Procedural scene geometry follows the same boundary. A geometry provider may
produce world-space position, normal and material semantics, but must not
apply a representative camera's projection inside a multiview draw. The
pass-owned output adapter remains the only owner of per-view projection and
`SV_ViewID` selection. The canonical `LineRenderer` therefore uses
view-independent world-space tube geometry; camera-facing and screen-space
line utilities are not material-bearing XR scene renderers. The architectural
decision is recorded in the
[LineRenderer council protocol](../architecture-council/2026-08-07-line-renderer-contract.md).

## Capability and acceptance requirements

The Vulkan device must expose texture arrays, multiview, and at least two
multiview views. The showcase pipeline was accepted on a Quest 2 with distinct,
stable stereo views, 4x MSAA, layered resolve and no observed tile artifacts.
Its source is
`test-projects/quest-openxr-showcase/Pipelines/QuestMultiview.pipeline`.
