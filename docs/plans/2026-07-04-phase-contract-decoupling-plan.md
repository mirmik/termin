# Phase Contract Decoupling Plan

Date: 2026-07-04
Kanboard: #184, #185

## Status

Active migration plan.

Progress:

- 2026-07-04: Added context-aware C++ drawable shader override path carrying a
  `MaterialPipelinePassContract` separately from `phase_mark`. Updated
  `ColorPass`, `ShadowPass`, `GeometryPassBase`, and `DepthOnlyPass` to use it
  for C++ drawables while keeping the C drawable ABI fallback.
- 2026-07-04: Extended material shader override requests so callers can pass
  explicit vertex/pass contracts. Skinned and foliage shader variants now have
  pass-contract based entry points; phase-name mapping remains only in legacy
  compatibility overloads and foliage direct-draw code.
- 2026-07-04: Made material shader override variant UUIDs include the explicit
  vertex/pass contract signature, so custom contracts no longer collide solely
  because they share the same original shader and variant op.
- 2026-07-04: Added pass contract to `RenderContext` for direct tgfx2 draw
  paths. `ColorPass`, `ShadowPass`, and `IdPass` now populate it; foliage
  direct drawing and line material-fragment selection use the pass contract
  instead of deriving shader intent from `phase_mark`.
- 2026-07-04: Removed the central material-pipeline pass enum from production
  code. `MaterialPipelinePassContract` now carries explicit static/skinned/
  foliage vertex transform contracts. Depth and normal passes own explicit
  depth/normal shader contracts instead of deriving layout from phase labels.
- 2026-07-04: Corrected the final phase model after review. A render pass must
  pass an explicit `phase_mark` when asking a drawable for geometry or direct
  drawing support. The phase is a drawable/render representation request and
  may also select a material phase draw set. It does not define shader ABI,
  vertex layout, resource layout, or material-pipeline variant intent.
- 2026-07-06: Renamed the public/config depth and normal pass field from
  `material_phase_mark` to `phase_mark`. The C++ storage is `pass_phase_mark`
  to avoid colliding with the virtual `phase_mark()` accessor; inspector and
  Python still expose `phase_mark`, and deserialization accepts the old
  `material_phase_mark` key as an explicit legacy compatibility path.
- 2026-07-06: Added context-aware `LineRenderer` shader usage collection.
  Runtime shader override and offline usage collection now both use
  `MaterialPipelinePassContract` for line material-fragment variants; the old
  phase-string path remains a compatibility adapter.
- 2026-07-06: Isolated legacy line/skinned override adapters and documented the
  live `GeometryPassBase`/`ShaderOverrideContext` boundary in code: `phase_mark`
  selects drawable/material representation, while `MaterialPipelinePassContract`
  selects vertex layout, pass resources, and material-pipeline variant intent.
- 2026-07-06: Promoted the phase responsibility boundary from migration plan to
  stable documentation in `docs/render-phase-semantics.md`. The document
  defines allowed/forbidden `phase_mark` responsibilities, catalogs current
  consumers, and records the remaining legacy compatibility boundaries.

This plan refines the material-pipeline contract direction from
`2026-06-27-shader-contract-material-pipeline-architecture.md`.

The immediate problem is not that phase names are strings. The problem is that
`phase_mark` currently answers unrelated questions:

- whether a drawable participates in a pass;
- which material phase should be selected;
- which shader variant should be assembled;
- which vertex transform resources and fragment interface are expected;
- which engine pass semantics are active.

Replacing string checks with a central enum would keep the same coupling in a
more rigid form. The target is pass-owned shader contracts, not a larger list of
well-known phase names or pass kinds inside material pipeline core.

## Target Boundary

Stable documentation: `docs/render-phase-semantics.md`.

`phase_mark` is a mandatory drawable/render representation label.

It may be used to:

- ask a drawable which geometry ids exist for that label;
- resolve the phase-specific mesh or direct draw representation for a geometry
  id;
