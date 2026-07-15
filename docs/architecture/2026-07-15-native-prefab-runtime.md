# Native Prefab Runtime Architecture

## Status and decision

Prefab support is a runtime engine feature with editor authoring tools. Its
canonical implementation must not depend on Python.

The target split is:

- C/C++ owns the prefab document model, validation, instantiation, instance
  state, reconciliation, lifetime tracking and runtime-package loading;
- Python may expose bindings and implement editor/build tooling, but it must
  not own the prefab mechanics required by a native runtime;
- the prefab and runtime libraries must remain usable when no Python
  interpreter, Python standard library, site-packages or Python module backend
  is present.

This language boundary applies to engine/runtime libraries, not to every host
application. `termin_player` is an editor-adjacent source/debug/automation host
and may embed and package Python. A Python-enabled host must still invoke the
same native prefab implementation through bindings; it does not justify a
second Python prefab runtime.

The host/library distinction is defined in
[Player Host and Embeddable Runtime Boundary](2026-07-15-player-and-runtime-boundary.md).

The existing Python implementation under `termin.prefab` is not the target
runtime. It is migration input for the editor tooling and tests. In particular,
`PrefabAsset`, `PrefabInstanceMarker`, `PrefabRegistry` and the Python
`PrefabRuntimePlugin` must not remain the canonical prefab-runtime execution
path.

This is a reconstruction of the prefab control layer, not a rewrite of scene
serialization. The existing native entity hierarchy serialization, clone
payload, UUID remapping and component factories remain the foundation.

## Invariants

### Language boundary

The following operations must be available through a native API and work in a
library build configured without Python:

- parse and validate a packaged prefab document;
- register and resolve a prefab asset by asset UUID;
- instantiate a complete hierarchy into a specified scene and parent;
- assign fresh runtime entity UUIDs and remap internal entity references;
- retain the association between instance nodes and source nodes;
- apply typed property overrides;
- reconcile a changed source document with live instances;
- destroy instances, unregister them and release asset state safely;
- serialize the native instance state as part of a scene when the format calls
  for it.

Python bindings may call these operations. They may not provide their only
implementation.

### Identity

Three identities are distinct and must never be conflated:

1. **Prefab asset UUID** identifies the prefab resource.
2. **Source-local ID** identifies an entity or component inside that prefab and
   remains stable while the source document is edited.
3. **Runtime UUID/handle** identifies one concrete entity or component in one
   scene instance.

Instantiation creates a mapping from source-local IDs to runtime handles.
Multiple instances therefore share source-local IDs but never runtime UUIDs.
Names and child/component indices are presentation and ordering data, not
identity.

### Ownership and lifetime

Live instance tracking belongs to the native scene/runtime layer. It uses
generation-checked handles or scene-owned records; it must not retain language
wrappers and must not depend on Python weak references.

The scene owns runtime entities and components. The prefab runtime owns only
the source document, the source-to-runtime mapping and reconciliation metadata.
Destroying or clearing a scene invalidates instance records deterministically.
Asset unload and hot reload must never dereference stale entities.

### Failure policy

Prefab loading and instantiation are transactional. Invalid version, duplicate
source-local ID, unresolved required type, malformed override or failed entity
creation aborts the operation with contextual logs. A partial hierarchy must
not be attached to the target scene, and editor save must not overwrite a
source document after a partial load.

There is no permissive fallback from a native prefab to the old Python runtime.

## Module ownership

### `termin-scene`

`termin-scene` remains prefab-neutral and owns:

- hierarchy serialization and deserialization primitives;
- clone payload creation and runtime UUID/reference remapping;
- scene/entity/component handles and their lifetime rules;
- language-neutral typed component inspection and assignment.

It must not know about prefab assets, overrides or source-local IDs beyond
generic metadata/serialization facilities needed by consumers.

### Native `termin-prefab`

`termin-prefab` becomes a native domain library, with an optional bindings
target. It owns:

- `PrefabDocument` and its versioned schema;
- source-local entity/component identity;
- `PrefabAsset` registration and lookup;
- `PrefabInstanceState` as native scene state/component data;
- typed override paths and values;
- `PrefabInstantiator` and `PrefabReconciler`;
- native instance indexing and hot-reload propagation.

The core target must not link Python, nanobind or editor libraries. Bindings are
a separate target and distribution surface.

### `termin-runtime`

`termin-runtime` owns packaged-project loading. It loads packaged prefab
resources through native `termin-prefab`, keeps them alive with the rest of the
runtime asset set and resolves scene references without requiring Python asset
plugins. A host that embeds Python may add Python-defined component factories,
but native prefab parsing, identity, hierarchy construction and instance state
do not depend on them.

The runtime-package manifest gains an explicit `prefab` resource type when
dynamic runtime instantiation is supported. A packaged prefab artifact is
validated build output, not an implicit read of a project-side `.prefab` file.

Scenes whose prefab instances are fully baked may omit unused prefab resources.
Scenes or native components that can instantiate a prefab at runtime must
declare that prefab in the package dependency graph.

### Editor and build tooling

Python is permitted on the authoring side:

- editor isolation mode and UI commands;
- inspector presentation and override visualization;
- source `.prefab` import/export orchestration;
- project dependency discovery and runtime-package export;
- validation diagnostics and migration commands;
- Python bindings used by editor automation and tests.

This code calls the native document/runtime APIs. It does not duplicate the
schema, hierarchy loader, override codec, registry or reconciler.

`termin.editor_core.prefab_persistence.PrefabPersistence` is therefore removed
or reduced to a thin editor transaction around the canonical native document.
The import side of the current Python asset plugin may remain editor tooling;
its runtime plugin does not.

