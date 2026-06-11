# Slang Scope-First Binding Migration

Date: 2026-06-11

## Decision

Termin should finish the Slang migration against a **scope-first,
bind-by-name** resource model.

The current Vulkan implementation uses a per-pipeline single descriptor set.
That is a valid transitional backend shape, but it is no longer the target
authoring/runtime model. Shader authors and render passes should not encode
backend set/binding numbers. They should describe and bind resources by stable
logical names, while generated layout metadata records each resource's update
scope and backend placement.

## Target Model

Shader resource identity is:

```text
logical name + kind + scope
```

Backend placement is generated metadata:

```text
Vulkan: (set, binding)
OpenGL: flat binding
D3D11: register class/index
```

The expected scopes are:

| Scope | Lifetime | Examples |
|---|---|---|
| `frame` | camera/frame constants | `per_frame` |
| `pass` | pass-wide resources | `lighting`, `shadow_block`, `shadow_maps` |
| `material` | material/phase resources | `material`, `albedo_texture`, `normal_texture` |
| `draw` | per-object/per-draw resources | `draw_data`, large object buffers |
| `transient` | pass-local scratch resources | fullscreen input/output textures |

Push constants remain the preferred path for small per-draw payloads that fit
within the 128-byte portability budget. Larger or backend-incompatible draw
data belongs in `draw` scope.

## Why Scope Before Multiple Sets

Moving all remaining code to bind-by-name while keeping one undifferentiated
resource bucket would preserve the wrong mental model: frame, pass, material,
and draw resources would still be rebuilt and rebound together.

Adding full Vulkan multiple descriptor sets first would also be too large a
step. It touches pipeline layout construction, descriptor set layout caches,
resource set allocation, command binding order, OpenGL flattening, tests, and
all active render passes at once.

The chosen sequence is therefore:

1. Add scope to shader layout metadata and runtime binding structures.
2. Split `RenderContext2` pending/dirty state by scope.
3. Keep Vulkan flattened to the current single set initially.
4. Migrate passes/materials to bind by name and scope-aware metadata.
5. Later map scopes to multiple Vulkan descriptor sets mechanically.

## Compatibility With Bind-By-Name

Bind-by-name remains the public API:

```cpp
ctx.bind_uniform("per_frame", per_frame_buffer);
ctx.bind_texture("albedo_texture", albedo);
```

The active shader layout resolves each name to kind, scope, and backend
placement. Callers should not pass numeric slots for migrated code paths.

Missing names, kind mismatches, and scope/backend layout mismatches must log
clear errors. Migrated Slang shaders marked artifact-required should fail
loudly when layout metadata is absent.

## Current State

- Author-authored `.slang` files should remain free of `[[vk::...]]` and
  `register(...)`.
- `termin_shaderc` emits `.layout.json` resource metadata beside generated
  artifacts.
- `tc_shader` can carry resource layout metadata loaded from sidecars.
- Scope metadata has been added to `tc_shader_resource_binding`, Python
  bindings, and generated `.layout.json` sidecars. Old sidecars without
  `scope` are still accepted and classified by conservative name/kind
  inference.
- `RenderContext2` already has initial symbolic binding methods.
- `RenderContext2` pending numeric/symbolic bindings are internally grouped
  by scope, then flattened back into the existing `ResourceSetDesc` backend
  shape at flush time.
- Grayscale, tonemap, and bloom use name-based bindings for their Slang
  post-process resources.
- Material/color rendering still contains numeric binding ABI for per-frame,
  shadows, material UBO/textures, and draw data.
- Vulkan currently builds one descriptor set layout per pipeline from SPIR-V
  reflection.

## Immediate Tasks

1. Broaden or replace default scope inference for known engine names:
   `per_frame -> frame`, lighting/shadows -> pass, `material` and material
   textures -> material, `draw_data` -> draw.
2. Add dirty-per-scope tracking on top of the scoped buckets. Existing backends
   may still receive a flattened resource set until Vulkan scoped sets land.
3. Update Slang/material generation so generated resource declarations do not
   encode Vulkan-only attributes. Push-constant use must become metadata or a
   backend-specific artifact decision, not authored/generated Slang source
   magic.
4. Migrate `ColorPass` and material UBO/texture binding to name-first lookup.
   Numeric fallback remains only for legacy GLSL paths.
5. Add validation for duplicate backend bindings with incompatible resource
   type/count/stage.
6. After the above is stable, introduce multiple Vulkan descriptor set layouts
   by scope and bind only dirty scopes.

## Retired Direction

The old two-set-vs-single-set debate is retired as a frontend/API decision.
Single-set remains an implementation detail of the current Vulkan backend.
Multiple Vulkan sets are useful as a later optimization and lifetime model
implementation, not as shader authoring syntax.

Do not revive a universal binding table or require Slang sources to carry
backend layout annotations.
