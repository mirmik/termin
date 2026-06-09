# Slang Two-Set Material Layout Transition

Date: 2026-06-09

## Goal

Move from the current forced shared Vulkan descriptor layout to a two-set scheme:

- **set = 0** — Engine resources. Fixed layout, shared across all shaders in a pass.
  One descriptor set allocated per frame/pass, bound once.
- **set = 1** — Material resources. Free layout, defined by per-shader specification.
  Binding numbers come from shader layout metadata, not hardcoded constants.

This unlocks:

- Arbitrary UBO/texture binding numbers for material resources.
- Split `Texture2D` + `SamplerState` (currently rejected by shared layout policy).
- `RWTexture` (storage textures) — currently rejected.
- Cleaner Slang source without bind-by-name being fully implemented first.
- Future multi-set resource organisation (e.g., set=2 for per-draw, set=3 for
  global samplers).

This plan is an **implementation bridge** toward the symbolic binding model
described in [Slang bind-by-name runtime](2026-06-09-slang-bind-by-name-runtime.md).
It makes per-shader material layouts real before the symbolic binding API exists.

## Current State

### Shared layout policy (`termin_shaderc.cpp:527-585`)

`apply_slang_vulkan_shared_layout_policy()` forcibly remaps ALL Slang resources
to a fixed numeric ABI:

```
material  → set=0, binding=1  (constant_buffer)
per_frame → set=0, binding=2  (constant_buffer)
draw_data → set=0, binding=24 (constant_buffer)
samplers  → set=0, binding ∈ {4,5,6,7, 9..15, 17..23}
```

Split textures, separate samplers, and storage textures are rejected with errors.

### Hardcoded runtime bindings

C++ render passes bind engine resources at hardcoded numeric slots:

| Resource | Constant | Value | Location |
|---|---|---|---|
| Lighting UBO | `LIGHTING_UBO_BINDING` | `0` | `lighting_ubo.hpp` |
| Material UBO | `MATERIAL_UBO_BINDING` | `1` | `material_ubo_apply.hpp` |
| PerFrame UBO | `ENGINE_PER_FRAME_UBO_BINDING` | `2` | `frame_uniforms.hpp` |
| Shadow UBO | `SHADOW_UBO_BINDING` | `3` | `color_pass.cpp` (local) |
| Material textures | `material_texture_binding_for_index(i)` | `4,5,6,7,9,...` | `shader_parser.hpp` |
| Shadow textures | `SHADOW_SLOT_BASE` | `8` | `color_pass.cpp` (local) |
| Draw/push data | (implicit) | `24` | `termin_shaderc` policy |

Only **Material UBO** already resolves its binding from `tc_shader.resource_bindings[]`
via `material_ubo_binding_for_shader()` — everything else ignores the layout sidecar.

### What already works

- `.layout.json` sidecars are generated for every compiled Slang stage.
- Sidecars are parsed and merged into `tc_shader.resource_bindings[]` at load time.
- `material_ubo_binding_for_shader()` already demonstrates the lookup pattern.
- Slang and Vulkan natively support multiple descriptor sets (`space` in Slang =
  `set` in Vulkan).

## Proposed Architecture

### Set assignments

```
set = 0  Engine resources (shared layout, bound per pass):
        [0]  lighting_ubo          (optional, only if shader needs it)
        [1]  (reserved / unused)
        [2]  per_frame
        [3]  shadow_ubo
        [8]  shadow_map_array     (array of combined shadow samplers)
        ...  (other engine-global resources)

set = 1  Material resources (per-shader layout, from specification):
        [*]  material             (ConstantBuffer<MaterialParams>)
        [*]  texture0, texture1, ...
        [*]  draw_data            (ConstantBuffer, per-draw transforms)
```

Material shaders declare resources in set=1. Engine passes bind set=0 resources
at stable slots regardless of which material shader is active. Material resources
in set=1 are bound per-draw according to the active shader's layout metadata.

### Slang source convention

Material shaders place engine resources in set=0 and material resources in set=1:

```slang
// set = 0 — engine (will be bound by pass, not by material system)
[[vk::binding(2, 0)]]
ConstantBuffer<PerFrame> per_frame;

// set = 1 — material (binding assigned by specification / compiler)
[[vk::binding(0, 1)]]
ConstantBuffer<MaterialParams> material;

[[vk::binding(1, 1)]]
Sampler2D albedo_texture;
```

