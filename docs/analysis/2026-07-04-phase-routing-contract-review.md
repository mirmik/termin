# Phase routing and shader pass contract review

Date: 2026-07-04

Status: architectural inspection after the first phase/pass-contract refactor.
Related board items: #184, #185.

## Summary

The current direction is correct: material pipeline and shader variant assembly
must receive explicit contracts instead of inferring layout/skinning behavior
from `phase_mark`.

The remaining problem is that `GeometryPassBase` now contains two phase-like
concepts:

- `phase_name()` - used for drawable geometry routing;
- `material_shader_phase_name()` - used for selecting an optional material
  phase shader.

That split made `DepthPass` and `NormalPass` return an empty routing phase
while keeping `material_phase_mark = "depth"` / `"normal"`. This is confusing
and changes the meaning of phase names from a routing/material-selection label
into an implicit "all geometry" sentinel. It also hides the public phase labels
`depth` and `normal` from the pass that still semantically is depth/normal.

Target boundary:

```text
phase mark     -> drawable participation and material phase selection
pass contract  -> shader ABI, vertex transform, resources, skinning template
```

The material pipeline should not know about phases. Render passes may use phase
marks to ask drawables for the right geometry/material phase, but the shader
contract must be passed independently.

## What the code currently does

`GeometryPassBase::collect_draw_calls()` uses `phase_name()` in three important
ways:

- it calls `drawable->get_geometry_ids_for_phase(routing_phase)`;
- later pass implementations call `drawable->resolve_mesh_geometry(phase_name(), ...)`;
- it uses either `material_shader_phase_name()` or `phase_name()` as
  `ShaderOverrideContext::phase_mark`.

So `phase_name()` is not just a debug label. It affects which submeshes are
drawn and how mesh geometry is resolved.

At the same time, `material_shader_phase_name()` is used to query
`drawable->get_geometry_draws(&mark)` and replace the base engine shader with a
material phase shader for a matching geometry id.

Current depth/normal shape:

```cpp
const char* phase_name() const override { return ""; }
const char* material_shader_phase_name() const override {
    return material_phase_mark.c_str(); // "depth" or "normal"
}
```

This means the pass is routed as empty/all geometry, but material shader
selection is routed as `depth` or `normal`.

## Why this is a problem

### Empty phase is an undocumented routing policy

For C drawables, `nullptr` and empty phase may historically mean "all phases" in
some paths. For C++ drawables, the current code passes a literal empty string to
`get_geometry_ids_for_phase("")` and `resolve_mesh_geometry("")`.

That makes "all geometry" depend on each drawable's interpretation of an empty
string. This is too implicit for a render-pass API.

If a pass needs all mesh geometry, that should be an explicit routing mode,
not `phase_name() == ""`.

### Depth and normal lose their phase identity

`depth` and `normal` are still useful phase labels. Materials may have depth or
normal phases, editor UI may expose those labels, and logs/debug tools should
show them.

Returning an empty `phase_name()` while carrying `depth`/`normal` in a second
property makes the public model harder to reason about:

```text
Which phase is this pass?        ""
Which material phase does it use? depth
Which shader contract does it use? depth
```

The expected answer should be simpler:

```text
phase mark:    depth
pass contract: depth
```

and analogously for normal.

### `material_shader_phase_name()` looks like a second phase

The name suggests that geometry routing and material shader selection are
separate phase systems. In the common case they should not be. A phase mark
should select both drawable participation and the material phase for that pass.

There is still a real distinction between:

- using a material phase shader as the source shader;
- using an engine-owned base shader and only asking the drawable for geometry.

But that is not a second phase. It is shader source policy.

Better names would make this clearer:

```cpp
phase_name()                         // routing/material phase label
material_shader_source_policy()      // none, same phase, or explicit override
shader_pass_contract()               // layout/skinning/resources
```

or:

```cpp
phase_mark()
shader_source_phase() -> optional<string>
shader_pass_contract()
```

If `shader_source_phase()` exists, its default should probably be "same as
`phase_mark()`" for passes that use material phase shaders, and explicit `none`
for passes like `IdPass` that intentionally use an engine shader.

### Phase is still in the shader override context

`ShaderOverrideContext` now carries `pass_contract`, which is good. It also
carries `phase_mark`, and C++ overrides still see it.