- select a matching `tc_material_phase` or material phase draw set;
- describe material/render queue or representation membership such as
  `opaque`, `transparent`, `shadow`, `pick`, `depth`, `normal`, `editor`, or a
  project-defined label.

A pass must not use an empty or omitted phase as a generic "all geometry"
request. A renderer may decide that a phase uses the same mesh geometry as
another phase, but that decision belongs inside the drawable/renderer
implementation for the requested label.

It must not be used to infer:

- vertex input layout;
- skinned, foliage, line, or other vertex transform templates;
- draw-scope resource names such as `draw_data`, `shadow_draw`, `depth_draw`,
  `normal_draw`, or `id_draw`;
- fragment override behavior;
- output semantics such as depth, object id, normal, or shadow caster;
- backend resource layout.

Render passes own shader intent.

A pass that needs a non-color shader contract must provide it explicitly. The
material pipeline assembler consumes generic contract objects and produces a
final `tc_shader` with `tc_shader_contract` plus resolved resource layout. It
does not decide that `normal`, `pick`, or `depth` are special shader-layout
names.

## Desired Model

The draw path should keep representation selection/material phase lookup
separate from shader assembly intent:

```text
DrawablePhaseRequest
  phase_mark: string

ShaderAssemblyIntent
  material contract
  vertex transform contract
  pass shader contract
```

The first one is the drawable-facing request for a render representation. It
can also be a user/project-visible material lookup label. The second one is
render-owned shader ABI and layout intent.

Examples:

```text
ColorPass
  phase_mark = "opaque"
  geometry = material draws for "opaque"
  pass contract = keep material fragment, standard color resources

CustomDepthPass
  phase_mark = "depth" or a project-owned label
  geometry = drawable representation for that phase
  optional material phase shader lookup = same label
  pass contract = depth output, position-only vertex interface

IdPass
  phase_mark = "pick"
  geometry = drawable pick representation
  pass contract = id payload/output resources

NormalPass
  phase_mark = "normal"
  geometry = drawable normal representation
  optional material phase shader lookup = "normal"
  pass contract = normal output resources and vertex normal requirement
```

The material pipeline core should see the contracts, not the phase names.

## Current Leak Points

### Phase-to-contract mapping

Previously, `termin-components-render/src/shader_skinning.cpp` mapped phase
strings to concrete material-pipeline pass meanings:

```text
shadow -> Shadow
depth  -> Depth
pick   -> Id
normal -> Normal
else   -> Color
```

That made an arbitrary routing label select vertex templates and draw-scope
resources. Production code no longer contains this authoritative mapping;
legacy overloads accept the old signature but do not infer `depth` or `normal`
shader layouts from the string. They build a full-material compatibility
contract for callers that cannot yet provide `ShaderOverrideContext`; pass-owned
render paths should not call them.

### Central pass-kind enum

The removed central pass-kind enum contained concrete pass meanings:

```text
Color, Shadow, Depth, DepthOnly, Id, Normal
```

`vertex_transform_contracts.cpp` used that enum to choose resource names and
template UUIDs. This was better than raw string checks at call sites, but it
still put knowledge of specific engine passes inside a shared material/vertex
contract layer. The current code exposes descriptor builders instead.

### Shadow special case

`ShadowPass` uses `shadow` for drawable membership and material phase
selection, but also drives an engine shadow shader path. That makes it unclear
whether the material shadow phase, the engine pass, or the component override
owns the final layout. Shadow must become an explicit contract decision.

### `pick` versus `id`

`IdPass` uses phase `pick`, while some line-renderer code and documentation
refer to auxiliary phase `id`. This looks like a stale compatibility alias and
should not leak into the new contract model.

### Offline shader usage collection

`collect_scene_shader_usages()` still walks scene material phases and calls the
legacy drawable usage hook. It remains useful as a scene/material-phase
compatibility collector, but it is incomplete for pass-owned contracts.
Runtime package/export now has a pass-aware path that feeds actual render
pipeline pass contracts into `collect_shader_usages_with_context()`.

