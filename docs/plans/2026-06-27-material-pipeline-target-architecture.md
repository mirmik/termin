# Material Pipeline Target Architecture

Date: 2026-06-27

## Status

Superseded by `2026-06-27-shader-contract-material-pipeline-architecture.md`
for the runtime contract model.

This document supersedes the transitional parts of
`2026-06-12-material-pipeline-slang-plan.md` for implementation planning. The
older plan correctly defines the direction: material rendering should be built
from material, vertex transform, and pass contracts. The current codebase only
implements helper functions around that idea. This plan turns the direction into
a concrete migration.

The immediate foliage regression is not the target. A local patch that only
filters one conflicting binding would keep the broken architecture alive. The
goal is to replace the transitional variant path with a real material pipeline
assembly layer.

## Problem Statement

Current rendering has useful pieces, but not a real material pipeline:

- `ensure_material_pipeline_shader()` binds a shader and selects reflected
  resource layout, but it does not know why the shader exists.
- `prepare_material_pipeline_resources()` binds common resources by name, but it
  does not own a complete binding contract.
- `get_material_vertex_variant()` swaps a vertex stage template with the
  original fragment stage, then manually seeds resource layout metadata.
- Skinned, foliage, line, and pass-specific paths decide their own shader
  variants and vertex inputs before entering the helper layer.
- Resource layout merge is not ownership-aware. It copies the original shader
  resources and then appends variant resources, which makes `draw_data`,
  `shadow_draw`, `normal_draw`, `foliage_draw`, and similar draw-scope resources
  collide.
- Vertex/fragment interface compatibility is an implicit convention instead of
  a validated contract.

The result is a set of helpers that look like a pipeline from the call sites,
but still behave as renderer-local special cases.

## Target Model

The material pipeline assembles one draw shader from three contracts:

```text
MaterialContract
  fragment behavior, material parameters, material textures, material features

VertexTransformContract
  static mesh, skinned mesh, foliage instances, line tube, later particles/morphs

PassContract
  color, shadow, depth, id, normal, highlight, postprocess-specific needs
```

The pipeline should produce:

```text
MaterialPipelineVariant
  TcShader shader
  MaterialPipelineLayout layout
  VertexStreamPlan vertex_streams
  ResourceBindingPlan resources
  MaterialPipelineDiagnostics diagnostics
```

The public renderer model remains bind-by-name:

```cpp
ctx.bind_uniform_data("per_frame", ...);
ctx.bind_uniform_data("material", ...);
ctx.bind_texture("u_albedo_texture", ...);
ctx.bind_uniform_data("draw_data", ...);
ctx.bind_uniform_data("bone_block", ...);
ctx.bind_storage_buffer("foliage_instances", ...);
```

Backend binding numbers, descriptor sets, register spaces, dynamic offsets, and
layout flattening are backend metadata. Pass/component code must not infer them.

## Contract Definitions

### MaterialContract

Owns fragment-stage material behavior.

Initial fields:

```cpp
struct MaterialContract {
    tc_material_phase* phase = nullptr;
    TcShader shader;
    std::string debug_name;
    std::string fragment_entry;
    MaterialFragmentInterface fragment_input;
    std::vector<PipelineResourceDecl> resources;
    tc_shader_feature_mask features = 0;
};
```

Responsibilities:

- provide the fragment source/module/entry point;
- describe material UBO fields and material textures from shaderc sidecar
  metadata;
- declare fragment input requirements by semantic name and type;
- declare material-scope resources only;
- never declare draw-scope transform resources such as `draw_data`,
  `bone_block`, or `foliage_draw`.

The current `tc_material_phase` remains the authoring/runtime carrier during
the migration. The new contract is an extracted view over it.

### VertexTransformContract

Owns vertex-stage transform behavior.

Initial fields:

```cpp
enum class VertexTransformKind {
    StaticMesh,
    SkinnedMesh,
    Foliage,
    FoliageShadow,
    WorldTubeLine,
};

struct VertexTransformContract {
    VertexTransformKind kind;
    std::string template_uuid;
    std::string vertex_entry;
    VertexInputContract vertex_inputs;
    MaterialFragmentInterface produced_fragment_input;
    std::vector<PipelineResourceDecl> resources;
    std::vector<InstanceStreamDecl> instance_streams;
};
```

Responsibilities:

- provide the vertex source/module/entry point;
- declare required mesh semantics: `position`, `normal`, `uv`, `tangent`,
  `joints`, `weights`, and future names;
