# Explicit XR multiview rendering

Status: implemented for the Vulkan/OpenXR Quest path; device acceptance is
still required.

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

Shadows, bloom, UI and World2D are outside the first contract. Adding one of
them requires an explicit multiview pass and typed graph sockets; the runtime
must not silently execute a mono pass once per eye.

## Shader ABI

Material vertex shaders are assembled with a pass-owned multiview output
adapter. `SV_ViewID` selects one of two per-view frame blocks. The two blocks
use the same `RenderCamera`-derived layout as the mono path, so material logic
does not acquire XR-specific camera classes or hidden globals. Tonemapping
samples the corresponding layer from a texture array and writes both external
layers in one multiview render pass.

## Capability and acceptance requirements

The Vulkan device must expose texture arrays, multiview, and at least two
multiview views. The remaining acceptance gate is a real Quest run with Vulkan
validation and both-eye visual inspection. The showcase pipeline is
`test-projects/quest-openxr-showcase/Pipelines/QuestMultiview.pipeline`.
