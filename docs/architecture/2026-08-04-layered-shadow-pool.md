# Backend-neutral Layered Shadow Pool

Date: 2026-08-04.

Status: proposed target architecture; not implemented.

Related work:

- Kanboard #1260 `[web/shaders] Make strict PBR and shadow package export pass WGSL validation`;
- [shader resource contracts](../../termin-graphics/docs/architecture/shader-resource-contracts.md);
- [backend-neutral MRT contract](2026-07-28-backend-neutral-mrt-contract.md).

## Context

The standard lighting shader currently declares:

```slang
Sampler2DShadow shadow_maps[MAX_SHADOW_MAPS];
```

At runtime, `ShadowMapArrayResource` is likewise a vector of independent
`TextureHandle` values. Despite its name, it does not own one GPU array
texture. The material pipeline binds every entry as a separate texture-array
binding.

This representation is not a portable baseline for the engine:

- WGSL does not allow ordinary arrays of texture or sampler handle types;
- WebGPU binding arrays require optional capabilities and are not the same as
  a sampled `texture_depth_2d_array`;
- sixteen shadow textures plus material textures put pressure on portable
  per-stage binding limits;
- every backend must legalize the same logical resource list differently;
- the current model prevents the framegraph and renderer from expressing that
  all equal-shaped shadow maps are layers of one owned resource.

The WGSL failure in #1260 exposes the mismatch, but the solution belongs to the
common graphics and renderer model rather than to the WebGPU backend.

## Decision

Termin will represent equal-shaped 2D shadow maps as layers of a
backend-neutral texture array owned by a renderer-level shadow pool.

```text
lights and cascades
        |
        v
ShadowPool allocation table
        |
        +--> layer view 0 -- ShadowPass attachment
        +--> layer view 1 -- ShadowPass attachment
        +--> layer view N -- ShadowPass attachment
        |
        v
whole-array sampled view -- lighting/PBR pass
```

There are three distinct concepts:

1. `tgfx2` owns general array textures and subresource views. These APIs are
   not shadow-specific.
2. `termin-render` owns `ShadowPool`, layer allocation, shadow metadata and
   framegraph integration.
3. Shaders consume a single depth-array resource plus a comparison sampler for
   one lighting batch. They do not consume a binding array of independent
   textures.

Scene components describe shadow intent and quality. They never expose WebGPU,
Vulkan, D3D11 or OpenGL resource types and do not retain texture layers.

## tgfx2 Resource Contract

`TextureDesc` must gain an explicit array-layer count. A value of one preserves
the existing 2D texture behavior.

```cpp
struct TextureDesc {
    uint32_t width;
    uint32_t height;
    uint32_t mip_levels;
    uint32_t array_layers = 1;
    uint32_t sample_count;
    PixelFormat format;
    TextureUsage usage;
};
```

Subresources are addressed through an explicit view descriptor and an owned
device-local handle:

```cpp
enum class TextureAspect { All, Color, Depth, Stencil };
enum class TextureViewDimension { D2, D2Array, Cube, CubeArray };

struct TextureViewDesc {
    TextureViewDimension dimension;
    TextureAspect aspect;
    uint32_t base_mip_level = 0;
    uint32_t mip_level_count = 1;
    uint32_t base_array_layer = 0;
    uint32_t array_layer_count = 1;
};
```

The exact public spelling may change during implementation, but the semantic
split is mandatory:

- `TextureHandle` identifies storage and owns width, height, format, mip count
  and layer count;
- `TextureViewHandle` identifies a validated range and interpretation of that
  storage;
- render-pass attachments consume a single-layer view;
- sampled bindings consume a compatible whole-array view;
- destroying a texture invalidates its views; views never own native storage.

The device validates ranges, aspects, formats, usage flags and view dimensions
when creating a view. Backend code must not silently clamp invalid ranges.

The portable capability contract must report at least:

- maximum 2D array layer count;
- support for sampling a depth 2D array with comparison;
- supported depth formats for both attachment and sampled usage.

Pool capacity is bounded by the minimum of the engine policy and reported
backend capabilities. Failure to allocate a required layer is diagnosed; it
must not silently bind an unrelated fallback shadow.

## ShadowPool Contract

A pool contains one physical array texture, its whole-array sampled view, and
single-layer attachment views. Compatible allocations share this key:

```text
ShadowPoolKey =
    projection family (2D)
    + width and height
    + depth format
    + sample count
    + sampling/filter policy
```

An allocation is renderer-owned transient identity:

```text
ShadowAllocation = pool identity + layer + generation
```

The generation prevents stale allocations from referring to a layer that was
reassigned after a pool rebuild. Lights keep shadow settings and receive
allocation results during render preparation; they do not own allocations
across renderer or device lifetime.

The pool storage is persistent across frames. Its allocation table may be
rebuilt per pipeline execution when visible shadow casters, cascade counts or
quality settings change. Stable input should produce stable layer assignment
to avoid needless cache churn and capture noise.

