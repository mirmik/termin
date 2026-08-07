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
layered RGBA16F + depth, 4x MSAA
  -> MultiviewColorPass (opaque)
  -> MultiviewColorPass (transparent)
  -> MultiviewResolvePass (layered, single-sample)
  -> MultiviewTonemapPass
  -> two-layer OpenXR swapchain
```

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

## Capability and acceptance requirements

The Vulkan device must expose texture arrays, multiview, and at least two
multiview views. The showcase pipeline was accepted on a Quest 2 with distinct,
stable stereo views, 4x MSAA, layered resolve and no observed tile artifacts.
Its source is
`test-projects/quest-openxr-showcase/Pipelines/QuestMultiview.pipeline`.
