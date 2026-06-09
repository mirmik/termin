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
  then from `TERMIN_SDK/share/termin/builtin_shaders`, then from the
  build-tree `termin-graphics/resources/builtin_shaders` directory.

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
| `termin-engine-shadow` | `ShadowEngineVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-shadow.vert.glsl`, `builtin_shaders/termin-engine-shadow.frag.glsl` |
| `termin-engine-debug-triangle` | `DebugTrianglePassVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-debug-triangle.vert.glsl`, `builtin_shaders/termin-engine-debug-triangle.frag.glsl` |
| `termin-engine-immediate` | `ImmediateEngineVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-immediate.vert.glsl`, `builtin_shaders/termin-engine-immediate.frag.glsl` |
| `termin-engine-canvas2d-solid` | `Canvas2DSolidVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-canvas2d.vert.glsl`, `builtin_shaders/termin-engine-canvas2d-solid.frag.glsl` |
| `termin-engine-canvas2d-texture` | `Canvas2DTextureVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-canvas2d.vert.glsl`, `builtin_shaders/termin-engine-canvas2d-texture.frag.glsl` |
| `termin-engine-id` | `IdEngineVSFS` | vertex + fragment | GLSL | `builtin_shaders/termin-engine-id.vert.glsl`, `builtin_shaders/termin-engine-id.frag.glsl` |
| `termin-engine-skybox` | `SkyboxEngineVSFS` | vertex + fragment | shader program | `builtin_shaders/termin-engine-skybox.shader` |
| `termin-engine-grayscale` | `GrayscaleEngineFS` | fragment | GLSL | `builtin_shaders/termin-engine-grayscale.frag.glsl` |
| `termin-engine-bloom-bright` | `BloomBrightFS` | fragment | GLSL | `builtin_shaders/termin-engine-bloom-bright.frag.glsl` |
| `termin-engine-bloom-downsample` | `BloomDownsampleFS` | fragment | GLSL | `builtin_shaders/termin-engine-bloom-downsample.frag.glsl` |
| `termin-engine-bloom-upsample` | `BloomUpsampleFS` | fragment | GLSL | `builtin_shaders/termin-engine-bloom-upsample.frag.glsl` |
| `termin-engine-bloom-composite` | `BloomCompositeFS` | fragment | GLSL | `builtin_shaders/termin-engine-bloom-composite.frag.glsl` |
| `termin-engine-tonemap` | `TonemapEngineFS` | fragment | GLSL | `builtin_shaders/termin-engine-tonemap.frag.glsl` |

## Migration rule

Do not add new inline engine shader strings in package/export code. Add a
catalog entry and a source file, then let the exporter generate backend
artifacts from that source.

Slang sources should not add new `[[vk::...]]` attributes. Stage IO should use
Slang/HLSL semantics. Texture-using post-process shaders remain catalog-managed
GLSL until the runtime can bind resources by logical name or consume generated
layout metadata.

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