- declare instance streams or storage-buffer instance data;
- declare draw-scope resources owned by the transform, such as `draw_data`,
  `bone_block`, `foliage_draw`, `foliage_instances`;
- declare the fragment input interface it produces.

Important rule: vertex transform resources replace the original vertex-stage
draw resources. They are not appended after blindly copying the original shader
layout.

### PassContract

Owns pass-level resources and pass-specific shader behavior.

Initial fields:

```cpp
enum class MaterialPassKind {
    Color,
    Shadow,
    Depth,
    DepthOnly,
    Id,
    Normal,
};

struct PassContract {
    MaterialPassKind kind;
    std::string phase_mark;
    std::string debug_name;
    std::optional<FragmentOverride> fragment_override;
    std::vector<PipelineResourceDecl> resources;
    std::vector<PipelineResourceDecl> draw_resources;
    VertexOutputRequirement vertex_output;
};
```

Responsibilities:

- declare frame/pass resources such as `per_frame`, lighting, shadow maps, id
  payloads, normal pass data, and pass-local transient textures;
- optionally provide a fragment override for shadow/depth/id-only variants;
- describe which vertex output semantics the pass needs;
- never rely on fixed shader binding numbers.

For color passes, the pass usually keeps the material fragment. For shadow,
depth, id, and normal passes, the pass may choose a compact pass fragment or an
empty fragment, but that choice is explicit in the contract.

## Resource Ownership And Merge Rules

Resource layout assembly must be deterministic and ownership-aware.

Each `PipelineResourceDecl` must include:

```cpp
struct PipelineResourceDecl {
    std::string name;
    ResourceKind kind;
    ResourceScope scope;
    ShaderStageMask stages;
    ResourceOwner owner;
    std::optional<uint32_t> logical_size;
    std::optional<ResourcePlacement> reflected_placement;
};
```

Owners:

```text
material
vertex_transform
pass
runtime_backend
legacy_glsl
```

Merge rules:

1. Same name/kind/scope from multiple owners is allowed only when the declaration
   is semantically shared and stage masks can be ORed. Example: `per_frame`
   needed by vertex and fragment stages.
2. Same backend placement with different names is an error. The assembler should
   report both owners and resources.
3. Same name with different kind or scope is an error.
4. Draw-scope resources from the source material vertex stage are discarded when
   a non-static vertex transform replaces that stage.
5. Material-scope resources from the material fragment are preserved.
6. Pass resources are merged after material and vertex transform resources.
7. Legacy GLSL fixed slots may exist only behind an explicit `legacy_glsl`
   owner and cannot satisfy migrated Slang contracts.

This replaces the current "copy original resource layout, append variant
resources" behavior.

## Shader Assembly

The first implementation can still call `tc_shader_from_sources_with_entries_ex`.
The difference is that the call is driven by contracts:

```cpp
MaterialPipelineVariantRequest request {
    .material = material_contract,
    .vertex_transform = vertex_transform_contract,
    .pass = pass_contract,
    .artifact_policy = TC_SHADER_ARTIFACT_REQUIRED,
};

MaterialPipelineVariant variant = material_pipeline_get_variant(request);
```

Short-term assembly:

```text
vertex source  = VertexTransformContract template source
fragment source =
  PassContract fragment override if present
  else MaterialContract fragment source
geometry source = rejected until a real contract exists
```

Long-term assembly:

```text
Slang modules + selected entry points + generated adapter module
```

The long-term form allows the pipeline to generate small adapter functions
instead of relying on all templates to manually match every material fragment
input shape.

### Implemented modular mesh vertex stages (2026-07-12 through 2026-07-17)

The shadow pass introduced this boundary for static and skinned casters:

```text
static/skinned transform provider
  + shadow vertex-output adapter
  -> deterministic imported Slang entry-point glue
```

`VertexTransformProvider` records its imported module and source identity,
mesh/instance inputs, transform-owned resources, and world-space semantics.
`VertexOutputAdapter` records its module/source identity, the world semantics
it consumes, clip/output semantics, and pass-owned resources. The assembler
merges material, provider, adapter, and pass contracts, and includes both
module identities in the shader intent fingerprint. Runtime Slang dependency
tracking then includes transitive imports in the artifact fingerprint.

The completed mesh migration uses one `termin_vertex_transform` module for
static and skinned material, position-only, and position+normal profiles.
`bone_block` is declared once by that transform module. Material, shadow,
depth, id, and normal projection/output behavior lives in pass-owned output
adapter modules, and their `per_frame` and draw resources remain pass-owned in
the contract. Compact depth/id inputs and the position+normal normal-pass input
remain explicit profiles rather than separate whole-stage shaders.

