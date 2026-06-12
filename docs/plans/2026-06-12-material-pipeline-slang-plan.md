# Material Pipeline Slang Migration Plan

Date: 2026-06-12

## Status

Active plan. This extends the scope-first bind-by-name migration with the
material pipeline, skinned meshes, and foliage variants.

The current engine already has the pieces needed for the target direction:
Slang built-in shaders, sidecar resource metadata, `TerminScope`, runtime
bind-by-name calls, and initial shader-owned vertex input reflection. The
remaining problem is that material rendering still treats vertex stages,
skinning, foliage, material resources, and pass resources as separate legacy
special cases.

## Goal

Make material rendering a single Slang-first pipeline where:

- material shaders describe logical inputs, resources, and entry points;
- renderers bind resources by name through reflected layout metadata;
- vertex transformation is a composable engine contract, not regex source
  injection;
- skinned meshes and foliage are vertex transform variants of the same
  material/pass pipeline;
- authored Slang does not contain backend-specific `[[vk::...]]`,
  `layout(binding=...)`, or fixed register annotations;
- legacy GLSL paths are retired instead of growing new compatibility layers.

## Target Shape

The material pipeline should be built from three contracts:

```text
material contract
  fragment behavior, material parameters, material textures

vertex transform contract
  static mesh, skinned mesh, foliage instancing, later morphs/particles

pass contract
  color, id, depth, shadow, highlight, and postprocess-specific resources
```

A concrete shader variant is assembled from those contracts into ordinary
backend artifacts:

```text
material phase + pass + vertex transform variant
  -> Slang entry points
  -> SPIR-V / backend artifact
  -> .layout.json sidecar
  -> runtime bind-by-name
```

The public runtime model remains:

```cpp
ctx.bind_uniform_data("per_frame", ...);
ctx.bind_uniform_data("material", ...);
ctx.bind_texture("albedo_texture", ...);
ctx.bind_uniform_data("draw_data", ...);
ctx.bind_uniform_data("bone_block", ...);
```

The backend placement is generated metadata. C++ pass and renderer code should
not know Vulkan binding numbers for migrated paths.

## Resource Scopes

Use the same scope vocabulary as the scope-first plan:

| Scope | Material Pipeline Use |
|---|---|
| `frame` | camera matrices, frame timing |
| `pass` | lights, shadow maps, pass params |
| `material` | material UBO and textures |
| `draw` | object transform, bone block, foliage draw data, instance buffers |
| `transient` | pass-local image inputs and scratch textures |

For the current Vulkan backend, these may still be flattened into one
descriptor set. That is an implementation detail. The source, sidecar, and
runtime API should already behave as if scopes are distinct.

## Material Contract

Material shaders should be Slang modules with explicit entry points and
resource declarations:

```slang
import termin_prelude;
import termin_lighting;
import termin_shadows;

struct MaterialParams { ... };

[[TerminScope("material")]]
ConstantBuffer<MaterialParams> material;

[[TerminScope("material")]]
Sampler2D albedo_texture;

[shader("fragment")]
FragmentOutput fs_main(FragmentInput input) { ... }
```

The material system should derive `TcMaterial` parameter layout from sidecar
field metadata. Python-side `set_material_ubo_layout(...)` declarations should
not be required for migrated Slang materials unless they are explicitly loading
old metadata.

## Vertex Transform Contract

Static, skinned, and foliage rendering need a shared logical vertex transform
layer.

Current first step:

- `termin_vertex_transform.slang` defines static and skinned input/output
  structs and helper functions.
- `SkinnedMeshRenderer` binds `bone_block` by name when layout metadata exists.
- `termin_shaderc` maps `bone_block` as draw-scope metadata and prevents it
  from colliding with `draw_data`.

Target next step:

- material variants should select a vertex transform entry point instead of
  injecting or replacing source text;
- the renderer should use shader-owned vertex input reflection for mesh,
  skinning, and foliage instance attributes;
- `shader_skinning.cpp` regex injection should be retired;
- skinning should be expressed as a Slang variant that declares
  `[[TerminScope("draw")]] ConstantBuffer<TerminBoneBlock> bone_block;`.

This is conceptually a stage before the material fragment logic, but it is not
a GPU stage after the vertex shader. It is a source/module composition step
that produces the actual vertex entry point for the selected variant.

## Foliage

Foliage should not remain a renderer-specific alternate ABI. It should become
another vertex transform variant using the same material and pass contracts.

Target foliage shape:

- foliage keeps its component/data ownership as described in
  `2026-05-26-foliage-scatter-system.md`;
- foliage rendering uses the same material phase fragment shader as ordinary
  meshes;
- foliage supplies a vertex transform variant that consumes prototype mesh
  vertices plus instance data;
- foliage resources use names such as `foliage_draw` and
  `foliage_instances`, both in draw scope;
- color, depth, id, and shadow passes bind their own pass resources by name
  and reuse the same foliage transform model;
- no foliage shader should depend on hard-coded backend bindings.

The current direct `draw_tgfx2()` path can stay as the draw-call integration
point, but it should prepare and bind resources through reflected shader layout
metadata. The direct path should not invent a separate material ABI.

## Pass Integration

`ColorPass`, `ShadowPass`, `DepthPass`, and `IdPass` should converge on the
same flow:

1. Select the material phase and pass contract.
2. Select a vertex transform variant: static, skinned, foliage, later more.
3. Ensure the combined shader artifacts and sidecars exist.
4. Bind frame/pass/material/draw resources by logical name.
5. Use shader-owned vertex input reflection for mesh and instance streams.
6. Draw through the backend without renderer-owned binding numbers.

Pass-specific shaders such as shadow-only and id-only variants should still be
Slang modules, but their resources should follow the same scope/name rules.

## Migration Sequence

1. Finish sidecar metadata quality.
   Ensure resource fields include type, offset, size, scope, backend placement,
   and enough vertex input metadata for renderers to build input layouts.

2. Move material parameter application fully to reflected layout.
   Remove Python-authored material UBO layout blocks for migrated Slang
   shaders. Keep explicit errors when a material expects metadata but the
   sidecar is missing.

3. Define the material entry point contract.
   Document required structs, common semantics, and how pass variants connect
   vertex output to fragment input.

4. Replace skinning regex injection.
   Generate or select Slang vertex transform variants and bind `bone_block` by
   name. Remove fixed binding assumptions from the renderer path.

5. Convert foliage to the same variant model.
   `foliage_draw` and `foliage_instances` must be reflected resources. The
   renderer binds them by name and uses reflected vertex input locations for
   prototype and instance streams.

6. Convert remaining material/pass GLSL shaders to Slang.
   Built-in and stdlib shaders should be single Slang modules where vertex and
   fragment entry points belong together when they share a contract.

7. Tighten runtime validation.
   Layout-only Slang shaders should fail loudly when a renderer tries to bind a
   missing name, mismatched kind, or incompatible vertex stream. Numeric
   fallback should be limited to explicitly legacy GLSL paths.

8. Retire dead legacy files and APIs.
   Remove unused GLSL include banks, old material shader variants, hard-coded
   binding constants outside centralized transitional policy, and source
   injection helpers after their users are gone.

9. Later: map scopes to real backend scope layouts.
   Once pass/material code no longer relies on numeric slots, Vulkan can move
   from one flattened set to multiple descriptor sets by scope. OpenGL can keep
   flattening as a backend implementation detail.

## Current Smells To Remove

- `shader_skinning.cpp` edits shader source with regex and encodes a binding
  ABI in generated GLSL.
- Foliage currently has standalone vertex shaders that must manually match
  material fragment varyings.
- Some renderers still know numeric slots or fixed vertex locations.
- Some tests still assert numeric `kind`/`scope` enum values instead of
  symbolic metadata.
- Some material fixtures still call `set_material_ubo_layout(...)` even when
  shader reflection should own the layout.
- GLSL built-in fragments that remain in the runtime catalog pull the engine
  back toward backend-authored layout syntax.

## Non-Goals

- Do not implement a separate foliage material system.
- Do not add a universal global binding table as the new abstraction.
- Do not require true Vulkan multi-set layouts before the bind-by-name
  migration is complete.
- Do not preserve old GLSL fallback paths for newly migrated Slang materials.
- Do not hide missing sidecar metadata by guessing layouts in migrated paths.

## Validation Checklist

- `termin_shaderc` tests cover scope inference, explicit `TerminScope`,
  duplicate binding conflicts, material fields, `bone_block`, and foliage
  resources.
- Built-in shader source tests compile all Slang modules used by the runtime
  catalog.
- Color/depth/id/shadow passes have tests or smoke scenes using static,
  skinned, and foliage draws with the same material.
- Vulkan validation shows no descriptor type mismatch and no missing vertex
  stage/fragment stage interface locations for migrated shaders.
- Runtime logs contain clear errors for missing names, not silent numeric
  fallback.
