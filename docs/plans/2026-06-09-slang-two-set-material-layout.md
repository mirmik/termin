# Shader-Driven Pipeline Layout (Godot-style per-pipeline single-set)

Date: 2026-06-09
Updated: 2026-06-10 — switched from two-set to per-pipeline single-set after review.

## Goal

Replace the fixed shared Vulkan descriptor layout with per-pipeline layouts
derived from shader reflection. The shader declares what it needs; the pipeline
builds its `VkDescriptorSetLayout` to match. No hardcoded binding table.

This is the same architecture Godot 4 uses: a single descriptor set per
pipeline, with binding numbers and types determined by SPIR-V reflection.

## What this unlocks

- Arbitrary UBO/texture binding numbers — shader chooses, not `termin_shaderc`.
- Split `Texture2D<T>` + `SamplerState` — no combined-sampler restriction.
- `RWTexture` / storage textures — not blocked by a shared layout.
- No default-texture fillers — the pipeline only declares what the shader uses.
- Slang material shaders with clean `[[vk::binding(N, 0)]]` or auto-assigned
  bindings.

## Architecture

```
┌──────────────────────────────────────────┐
│ Shader (SPIR-V)                          │
│   OpDecorate %ubo Binding 0              │
│   OpDecorate %tex Binding 4              │
│   OpDecorate %samp Binding 5             │
└──────────────┬───────────────────────────┘
               │ reflect bindings from SPIR-V
               ▼
┌──────────────────────────────────────────┐
│ VkDescriptorSetLayout (per pipeline)     │
│   binding 0: UNIFORM_BUFFER_DYNAMIC      │
│   binding 4: SAMPLED_IMAGE               │
│   binding 5: SAMPLER                     │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│ VkPipelineLayout (1 set)                 │
│   + VkPushConstantRange (128 bytes)      │
└──────────────────────────────────────────┘
```

### Render pass code — unchanged

Engine passes bind resources at numeric slots. The shader declares matching
slots. No `set` parameter anywhere — there is only set=0.

```cpp
ctx2->bind_uniform_buffer_ring(0, &pf, sizeof(pf));     // per_frame
ctx2->bind_uniform_buffer_ring(3, &sb, sizeof(sb));     // shadow_ubo
ctx2->bind_sampled_texture(4, albedo_tex);              // material texture
ctx2->bind_sampled_texture(8, shadow_map, sampler);     // shadow map array
```

Eventually the symbolic binding API (bind-by-name) replaces numeric slots, but
this plan does not require it.

### Slang source convention

Material shaders declare bindings naturally. No forced remapping into a shared
slot array:

```slang
// Engine resources — at the slots the render pass expects
[[vk::binding(0, 0)]]
ConstantBuffer<PerFrame> per_frame;

// Material resources — any binding numbers, no collision with engine
[[vk::binding(0, 0)]]
ConstantBuffer<MaterialParams> material;   // binding 0 in this shader is material, not per_frame

[[vk::binding(1, 0)]]
Texture2D<float4> albedo;

[[vk::binding(2, 0)]]
SamplerState albedo_sampler;
```

Note: `per_frame` and `material` both use `binding(0, 0)` — they are in
**different shader stages** or different pipelines. The pipeline is built
for a specific VS+FS pair; bindings are scoped to that pair.

## Implementation

### Phase 1: Per-pipeline VkDescriptorSetLayout

**Task:** Replace `create_shared_layouts()` with per-pipeline layout creation.

- [ ] `create_shader()` reflects descriptor bindings from SPIR-V bytecode
      (descriptor type, binding number, stage flags). Stored in
      `VkShaderResource::bindings`.

- [ ] `create_pipeline()` collects bindings from VS + FS, merges them into
      one `VkDescriptorSetLayout`, caches layouts by FNV-1a hash.

- [ ] `create_resource_set()` accepts `VkDescriptorSetLayout` parameter.
      Removes all default-texture filler logic. Allocates exactly the
      bindings the caller provides, validated against the layout.

