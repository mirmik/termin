# Shader Contract Material Pipeline Architecture

Date: 2026-06-27

## Status

Target architecture. This document supersedes the runtime `MaterialPipelineVariant`
model described in `2026-06-27-material-pipeline-target-architecture.md`.

The important correction is that runtime draw paths should not look up a
material-pipeline-specific variant after shader override. Shader override stays
the C protocol and returns `tc_shader_handle`. The selected `tc_shader` carries
the generic shader contract required to bind and draw it.

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
      v
tc_shader_contract
      |
      v
bind resources + submit draw
```

There is no runtime `material_pipeline_variant_from_shader_contract()` lookup.
If the shader contract is complete, it is sufficient for pass draw submission.

## Layer Ownership

### `tc_shader`

`tc_shader` is the shader identity and runtime shader object. It may reference
an optional generic `tc_shader_contract`.

It must not know about:

- material pipeline variants;
- material/pass/vertex-transform contracts;
- drawable providers;
- concrete render passes.

It may know:

- source, entry points, language, artifact policy;
- compiled/reflected resource layout;
- variant identity and original shader relation;
- optional shader contract handle.

### `tc_shader_contract`

`tc_shader_contract` is a C ABI draw contract for the final shader program.
It describes the shader-facing interface, not the material pipeline provenance.

Required initial data:

```c
typedef enum tc_shader_contract_producer_kind {
    TC_SHADER_CONTRACT_PRODUCER_UNKNOWN = 0,
    TC_SHADER_CONTRACT_PRODUCER_SHADERC_REFLECTION = 1,
    TC_SHADER_CONTRACT_PRODUCER_MATERIAL_PIPELINE = 2,
    TC_SHADER_CONTRACT_PRODUCER_ENGINE_GENERATED = 3,
    TC_SHADER_CONTRACT_PRODUCER_LEGACY = 4,
} tc_shader_contract_producer_kind;

typedef enum tc_shader_contract_draw_kind {
    TC_SHADER_CONTRACT_DRAW_MESH = 0,
    TC_SHADER_CONTRACT_DRAW_INSTANCED_MESH = 1,
    TC_SHADER_CONTRACT_DRAW_DIRECT = 2,
    TC_SHADER_CONTRACT_DRAW_FULLSCREEN = 3,
    TC_SHADER_CONTRACT_DRAW_COMPUTE = 4,
} tc_shader_contract_draw_kind;

typedef struct tc_shader_contract_vertex_input {
    char semantic[TC_SHADER_RESOURCE_NAME_MAX];
    uint32_t type;
    uint32_t required;
} tc_shader_contract_vertex_input;

typedef struct tc_shader_contract_storage_buffer {
    char resource_name[TC_SHADER_RESOURCE_NAME_MAX];
    uint32_t stride;
} tc_shader_contract_storage_buffer;

typedef struct tc_shader_contract_view {
    uint32_t schema_version;
    uint32_t producer_kind;
    uint32_t draw_kind;
    tc_shader_handle shader;

    const tc_shader_contract_vertex_input* vertex_inputs;
    uint32_t vertex_input_count;

    const tc_shader_contract_storage_buffer* storage_buffers;
    uint32_t storage_buffer_count;

    const tc_shader_resource_binding* resources;
    uint32_t resource_count;

    const char* debug_name;
    const char* producer_debug_name;
} tc_shader_contract_view;
```

The exact structs may evolve, but the contract must stay generic:

- vertex input requirements;
- storage/instance resource requirements;
- shader resources by name/kind/scope/stage/backend placement;
- draw kind;
- producer/debug provenance.

It must not contain:

- `MaterialContract`;
- `PassContract`;
- `VertexTransformContract`;
- material pipeline diagnostics as C++ objects;
- pass or drawable runtime data providers.

### Material Pipeline

The material pipeline remains in `termin-render`.

It owns:

- `MaterialContract`;
- `VertexTransformContract`;
- `PassContract`;
- ownership-aware resource merge;
- source assembly;
- validation diagnostics;
- cache keys and invalidation policy.

It does not publish a runtime `MaterialPipelineVariant` that passes must look up.
Instead it publishes the final shader and its generic `tc_shader_contract`.

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
const tc_shader_contract_view* contract = tc_shader_contract_view(shader);
```

The pass uses the contract to:

- bind resources by declared resource name/scope/kind;
- choose mesh attributes by semantic name;
- validate storage/instance requirements;
- select mesh vs instanced/direct/fullscreen/compute draw executor.

The pass still owns:

- render target/depth target;
- viewport/scissor;
- clear/load policy;
- raster/depth/blend state;
- actual provider data for pass resources.

The contract declares requirements. It does not own the data.

## Material Pipeline Assembly

The assembler flow:

```text
1. Extract MaterialContract from material shader/phase.
2. Select VertexTransformContract.
3. Select PassContract.
4. Validate fragment interface compatibility.
5. Merge resources with owner-aware rules.
6. Generate/choose vertex and fragment sources.
7. Create or fetch tc_shader.
8. Build tc_shader_contract from the assembled result.
9. Attach contract to tc_shader.
10. Return tc_shader_handle.
```

This makes `tc_shader_handle` the only runtime shader identity and
`tc_shader_contract` the authoritative draw contract.

## Legacy Policy

Shaders without `tc_shader_contract` are legacy/external shaders. Their handling
must be explicit:

- legacy reflection fallback is allowed only in named compatibility paths;
- migrated material-pipeline shaders must always have a contract;
- missing contract on a migrated path is an error, not silent inference.

## Migration Plan

1. Revert the transitional `MaterialPipelineCompiledVariant` runtime plumbing.
2. Add `tc_shader_contract` C structs, registry, and `tc_shader` contract link.
3. Make material pipeline assembly attach a shader contract directly to the
   produced `tc_shader`.
4. Replace `ResourceBindingPlan`/`VertexStreamPlan` runtime pass plumbing with
   reads from `tc_shader_contract`.
5. Keep material/pass/vertex-transform contracts inside `termin-render`.
6. Remove public runtime `MaterialPipelineVariant`; keep only internal assembly
   helpers if needed.
7. Make passes fail clearly when migrated shaders lack a contract.

## Validation

Required tests:

- `tc_shader` can expose its attached `tc_shader_contract`.
- C drawable override path returns `tc_shader_handle`; pass can resolve the
  contract from that handle.
- material pipeline assembly creates both shader and contract.
- skinned shader contract declares `joints`, `weights`, and `bone_block`.
- foliage shader contract declares prototype mesh inputs and foliage instance
  storage.
- shadow/depth/id contracts request compact vertex inputs.
- legacy shader without contract takes only explicit legacy fallback path.

## Non-Goals

- Do not move material pipeline contracts into `termin-graphics`.
- Do not make `tc_shader_contract` a renamed `MaterialPipelineVariant`.
- Do not add a second C++ shader override path.
- Do not make passes depend on material-pipeline-specific runtime lookups.