Each shadow metadata record contains at least:

- light-space matrix;
- source light index;
- cascade index and split range;
- texture-array layer;
- validity flags required by the sampling contract.

`MAX_SHADOW_MAPS` may remain a portable upper bound for metadata records in the
first implementation. It no longer means an equal number of texture bindings.

## Pool Selection and Batching

The baseline lighting pass binds exactly one 2D shadow pool. Directional-light
cascades and spot-light shadows that share its key occupy separate layers.

The renderer may maintain multiple pools when resolution or format policies
differ, but it must not expose them by creating an unbounded array of array
textures. A lighting implementation that needs multiple pools must choose an
explicit portable policy, such as separate lighting batches or a small fixed
set of declared pool slots with capability validation.

The initial migration should use one standard resolution and depth format for
the forward PBR lighting batch. Variable-resolution pools are an extension,
not a prerequisite for restoring the standard lit web scene.

Point-light shadows are not part of the initial 2D-array contract. Their
portable representation must be decided separately between cube arrays and an
explicit six-layer 2D layout. The 2D pool must not pretend that a point-light
shadow is natively a `texture_depth_cube_array`.

## Shader ABI

The standard 2D shadow resource becomes one depth-array texture and one
comparison sampler. Conceptually:

```slang
Texture2DArray<float> shadow_maps;
SamplerComparisonState shadow_sampler;
```

Shadow sampling selects `metadata.texture_array_layer`; it does not select a
resource binding. The generated target representation is backend-specific, but
the shader contract is not:

| Backend | Storage and views | Shader-facing resource |
|---|---|---|
| WebGPU | 2D depth texture with `depthOrArrayLayers`; per-layer and array views | WGSL `texture_depth_2d_array` + `sampler_comparison` |
| Vulkan | 2D array `VkImage`; 2D attachment views and 2D-array sampled view | sampled depth `VK_IMAGE_VIEW_TYPE_2D_ARRAY` |
| D3D11 | `Texture2DArray`; per-slice DSV and array SRV | `Texture2DArray<float>` + comparison sampler |
| OpenGL | `GL_TEXTURE_2D_ARRAY`; `glFramebufferTextureLayer` for writes | `sampler2DArrayShadow` |

Shader reflection and the backend binding plan describe one texture resource
and one sampler resource. No backend is allowed to reinterpret the ABI as
sixteen independent bindings merely because the old source used
`Sampler2DShadow[MAX_SHADOW_MAPS]`.

## Framegraph and Synchronization

The framegraph resource is the shadow pool texture. Shadow passes write
single-layer views and the lighting pass reads the whole-array view.

The first implementation may synchronize conservatively at whole-texture
granularity, provided dependency ordering remains correct. View identity must
still be preserved in render-pass descriptors so a shadow pass writes only its
allocated layer. Later subresource-aware scheduling can reduce false hazards
without changing the public resource model.

The current `ShadowArrayMap` side channel and `ShadowMapArrayResource::entries`
vector are migration mechanisms, not the target ownership boundary. The target
framegraph value carries or resolves a `ShadowPool` resource, while allocation
metadata remains renderer-owned.

## Migration Plan

1. Add array-layer descriptors, texture views, capabilities and validation to
   tgfx2 without changing existing single-layer callers.
2. Implement the same view semantics in WebGPU, Vulkan, D3D11 and OpenGL, with
   backend-independent creation and attachment tests.
3. Introduce renderer-owned `ShadowPool` and allocate directional cascades and
   spot shadows into its layers.
4. Change render-pass depth attachments to accept layer views and bind the
   whole-array sampled view in the color/lighting pass.
5. Replace the standard shader ABI binding array with one depth-array texture,
   one comparison sampler and layer indices in shadow metadata.
6. Remove per-element `bind_texture_array_element` handling for the standard
   `shadow_maps` ABI resource and retire the misleading vector-based
   `ShadowMapArrayResource` representation.
7. Make #1260's strict PBR/shadow fixture validate through pinned Naga and render
   in the browser using the normal package and pipeline.
8. Run the built-in shader audit and cross-backend shadow smokes before deleting
   old source and binding compatibility paths.

The migration is intentionally forward-only. A WebGPU-only source rewrite or
an implicit fallback to unshadowed PBR is not completion of this contract.

## Verification

The common smoke scene contains:

- one directional light with multiple cascades;
- one spot light;
- at least one standard PBR object receiving both shadows;
- enough metadata checks to prove that each shadow samples its assigned layer.

It verifies:

- per-layer depth rendering does not overwrite sibling layers;
- the whole-array sampled view observes every written layer;
- comparison sampling and layer selection agree across backends;
- invalid view ranges and exhausted pool capacity produce error diagnostics;
- resize, pipeline rebuild and device teardown do not leave stale views;
- strict WebGPU package export passes pinned Naga;
- WebGPU, Vulkan, D3D11 and OpenGL implement the same logical scenario.

Point-light coverage is added with its separate representation decision.