The five `termin-engine-skinned-*` whole-stage templates and the shadow-only
static/skinned provider wrappers were removed. Mesh assembly no longer falls
back to a pass-specific `template_uuid`; foliage remains the only transitional
whole-stage transform family and is tracked separately by #345/#346.

## Interface Contracts

The pipeline needs explicit vertex/fragment interface metadata.

Initial standard interface:

```text
world_pos         float3
normal_world      float3
uv                float2
tangent_world     float3
bitangent_world   float3
tbn_valid         float
```

Validation:

- every fragment input required by `MaterialContract` must be produced by
  `VertexTransformContract` or by a generated adapter;
- pass-specific fragment overrides declare their own requirements;
- missing semantics fail variant assembly with a clear diagnostic;
- extra produced semantics are allowed;
- type mismatch fails assembly.

The current foliage contract depends on this standard interface. That is valid
for migrated standard materials such as CookTorrancePBR, but not for arbitrary
custom material vertex/fragment contracts. The pipeline must make that boundary
explicit.

## Vertex Input And Draw Plan

`MaterialPipelineVariant` must include a draw plan:

```cpp
struct VertexStreamPlan {
    std::vector<MeshAttributeRequirement> mesh_attributes;
    std::vector<InstanceStreamRequirement> instance_attributes;
    std::vector<StorageBufferRequirement> storage_buffers;
};
```

This replaces transitional enums such as `MaterialMeshVertexInput` as the source
of truth. The enum may remain as an adapter while passes migrate.

Rules:

- mesh attributes are resolved by semantic name, not fixed location;
- compact shadow/depth/id shaders request only the attributes they consume;
- skinned variants request `joints` and `weights` by semantic;
- foliage variants request prototype mesh attributes plus instance storage;
- missing required attributes fail before draw submission.

## Runtime Binding Plan

Resource binding should move from pass-local ad hoc code to a plan-driven
binder.

Initial API shape:

```cpp
struct MaterialPipelineBindContext {
    EnginePerFrameStd140* per_frame = nullptr;
    MaterialData* material = nullptr;
    DrawDataProvider* draw = nullptr;
    PassDataProvider* pass = nullptr;
    InstanceDataProvider* instances = nullptr;
};

bool material_pipeline_bind_resources(
    tgfx::RenderContext2& ctx,
    const MaterialPipelineVariant& variant,
    const MaterialPipelineBindContext& context);
```

The provider objects can be thin adapters at first. The important part is that
binding is driven by `variant.resources`, not by each pass guessing which names
exist.

Examples:

- static mesh draw provider binds `draw_data`;
- skinned draw provider binds `draw_data` and `bone_block`;
- foliage draw provider binds `foliage_draw` and `foliage_instances`;
- shadow pass provider binds `per_frame` and shadow pass draw payloads only when
  the selected pass contract declares them.

## Foliage Target Shape

Foliage remains a direct draw integration point initially, but it stops owning
shader assembly details.

Current direct responsibilities to keep:

- owns `FoliageData`;
- owns instance buffer upload/cache;
- issues `draw_indexed_instanced`;
- supplies `FoliageDrawData` and `foliage_instances` provider data.

Responsibilities to move into material pipeline:

- variant selection;
- vertex template selection;
- resource layout assembly;
- fragment input compatibility validation;
- vertex stream plan;
- pass contract compatibility.

Short-term:

```cpp
FoliageLayerComponent
  -> request MaterialPipelineVariant(kind=Foliage, pass=Color/Shadow/...)
  -> upload/cache instance data
  -> material_pipeline_bind_resources(...)
  -> draw_indexed_instanced(...)
```

Long-term:

Foliage direct draw should be just another draw executor using a
`MaterialPipelineDrawPacket`.

## Skinned Mesh Target Shape

Skinned mesh should become the reference migration path because it already uses
engine-authored Slang templates successfully.

Move from:

```text
SkinnedMeshRenderer::override_shader()
  -> get_skinned_shader()
  -> get_material_vertex_variant()
```

To:

```text
SkinnedMeshRenderer
  -> request MaterialPipelineVariant(kind=SkinnedMesh, pass=current)
  -> provide bone_block draw data
```

The skinned templates and `termin_vertex_transform.slang` can stay. The
important change is ownership: the pipeline assembler owns resource merge and
interface validation.

