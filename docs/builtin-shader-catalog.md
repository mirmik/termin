# Built-in shader catalog

Built-in engine shaders must have one canonical identity and one artifact
generation path.

## Status

`engine-shader-catalog.json` is transitional. It exists to keep current source
loading, packaging, and artifact staging working while built-in shaders move
toward generated/reflection-derived runtime metadata. Do not expand it with new
semantic contract, draw-kind, or backend placement policy. The target direction
is to delete this JSON manifest, not to make it the engine shader database.

Built-in shaders must converge on the same runtime model as material-assembled
shaders:

```text
tc_shader
  +-- tc_shader_contract        // backend-agnostic interface requirements
  +-- shader resource layout    // resolved backend/runtime placement
```

The contract declares what the shader needs. The layout declares where those
resources are bound. The render pass that uses the shader owns draw intent
(`mesh`, `fullscreen`, `compute`, and similar execution policy).

## Transitional manifest

- Package/export metadata lives in
  `termin-graphics/resources/builtin_shaders/engine-shader-catalog.json`.
- Runtime metadata for built-ins that are consumed directly by tgfx2 lives in
  `termin-graphics/include/tgfx2/engine_shader_catalog.hpp`.
- Built-in source files live in `termin-graphics/resources/builtin_shaders/`.
- SDK installs those source files to `share/termin/builtin_shaders/`.
- The live C++ catalog/source loader is owned by `termin_graphics2` and exposed
  through `tgfx2/builtin_shader_sources.hpp`, so engine renderers and render
  passes resolve built-ins through the same API.
- Runtime/package exporters resolve built-in sources from the repo first, then
  from `TERMIN_SDK/share/termin/builtin_shaders`, then from
  `sys.prefix/share/termin/builtin_shaders`.
- C++ engine renderers and render passes register live built-in shaders by
  stable catalog UUID.
  The catalog/source loader resolves files from `TERMIN_BUILTIN_SHADER_ROOT`,
  then from `TERMIN_SDK/share/termin/builtin_shaders`, then from
  `share/termin/builtin_shaders` next to the loaded native library, its parent
  SDK directories, or the process working directory.
- Build-tree CTest/local binaries use the same runtime layout: `termin-graphics`
  stages built-ins once into `${CMAKE_BINARY_DIR}/share/termin/builtin_shaders`.
- C# SDK staging copies installed built-ins from
  `share/termin/builtin_shaders/` into the C# SDK drop so `Termin.Wpf`/tcplot
  consumers can run without a termin source checkout on the target machine.

## Artifact layout

Generated artifacts use the same backend-aware layout as material shaders:

```text
shaders/vulkan/<uuid>.vert.spv
shaders/vulkan/<uuid>.frag.spv
shaders/opengl/<uuid>.vert.glsl
shaders/opengl/<uuid>.frag.glsl
```

GLSL built-ins currently generate Vulkan SPIR-V only. Slang built-ins generate
Vulkan SPIR-V and OpenGL GLSL.

Built-in shader layout metadata is written to:

```text
shaders/layout/<uuid>.shader-layout.json
```

The current sidecar is catalog-derived metadata for some entries and
reflection-derived metadata for generated Slang artifacts. It is intentionally
named as a layout sidecar so the runtime can migrate toward the scope-first
bind-by-name model without changing the package shape later.

## Resource scope policy

Resources that need stable engine buckets must declare `scope` explicitly in
the catalog or via Slang `[[TerminScope("...")]]` reflection metadata. This
includes `frame`, `pass`, `material`, and `draw` resources.

Resources without an explicit scope are treated as `transient`. The shader
compiler, sidecar loader, and live built-in catalog loader share this default;
they must not infer non-transient scopes from resource names such as
`material`, `draw_data`, or `u_params`.

## Current entries