## Document and instance model

The next prefab schema is a deliberate new version. Existing `1.0` and `2.0`
documents are not silently reinterpreted. During active development they may be
handled by an explicit one-shot editor migration or rejected with a diagnostic.

A source document contains at least:

```text
PrefabDocument
  schema_version
  asset_uuid
  root_source_id
  entities[]
    source_id
    parent_source_id
    name, pose, flags, order
    components[]
      source_id
      native type identity
      typed serialized fields
```

An instance contains at least:

```text
PrefabInstanceState
  prefab_asset_uuid
  source_revision
  source_id -> runtime handle mapping
  typed property overrides
  structural overrides
```

Property paths address stable source entity/component IDs plus a typed inspect
field path. Human-readable names can be included in diagnostics but are not
used to resolve ownership. Override values use an explicit versioned tagged
codec for scalar, container, math and resource-reference values; numeric lists
are never guessed to be vectors.

## Instantiation and reconciliation

Instantiation is one native transaction:

1. Validate the document and target scene/parent.
2. Allocate all entities with fresh runtime UUIDs.
3. Build the source-to-runtime mapping.
4. Attach the hierarchy.
5. Create native components and remap internal references.
6. Apply instance overrides, if loading saved instance state.
7. Publish the instance record only after the hierarchy is complete.

Reconciliation compares source revisions by stable source-local identity. It
updates source-owned values, creates/removes/reorders source-owned structure and
preserves explicit local overrides. Unsupported structural conflicts produce a
diagnostic and remain represented in instance state; they are not silently
dropped.

Editor property commits and undo/redo write the same typed native override
model. Editing a prefab source in isolation modifies the source document and
must not create instance overrides.

## Python-free library gate

The repository must have a positive gate, not merely an intention:

- native prefab and `termin-runtime` tests configure and link with Python
  discovery disabled;
- a native test host loads a packaged prefab, instantiates it into a scene and
  reconciles an update without initializing Python;
- runtime-package validation can check target capabilities: a native-only host
  rejects component types for which it has no factory, while a Python-enabled
  host may declare Python component support;
- dependency tests fail if native prefab/runtime targets acquire an editor or
  Python dependency.

A Python-enabled player, source host or automation host is allowed. It may link
`Python::Python`, package Python modules and load Python components. Its prefab
operations still go through bindings to the native prefab library, and its
existence must not weaken the Python-free library gate.

## Implementation state (2026-07-15)

The first native execution slice is in place:

- `termin-prefab` now contains a Python-free `termin_prefab` library and an
  optional `_prefab_native` binding;
- `PrefabInstantiator` validates a serialized hierarchy, creates fresh runtime
  UUIDs, remaps internal entity references and deserializes the full hierarchy
  directly into an explicit target scene and optional parent;
- hierarchy base creation in `termin-scene` rolls back already-created entities
  when a descendant cannot be constructed;
- `PrefabAsset.instantiate()` and editor drag/drop are thin callers of that
  native transaction rather than a second Python hierarchy loader;
- native and Python integration tests cover nested hierarchies, two disjoint
  instances, internal references, parented target-pool creation and malformed
  input without partial scene mutation;
- native components now carry a persistent `source_id` separate from their
  runtime pointer/owner handle. It is generated on attachment, serialized with
  hierarchy data, retained by runtime clones and preserved through
  `UnknownComponent` degradation and upgrade. This is the component-identity
  substrate required by the next `PrefabDocument` schema.

The remaining violations and gaps are:

- document parsing and versioning have not yet moved into the native library;
  the current instantiator accepts the existing serialized hierarchy
  representation. Entity source IDs are still represented by source UUIDs,
  while component `source_id` is now explicit;
- prefab instance state is still a `PythonComponent`, and live tracking still
  uses a Python `WeakSet`;
- the Python runtime asset plugin remains until native asset registration and
  packaged loading replace it;
- `termin-runtime` itself is already a native, Python-free library and is the
  correct packaged-project loading boundary, but it does not yet load prefab
  resources;
- native typed overrides and reconciliation are not implemented yet.

`termin_player` requiring and packaging Python is intentional for its role as
an editor-adjacent development/source host and is not a violation of this
architecture. The violation would be implementing prefab semantics only in
that host's Python modules or making native `termin-prefab`/`termin-runtime`
link against Python.

## Migration order

1. Introduce the native prefab document, identity and typed-value contracts,
   with Python-free unit tests.
2. Move hierarchy instantiation to the native clone/deserialization path and
   prove multiple instances, full hierarchy and reference remapping.
3. Replace `PrefabInstanceMarker` and `PrefabRegistry` with native instance
   state and scene-owned tracking.
4. Make editor persistence and UI consume bindings to the canonical native
   document; remove the second serializer and old runtime plugin.
5. Add native prefab resources to runtime-package export, validation and
   `termin-runtime` loading.
6. Add native reconciliation and editor override capture, then retire the old
   Python implementation and schemas.

The first four steps establish correctness. The last two close the runtime
boundary and make prefab behavior independent of whether a particular host
embeds Python.

## Related work

- Kanboard #390: prefab instance override reconciliation umbrella.
- Kanboard #443: typed override value codec; implementation must target the
  native tagged-value contract described here.
- Kanboard #444: restore source values when clearing overrides.
- Kanboard #461: complete hierarchy instantiation and fresh identities.
- Kanboard #462: canonical editor persistence and lossless round-trip.
- Kanboard #463: live instance tracking and hot reload.
- Kanboard #464: editor mutation capture and undo/redo integration.
