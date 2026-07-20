# Canonical C resource layer audit

Date: 2026-07-20

Authority: `docs/canonical-c-layer-resource-storage.md`.

## Required invariants

Canonical engine resources live in process-owned C storage. Language and
subsystem boundaries exchange weak generation handles, while explicit strong
owners retain/release resources. Runtime systems such as `EngineCore` may use
the pools but do not initialize, shut down, or otherwise own them.

An aggregate runtime resource owns its nested polymorphic objects and records
the deleter supplied by their factory. The nested object's lifetime cannot
exceed the aggregate owner's lifetime.

## Pipeline result

The two pipeline roles are distinct parts of one pattern, not two competing
resource models:

- `tc_pipeline_template` is the canonical immutable/versioned compiled template;
- `tc_pipeline` is a mutable execution instance and owns live `tc_pass`
  implementations plus their deleters and device-local caches;
- a scene holds a strong `tc_pipeline_template_handle` reference;
- `RenderTopology` creates a separate `tc_pipeline` instance per attached
  scene/topology and the instance retains its template.

The explicit runtime-only `tc_pipeline_create()` factory is the deliberate
exception: it creates only a mutable collection and returns an invalid
template handle. It must not synthesize an empty canonical resource that could
be mistaken for the collection's immutable definition.

The implementation after #653/#654 still routed scenes through a second
process-global `tc_scene_pipeline_template` registry. That resource stored an
authored graph, was serialized into scene mounts, and was compiled at scene
attach time. It bypassed the new canonical resource and kept authoring data in
the runtime layer.

#687 removes that duplicate registry. #692 gives the surviving canonical type
its unambiguous `tc_pipeline_template` name. Scene mounts now retain canonical
compiled templates, serialize their UUID references, and instantiate runtime
pipelines directly from compiled descriptors. Authored graph/pass-list data
stays at the asset/import boundary.

## Resource inventory

| Resource | C storage / identity | Audit status |
| --- | --- | --- |
| `tc_mesh` | process-global generation pool + UUID map | Canonical shape; common lifecycle/diagnostics cleanup remains |
| `tc_texture` | process-global generation pool + UUID map | Canonical shape; common lifecycle/diagnostics cleanup remains |
| `tc_shader` | process-global generation pool + UUID map | Canonical shape; strongest current stale-handle diagnostics |
| `tc_shader_program` | process-global generation pool + UUID map | Canonical shape; missing uniform Core Registry projection |
| `tc_material` | process-global generation pool + UUID map | Canonical shape; common lifecycle/diagnostics cleanup remains |
| `tc_pipeline_template` | process-global generation pool + UUID map | Canonical after #687 scene-mount migration |
| `tc_animation` | process-global generation pool + UUID map | Canonical shape; lifecycle differs from navmesh/voxel grid |
| `tc_skeleton` | process-global generation pool + UUID map | Canonical shape; lifecycle differs from navmesh/voxel grid |
| `tc_navmesh` | process-global generation pool + UUID map | Handle/storage canonical; release does not destroy at zero |
| `tc_voxel_grid` | process-global generation pool + UUID map | Handle/storage canonical; release does not destroy at zero |
| `tc_scene` | process-global generation pool | Canonical long-lived runtime object |
| `tc_viewport` | process-global generation pool | Canonical shape; bootstrap ownership must be made uniform |
| `tc_render_target` | process-global generation pool | Canonical shape; bootstrap ownership must be made uniform |
| `tc_display` | individually allocated raw pointer | Non-canonical; tracked by #690 |
| `tc_ui_document` | individually allocated raw pointer | Non-canonical; tracked by #691 |
| `tc_entity` | scene-owned SoA generation pool | Correct second-level form |

## Nested polymorphic ownership

| Base type | Owner | Audit status |
| --- | --- | --- |
| `tc_component` | `tc_entity` | Owner/deleter pattern implemented |
| `tc_pass` | runtime `tc_pipeline` | Owner/deleter pattern implemented and tested |
| `tc_widget` | `tc_ui_document` | Document-local handles exist; document storage itself is non-canonical (#691) |
| `tc_render_surface` | `tc_display` | Raw pointer boundary and ownership contract require the #690 migration |

## Cross-cutting gaps

The generation check exists in the pools, but most `tc_*_get` functions return
`NULL` silently for a stale handle. Only selected paths, notably shader static
retention and the corrected scene pipeline mount, emit useful diagnostics.
Uniform checked resolution and Core Registry coverage are tracked by #689.

Initialization and final-release policy are also inconsistent. Some canonical
registries self-initialize, only a subset participates in process bootstrap,
and `navmesh`/`voxel_grid` release semantics differ from
`animation`/`skeleton`. The common lifecycle migration is tracked by #688.

No compatibility fallback should recreate the historical
`tc_scene_pipeline_template`, raw
display ownership, or raw UI-document ownership. This is an active-development
migration and old authored/runtime data should fail with a logged diagnostic
until republished through the canonical resource path.