Once the two-set scheme is stable, the `[[vk::binding(..., 0)]]` on engine resources
can be replaced by named bindings when the symbolic API is ready. Material resources
in set=1 may keep explicit bindings assigned by the build system, or move to
auto-assignment from reflection.

### Build system changes

1. `termin_shaderc` stops applying `apply_slang_vulkan_shared_layout_policy()` for
   material shaders (those with `@property` and `@language slang`).
2. Instead, `termin_shaderc` (or a companion layout tool) reads Slang reflection
   and validates that:
   - Engine resources (`per_frame`, shadow-related) are in set=0 with expected bindings.
   - Material resources are in set=1.
   - No collisions within each set.
3. The `.layout.json` sidecar records the final binding assignment for both sets.

### Runtime changes

Engine passes continue to bind set=0 resources at hardcoded slots — this
does not change.

Material binding code (`material_ubo_apply.cpp`) already resolves material UBO
from layout metadata. It must be extended to also resolve texture binding slots
from layout metadata instead of using `material_texture_binding_for_index()`.

`RenderContext2` (or its Vulkan backend) must be taught to support two descriptor
sets: set=0 is shared and pre-bound, set=1 is per-draw and allocated from a
per-shader `VkDescriptorSetLayout`.

## Non-Goals

- Full symbolic bind-by-name API. That is tracked in
  [2026-06-09-slang-bind-by-name-runtime.md](2026-06-09-slang-bind-by-name-runtime.md).
  This plan is the layout infrastructure that makes symbolic binding possible later.
- Removing hardcoded engine resource bindings from C++ passes. Engine resources
  stay on set=0 with fixed bindings until symbolic binding is available.
- Migrating all built-in shaders to Slang. Engine shaders continue to work with
  the current shared layout or can opt into set=0-only usage.

## Phases

### Phase 1: Vulkan Multi-Set Backend Support

Teach the Vulkan backend to allocate and bind multiple descriptor sets.

Tasks:

- Extend `VulkanRenderDevice` / pipeline layout creation to support a
  `VkDescriptorSetLayout` per set.
- `RenderContext2` gains internal tracking of which set a binding targets.
- Numeric binding slots are qualified by set: `ctx2->bind_uniform_buffer(set=0,
  slot=2, ...)` or `ctx2->bind_uniform_buffer(set=1, slot=0, ...)`.
- Default behaviour when no set is specified: set=0 (backward compatible).

Acceptance:

- Existing shaders continue to render with all resources in set=0.
- A test shader with resources in set=1 renders correctly through Vulkan.

Status: not started.

### Phase 2: Material Shader Set-1 Generation

Stop remapping material resources into set=0.

Tasks:

- Add a `--layout-scheme two-set` (or similar) flag to `termin_shaderc`.
- In two-set mode, skip `apply_slang_vulkan_shared_layout_policy()` and
  `patch_slang_vulkan_spirv_bindings()` for set=1 resources.
- Validate that engine-named resources (`per_frame`, shadow-related) are in set=0
  with the expected bindings.
- Record final bindings in `.layout.json` with set information.
- Keep the shared layout policy as default until two-set is proven.

Acceptance:

- A Slang `.shader` with `@language slang` and `@property` compiles to SPIR-V
  with material resources in set=1.
- `.layout.json` records correct set/binding per resource.
- Vulkan smoke renders the shader through the two-set pipeline layout.

Status: not started.

### Phase 3: Runtime Material Texture Binding from Layout

Replace hardcoded texture slot computation with layout lookup.

Tasks:

- Extend `apply_material_phase_ubo()` / `bind_material_ubo()` to look up texture
  binding slots from `tc_shader.resource_bindings[]` by texture name, instead of
  using `material_texture_binding_for_index(i)`.
- The lookup key is the texture property name (e.g., `"albedo_texture"`).
- Fallback to index-based computation for legacy shaders without layout metadata.
- Remove `MATERIAL_TEX_SLOT_BASE` and `material_texture_binding_for_index()`
  dependence from the material UBO path.

Acceptance:

