# tgfx2 Backend Binding Plan Layer

Дата: 2026-06-21

Связанные документы:

- `docs/analysis/2026-06-21-d3d11-vulkan-abstraction-gap.md`
- `docs/analysis/2026-06-15-shaderc-placement-policy.md`
- `docs/plans/2026-06-20-d3d11-runtime-placement-goal-plan.md`
- `termin-graphics/docs/architecture/shader-resource-contracts.md`
- `termin-graphics/docs/architecture/pipeline-layout.md`

Связанные задачи:

- Kanboard #18 - `[render] Довести Direct3D11 backend MVP`
- Kanboard #21 - `[render] Decide shaderc reflected placement policy`

## Goal

Выделить в tgfx2 явный слой, который переводит semantic shader resources в
backend-native binding model. После этого frontend/runtime не должны
притворяться Vulkan-подобной descriptor-set системой, а backend-и не должны
подделываться под центральный универсальный `binding`.

Целевая формула:

```text
semantic shader interface
  -> backend binding plan / pipeline resource layout
  -> runtime binds semantic values into plan entries
  -> backend applies native resource binding
```

Общей остаётся **семантика** ресурсов: имена, scopes, kinds, stage visibility,
размеры constant buffers. Backend-specific остаётся **placement и execution**:
Vulkan descriptor layouts, D3D11 registers, OpenGL binding points / texture
units.

## Problem Statement

Текущий D3D11 runtime placement pass закрыл важный MVP-разрыв: sidecar metadata
теперь доходит до `D3D11CommandList`. Но архитектурная форма всё ещё
переходная:

- `tc_shader_resource_binding` несёт одновременно semantic metadata,
  Vulkan/OpenGL-ish `set/binding` и D3D11 `register_class/register_index`;
- `tgfx::ResourceBinding` стал generic value binding с optional D3D11 fields;
- `ResourceSetDesc` остаётся flat vector of bindings;
- `RenderContext2::flush_resource_set()` решает, можно ли создать resource set,
  через `descriptor_set_layout != 0`;
- OpenGL и D3D11 вынуждены возвращать fake pipeline-id token из
  `pipeline_descriptor_set_layout()`, потому что настоящего descriptor set
  layout у них нет.

Это рабочее состояние для MVP, но плохая долговременная граница. Если
продолжить расширять эти структуры, центральная модель останется
Vulkan-shaped, а D3D11/OpenGL будут носить вокруг неё compatibility
interpretation.

## Architecture Principle

Не должно быть одного backend-neutral numeric slot.

Должны быть:

1. backend-neutral **resource semantics**;
2. backend-specific **binding plan**;
3. backend-native **command execution**.

Pass/material/render code имеет право знать:

- `per_frame` is frame constants;
- `draw_data` is draw constants;
- `material` is material constants;
- `albedo_texture` is a material texture;
- `shadow_maps` is a pass texture.

Pass/material/render code не имеет права знать:

- Vulkan descriptor set/binding;
- D3D11 `b#`, `t#`, `s#`, `u#`;
- OpenGL texture unit / UBO binding point;
- push-constant emulation slot.

Backend command list не должен выводить semantic meaning из имени ресурса. Он
должен получить план в своей нативной форме и исполнить его.

## Proposed Layers

### 1. Shader Semantic Interface

Источник: `tc_shader_resource_binding` и sidecar metadata.

Ответственность:

- canonical resource name/id;
- kind: constant buffer, texture, sampler, storage buffer, storage texture;
- scope: frame, pass, material, draw, transient, unscoped;
- stage mask;
- reflected size and fields for constant buffers;
- optional stable semantic id for engine-reserved resources.

Не ответственность:

- Vulkan descriptor set;
- D3D11 register class/index;
- OpenGL binding point;
- backend object handles;
- dynamic offset strategy.

Минимально это может быть view over existing `tc_shader_resource_binding`.
Долгосрочно лучше иметь C++-side immutable `ShaderResourceInterface` created
from sidecar/import data.

### 2. Backend Binding Plan

Новый слой. Он берёт shader semantic interface, active backend type,
capabilities and placement metadata, затем строит backend-native plan.

Пример conceptual data:

```cpp
struct ShaderResourceKey {
    ResourceId id;
    ResourceScope scope;
    ResourceKind kind;
};

struct BackendBindingPlanEntry {
    ShaderResourceKey resource;
    StageMask stages;
    uint32_t array_count;
    uint32_t size;
    BackendPlacement placement;
};

struct BackendBindingPlan {
    BackendType backend;
    PipelineResourceLayoutHandle layout;
    std::vector<BackendBindingPlanEntry> entries;
};
```

`BackendPlacement` не должен быть одним числом. Он должен быть tagged union или
backend-owned payload:

