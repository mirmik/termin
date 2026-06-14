# Material Pipeline Slang Migration Plan

Date: 2026-06-12

## Status

Active plan. This extends the scope-first bind-by-name migration with the
material pipeline, skinned meshes, and foliage variants.

Current implementation checkpoint:

- `termin/render/material_pipeline.hpp` provides the first shared resource
  binding and shader preparation helpers for material draws.
- `ColorPass` uses that helper for ordinary mesh material resources and the
  direct drawable tgfx2 material path.
- `ColorPass.extra_textures` now binds graph textures by reflected shader
  resource name instead of allocating backend texture slots.
- `DepthPass`, `DepthOnlyPass`, `IdPass`, `ShadowPass`, and `NormalPass` use
  the same helper for shader preparation and their pass/draw named uniform
  payloads.
- `MaterialPass` uses the material pipeline helper for shader preparation,
  per-frame data, material UBO/textures, and bind-by-name graph inputs.
- `termin/render/material_pipeline.hpp` also owns shared vertex variant
  assembly through `MaterialVertexVariantRequest` /
  `get_material_vertex_variant()`. Skinned and foliage variants now use this
  common path instead of renderer-local shader assembly code.
- `FoliageLayerComponent` prepares instanced foliage shader variants and
  material resources through the same helper; foliage-specific draw resources
  still bind explicitly by logical name.
- `LineRenderer` has the first `WorldTube` integration slice: tube body/cap
  material variants now combine the procedural line vertex contract with the
  material fragment contract, and `tgfx2::WorldTubeLineRenderer` accepts
  caller-owned shader/layout/resource binding instead of forcing an internal
  line shader layout for material draws.
- Migrated Slang material shaders and Slang vertex-transform variants no
  longer receive parser-authored `material_ubo_entries`. The runtime material
  layout for Slang is expected to come from shaderc sidecar field metadata;
  parser-authored GLSL layouts now use compact resource metadata instead of
  the removed fixed-slot policy.
- `SkinnedMeshRenderer` ownership moved from `termin-app` to
  `termin-components-render`; the old `termin._native.render` binding is now a
  compatibility alias to the canonical render-components native class.
- Legacy `shader_skinning` ownership moved out of `termin-render-passes` and
  into `termin-components-render` with the renderer that still uses it.
- Slang skinning now uses engine-authored vertex transform templates for
  material, shadow, depth, id, and normal variants. `SkinnedMeshRenderer`
  selects the template by phase/pass, keeps the original fragment stage, binds
  `bone_block` by reflected draw-scope name, and avoids creating variants of
  variants.
- Skinned pass-only draws use shader-owned vertex input reflection, so compact
  pass shaders can declare only the inputs they consume instead of depending on
  full material vertex locations.
- Material pass mesh input selection is centralized in `termin-render` through
  `MaterialMeshVertexInput` / `draw_material_pipeline_mesh()`. Pass code now
  requests logical contracts such as full material, position-only, or
  position+normal; the transitional standard-location ABI is isolated in the
  material pipeline helper.
- The material pipeline helper lives in `termin-render`, not
  `termin-render-passes`, so lower component renderers can share it without
  depending on concrete pass modules.
- Regex-based skinning injection has been removed. Skinned variants are
  Slang-template variants and old GLSL shaders must migrate instead of getting
  generated auto-skinning code.

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
- GLSL compatibility paths are retired instead of growing new compatibility layers.

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

Current checkpoint:

- `termin_vertex_transform.slang` defines static and skinned input/output
  structs and helper functions, including reusable skinned position/normal
  transforms.
- `SkinnedMeshRenderer` binds `bone_block` by name when layout metadata exists.
- `termin_shaderc` maps `bone_block` as draw-scope metadata and prevents it
  from colliding with `draw_data`.
- `SkinnedMeshRenderer` now lives in `termin-components-render`.
- Built-in Slang skinning templates cover material, shadow, depth, id, and
  normal passes. They replace only the vertex stage and preserve the selected
  material/pass fragment stage.
- Pass-specific skinned mesh paths opt into shader-owned vertex input mapping,
  so `position/joints/weights` and `position/normal/joints/weights` compact
  shaders do not need to fake unused material inputs.
- Pass code now requests logical mesh input contracts through
  `MaterialMeshVertexInput`; skinned variants are selected from shader variant
  metadata instead of each pass spelling out `position/joints/weights` location
  lists.

Current remaining step:

- move static mesh material variants into the same material-pipeline assembly
  point, so the shared mechanism covers static, skinned, foliage, and later
  morph/particle vertex transform variants;
- replace the centralized standard-location mesh ABI with semantic vertex
  layout metadata, so the renderer can build mesh, skinning, and foliage
  instance inputs from reflected names instead of numeric locations;
- legacy `shader_skinning.cpp` regex injection is retired; skinned variants
  now require Slang templates and shaderc-reflected resources.

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

Current checkpoint:

- foliage material/shadow vertex variants are assembled by
  `get_material_vertex_variant()` using engine-authored foliage templates and
  the selected material/pass fragment stage;
- `foliage_draw` and `foliage_instances` are still bound explicitly by logical
  name in `FoliageLayerComponent`, because the component owns instance buffers
  and direct draw submission;
- remaining work is to make foliage vertex input layout fully reflection-owned
  and to converge pass integration with static/skinned draw flows.

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
   Status: Slang material/pass skinning variants now select engine-authored
   vertex transform templates through `get_material_vertex_variant()` and bind
   `bone_block` by name. The old GLSL skinning injector is gone.

5. Convert foliage to the same variant model.
   Status: foliage material/shadow variants now use the shared material vertex
   variant helper. Remaining work: use reflected vertex input locations for
   prototype and instance streams, and reduce direct renderer-specific binding
   code where the common pass flow can own it.

6. Convert remaining material/pass GLSL shaders to Slang.
   Built-in and stdlib shaders should be single Slang modules where vertex and
   fragment entry points belong together when they share a contract.

7. Tighten runtime validation.
   Layout-only Slang shaders should fail loudly when a renderer tries to bind a
   missing name, mismatched kind, or incompatible vertex stream. Numeric
   fallback is no longer part of the material pipeline contract.

8. Replace centralized standard vertex-location policy with semantic mesh
   layout metadata.
   Status: pass-local `{0}` / `{0,4,5}` lists have moved into
   `MaterialMeshVertexInput`, but the final shape should derive compact draw
   layouts from mesh attribute names plus shader reflection.

9. Retire dead legacy files and APIs.
   Remove unused GLSL include banks, old material shader variants, hard-coded
   binding constants outside centralized transitional policy, and source
   injection helpers after their users are gone.

9. Later: map scopes to real backend scope layouts.
   Once pass/material code no longer relies on numeric slots, Vulkan can move
   from one flattened set to multiple descriptor sets by scope. OpenGL can keep
   flattening as a backend implementation detail.
   Status: `termin_shaderc` now preserves Slang-reflected placement. The old
   fixed-slot rewrite mode has been removed from the compiler.

## Current Smells To Remove

- Static MeshRenderer material flow still needs to use the same
  material-pipeline assembly point as skinned and foliage variants.
- Foliage still owns direct draw/resource binding glue for instance data; this
  is narrower than the old renderer-specific shader assembly path but still a
  separate integration path.
- `WorldBillboard` line rendering still uses the older fragment-only variant
  path; `WorldTube` is the first line mode moved toward combined material
  variants.
- Some renderers still know fixed vertex locations directly instead of deriving
  them from reflected mesh/shader metadata.
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
