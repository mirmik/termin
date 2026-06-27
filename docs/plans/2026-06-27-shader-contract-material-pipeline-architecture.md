# Shader Contract Material Pipeline Architecture

Date: 2026-06-27

## Status

Active target architecture. This document supersedes the runtime
`MaterialPipelineVariant` model described in
`2026-06-27-material-pipeline-target-architecture.md`.

The important correction is that runtime draw paths should not look up a
material-pipeline-specific variant after shader override. Shader override stays
the C protocol and returns `tc_shader_handle`.

The selected `tc_shader` carries two different pieces of runtime metadata:

- `tc_shader_contract`: backend-agnostic shader interface requirements;
- shader resource layout: resolved backend/runtime placement for those
  resources.

The contract is not a render-pass or draw-submission object. Draw intent remains
owned by the pass/component path that asked for the shader.

## Core Decision

The material pipeline assembler produces:

```text
MaterialContract
+ VertexTransformContract
+ PassContract
      |
      v
tc_shader
+ tc_shader_contract
```

The runtime path consumes:

```text
tc_component_override_shader(...)
      |
      v
tc_shader_handle
      |
      +--> tc_shader_contract         // validate required inputs/resources
      |
      +--> shader resource layout     // bind resolved backend placements
      |
      v
pass-owned draw/dispatch
```

There is no runtime `material_pipeline_variant_from_shader_contract()` lookup.
If the shader contract and resource layout are complete, the selected pass has
enough information to validate and bind the shader without knowing which
assembler produced it.

## Layer Ownership

### `tc_shader`

`tc_shader` is the shader identity and runtime shader object. It may reference
an optional generic `tc_shader_contract` and a resolved resource layout.

It must not know about:

- material pipeline variants;
- material/pass/vertex-transform contracts;
- drawable providers;
- concrete render passes;
- mesh/fullscreen/compute draw policy.

It may know:

- source, entry points, language, artifact policy;
- compiled/reflected resource layout;
- variant identity and original shader relation;
- optional shader interface contract.

### `tc_shader_contract`

`tc_shader_contract` is a C ABI shader interface contract for the final shader
program. It describes what the shader requires from its caller. It does not
describe why the shader exists, which pass will draw it, or how a backend places
the resources.

Target data:

```c
typedef struct tc_shader_contract_vertex_input {
    char semantic[TC_SHADER_RESOURCE_NAME_MAX];
    uint32_t type;
    uint32_t required;
} tc_shader_contract_vertex_input;

typedef struct tc_shader_resource_requirement {
    char name[TC_SHADER_RESOURCE_NAME_MAX];
    uint32_t kind;
    uint32_t scope;
    uint32_t stage_mask;
    uint32_t size;
    const tc_shader_resource_field* fields;
    uint32_t field_count;
} tc_shader_resource_requirement;

typedef struct tc_shader_contract_view {
    uint32_t schema_version;
    uint32_t source_kind;
    tc_shader_handle shader;

    const tc_shader_contract_vertex_input* vertex_inputs;
    uint32_t vertex_input_count;

    const tc_shader_resource_requirement* resources;
    uint32_t resource_count;

    const char* debug_name;
    const char* source_debug_name;
} tc_shader_contract_view;
```

The exact structs may evolve, but the contract must stay generic:

- vertex input requirements;
- shader resource requirements by name/kind/scope/stage;
- resource structural data needed for validation;
- debug provenance that does not force `termin-graphics` to know render-layer
  concepts.

It must not contain:

- `MaterialContract`;
- `PassContract`;
- `VertexTransformContract`;
- material pipeline producer enums;
- draw kind or draw executor policy;
- backend placements such as Vulkan set/binding or D3D11 register assignment;
- material pipeline diagnostics as C++ objects;
- pass or drawable runtime data providers.

The previous C ABI contained `draw_kind` and stored `tc_shader_resource_binding`
in the contract view. These were migration leftovers, not the target
architecture. The target ABI uses requirement-only contract resources plus a
separate resolved resource layout.

### Shader Resource Layout

The resolved shader resource layout is a sibling of the shader contract, not a
field inside it.

It describes where already-declared resources are bound for a concrete backend
or runtime binding model:

- Vulkan descriptor set/binding;
- D3D11 register class/index;
- OpenGL binding/import metadata where needed;
- stage masks and binding metadata required by backend validation.

`tc_shader_resource_binding` currently serves this role and may remain as the
transitional ABI type for resolved layout. New semantic requirements must not be
added to it as a substitute for `tc_shader_resource_requirement`.