```cpp
struct VulkanPlacement {
    uint32_t set;
    uint32_t binding;
    VkDescriptorType descriptor_type;
};

struct D3D11Placement {
    D3D11RegisterClass register_class; // b/t/s/u
    uint32_t register_index;
    StageMask stages;
};

struct OpenGLPlacement {
    OpenGLBindingClass binding_class; // ubo/ssbo/texture/image/sampler
    uint32_t binding_point;
    uint32_t texture_unit;
};
```

The exact public ABI may avoid exposing native Vulkan/D3D/OpenGL types in
shared headers. The important part is type separation: semantic interface and
backend placement must not be the same struct.

### 3. Runtime Binding State

`RenderContext2` should bind resource values by semantic resource, not by raw
backend slot.

Current:

```text
name -> tc_shader_resource_binding -> ResourceBinding{set,binding,d3d11?}
```

Target:

```text
name -> ShaderResourceKey -> BackendBindingPlanEntry -> backend value binding
```

`RenderContext2` keeps scope-aware dirty state:

- frame bucket;
- pass bucket;
- material bucket;
- draw bucket;
- transient bucket.

The flattening step into one `ResourceSetDesc` is transitional. The target
flush API should allow backends to bind only the dirty scope/resource groups
that make sense for them.

### 4. Backend Resource Binding

Backends consume binding plans in their native model.

Vulkan:

- builds/caches `VkDescriptorSetLayout` and `VkPipelineLayout` from the Vulkan
  plan;
- allocates descriptor sets per scope/set according to plan;
- uses descriptor type, set, binding and dynamic offsets as native Vulkan
  concepts.

D3D11:

- does not consume descriptor sets;
- applies `VSSet/PSSet/GSSetConstantBuffers` for `b#`;
- applies `*SetShaderResources` for `t#`;
- applies `*SetSamplers` for `s#`;
- rejects or implements `u#` explicitly;
- uses stage mask from the plan, not all graphics stages by default.

OpenGL:

- does not consume descriptor sets;
- applies UBO/SSBO/image binding points and texture/sampler units;
- can keep program-local binding decisions in the plan;
- does not need a fake descriptor-set layout token.

## Naming And API Direction

The current name `pipeline_descriptor_set_layout()` is too Vulkan-specific.
Replace it in stages with a neutral concept:

```cpp
virtual PipelineResourceLayoutHandle pipeline_resource_layout(
    PipelineHandle pipeline
) const = 0;
```

or, if the layout is backend-private:

```cpp
virtual uintptr_t pipeline_resource_layout_token(PipelineHandle pipeline) const;
```

Rules:

- token existence means "this pipeline has a backend resource binding plan",
  not "this pipeline has a Vulkan descriptor set layout";
- Vulkan may map token to `VkDescriptorSetLayout`/`VkPipelineLayout` internals;
- D3D11/OpenGL may map token to a pipeline-local plan id;
- `RenderContext2` must stop treating `descriptor_set_layout == 0` as the
  central resource-binding gate for all backend types.

`ResourceSetDesc` should also be split conceptually:

```text
Resource values supplied by runtime
Backend binding plan supplied by pipeline/backend
```

Instead of:

```text
ResourceSetDesc = vector of values that also carries placement fields
```

## Ownership

| Decision | Owner |
| --- | --- |
| Which resources a shader declares | shader source / sidecar import |
| What scope a resource belongs to | shader semantic interface / compiler policy |
| Whether a resource is engine-reserved | shader contract / compiler policy |
| Vulkan descriptor set/binding/type | backend binding plan |
| D3D11 register class/index | backend binding plan |
| OpenGL binding point / texture unit | backend binding plan |
| Which value is bound this frame | `RenderContext2` / pass/material code |
| Native API calls | backend command list |
| Unsupported resource diagnostics | binding plan validation + backend |

## Capability And Policy Integration

The binding plan builder should validate backend capabilities before command
execution:

- max constant buffers per stage;
- max SRV/sampler/UAV slots;
- supported stages;
- dynamic constant-buffer offset support;
- native push constants support;
- storage buffer/texture support;
- array/resource count limits;
- required alignment for constant buffer offsets/ranges.

Unsupported features should fail or log at plan build / resource binding time,
not silently remap into approximate slots.

Push constants should become semantic small constants:

```text
pass-local small constants, max N bytes, frequent updates
```

Backend plan decides:

- Vulkan: native push constant range;
- D3D11: reserved or generated constant buffer binding;
- OpenGL: UBO/emulation path;
- unsupported backend: capability error.

## Transition Plan

Status 2026-06-21:

- Phase 1 started: `IRenderDevice` has neutral
  `pipeline_resource_layout_token()`, while
  `pipeline_descriptor_set_layout()` remains as compatibility wrapper.
- `ResourceSetDesc` now has `resource_layout_token` plus transitional
  `descriptor_set_layout`; Vulkan accepts either through
  `effective_resource_layout_token()`.
