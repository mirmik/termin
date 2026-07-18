# Render Phase Semantics

Related board items: #184, #185.

This document defines the live meaning of `phase_mark` in Termin render code.
Migration history and implementation notes live in
`docs/plans/2026-07-04-phase-contract-decoupling-plan.md`; this page is the
stable contract new render code should follow.

## Definition

`phase_mark` is a drawable-facing render representation label.

A render pass uses it to ask a drawable for the representation that should
participate in that pass. For material-backed drawables the same label normally
selects matching `tc_material_phase` entries. For direct-draw or custom
drawables it may select another representation such as shadow casters, picking
geometry, editor/debug primitives, transparent text, or a project-owned custom
surface.

The label is mandatory at geometry pass boundaries. A pass must not use an
empty phase mark as an implicit "all geometry" request. If a future pass needs
all-geometry routing, it should add an explicit routing policy instead of
overloading the empty string.

## Allowed Responsibilities

Code may use `phase_mark` for:

- drawable participation and representation lookup;
- material phase filtering and material phase shader source selection;
- phase-specific mesh/submesh or direct-draw geometry selection;
- render queue or representation names such as `opaque`, `transparent`,
  `shadow`, `pick`, `depth`, `normal`, `editor`, or project-owned labels;
- diagnostics, inspector fields, and editor/debug visibility.

`phase_mark` values are conventions, not an engine-wide enum. Custom render
passes may use project-owned labels without modifying shared material pipeline
or shader assembly code.

## Forbidden Responsibilities

Code must not use `phase_mark` to infer:

- vertex input layout;
- static, skinned, foliage, line, or other vertex transform templates;
- draw-scope resource names such as `draw_data`, `shadow_draw`, `depth_draw`,
  `normal_draw`, or `id_draw`;
- whether a pass consumes material fragment code;
- fragment interface requirements;
- pass output semantics such as depth, normal, object id, or shadow map;
- backend descriptor/resource layout.

Those decisions belong to the pass-owned shader contract, represented in C++ by
`MaterialPipelinePassContract` and the vertex transform contracts it carries.
The `RenderItem -> RenderTask` planner receives that contract and is the
authoritative shader ABI and material-pipeline variant boundary.

## Built-In Labels

Current built-in labels are compatibility and default configuration
conventions:

| Label | Owner/Use |
| --- | --- |
| `opaque` | Default `ColorPass` material/drawable representation. |
| `transparent` | Transparent material/text representation. |
| `shadow` | Shadow caster representation and optional material shadow phase. |
| `pick` | `IdPass` drawable representation for object picking. |
| `depth` | Default `DepthPass`/`DepthOnlyPass` representation and material shader source label. |
| `normal` | Default `NormalPass` representation and material shader source label. |
| `editor` | Editor/debug representations used by editor-facing components. |

The names above do not select shader layout by themselves. For example,
`DepthPass` uses the default label `depth` and separately declares a depth pass
contract. A custom pass may request `phase_mark = "actor_attribute"` while
declaring either a full material/world-position contract or a compact
position-only contract.

`pick` is the canonical public phase label for object picking. `id` is
resource/pass/debug terminology, not a built-in picking phase alias. Material
authors may still create a custom material phase named `id`, but engine
drawable APIs must not treat it as a second public picking representation
unless a separate pass really owns that representation.

## Current Consumers

### Material Routing

`MeshRenderer`, `SkinnedMeshRenderer`, `LineRenderer`, `WorldTextComponent`,
foliage, and voxel debug/display components expose phase marks and filter
material phases by label. This is the primary and intended use of
`phase_mark`.

### Pass Routing

`ColorPass`, `ShadowPass`, `IdPass`, `DepthPass`, `DepthOnlyPass`, and
`NormalPass` provide explicit phase labels when collecting draw calls or shader
usage. `GeometryPassBase` treats an empty phase label as an error and stops
collection.

### Shader Contracts

Passes declare shader/layout intent through `MaterialPipelinePassContract`.
Registered RenderItem encoder planners consume that contract when selecting the
final shader and enumerating shader usages; drawables do not own shader
selection.

### Drawable ABI

The C drawable ABI exposes participation and typed RenderItem collection only.
It has no shader override or shader-usage callbacks. C, C++, and Python
components publish the same typed RenderItems and therefore reach the same
pass-owned task shader planner.

### Debug And Editor

Inspector fields expose pass phase labels because users need to configure which
drawable/material representation a pass requests. Debugger and editor tooling
may display phase names, but should not treat them as a complete description of
shader ABI or backend resource layout.

## Rules For New Code

When adding a render pass:

- expose a non-empty `phase_mark` if the pass asks drawables for geometry;
- document the default label as a representation/material routing convention;
- declare shader ABI, vertex transform, resources, and fragment requirements
  through a pass contract;
- use material phase shaders only as an explicit shader source policy, not as a
  second hidden phase system;
- add tests that use a custom phase label when the pass contract must be
  independent from well-known built-in labels.

When adding a drawable:

- return only the registered phase bits the drawable actually supports from
  `get_phase_mask()`/`phase_mask`;
- submit renderable work through RenderItems from `collect_render_items()`;
- submit actual draw work through RenderItems and registered encoders, not
  drawable-owned backend draw calls;
- implement shader variants in the item kind's task-planning hook using the
  pass-owned `MaterialPipelinePassContract`;
- enumerate every runtime shader produced by that planner for build/export.

If a behavior cannot be expressed without reading semantic shader meaning from
a phase label, the missing concept should become an explicit contract field or
pass policy.
