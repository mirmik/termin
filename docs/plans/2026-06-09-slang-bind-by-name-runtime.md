# Slang Bind-By-Name Runtime Plan

Date: 2026-06-09

## Goal

Move Termin's shader resource binding model from backend numeric slots to
Slang/reflection-driven symbolic bindings.

The target state is:

- Slang source files do not contain backend-specific layout attributes such as
  `[[vk::binding]]` or `[[vk::location]]`.
- Shader stage IO is expressed through Slang/HLSL semantics:
  `POSITION`, `TEXCOORD0`, `COLOR0`, `SV_Position`, `SV_Target0`, etc.
- Shader resources are expressed by logical names:
  `params`, `input_texture`, `bloom_texture`, `material`, `draw`, etc.
- Generated artifacts carry enough layout metadata for each backend to bind
  resources correctly.
- Render passes and materials bind resources by logical names or stable
  resource identifiers, not by hard-coded integers like `4` and `5`.

This is the long-term replacement for the current bridge where GLSL/Vulkan
shader text and render code share numeric binding slots.

## Problem

Current tgfx2 code assumes a shared numeric descriptor ABI:

- UBOs live in bindings such as `0`, `1`, `2`, `3`, `16`, `24`.
- sampled textures live in bindings `4..7`, `8`, `9..15`, `17..23`.
- post-process passes bind fullscreen input textures to slots like `4` and
  `5`.

This works for GLSL because source files explicitly write
`layout(binding = N)`. It does not map cleanly to backend-neutral Slang.

If we remove `[[vk::binding]]` from Slang without changing the runtime model,
Slang can compile successfully but infer bindings that do not match tgfx2's
runtime slots. That creates silent runtime breakage: the pass binds a texture
to slot `4`, while the generated shader reads another slot.

`[[vk::binding]]` fixes the immediate problem but leaks Vulkan layout into the
source language. HLSL-style `register(...)` is also only a bridge, not the
desired engine model: it still makes shader authors manage backend/resource
slots directly.

## Non-Goals

- Do not repair shadow correctness as part of this migration. Shadow shaders
  can be migrated after the binding model is stable.
- Do not require Slang at runtime. Runtime backends consume generated
  artifacts and metadata.
- Do not switch every built-in shader in one step. The migration should be
  staged and testable.
- Do not remove the legacy numeric APIs immediately. They remain as a
  compatibility layer until passes and materials have moved.

## Architecture

### Source Model

Slang source should describe logical shader interfaces:

```slang
struct FragmentInput
{
    float2 uv : TEXCOORD0;
};

struct FragmentOutput
{
    float4 color : SV_Target0;
};

struct TonemapParams
{
    float exposure;
    int method;
};

ConstantBuffer<TonemapParams> params;
Sampler2D input_texture;

[shader("fragment")]
FragmentOutput main(FragmentInput input)
{
    FragmentOutput output;
    float3 color = input_texture.Sample(input.uv).rgb * params.exposure;
    output.color = float4(color, 1.0);
    return output;
}
```

The source should not contain:

```slang
[[vk::location(...)]]
[[vk::binding(...)]]
```

Stage IO locations are derived from semantics and validated through reflection.
Resource backend bindings are generated outside the source.

### Shader Layout Metadata

Every generated shader artifact should have a sidecar layout file. Proposed
path shape:

```text
shaders/layout/<uuid>.shader-layout.json
```

Example:

```json
{
  "version": 1,
  "uuid": "termin-engine-tonemap",
  "language": "slang",
  "entry": "main",
  "stages": {
    "fragment": {
      "inputs": [
        {"name": "uv", "semantic": "TEXCOORD0", "location": 0}
      ],
      "outputs": [
        {"name": "color", "semantic": "SV_Target0", "location": 0}
      ],
      "resources": [
        {
          "name": "params",
          "kind": "constant_buffer",
          "struct": "TonemapParams",
          "backend": {
            "vulkan": {"set": 0, "binding": 0},
            "opengl": {"binding": 0},
            "d3d11": {"register_class": "b", "register": 0}
          }
        },
        {
          "name": "input_texture",
          "kind": "combined_sampler2d",
          "backend": {
            "vulkan": {"set": 0, "binding": 4},
            "opengl": {"binding": 4},
            "d3d11": {
              "texture_register": {"class": "t", "index": 4},
              "sampler_register": {"class": "s", "index": 4}
            }
          }
        }
      ]
    }
  }
}
```