- `RenderContext2` uses resource-layout terminology and calls the neutral
  token API. Behavior is intentionally unchanged: resource values are still
  flattened into `ResourceSetDesc`.
- Phase 2 started: `tgfx2/backend_binding_plan.hpp` defines semantic resource
  keys, backend placement variants, `BackendBindingPlan`, and a builder from
  existing `tc_shader_resource_binding` metadata. Focused tests cover
  Vulkan/D3D11/OpenGL placement separation, D3D11 register conflicts, and the
  current Vulkan set-0 guard. `RenderContext2` does not consume this plan yet.
- Phase 3 started: `RenderContext2::use_shader_resource_layout()` builds and
  caches `BackendBindingPlan` for the active backend. `bind_uniform_data()` and
  queued symbolic bindings now resolve placement through plan entries instead
  of copying backend placement directly from `tc_shader_resource_binding`.
  Compatibility remains: resolved values still flatten into `ResourceBinding`
  and `ResourceSetDesc`.
- Phase 4 started internally: `RenderContext2` now stores migrated symbolic
  bindings as `PlannedResourceBinding { BackendBindingPlanEntry,
  BoundResourceValue }`. The legacy `ResourceBinding` object is now produced at
  the backend boundary in `flatten_pending_bindings()`. Numeric binding APIs
  remain legacy `ResourceBinding` paths, and backend `ResourceSetDesc` is not
  split yet.
- Phase 4 boundary type added: `backend_binding_plan.hpp` now exposes
  `BoundResourceValue`, `BoundResourceBinding`, and `BoundResourceSetDesc`.
  `RenderContext2` builds `BoundResourceSetDesc` first, then adapts it to the
  transitional `ResourceSetDesc` in one place before calling
  `IRenderDevice::create_resource_set()`. Backend APIs still consume
  `ResourceSetDesc`.
- Backend boundary API started: `IRenderDevice` now exposes
  `create_bound_resource_set(BoundResourceSetDesc, legacy_numeric_bindings)`
  with a default adapter to `create_resource_set(ResourceSetDesc)`.
  `RenderContext2` calls this boundary API instead of adapting directly. The
  shared adapter lives in the binding-plan layer; concrete backends still use
  the default wrapper.
- OpenGL backend started consuming the boundary directly:
  `OpenGLRenderDevice::create_bound_resource_set()` stores
  `BoundResourceSetDesc`, and `OpenGLCommandList::bind_resource_set()` applies
  planned bindings through OpenGL binding points / texture units. Legacy
  numeric bindings remain supported beside the new path.
- OpenGL runtime coverage added: `tgfx2_opengl_bound_resource_set` creates an
  SDL2 OpenGL context, binds a UBO through `BoundResourceSetDesc` with explicit
  OpenGL placement, renders offscreen, and verifies the result with
  `read_pixel_rgba8()`.
- D3D11 backend started consuming the boundary directly:
  `D3D11RenderDevice::create_bound_resource_set()` stores
  `BoundResourceSetDesc`, and `D3D11CommandList::bind_resource_set()` applies
  planned bindings through D3D11 register class/index placement. Legacy numeric
  bindings remain supported beside the new path. The existing
  `tgfx2_d3d11_smoke` normal-material pass now creates its constant-buffer
  resource set through `BoundResourceSetDesc`; Windows runtime validation is
  still required.

### Phase 0: Freeze Current Contract

Do not add new D3D/OpenGL/Vulkan-specific branches above `RenderContext2`.
Do not add new production shader-authored `register(...)` or `[[vk::...]]`
placement.

Acceptance:

- current D3D11 placement pass remains working;
- `tc_shader_resource_binding` is treated as transitional import metadata,
  not the final cross-backend plan structure.

### Phase 1: Introduce Names Without Behavior Change

Add neutral API names while keeping compatibility wrappers:

- `pipeline_resource_layout_token()` or equivalent;
- comments/docs that deprecate `pipeline_descriptor_set_layout()` as a generic
  concept;
- `PipelineResourceLayout` / `BackendBindingPlan` type skeletons behind
  current `ResourceSetDesc` behavior.

Acceptance:

- Vulkan/OpenGL/D3D11 behavior unchanged;
- no fake descriptor-set terminology in new code paths;
- existing tests still pass.

### Phase 2: Build Plan From Existing Shader Metadata

Create a binding-plan builder that consumes existing `tc_shader_resource_binding`
metadata.

Initial implementation can be mechanical:

- Vulkan placement comes from existing `set/binding/kind`;
- D3D11 placement comes from existing `d3d11.register_class/register_index`;
- OpenGL placement comes from existing `binding` plus kind-specific policy.

Acceptance:

- plan entries are distinguishable from semantic shader resources in types;
- validation catches malformed or missing placement for the active backend;
- tests prove same semantic resource can produce different backend placement
  representations.