## Contract Shape

The final API does not need a central enum for every pass. It needs explicit
contracts that are cheap to construct and easy for built-in passes to share.

Sketch:

```cpp
struct PhaseSelection {
    std::string phase_mark;
};

struct PassShaderContract {
    std::string debug_name;
    bool uses_material_fragment = true;
    std::optional<FragmentOverride> fragment_override;
    MaterialFragmentInterface required_vertex_output;
    std::vector<MaterialPipelineResourceDecl> resources;
};

struct VertexTransformContract {
    VertexTransformKind kind;
    std::string debug_name;
    std::optional<std::string> template_uuid;
    VertexInputContract vertex_inputs;
    MaterialFragmentInterface produced_fragment_input;
    std::vector<MaterialPipelineResourceDecl> resources;
    std::vector<InstanceStreamDecl> instance_streams;
};

struct ShaderAssemblyIntent {
    MaterialPipelineMaterialContract material;
    VertexTransformContract vertex_transform;
    PassShaderContract pass;
};
```

Built-in helpers may exist, but they should return concrete contract objects:

```cpp
PassShaderContract make_color_pass_contract();
PassShaderContract make_depth_output_contract(...);
PassShaderContract make_normal_output_contract(...);
PassShaderContract make_id_output_contract(...);
VertexTransformContract make_skinned_vertex_transform(...);
```

The helpers are convenience factories, not the only legal vocabulary.

## Migration Plan

### 1. Document and enforce the phase boundary

Add living render documentation that defines `phase_mark` as a mandatory
drawable representation/material selection label.

Expected changes:

- document allowed and forbidden phase responsibilities;
- list current built-in phase labels as conventions, not as engine-wide enum
  values;
- add comments around `Drawable`, `ColorPass`, geometry passes, and material
  pipeline entry points where the boundary is easy to violate.

Validation:

- documentation references #184 and #185;
- no code behavior changes in this step.

### 2. Introduce explicit shader intent at pass boundaries

Add a small render-facing context object passed from render passes into drawable
shader override paths.

The context should carry:

- `phase_mark` for drawable representation/material selection;
- pass-owned shader contract or a handle to one;
- optional debug label/pass name.

The old C ABI can keep accepting `(phase_mark, geometry_id, original_shader)`
during migration, but C++ paths should have a non-phase way to pass shader
intent.

Expected changes:

- add a C++ `RenderDrawContext` or `ShaderOverrideContext`;
- teach `GeometryPassBase`, `ColorPass`, `ShadowPass`, `DepthPass`,
  `NormalPass`, and `IdPass` to build one;
- keep compatibility adapters for existing `tc_component_override_shader`.

Validation:

- existing passes draw the same scenes;
- custom pass tests can use arbitrary phase names with explicit contracts.

### 3. Move phase-to-pass-kind mapping to compatibility only

Stop using `phase_mark` as the primary input for material pipeline variants.

Expected changes:

- replace `get_skinned_shader(phase_mark, original_shader)` with an API that
  receives explicit shader intent or contract objects;
- keep the old overload as a compatibility adapter near pass boundaries;
- make legacy adapters conservative and local so they do not become a new
  phase-name-to-layout policy source.

Validation:

- `shader_skinning.cpp` no longer contains the authoritative phase string
  mapping;
- existing `shadow/depth/pick/normal` behavior remains covered by tests;
- a non-standard phase label can still request color-style skinned rendering.

### 4. Replace central pass-kind enum with contract descriptors

Remove the central pass-kind enum and make pass contracts carry explicit
vertex-transform descriptors.

Expected changes:

- move built-in depth, normal, id, and shadow knowledge out of generic
  material pipeline assembly code;
- make vertex transform factories accept explicit requirements/resource
  declarations instead of pass-kind enum values;
- keep shared helper functions for common resource declarations such as
  `per_frame` and draw UBOs.

Validation:

- adding a new pass-specific contract does not require editing a central enum;
- material pipeline assembler has no switch over concrete pass names;
- tests assert the produced shader contract/resources, not enum values.