The logical name and kind are the stable ABI. Backend numeric slots are
generated data and may differ by backend.

### Runtime Model

Runtime code should move toward this shape:

```cpp
ctx.bind_uniform("params", params_buffer);
ctx.bind_texture("input_texture", input_texture);
ctx.bind_texture("bloom_texture", bloom_texture);
```

Before draw/dispatch, tgfx2 resolves symbolic names through the active shader
layout metadata and emits backend resource bindings.

Legacy code may continue to call:

```cpp
ctx.bind_uniform_buffer(0, params_buffer);
ctx.bind_sampled_texture(4, input_texture);
```

but migrated shaders and passes should not add new numeric binding usage.

### Material Model

Slang material properties should be generated as named resources:

- `frame` or `per_frame`
- `material`
- `draw`
- named textures such as `albedo_texture`, `normal_texture`

The material compiler/build step owns backend layout assignment. Shader source
does not know binding numbers.

## Phase 1: Reflection And Layout Capture

Teach `termin_shaderc` or a companion layout tool to produce sidecar shader
layout metadata for Slang stages.

Tasks:

- Invoke Slang reflection for every compiled Slang stage.
- Capture entry point, stage, inputs, outputs, resources, resource kind,
  semantic names, and generated backend binding information.
- Write `*.shader-layout.json` next to generated artifacts.
- Validate that generated stage IO matches the source semantics expected by
  the engine.
- Keep existing artifact generation behavior unchanged while layout metadata is
  introduced.

Acceptance:

- A Slang shader compiled for Vulkan and OpenGL produces artifacts plus one
  layout JSON file.
- Tests assert that `TEXCOORD0` maps to fragment input location `0` without
  `[[vk::location]]` in source.
- Tests assert that resource names appear in the layout metadata.

## Phase 2: Backend Layout Assignment

Move backend binding assignment out of shader source.

Tasks:

- Define a small internal layout schema for required engine resources.
- For built-ins, store logical resource requirements in the built-in shader
  catalog.
- For material shaders, derive logical resource requirements from material
  properties and Slang reflection.
- Assign backend bindings from a deterministic allocator.
- Detect collisions before artifacts reach runtime.

Acceptance:

- Built-in Slang source can omit `[[vk::binding]]`.
- The layout sidecar records where each resource landed for Vulkan/OpenGL.
- Collision diagnostics include shader UUID, stage, resource name, target, and
  requested/generated binding.

## Phase 3: Runtime Layout Loading

Load shader layout metadata into tgfx2 runtime objects.

Tasks:

- Extend shader artifact lookup to also find `shader-layout.json`.
- Add a `ShaderLayout` or equivalent runtime structure.
- Attach layout metadata to shader/pipeline state used by draw calls.
- Log missing or incompatible layout metadata for Slang shaders.
- Keep GLSL fallback behavior for legacy shaders.

Acceptance:

- Slang shaders marked artifact-required fail loudly if layout metadata is
  missing.
- Error logs include backend, shader UUID, stage, and expected layout path.
- Existing GLSL shaders continue to render.

## Phase 4: Symbolic Resource Binding API

Add symbolic binding methods without removing the existing numeric API.

Possible C++ shape:

```cpp
void bind_uniform(std::string_view name, BufferHandle buffer,
                  uint64_t offset = 0, uint64_t range = 0);
void bind_texture(std::string_view name, TextureHandle texture,
                  SamplerHandle sampler = {});
void bind_texture_array_element(std::string_view name, uint32_t array_element,
                                TextureHandle texture,
                                SamplerHandle sampler = {});
```

Tasks:

- Store pending symbolic bindings in `RenderContext2`.
- Resolve symbolic bindings to backend resource bindings from the active
  shader/pipeline layout.
- Report unused or missing symbolic bindings with useful logs.
- Decide whether symbolic binding resolution happens when setting shaders,
  creating pipelines, or issuing draw calls.

Acceptance:

- A fullscreen/post-process pass can bind `input_texture` by name.
- Missing `input_texture` logs a clear error instead of silently sampling a
  default texture.
- Numeric bindings still work for old GLSL paths.

## Phase 5: First Runtime Pass Migration

Migrate the smallest pass that exercises texture resources.

Recommended order:

1. fullscreen/present fragment path
2. grayscale
3. tonemap
4. bloom bright/downsample/upsample/composite

Tasks:

- Convert the selected shader source to clean Slang.
- Move its resource requirements into the built-in shader catalog.
- Generate Vulkan/OpenGL artifacts and layout metadata.
- Update the pass to bind resources by name.
- Keep a narrow GLSL fallback only while the pass is actively migrating.

Acceptance:

- The migrated pass renders through clean Slang source with no `[[vk::...]]`
  attributes.
- Vulkan smoke validates the generated artifact and resource binding path.
- OpenGL either consumes generated GLSL artifact metadata or has an explicit
  documented compatibility gap.

## Phase 6: Material Pipeline Migration

After built-in passes prove the model, move materials.

Tasks:

- Define Slang-native material property lowering.
- Replace GLSL-specific `@property` rewriting with a Slang material ABI.
- Generate material constant buffers and texture resource declarations without
  hard-coded backend layout in source.
- Bind material resources by name in color/depth/shadow passes.
- Decide how shader modules/includes are represented for Slang material code.

Acceptance:

- A simple material with one constant buffer and one texture renders on Vulkan
  without `[[vk::binding]]`.
- Material package artifacts include layout metadata.
- Runtime package loading preserves enough metadata to bind material resources
  symbolically.

## Phase 7: Legacy Numeric Binding Retirement

Once built-ins and materials use symbolic bindings, reduce the old numeric
surface.

Tasks:

- Mark numeric binding APIs as compatibility-only in docs.
- Replace remaining new-code call sites with symbolic binding calls.
- Keep backend internals numeric; remove numeric details only from public pass
  and shader authoring layers.
- Update `docs/gpu-pipeline-layout.md` to describe backend-generated layouts
  instead of source-authored binding slots.

Acceptance:

- No migrated Slang source contains `[[vk::binding]]` or
  `[[vk::location]]`.
- New render passes do not need to know texture slot numbers.
- Numeric binding call sites are either legacy GLSL paths or backend internals.

## Testing Strategy

Unit tests:

- `termin_shaderc` layout JSON generation with fake and real Slang paths.
- Reflection parsing for inputs, outputs, constant buffers, and textures.
- Collision diagnostics for duplicate backend binding assignment.
- Runtime layout loading success/failure.

Integration tests:

- Runtime package export writes artifacts and layout sidecars.
- Vulkan smoke renders a clean Slang fullscreen/post-process shader.
- OpenGL artifact smoke verifies generated GLSL plus layout metadata where the
  current GL target supports it.

Regression tests:

- Legacy GLSL package export remains compatible.
- Existing numeric binding paths continue to work until explicitly retired.
- Missing Slang layout metadata fails loudly.

## Risks

- Slang reflection API integration may be larger than the current command-line
  wrapper.
- OpenGL generated GLSL may not preserve resource names in a form that is easy
  to map without extra metadata.
- Combined sampler handling differs across Vulkan/OpenGL/D3D-style syntax.
  The runtime model should represent the logical resource as a combined
  sampler where that is what the pass wants.
- Backends currently normalize missing texture slots to a default texture.
  That behavior can hide symbolic binding mistakes unless migrated paths opt
  into stricter validation.

## Immediate Implementation Slice

The first slice should be small but architectural:

1. Remove `[[vk::location]]` from the canonical FSQ Slang source and prove
   semantics preserve the expected locations.
2. Add layout sidecar generation for a Slang shader that has no texture
   resources.
3. Add the `ShaderLayout` runtime structure and layout lookup path.
4. Add symbolic binding methods, initially resolving only resources whose
   backend binding is already present in the layout sidecar.
5. Migrate one texture-using fullscreen pass after layout loading and symbolic
   binding resolution are tested.

This keeps source cleanup and runtime binding migration connected, without
pretending that simply deleting `[[vk::binding]]` is safe.