### Phase 3: Route RenderContext2 Through Plan Entries

Change symbolic binding resolution:

```text
name -> semantic resource -> plan entry -> pending value
```

instead of directly copying placement from `tc_shader_resource_binding` into
`ResourceBinding`.

Acceptance:

- `RenderContext2` does not inspect D3D11 register metadata directly;
- missing plan entry logs an actionable error;
- scope buckets remain intact and are not flattened until the backend boundary.

### Phase 4: Split Resource Values From Placement

Replace `ResourceBinding` as "value plus placement" with separate concepts:

- `BoundResourceValue`: buffer/texture/sampler/offset/range/array element;
- `BackendBindingPlanEntry`: backend slot/register/descriptor information;
- backend-specific resource-set/update payload built from both.

Acceptance:

- D3D11 backend no longer needs compatibility path from generic
  `binding + kind` for migrated shader-layout paths;
- Vulkan descriptor set update code gets descriptor placement from plan, not
  from value bindings;
- OpenGL binding code gets GL placement from plan, not from a fake descriptor
  set layout token.

### Phase 5: Backend-Native Resource Groups

Remove the assumption that every backend receives one flat `ResourceSetDesc`.

Possible shapes:

- Vulkan receives descriptor-set updates grouped by descriptor set/scope;
- D3D11 receives stage/register-class updates grouped by dirty scope;
- OpenGL receives binding point / texture unit updates grouped by program.

Acceptance:

- frame/pass/material/draw dirty tracking can avoid rebinding unrelated scopes;
- Vulkan multi-set layout can be introduced without changing pass code;
- D3D11 no longer depends on descriptor-set-shaped data.

### Phase 6: Deprecate Transitional Fields

After migrated paths use binding plans:

- stop adding new backend fields to `tc_shader_resource_binding`;
- keep sidecar parsing backward compatible only where needed;
- move backend placement into per-backend plan data;
- make numeric binding APIs explicitly legacy or low-level.

Acceptance:

- new migrated Slang path cannot bind by guessed numeric slot;
- tests fail if a migrated pass bypasses binding-plan resolution;
- documentation names `BackendBindingPlan` / `PipelineResourceLayout` as the
  live contract.

## Test Strategy

Focused tests:

1. Plan builder converts one semantic interface into Vulkan, D3D11 and OpenGL
   placements without changing semantic resource ids.
2. D3D11 plan allows `b2` and `t2` simultaneously and rejects same
   `(stage, class, index)` conflicts.
3. Vulkan plan rejects non-zero descriptor sets until multi-set support is
   deliberately implemented.
4. OpenGL plan assigns distinct UBO binding and texture unit concepts instead
   of treating both as one generic binding number.
5. `RenderContext2` symbolic bind path only carries resource values after plan
   resolution.
6. Missing backend placement for active backend is a hard error or clear log,
   not a silent compatibility bind.
7. OpenGL runtime path creates a bound resource set from
   `BoundResourceSetDesc` and applies backend-native UBO placement during draw.
8. D3D11 runtime path creates a bound resource set from
   `BoundResourceSetDesc` and applies backend-native `b/t/s/u` placement
   during draw.

Regression commands:

```bash
./run-tests.sh
```

Focused Linux checks before Windows D3D11 verification:

```bash
ctest --test-dir build/Release-tests -R 'tgfx|render_context|backend_window' --output-on-failure
ctest --test-dir build/Release-tests -R '^tgfx2_opengl_bound_resource_set$' --output-on-failure
./run-tests-python.sh termin-graphics/tests/python/test_termin_shaderc_cli.py
```

Windows D3D11 checks remain from the D3D11 MVP plan:

```powershell
ctest --test-dir build\Release-tests -C Release -R tgfx2_d3d11_smoke --output-on-failure
ctest --test-dir build\Release-tests -C Release -R backend_window_d3d11_present --output-on-failure
```

## Stop Conditions

Stop and split work if:

- the first implementation requires changing pass/material code before the
  plan layer exists;
- `tc_shader_resource_binding` ABI changes force a broad SDK rebuild without a
  staged compatibility path;
- Vulkan descriptor cache lifetime becomes ambiguous after introducing plan
  handles;
- D3D11/OpenGL still need fake descriptor-set semantics after Phase 4.

## Expected End State

- Shader/pass/frontend code binds semantic resources only.
- `tc_shader_resource_binding` is shader interface/import metadata, not the
  universal backend placement carrier.
- `BackendBindingPlan` / `PipelineResourceLayout` is the explicit translation
  boundary.
- Vulkan works with descriptor layouts and descriptor sets.
- D3D11 works with register classes, register indices and stage-local calls.
- OpenGL works with program/binding-point/texture-unit state.
- The central model is semantic, not a lowest-common-denominator rendering API.