### 5. Make shadow ownership explicit

Resolve the shadow path as a first-class pass contract.

Expected decision:

- either shadow variants are assembled from the material shadow phase shader;
- or the engine shadow shader is an explicit pass fragment/vertex override;
- in both cases, alpha/discard/material requirements must be represented by the
  contract, not by relying on the `shadow` phase string.

Expected changes:

- `ShadowPass` builds explicit shader intent;
- material shadow phase is used for selection/state/material inputs only where
  the contract says so;
- direct draw and mesh-backed shadow paths bind resources from the same
  declared contract model.

Validation:

- alpha-tested shadow casters have an explicit tested path;
- shadow resource layout no longer depends on hidden phase-name behavior.

### 6. Clean up `pick` and `id`

Choose one public phase label for picking. Keep any old spelling only as a
documented compatibility alias at the pass boundary.

Recommended direction:

- keep `pick` as the phase label used by `IdPass`;
- keep `Id` or `id` only as output/pass/debug terminology;
- remove `id` from line-renderer auxiliary phase logic unless a real pass uses
  it.

Validation:

- `IdPass` tests and line-renderer tests describe the accepted label;
- no production code treats both `pick` and `id` as independent phase names.

### 7. Remove compatibility inference

After passes and components have explicit shader intent, delete the legacy
inference path.

Expected changes:

- remove phase-name-to-contract adapters;
- remove warnings added in step 3;
- remove any remaining compatibility-only contract inference;
- update docs from migration wording to final architecture wording.

Validation:

- full `./run-tests.sh` passes;
- shader ABI/material pipeline tests cover custom pass contracts;
- render-pass smoke tests cover color, transparent, shadow, depth, normal, and
  picking.

## Test Strategy

Add focused tests before broad migration:

- a skinned mesh rendered under a custom color phase that is not named
  `opaque` or `transparent`;
- a custom depth-like pass that can request a project-owned phase label instead
  of the built-in `depth` label;
- a custom color-like pass whose phase label is `depth_debug` and must not pick
  depth layout by substring or fallback convention;
- a line renderer under a non-standard phase whose material-fragment variants
  are selected from `MaterialPipelinePassContract`, including world-tube body
  and cap variants;
- IdPass/picking behavior with the canonical `pick` label;
- line-renderer direct draw rejection/acceptance after `id` cleanup;
- shadow caster with material alpha/discard requirements.

The key assertion is that shader contract resources come from explicit pass
intent, while drawable representation and material phase selection come from
`phase_mark`.

## Compatibility Notes

Existing assets and projects may continue to use:

- `opaque`;
- `transparent`;
- `shadow`;
- `pick`;
- editor/debug phase labels.

`depth` and `normal` are canonical material shader override labels for the
engine depth and normal passes, and they are also the default drawable
representation requests those passes issue. They are not shader layout labels:
if a project uses those strings, their presence alone carries no special layout
meaning. Depth and normal engine passes request the matching drawable phase and
use explicit shader contracts instead of deriving contracts from those names.

If depth/normal rendering needs material-specific shader code, the pass uses
its configured `phase_mark` as both the drawable representation request and the
material phase lookup key. The pass still owns the material-pipeline contract
and falls back to the engine shader when no matching material phase exists.
Serialized data using the old `material_phase_mark` key is read only as a
legacy migration path.

During migration the remaining labels should remain accepted only as routing
labels owned by the relevant pass setup. Their presence must not be sufficient
to select a shader contract in shared material pipeline code.

## Completion Criteria

The migration is complete when:

- `phase_mark` is documented as mandatory drawable representation/material
  phase selection;
- material pipeline assembly accepts explicit pass and vertex transform
  contracts;
- no shared material pipeline or component shader override code infers layout
  from `phase_mark`;
- adding a new pass-specific shader contract does not require extending a
  central enum;
- `pick`/`id` naming is resolved;
- shadow shader ownership is explicit and tested.