That is acceptable as migration glue, but the contract must be authoritative
for shader layout and skinning. `phase_mark` in that context should only be
compatibility/debug/material-selection context, not the source of shader ABI.

### Skinned variant cache key is incomplete

`SkinnedMeshRenderer::pass_contract_cache_key()` currently includes:

- `debug_name`;
- `uses_material_fragment`;
- required material fragment inputs;
- pass-level resources.

It does not include the static/skinned/foliage vertex transform contract
details. Two pass contracts with the same pass-level fields but different
skinned vertex transform template, vertex inputs, produced fragment interface,
or vertex resources can collide and reuse the wrong skinned shader.

This is especially risky for custom passes such as an actor attribute map,
depth/normal variants, or future project-specific render passes.

The cache key should include the full shader assembly intent or reuse the same
signature/fingerprint used by material shader override variant UUID generation.

### Offline shader usage collection is still legacy-shaped

`collect_scene_shader_usages()` calls the C drawable protocol:

```cpp
tc_component_collect_shader_usages(
    component,
    phase->phase_mark,
    draw.geometry_id,
    phase->shader,
    ...
);
```

`SkinnedMeshRenderer::collect_shader_usages()` then calls the legacy
`get_skinned_shader(phase_mark, original_shader)`, which now returns a legacy
material contract.

Runtime draw paths can use the new `ShaderOverrideContext`, but build/export
shader collection can still miss variants that require explicit pass contracts.
This needs a context-aware collection path before custom passes rely on package
precompilation.

## Recommended direction

### 1. Keep depth and normal as real phase labels

`DepthPass::phase_name()` should return the configured depth phase mark.
`NormalPass::phase_name()` should return the configured normal phase mark.

The default values should remain:

```text
depth
normal
```

If the pass wants a material phase shader, it should use that same phase by
default. If a pass wants to draw all geometry, add an explicit routing policy
instead of encoding it as an empty phase string.

### 2. Rename or remove the second phase hook

`material_shader_phase_name()` should not read as "there is another phase".

Possible model:

```cpp
enum class ShaderSourcePolicy {
    EngineBaseShader,
    MaterialPhaseSameAsRoutingPhase,
    MaterialPhaseOverride,
};
```

Then the pass has one phase mark and a clear decision about whether material
phase shader source participates.

Another acceptable model is an optional:

```cpp
std::optional<std::string> material_shader_source_phase() const;
```

but the API documentation must state that this is shader source selection, not
geometry routing.

### 3. Make all-geometry routing explicit

If built-in passes need to render every mesh regardless of material phase, add
a separate API:

```cpp
enum class GeometryRoutingMode {
    Phase,
    AllGeometry,
};
```

or:

```cpp
virtual std::optional<std::string> geometry_routing_phase() const;
```

where `std::nullopt` is documented as all geometry. Do not use `""` as the
sentinel.

This is orthogonal to `phase_mark`: a pass can have debug/material phase
identity `depth` and still explicitly choose all-geometry routing if that is the
desired behavior.

### 4. Make shader contract fingerprints complete

The skinned shader cache key should include:

- pass-level required fragment input;
- pass-level resources;
- `uses_material_fragment`;
- static vertex transform contract;
- skinned vertex transform contract;
- foliage vertex transform contract, if present;
- template UUIDs and produced fragment interfaces;
- vertex resource declarations such as `draw_data`, `depth_draw`,
  `normal_draw`, `id_draw`, `bone_block`.

Prefer sharing one canonical fingerprint helper with material shader override
variant UUID generation.

### 5. Add context-aware shader usage collection

The package/export collector needs a way to ask passes for the same
`ShaderOverrideContext` or shader assembly intent that runtime rendering uses.

Until then, custom pass variants can work during live rendering but be absent
from collected shader artifacts.

## Concrete follow-up items

- Restore `depth` and `normal` as the default routing/material phase labels for
  `DepthPass` and `NormalPass`.
- Replace empty-string routing with an explicit all-geometry routing policy if
  that behavior is actually required.
- Reframe `material_shader_phase_name()` as shader source policy or remove it
  in favor of one phase mark plus explicit engine/material shader source choice.
- Extend `SkinnedMeshRenderer` cache keys to include full pass and vertex
  transform contract fingerprints.
- Add a context-aware shader usage collection path so export/precompile sees
  explicit pass contracts.