### Material Pipeline

The material pipeline remains in `termin-render`.

It owns:

- `MaterialContract`;
- `VertexTransformContract`;
- `PassContract`;
- ownership-aware resource merge;
- separation between semantic resource requirements and resolved backend
  placement;
- source assembly;
- validation diagnostics;
- cache keys and invalidation policy.

It does not publish a runtime `MaterialPipelineVariant` that passes must look up.
Instead it publishes the final shader with its generic `tc_shader_contract` and
resolved resource layout.

`MaterialPipelineVariant` should be removed as a public runtime concept. During
migration it may temporarily exist as an internal assembly result, but draw paths
must converge on `tc_shader_contract`.

## Runtime Draw Path

Passes draw mesh-backed components through the same C shader override path:

```c
tc_shader_handle final_shader =
    tc_component_override_shader(component, phase_mark, geometry_id, base_shader);
```

Then the pass resolves the shader contract:

```c
tc_shader* shader = tc_shader_get(final_shader);
tc_shader_contract_view contract;
bool has_contract = tc_shader_get_contract_view(shader, &contract);
```

The pass uses the contract to:

- choose mesh attributes by semantic name;
- validate buffer/texture/uniform requirements;
- validate that pass/component providers can satisfy required resources.

This validation is render-owned policy. `termin-graphics` stores the generic
contract and layout, while `termin-render` decides whether a missing contract is
an error for the current path. Migrated paths use `validate_shader_contract()`
to require contracts and compare semantic resource requirements against the
resolved shader resource layout.

The pass uses the resource layout to:

- bind resources by declared resource name/scope/kind;
- map those resources to resolved backend placement;
- validate backend layout compatibility.

The pass still owns:

- render target/depth target;
- viewport/scissor;
- clear/load policy;
- raster/depth/blend state;
- actual provider data for pass resources;
- mesh/fullscreen/compute draw or dispatch policy.

The contract declares requirements. It does not own the data.

## Material Pipeline Assembly

The assembler flow:

```text
1. Extract MaterialContract from material shader/phase.
2. Select VertexTransformContract.
3. Select PassContract.
4. Validate fragment interface compatibility.
5. Merge resource requirements with owner-aware rules.
6. Validate that every merged resource has resolved backend placement.
7. Generate/choose vertex and fragment sources.
8. Create or fetch tc_shader.
9. Attach semantic requirements to `tc_shader_contract`.
10. Attach resolved placement to shader resource layout.
11. Return tc_shader_handle.
```

This makes `tc_shader_handle` the only runtime shader identity and
`tc_shader_contract` the authoritative shader interface contract.

Material pipeline resource declarations are deliberately split:

- `MaterialPipelineResourceRequirement`: shader-facing semantic requirement
  (`name`, `kind`, `scope`, `stage_mask`, `size`);
- `MaterialPipelineResourcePlacement`: resolved backend/runtime location
  (`set`, `binding`, resolved flag);
- `MaterialPipelineResourceDecl`: requirement + placement + ownership metadata.

Resource merge treats same-name `kind/scope` mismatches as contract conflicts
and same-name or same-slot `set/binding` mismatches as placement conflicts. A
resolved placement may satisfy a matching unplaced requirement. This keeps
backend placement out of the semantic resource contract.

## Built-In Shader Catalog Contracts

The built-in shader catalog is a transitional source loader, not a target
contract database. Catalog-registered engine shaders currently attach a generic
`tc_shader_contract` with source kind `TC_SHADER_CONTRACT_SOURCE_GENERATED`
during `register_builtin_shader_from_catalog()`, but this must not grow
`engine-shader-catalog.json`.

The temporary catalog contract is inferred from the existing loader metadata:

- `stages.vertex.inputs` declares required vertex input semantics;
- existing layout metadata declares runtime resources by name, kind, scope, and
  stage;
- backend placement stays in the shader resource layout.

This keeps runtime passes on the same `tc_shader -> tc_shader_contract` path for
material pipeline shaders and engine built-ins. Draw mode is owned by the pass
using the shader, not by the catalog contract. New contract or placement metadata
must not be added to `engine-shader-catalog.json`; the target direction is to
delete that manifest and move engine shader identity/contract ownership into
code-generated or reflection-derived sources.

## Legacy Policy

Shaders without `tc_shader_contract` are legacy/external shaders. Their handling
must be explicit:

- legacy reflection fallback is allowed only in named compatibility paths;
- migrated material-pipeline shaders must always have a contract;
- missing contract on a migrated path is an error, not silent inference.