- `SlangTexturedNormal` material renders with texture bound at the slot specified
  in its `.layout.json`, not at a hardcoded index slot.
- Legacy GLSL materials continue to work through the fallback path.

Status: not started.

### Phase 4: Unlock Rejected Resource Types

Remove the shared-layout restrictions for set=1 resources.

Once material resources live in their own set, the shared layout policy no longer
needs to reject:

- Split `Texture2D<T>` + `SamplerState` (currently blocked with "does not support
  split Slang Texture*/SamplerState" errors).
- `RWTexture` / storage textures (currently blocked with "does not support storage
  texture" errors).
- Sampler count beyond the shared slot array.

Tasks:

- Remove or gate the rejection logic in `apply_slang_vulkan_shared_layout_policy`
  to only apply to set=0 resources.
- Material shaders in set=1 can use any Slang resource type that the Vulkan
  backend supports.
- Test coverage for split texture + sampler in a material shader.

Acceptance:

- A material shader using `Texture2D<float4> tex` + `SamplerState samp` in set=1
  compiles and renders on Vulkan.
- A material shader using `RWTexture2D<float4>` in set=1 compiles and renders.

Status: not started.

### Phase 5: OpenGL and D3D Compatibility

Ensure the two-set scheme does not break non-Vulkan backends.

Tasks:

- Verify that Slang GLSL output for two-set slangc invocation maps set=1
  resources into a binding range that does not collide with set=0 engine resources.
- Adjust `-fvk-b-shift`, `-fvk-t-shift`, `-fvk-s-shift` flags or add set-specific
  shift ranges.
- Document the generated GLSL binding layout for two-set shaders.
- For D3D11 (future Windows path), verify that `space0` → standard registers,
  `space1` → offset register range.

Acceptance:

- A two-set Slang material compiles to valid GLSL with non-colliding bindings.
- OpenGL smoke renders the material through the GL backend.

Status: not started.

### Phase 6: Remove Shared-Layout Default

After all material shaders use the two-set scheme and the old path has no
active consumers:

Tasks:

- Make two-set the default for `@language slang` `.shader` files.
- Remove `apply_slang_vulkan_shared_layout_policy()`.
- Remove `patch_slang_vulkan_spirv_bindings()`.
- Remove dead code in `termin_shaderc` that infers bindings from regex-based
  source scanning (replaced by reflection).
- Clean up the sampled slot array `{4,5,6,7,9,10,...}`.

Acceptance:

- `termin_shaderc` no longer contains a hardcoded binding map.
- All Slang shaders compile with bindings from their specification/reflection.

Status: not started.

## Risks

- **Vulkan pipeline layout explosion**: Each material shader with a unique set=1
  layout needs its own `VkPipelineLayout`. Modern drivers handle thousands of
  layouts, but descriptor set allocation must be cached. Mitigation: share set=1
  layouts where two shaders have identical material resource signatures.

- **OpenGL binding collision**: Slang GLSL output maps set=1 to a shifted binding
  range. If the range overlaps with engine resources in set=0, the GL backend
  will misbind. Mitigation: choose a large shift offset (e.g., +32 for all set=1
  resources) and validate in smoke tests.

- **Descriptor set allocation overhead**: Currently one descriptor set per frame
  contains all bindings. With two sets, set=0 stays per-frame; set=1 is per-draw
  and needs per-draw allocation. Mitigation: pool/reuse set=1 allocations, or
  use push descriptors for small material UBOs.

- **Existing material shaders**: Current Slang material `.shader` files
  (SlangNormalColor, SlangTexturedNormal) manually declare `per_frame` and
  `draw_data` ConstantBuffers in the stage source without set qualifiers.
  They default to set=0. These need to be updated to either:
  - Move material resources to set=1 (draw_data, material)
  - Or keep everything in set=0 as a compatibility mode
  Decision needed per shader.

## Related Documents

- [Slang bind-by-name runtime](2026-06-09-slang-bind-by-name-runtime.md) —
  long-term symbolic binding API that this plan enables.
- [Slang shader pipeline](2026-06-07-slang-shader-pipeline.md) —
  Slang toolchain and artifact pipeline.
- [Slang shader support](2026-05-25-slang-shader-support-plan.md) —
  initial Slang integration plan.