- [ ] `PipelineCacheKey` includes the descriptor layout hash so pipelines
      with different reflection signatures do not collide.

- [ ] Remove: `create_shared_layouts()`, `descriptor_set_layouts_[]`,
      `shared_pipeline_layout_`, `kMaxDescriptorSets`, `set1_layout`,
      `set_count`, `descriptor_set_layout_cache_`.

- [ ] Remove `set` parameter from `RenderContext2::bind_*` methods and
      `ResourceBinding::set` / `ResourceSetDesc::set` field.

**Acceptance:** Existing shaders render through per-pipeline layouts.
A new shader with split `Texture2D` + `SamplerState` compiles and renders.

Status: not started.

### Phase 2: Slang stops using shared layout policy

**Task:** `termin_shaderc` stops forcing Slang resources into the hardcoded
slot table. SPIR-V bindings are left as-is from reflection or specification.

- [ ] Add a `--layout-scheme per-pipeline` flag (default for new shaders).
- [ ] In per-pipeline mode, skip `apply_slang_vulkan_shared_layout_policy()`
      and `patch_slang_vulkan_spirv_bindings()`.
- [ ] Validate no collision: engine-named resources (`per_frame`,
      shadow-related) must not overlap with material resource bindings.

**Acceptance:** Slang material compiles to SPIR-V with its natural binding
numbers. `.layout.json` records them.

Status: not started.

### Phase 3: Runtime material texture binding from layout

**Task:** Passes look up texture binding slots from `tc_shader.resource_bindings[]`
instead of using `material_texture_binding_for_index()`.

Same as the original Phase 3 — unchanged from the previous plan.

Status: not started.

### Phase 4: Unlock rejected resource types

**Task:** Remove shared-layout policy restrictions. Slang material shaders
can use split textures, separate samplers, storage textures.

Status: not started.

### Phase 5: OpenGL compatibility

**Task:** GLSL output from Slang for per-pipeline shaders maps bindings
without the shared layout policy. GLSL has a flat namespace — no set
qualifiers needed. Binding numbers from SPIR-V reflection carry through
to GLSL `layout(binding=N)`.

Status: not started.

### Phase 6: Remove shared-layout default

**Task:** After all shaders use per-pipeline layouts, remove the shared
layout policy code from `termin_shaderc`.

Status: not started.

## Risks

- **Pipeline layout count:** each VS+FS pair with unique bindings produces
  a new `VkDescriptorSetLayout`. Modern drivers handle thousands. Layouts
  with identical binding signatures (same types and numbers) are cached
  and shared. Mitigation: FNV-1a hash of bindings as cache key.

- **OpenGL binding collision:** GLSL has a flat namespace. Two shaders
  that declare `layout(binding=0)` for different things must not be active
  simultaneously. This is already true today.

- **Transition from shared layout:** built-in GLSL shaders currently rely
  on `create_shared_layouts()` filling 25 binding slots. After removal,
  each pipeline declares only its used bindings. Missing bindings become
  visible as Vulkan validation errors instead of silent default-texture
  fallback. This is a feature, not a bug — it catches binding mismatches
  that the shared layout was hiding.

## Design Decision: One set, not two

Reviewed 2026-06-10. After comparing Godot 4 (per-pipeline single-set),
The Forge (three-set), Filament (bindless), and Unreal 5 (moving to
bindless):

- Two descriptor sets provide per-pass engine binding as the sole
  architectural advantage over a single set. This saves one
  `vkCmdBindDescriptorSets` call per pass — negligible.

- Per-pipeline single-set is simpler: fewer abstractions, less code,
  no `set_index` parameter anywhere in the API, OpenGL trivially
  compatible.

- Bindless (descriptor indexing) is the right long-term horizon, but
  requires Vulkan 1.2+ and a larger rework. Single-set is the natural
  stepping stone.

## Related Documents

- [Slang bind-by-name runtime](2026-06-09-slang-bind-by-name-runtime.md) —
  long-term symbolic binding API.
- [Slang shader pipeline](2026-06-07-slang-shader-pipeline.md) —
  Slang toolchain and artifact pipeline.
