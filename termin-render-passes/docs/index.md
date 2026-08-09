# termin-render-passes

Concrete render pass implementations built on top of `termin-render`.

This module owns reusable pass classes such as presentation, fullscreen effects,
ground grid rendering, and diagnostic passes. Application/editor code should
consume these passes through the public C++ headers under `<termin/render/...>`
or Python package `termin.render_passes`, not compile pass sources from
`termin-app`.

## Color pipeline contract

The built-in default and editor pipelines keep every internal scene and
post-processing color resource in linear `RGBA16F`. Their terminal path is:

```text
linear HDR scene -> bloom -> TonemapPass -> linear UI -> PipelineColorExport(DisplayLinear)
                                                            |
                                                            v
                                                   physical ColorTarget
```

`TonemapPass` owns exposure and the selected tone curve (ACES by default). Its
result is still linear; it never performs gamma or sRGB encoding.
The render executor binds the semantic pipeline export to the caller-owned
physical target. Matching descriptors are bound directly. Format, extent or
sample-count mismatches receive one copy/resolve epilogue; an sRGB target
performs the IEC sRGB transfer at that physical boundary. Scene-linear exports
are not implicitly tonemapped into SDR targets.

`OutputTransformPass` and `PresentToScreenPass` remain available while authored
and external pipelines migrate away from the legacy `OUTPUT` resource. Built-in
default and editor pipelines do not use them.

Scene UI is composited before the pipeline export so scene and UI receive
exactly one encoding step at the eventual display target. UI color literals
therefore participate in the linear compositing contract; wide-gamut and
HDR-display transforms remain separate future work.

## Image-based lighting

The standard Cook--Torrance surface consumer uses split-sum image-based
lighting in addition to explicit scene lights. `EnvironmentLightingPass`
publishes one typed `environment_lighting` framegraph resource containing:

- a cosine-convolved diffuse irradiance map;
- a GGX-prefiltered specular map whose mip level represents perceptual
  roughness;
- the two-channel integrated BRDF lookup table.

Directional maps use octahedral projection into ordinary 2D `RGBA32F`
textures. This is intentional: tgfx2 cubemaps and layered textures are not yet
a portable contract across Vulkan, OpenGL, D3D11, and WebGPU. The BRDF table is
`RG32F`. All three textures are pass-owned shader ABI resources declared by
the built-in `termin_ibl` Slang module.

At present the pass prefilters the scene's solid or vertical-gradient sky on
the CPU and uploads it only when sky or ambient settings change. Ambient color
and intensity act as the environment tint and exposure. `TC_SKYBOX_NONE`
hides the visual background but retains solid ambient illumination. An HDR or
EXR image source should be added through the same typed resource after the
texture asset pipeline supports float source data; it must not introduce a
second PBR lighting path.

`DebugGeometryPass`, `ImmediateDepthPass`, and `UnifiedGizmoPass` live here as
debug/editor render passes. Debug-producing components publish backend-neutral
primitives through the scene render lifecycle; the pass library does not depend
on component packages merely to discover debug geometry.

Shadow camera helpers (`ShadowCameraParams`, `build_shadow_view_matrix`,
`build_shadow_projection_matrix`, `compute_light_space_matrix`,
`compute_frustum_corners`, `fit_shadow_frustum_to_camera`) are part of the
public `termin.render_passes` Python API. The legacy `termin._native.render`
surface has been removed; use the canonical package directly.

Модуль владеет `ShadowMapArrayResource` и регистрирует `shadow_map_array` как
расширение общего non-texture framegraph resource registry. `ShadowPass` и
`ColorPass` получают typed resource через нейтральную таблицу
`ExecuteContext::frame_graph_resources`; generic executor не включает shadow
headers и использует только зарегистрированный depth sampled preview (дальний
каскад, дающий полный обзор shadow distance) для обычных
texture/debugger consumers.

`UIWidgetPass` is one native C++ pass on desktop, Android, and OpenXR. It
collects the `scene_ui_document` component capability, applies component,
entity, layer, and optional internal-hierarchy filtering, then submits the
documents in stable `(priority, identity)` order to
`NativeDocumentPainter`. The pass owns painter GPU resources; UI components
and their document assets remain CPU-only.
`include_scene_entities` and `include_internal_entities` independently select
documents owned by the rendered scene and by the render host's internal entity
hierarchy. Runtime passes include scene documents by default; editor pipelines
can therefore suppress runtime overlays without changing scene layers while
still retaining editor-owned documents.

If a document already carries host-published presentation metrics,
`UIWidgetPass` preserves its density scale, font scale, and physical safe
insets. The pass always binds the physical extent to its current render target,
because that extent belongs to the active presentation and may change when an
editor viewport or window is resized. Documents without a platform source
receive identity density/font policy and the same current render extent.
Android publishes density, normalized font scale, safe insets, and the latest
surface extent through its Activity/bootstrap bridge before scene rendering;
the frame pass verifies that the preserved safe-area policy is valid for the
actual target extent.

For distinct framegraph resources the pass copies input scene color to the
output before opening the UI pass with load semantics. For an inplace alias it
opens the existing target with load semantics directly. Python exposes the
native type directly from `termin.render_passes`; there is no separate Python
pass implementation or compatibility module.