## Migration Plan

1. Done: remove the transitional `MaterialPipelineCompiledVariant` runtime
   plumbing and public `MaterialPipelineVariant` layer.
2. Done: add `tc_shader_contract` C structs, ownership, deep-copy attach,
   clear, and view accessors on `tc_shader`.
3. Done: make material pipeline assembly attach a shader contract directly to the
   produced `tc_shader`.
4. Done: replace runtime draw decisions with reads from `tc_shader_contract`.
   Compact static, skinned, and foliage mesh input selection now reads the
   contract when present.
5. Done: keep material/pass/vertex-transform contracts inside `termin-render`;
   `termin-graphics` only knows the generic `tc_shader_contract`.
6. Done: remove public runtime `MaterialPipelineVariant`; the new assembly
   result is `MaterialPipelineShaderAssemblyResult` and immediately produces a
   `tc_shader`.
7. Done: migrated shader override paths fail clearly when a required material
   pipeline shader lacks a contract.
8. Done: split material pipeline resource declarations into semantic
   requirements and resolved placement.
9. Done: split the public C shader metadata the same way:
   `tc_shader_contract` should expose requirement-only resources, while
   `tc_shader_resource_binding` remains resolved layout metadata.
10. Done: remove `draw_kind` from `tc_shader_contract`; pass/component code owns
    mesh, instanced, fullscreen, and compute execution policy.
11. Done: replace render-specific producer enums with backend-agnostic contract
    source/debug metadata.
12. Done: add a render-side shader contract validator that can require a
    contract on migrated paths and compare semantic resource requirements
    against resolved layout entries.
13. Done: remove `tc_shader_set_resource_layout()` back-propagation into
    `tc_shader_contract`. Layout updates no longer mutate contract resources.

## Implementation Notes

- `tc_shader` owns the contract data. Setting shader sources clears stale
  contracts, matching resource layout lifetime.
- `MaterialPipelineShaderAssemblyRequest` is the C++ assembly input. It is not
  a runtime variant object.
- `assemble_material_shader_override()` is the current drawable override helper
  for skinned and foliage shaders. It returns a normal `TcShader` whose raw
  `tc_shader` has a generic contract.
- `tc_shader.variant_op` is still set for shader identity/staleness
  compatibility while remaining draw paths migrate to contract reads.
- Material contract extraction filters out vertex-only resources from the
  original shader. This prevents old material vertex resources such as
  `draw_data` from conflicting with replacement vertex transforms such as
  `foliage_draw`.
- Material pipeline resource merge no longer treats `set/binding` as part of the
  semantic resource requirement. Placement conflicts are diagnosed separately.
- Parser-created material shaders attach a generic declared-source contract with
  inferred vertex inputs, material UBO metadata, and current shader resources.
- Catalog-registered built-in shaders attach a transitional engine-generated
  contract inferred from current loader metadata. Do not add new contract fields
  to `engine-shader-catalog.json`.
- `tc_shader_set_resource_layout()` does not update `tc_shader_contract`.
  Contract producers must attach semantic requirements explicitly. The render
  validator compares those requirements against the sibling resource layout.
- Some transitional producers still derive contract requirements from current
  layout metadata at attachment time. That is allowed only as producer-local
  migration code; it must not become core `tc_shader` behavior.

## Validation

Required tests:

- Done: `tc_shader` can expose its attached `tc_shader_contract`.
- Done: C drawable override path returns `tc_shader_handle`; pass can resolve the
  contract from that handle.
- Done: material pipeline assembly creates both shader and contract.
- Done: skinned shader contract declares `joints`, `weights`, and `bone_block`.
- Done: foliage shader contract declares prototype mesh inputs and foliage
  instance storage.
- Done: shadow/depth/id contracts request compact vertex inputs.
- Done: parser-created static material shaders expose shader parser contracts.
- Done: catalog-registered built-in shaders expose engine-generated contracts.
- Done: legacy shader without contract takes only explicit legacy fallback path.
- Done: render-side validation rejects missing required contracts and
  contract/layout resource mismatches.
- Done: resource layout updates do not rewrite existing contract resources.

## Non-Goals

- Do not move material pipeline contracts into `termin-graphics`.
- Do not make `tc_shader_contract` a renamed `MaterialPipelineVariant`.
- Do not add a second C++ shader override path.
- Do not make passes depend on material-pipeline-specific runtime lookups.
- Do not put draw submission categories into `tc_shader_contract`.
