# Built-in shader catalog

Built-in engine shaders must have one canonical identity and one artifact
generation path.

## Source of truth

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

The current sidecar is catalog-derived metadata, not Slang reflection output
yet. It is intentionally named as a layout sidecar so the runtime can migrate
toward the bind-by-name plan without changing the package shape later.

## Current entries

| UUID | Name | Stage | Language | Source |
|---|---|---|---|---|
| `termin-engine-fsq` | `FullscreenQuadEngineVS` | vertex | Slang | `builtin_shaders/termin-engine-fsq.vert.slang` |
| `termin-runtime-default-color` | `TerminRuntimeDefaultColor` | vertex + fragment | GLSL | `builtin_shaders/termin-runtime-default-color.vert.glsl`, `builtin_shaders/termin-runtime-default-color.frag.glsl` |
| `termin-engine-shadow` | `ShadowEngineVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-shadow.vert.glsl`, `builtin_shaders/termin-engine-shadow.frag.glsl` |
| `termin-engine-debug-triangle` | `DebugTrianglePassVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-debug-triangle.vert.glsl`, `builtin_shaders/termin-engine-debug-triangle.frag.glsl` |
| `termin-engine-present-blit` | `PresentBlitVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-present-blit.vert.glsl`, `builtin_shaders/termin-engine-present-blit.frag.glsl` |
| `termin-engine-immediate` | `ImmediateEngineVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-immediate.vert.glsl`, `builtin_shaders/termin-engine-immediate.frag.glsl` |
| `termin-engine-canvas2d-solid` | `Canvas2DSolidVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-canvas2d.vert.glsl`, `builtin_shaders/termin-engine-canvas2d-solid.frag.glsl` |
| `termin-engine-canvas2d-texture` | `Canvas2DTextureVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-canvas2d.vert.glsl`, `builtin_shaders/termin-engine-canvas2d-texture.frag.glsl` |
| `termin-engine-text2d` | `Text2DEngineVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-text2d.vert.glsl`, `builtin_shaders/termin-engine-text2d.frag.glsl` |
| `termin-engine-text2d-sdf` | `Text2DEngineSdfVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-text2d-sdf.vert.glsl`, `builtin_shaders/termin-engine-text2d-sdf.frag.glsl` |
| `termin-engine-text3d` | `Text3DEngineVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-text3d.vert.glsl`, `builtin_shaders/termin-engine-text3d.frag.glsl` |
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
| `termin-engine-navmesh-debug` | `NavMeshDebugVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-navmesh-debug.vert.glsl`, `builtin_shaders/termin-engine-navmesh-debug.frag.glsl` |
| `termin-engine-off-mesh-link-debug` | `OffMeshLinkDebugVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-off-mesh-link-debug.vert.glsl`, `builtin_shaders/termin-engine-off-mesh-link-debug.frag.glsl` |
| `termin-engine-voxel-display` | `VoxelDisplay` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-voxel-display.vert.glsl`, `builtin_shaders/termin-engine-voxel-display.frag.glsl` |
| `termin-engine-voxelizer-line` | `VoxelizerLine` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-voxelizer-line.vert.glsl`, `builtin_shaders/termin-engine-voxelizer-line.frag.glsl` |
| `termin-engine-pick-material` | `PickShader` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-pick-material.vert.glsl`, `builtin_shaders/termin-engine-pick-material.frag.glsl` |
| `termin-engine-shadow-material` | `ShadowShader` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-shadow-material.vert.glsl`, `builtin_shaders/termin-engine-shadow-material.frag.glsl` |
| `termin-engine-depth-material` | `DepthShader` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-depth-material.vert.glsl`, `builtin_shaders/termin-engine-depth-material.frag.glsl` |
| `termin-engine-foliage-instanced` | `FoliageInstancedVariantVS` | vertex template | GLSL | `builtin_shaders/termin-engine-foliage-instanced.vert.glsl` |
| `termin-engine-foliage-shadow` | `FoliageShadowVariantVS` | vertex template | GLSL | `builtin_shaders/termin-engine-foliage-shadow.vert.glsl` |
| `termin-engine-id` | `IdEngineVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-id.vert.glsl`, `builtin_shaders/termin-engine-id.frag.glsl` |
| `termin-engine-normal` | `NormalEngineVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-normal.vert.glsl`, `builtin_shaders/termin-engine-normal.frag.glsl` |
| `termin-engine-depth` | `DepthEngineVSFS_Encoding` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-depth.vert.glsl`, `builtin_shaders/termin-engine-depth.frag.glsl` |
| `termin-engine-depth-only` | `DepthOnlyEngineVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-depth-only.vert.glsl`, `builtin_shaders/termin-engine-depth-only.frag.glsl` |
| `termin-engine-depth-to-color` | `DepthToColorFS` | fragment | GLSL | `builtin_shaders/termin-engine-depth-to-color.frag.glsl` |
| `termin-engine-color-to-depth` | `ColorToDepthFS` | fragment | GLSL | `builtin_shaders/termin-engine-color-to-depth.frag.glsl` |
| `termin-engine-skybox` | `SkyboxEngineVSFS` | vertex + fragment | shader program | `builtin_shaders/termin-engine-skybox.shader` |
| `termin-engine-grayscale` | `GrayscaleEngineFS` | fragment | Slang | `builtin_shaders/termin-engine-grayscale.frag.slang` |
| `termin-engine-bloom-bright` | `BloomBrightFS` | fragment | Slang | `builtin_shaders/termin-engine-bloom-bright.frag.slang` |
| `termin-engine-highlight` | `HighlightEngineFS` | fragment | GLSL | `builtin_shaders/termin-engine-highlight.frag.glsl` |
| `termin-engine-gizmo-mask` | `GizmoMaskVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-gizmo-mask.vert.glsl`, `builtin_shaders/termin-engine-gizmo-mask.frag.glsl` |
| `termin-engine-ground-grid` | `GroundGridEngineVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-ground-grid.vert.glsl`, `builtin_shaders/termin-engine-ground-grid.frag.glsl` |
| `termin-engine-solid-primitive` | `SolidPrimitiveEngineVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-solid-primitive.vert.glsl`, `builtin_shaders/termin-engine-solid-primitive.frag.glsl` |
| `termin-engine-bloom-downsample` | `BloomDownsampleFS` | fragment | Slang | `builtin_shaders/termin-engine-bloom-downsample.frag.slang` |
| `termin-engine-bloom-upsample` | `BloomUpsampleFS` | fragment | Slang | `builtin_shaders/termin-engine-bloom-upsample.frag.slang` |
| `termin-engine-bloom-composite` | `BloomCompositeFS` | fragment | Slang | `builtin_shaders/termin-engine-bloom-composite.frag.slang` |
| `termin-engine-tonemap` | `TonemapEngineFS` | fragment | Slang | `builtin_shaders/termin-engine-tonemap.frag.slang` |

## Migration rule

Do not add new inline engine shader strings in package/export code. Add a
catalog entry and a source file, then let the exporter generate backend
artifacts from that source.

Slang sources should not add new `[[vk::...]]` attributes. Stage IO should use
Slang/HLSL semantics. Texture-using post-process shaders remain catalog-managed
GLSL until the runtime can bind resources by logical name or consume generated
layout metadata.

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

Runtime fallback GLSL is allowed only for legacy/editor compatibility when no
artifact root is configured. It must stay next to the catalog entry, not in a
caller-specific copy.

Live engine renderers and render passes should call the built-in catalog loader
with only the stable shader UUID. Filenames, shader names, and stage shape
belong in `engine-shader-catalog.json`, not in individual pass implementations.
The current C++ live registration helper accepts catalog-managed GLSL stage
entries and `.shader` program entries; Slang built-ins are consumed through
generated artifacts until the live runtime path can bind by reflected layout.