| UUID | Name | Stage | Language | Source |
|---|---|---|---|---|
| `termin-engine-fsq` | `FullscreenQuadEngineVS` | vertex | Slang | `builtin_shaders/termin-engine-fsq.vert.slang` |
| `termin-runtime-default-color` | `TerminRuntimeDefaultColor` | vertex + fragment | Slang | `builtin_shaders/termin-runtime-default-color.slang` |
| `termin-engine-shadow` | `ShadowEngineVSFS` | vertex + fragment | Slang | `builtin_shaders/termin-engine-shadow.slang` |
| `termin-engine-debug-triangle` | `DebugTrianglePassVSFS` | vertex + fragment | Slang | `builtin_shaders/termin-engine-debug-triangle.slang` |
| `termin-engine-present-blit` | `PresentBlitVSFS` | vertex + fragment | Slang | `builtin_shaders/termin-engine-present-blit.slang` |
| `termin-engine-immediate` | `ImmediateEngineVSFS` | vertex + fragment | Slang | `builtin_shaders/termin-engine-immediate.slang` |
| `termin-engine-canvas2d-solid` | `Canvas2DSolidVSFS` | vertex + fragment | Slang | `builtin_shaders/termin-engine-canvas2d-solid.slang` |
| `termin-engine-canvas2d-texture` | `Canvas2DTextureVSFS` | vertex + fragment | Slang | `builtin_shaders/termin-engine-canvas2d-texture.slang` |
| `termin-engine-text2d` | `Text2DEngineVSFS` | vertex + fragment | Slang | `builtin_shaders/termin-engine-text2d.slang` |
| `termin-engine-text2d-sdf` | `Text2DEngineSdfVSFS` | vertex + fragment | Slang | `builtin_shaders/termin-engine-text2d-sdf.slang` |
| `termin-engine-text3d` | `Text3DEngineVSFS` | vertex + fragment | Slang | `builtin_shaders/termin-engine-text3d.slang` |
| `termin-engine-screen-line` | `ScreenSpaceLineVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-screen-line.vert.glsl`, `builtin_shaders/termin-engine-screen-line.frag.glsl` |
| `termin-engine-screen-line-cap` | `ScreenSpaceLineCapVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-screen-line-cap.vert.glsl`, `builtin_shaders/termin-engine-screen-line.frag.glsl` |
| `termin-engine-screen-line-join` | `ScreenSpaceLineJoinVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-screen-line-join.vert.glsl`, `builtin_shaders/termin-engine-screen-line.frag.glsl` |
| `termin-engine-screen-line-round-join` | `ScreenSpaceLineRoundJoinVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-screen-line-round-join.vert.glsl`, `builtin_shaders/termin-engine-screen-line.frag.glsl` |
| `termin-engine-world-line` | `WorldSpaceLineVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-world-line.vert.glsl`, `builtin_shaders/termin-engine-world-line.frag.glsl` |
| `termin-engine-world-line-cap` | `WorldSpaceLineCapVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-world-line-cap.vert.glsl`, `builtin_shaders/termin-engine-world-line.frag.glsl` |
| `termin-engine-world-line-join` | `WorldSpaceLineJoinVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-world-line-join.vert.glsl`, `builtin_shaders/termin-engine-world-line.frag.glsl` |
| `termin-engine-world-line-round-join` | `WorldSpaceLineRoundJoinVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-world-line-round-join.vert.glsl`, `builtin_shaders/termin-engine-world-line.frag.glsl` |
| `termin-engine-world-line-lit` | `WorldSpaceLineLitFS` | fragment | GLSL | `builtin_shaders/termin-engine-world-line-lit.frag.glsl` |
| `termin-engine-world-tube-line` | `WorldTubeLineVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-world-tube-line.vert.glsl`, `builtin_shaders/termin-engine-world-tube-line.frag.glsl` |
| `termin-engine-world-tube-line-cap` | `WorldTubeLineCapVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-world-tube-line-cap.vert.glsl`, `builtin_shaders/termin-engine-world-tube-line.frag.glsl` |
| `termin-engine-world-tube-line-lit` | `WorldTubeLineLitFS` | fragment | GLSL | `builtin_shaders/termin-engine-world-tube-line-lit.frag.glsl` |
| `termin-engine-line-default` | `DefaultLineShader` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-line-default.vert.glsl`, `builtin_shaders/termin-engine-line-default.frag.glsl` |
| `termin-engine-navmesh-debug` | `NavMeshDebugVSFS` | vertex + fragment | Slang | `builtin_shaders/termin-engine-navmesh-debug.slang` |
| `termin-engine-off-mesh-link-debug` | `OffMeshLinkDebugVSFS` | vertex + fragment | Slang | `builtin_shaders/termin-engine-off-mesh-link-debug.slang` |
| `termin-engine-voxel-display` | `VoxelDisplay` | vertex + fragment | Slang | `builtin_shaders/termin-engine-voxel-display.slang` |
| `termin-engine-voxelizer-line` | `VoxelizerLine` | vertex + fragment | Slang | `builtin_shaders/termin-engine-voxelizer-line.slang` |
| `termin-engine-pick-material` | `PickShader` | vertex + fragment | Slang | `builtin_shaders/termin-engine-pick-material.slang` |
| `termin-engine-shadow-material` | `ShadowShader` | vertex + fragment | Slang | `builtin_shaders/termin-engine-shadow-material.slang` |
| `termin-engine-depth-material` | `DepthShader` | vertex + fragment | Slang | `builtin_shaders/termin-engine-depth-material.slang` |
| `termin-engine-foliage-instanced` | `FoliageInstancedVariantVS` | vertex template | Slang | `builtin_shaders/termin-engine-foliage-instanced.vert.slang` |
| `termin-engine-foliage-shadow` | `FoliageShadowVariantVS` | vertex template | Slang | `builtin_shaders/termin-engine-foliage-shadow.vert.slang` |
| `termin-engine-id` | `IdEngineVSFS` | vertex + fragment | Slang | `builtin_shaders/termin-engine-id.slang` |
| `termin-engine-normal` | `NormalEngineVSFS` | vertex + fragment | Slang | `builtin_shaders/termin-engine-normal.slang` |
| `termin-engine-depth` | `DepthEngineVSFS_Encoding` | vertex + fragment | Slang | `builtin_shaders/termin-engine-depth.slang` |
| `termin-engine-depth-only` | `DepthOnlyEngineVSFS` | vertex + fragment | Slang | `builtin_shaders/termin-engine-depth-only.slang` |
| `termin-engine-depth-to-color` | `DepthToColorFS` | fragment | Slang | `builtin_shaders/termin-engine-depth-to-color.frag.slang` |
| `termin-engine-color-to-depth` | `ColorToDepthFS` | fragment | Slang | `builtin_shaders/termin-engine-color-to-depth.frag.slang` |
| `termin-engine-skybox` | `SkyboxEngineVSFS` | vertex + fragment | shader program | `builtin_shaders/termin-engine-skybox.shader` |
| `termin-engine-grayscale` | `GrayscaleEngineFS` | fragment | Slang | `builtin_shaders/termin-engine-grayscale.frag.slang` |
| `termin-engine-bloom-bright` | `BloomBrightFS` | fragment | Slang | `builtin_shaders/termin-engine-bloom-bright.frag.slang` |
| `termin-engine-highlight` | `HighlightEngineFS` | fragment | Slang | `builtin_shaders/termin-engine-highlight.frag.slang` |
| `termin-engine-gizmo-mask` | `GizmoMaskVSFS` | vertex + fragment | Slang | `builtin_shaders/termin-engine-gizmo-mask.slang` |
| `termin-engine-ground-grid` | `GroundGridEngineVSFS` | vertex + fragment | Slang | `builtin_shaders/termin-engine-ground-grid.slang` |
| `termin-engine-solid-primitive` | `SolidPrimitiveEngineVSFS` | vertex + fragment | Slang | `builtin_shaders/termin-engine-solid-primitive.slang` |
| `termin-engine-bloom-downsample` | `BloomDownsampleFS` | fragment | Slang | `builtin_shaders/termin-engine-bloom-downsample.frag.slang` |
| `termin-engine-bloom-upsample` | `BloomUpsampleFS` | fragment | Slang | `builtin_shaders/termin-engine-bloom-upsample.frag.slang` |
| `termin-engine-bloom-composite` | `BloomCompositeFS` | fragment | Slang | `builtin_shaders/termin-engine-bloom-composite.frag.slang` |
| `termin-engine-tonemap` | `TonemapEngineFS` | fragment | Slang | `builtin_shaders/termin-engine-tonemap.frag.slang` |

## Migration rule

Do not add new inline engine shader strings in package/export code. Add a
catalog entry and a source file, then let the exporter generate backend
artifacts from that source.

Slang sources should not add new `[[vk::...]]` attributes. Stage IO should use
Slang/HLSL semantics. Texture-using post-process shaders should use generated
layout metadata and bind resources by logical name when they are migrated to
Slang.

Legacy material fallback shaders may stay catalog-managed GLSL with
`legacy_uniform` resources while they still run through the old material uniform
path. The catalog owns their source location, but they are not Slang-ready until
the material ABI moves to named resources/constant buffers.

Runtime shader variants may use catalog-managed stage templates when only one
stage is engine-authored and the other stage still comes from a material. These
entries should be loaded with `load_builtin_shader_stage_source_from_catalog`
and should not be registered as complete live shaders.

Built-in `.shader` program entries are allowed when the current engine path
still needs the material shader parser to synthesize `MaterialParams` GLSL.
Exporters parse those program sources and package generated GLSL stage
artifacts while keeping the program source path in the layout sidecar.

Live engine renderers and render passes should call the built-in catalog loader
with only the stable shader UUID. Filenames, shader names, and stage shape
belong in `engine-shader-catalog.json`, not in individual pass implementations.
Migrated Slang built-ins should consume generated artifacts plus layout
metadata, then bind resources by logical name. Runtime GLSL fallbacks should
not be added; missing artifacts are errors.

This is a transitional rule for the current manifest. New semantic shader
contracts, draw intent, and backend placement policy should be supplied by
generated/reflection-derived metadata or by the owning shader provider, not by
growing `engine-shader-catalog.json`.