## Static Mesh Target Shape

Static mesh should not be a special case outside the pipeline.

The static vertex transform contract should describe the current standard mesh
material vertex behavior. It can use either:

- the original material vertex stage while legacy materials remain; or
- a standard engine static vertex template for migrated Slang materials.

The target is a standard engine static transform module that produces the same
interface as skinned and foliage transforms. Custom vertex material contracts
must be represented explicitly, not smuggled through "use original vertex
source" behavior.

## Pass Migration

Each pass should request a variant through the same API.

Color:

- material fragment normally preserved;
- pass resources: frame, lighting, shadow maps, transient graph inputs;
- vertex transform selected by drawable/component.

Shadow:

- pass fragment override or empty fragment;
- vertex transform selected by drawable/component;
- shadow draw resources declared by the pass or transform contract, not copied
  from unrelated original vertex layout.

Depth/DepthOnly:

- compact pass fragment or no fragment as backend allows;
- compact vertex input plan;
- no material textures unless explicitly required.

Id:

- pass-owned id payload;
- compact vertex input plan;
- no material UBO unless explicitly part of the selected id material contract.

Normal:

- pass-owned normal output contract;
- position+normal mesh requirements;
- skinned normal transform uses `bone_block`.

## Proposed Module Layout

Add to `termin-render`:

```text
include/termin/render/material_pipeline_contracts.hpp
include/termin/render/material_pipeline_variant.hpp
include/termin/render/material_pipeline_binder.hpp
include/termin/render/vertex_transform_contracts.hpp

src/material_pipeline_contracts.cpp
src/material_pipeline_variant.cpp
src/material_pipeline_binder.cpp
src/vertex_transform_contracts.cpp
```

Keep `material_pipeline.hpp` as a compatibility facade during migration. It
should eventually re-export the new API or disappear.

Do not put the assembler in `termin-render-passes`. Component renderers such as
foliage and skinned mesh must be able to use it without depending on pass
modules.

## Migration Phases

### Phase 0: Freeze The Transitional Boundary

Goals:

- document current helpers as transitional;
- stop adding renderer-specific layout seed fixes;
- add diagnostics around existing resource conflicts so failures explain the
  missing architecture.

Deliverables:

- this plan;
- a taskboard note linking the plan to foliage/material pipeline work;
- no production behavior change required.

### Phase 1: Add Contract Types And Diagnostics

Goals:

- introduce contract structs without replacing draw paths;
- add `MaterialPipelineDiagnostic` objects with structured error codes;
- add resource owner and interface semantic types.

Deliverables:

- new headers and tests for resource merge validation;
- no pass migration yet.

Tests:

- merge same resource name/kind/scope succeeds;
- merge same placement/different name fails;
- draw-scope replacement rule fails if both old and new owners claim the same
  draw semantic;
- diagnostics include owner, scope, kind, and debug name.

### Phase 2: Build The Variant Assembler

Goals:

- implement `material_pipeline_get_variant(request)`;
- keep using existing shader source creation under the hood;
- replace manual resource layout seeding with contract-owned resource assembly;
- cache variants by material shader generation, pass contract id, and vertex
  transform contract id.

Deliverables:

- assembler API;
- source combination path;
- resource layout assembly from contracts;
- sidecar/reflection ingestion where available.

Tests:

- static color variant preserves material resources;
- skinned color variant adds `bone_block`;
- foliage color variant adds `foliage_draw` and `foliage_instances` without
  inheriting `draw_data`;
- shadow foliage variant does not inherit `shadow_draw` unless its selected
  contract owns it.

### Phase 3: Introduce Vertex Transform Registry

Goals:

- register built-in transform contracts: static, skinned, foliage, foliage
  shadow;
- centralize template uuid, entry point, vertex input, produced interface, and
  draw resources.

Deliverables:

- `get_builtin_vertex_transform_contract(kind, pass_kind)`;
- reflection-aware vertex stream plan builder;
- compatibility adapter from `MaterialMeshVertexInput`.

Tests:

- static/skinned/foliage transform contracts declare expected mesh semantics;
- foliage contract declares instance storage;
- compact shadow/depth/id contracts request compact input sets.

### Phase 4: Migrate Skinned Mesh

Goals:

- move `get_skinned_shader()` behavior onto the new assembler;
- keep public component behavior stable;
- make `bone_block` binding plan-driven.

Deliverables:

- `SkinnedMeshRenderer` requests a `SkinnedMesh` transform variant;
- bone matrices are carried by the typed mesh RenderItem and bound by the
  shared mesh encoder; the old `upload_per_draw_uniforms_tgfx2()` callback is
  removed;
