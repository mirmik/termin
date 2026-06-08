# Built-in shader catalog

Built-in engine shaders must have one canonical identity and one artifact
generation path.

## Source of truth

- Runtime metadata lives in `termin-graphics/include/tgfx2/engine_shader_catalog.hpp`.
- Built-in source files live in `termin-graphics/resources/builtin_shaders/`.
- SDK installs those source files to `share/termin/builtin_shaders/`.
- Runtime/package exporters resolve built-in sources from the repo first, then
  from `TERMIN_SDK/share/termin/builtin_shaders`, then from
  `sys.prefix/share/termin/builtin_shaders`.

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

## Current entries

| UUID | Name | Stage | Language | Source |
|---|---|---|---|---|
| `termin-engine-fsq` | `FullscreenQuadEngineVS` | vertex | Slang | `builtin_shaders/termin-engine-fsq.vert.slang` |

## Migration rule

Do not add new inline engine shader strings in package/export code. Add a
catalog entry and a source file, then let the exporter generate backend
artifacts from that source.

Runtime fallback GLSL is allowed only for legacy/editor compatibility when no
artifact root is configured. It must stay next to the catalog entry, not in a
caller-specific copy.