- old `get_skinned_shader()` becomes compatibility wrapper or is removed after
  callers migrate.

Tests:

- existing skinned variant tests updated to assert contract output;
- skinned material/shadow/depth/id/normal variants assemble through one API;
- no regex/source injection path returns.

### Phase 5: Migrate Foliage

Goals:

- move foliage variant assembly out of `FoliageLayerComponent`;
- keep instance upload and direct indexed instanced draw in the component for
  now;
- bind foliage resources via pipeline resource plan.

Deliverables:

- foliage draw requests `Foliage` or `FoliageShadow` transform;
- foliage direct draw uses `MaterialPipelineVariant` and `VertexStreamPlan`;
- component provides `foliage_draw` and `foliage_instances` data only.

Tests:

- CookTorrancePBR foliage color variant assembles without resource conflicts;
- foliage shadow variant assembles without resource conflicts;
- missing prototype mesh semantic logs a contract validation error;
- material fragment requiring unsupported input fails before draw.

### Phase 6: Migrate Static Mesh And Passes

Goals:

- ordinary `MeshRenderer` also requests a static transform variant;
- color/shadow/depth/id/normal passes stop selecting shader resources locally;
- pass-specific resources become `PassContract` providers.

Deliverables:

- `ColorPass`, `ShadowPass`, `DepthPass`, `IdPass`, `NormalPass` use
  `material_pipeline_get_variant`;
- `prepare_material_pipeline_resources()` becomes an implementation detail of
  the binder or is removed.

Tests:

- one material renders through static, skinned, and foliage paths;
- same material works in color and shadow;
- pass-specific compact variants do not require unused mesh attributes.

### Phase 7: Remove Transitional APIs

Goals:

- remove `get_material_vertex_variant()` or reduce it to a test-only wrapper;
- remove `MaterialMeshVertexInput` as source of truth;
- remove manual fixed-binding seed code from migrated paths;
- isolate or delete legacy GLSL compatibility.

Deliverables:

- production paths use contract assembly;
- old helpers either gone or explicitly named `legacy`.

Tests:

- no migrated Slang path depends on parser-authored fixed GLSL bindings;
- no pass/component code hardcodes backend binding numbers for material draws;
- shader compilation path does not infer scope or placement from magic resource
  names for migrated Slang paths.

## Validation Gates

Every phase that changes production rendering must pass:

- targeted C++ tests for the changed module;
- shaderc tests for resource/scope metadata affected by the phase;
- `termin_render_passes_builtin_shader_sources_test`;
- at least one local smoke scene for static mesh, skinned mesh, and foliage when
  the phase touches draw behavior;
- `./run-tests.sh` before moving broad migration work to test/merge.

Additional smoke goals before closing the migration:

- static + skinned + foliage using the same CookTorrancePBR material;
- color + shadow + depth/id/normal coverage for at least static and skinned;
- foliage color + shadow coverage;
- Vulkan validation with no descriptor mismatch;
- D3D11 smoke once backend storage/dynamic-offset policy is clear.

## Taskboard Links

Known related tasks:

- `#1 [render] Разобраться с foliage shadow artifacts`
- `#20 [render] Retire legacy GLSL compatibility bindings`
- `#85 [graphics/shaders] Убрать magic names из shader compilation paths`
- `#89 [graphics/d3d11] Закрыть backend parity после добавления D3D11`

The material pipeline rewrite should either update these cards as work lands or
spawn a dedicated umbrella card if the migration becomes too large for the
existing tasks.

## Non-Goals

- Do not patch the current foliage crash by adding more special-case binding
  filters.
- Do not create a separate foliage material system.
- Do not resurrect regex-based skinning or GLSL auto-skinning.
- Do not make a global fixed binding table the new abstraction.
- Do not require true multi-descriptor-set Vulkan layout before the logical
  contract migration is complete.
- Do not silently guess missing sidecar metadata in migrated Slang paths.

## First Implementation Slice

Start with a non-rendering slice:

1. Add contract/diagnostic/resource merge types in `termin-render`.
2. Add tests for ownership-aware resource merge.
3. Add built-in transform contract declarations for static, skinned, foliage.
4. Add a variant assembler test that creates a foliage material variant without
   drawing it.

This slice proves the architecture without touching pass execution. After it is
green, migrate skinned mesh first because it is already closest to the target
model and has narrower runtime behavior than foliage.
