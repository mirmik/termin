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

A canonical source document currently uses schema `3.0`. It deliberately wraps
the existing native hierarchy serialization instead of introducing a second
flat entity codec:

```text
PrefabDocument
  version = "3.0"
  uuid                         # prefab asset UUID
  root
    uuid                       # entity source-local ID
    name, pose, flags, order
    components[]
      source_id
      native type identity
      typed serialized fields
    children[]                 # recursive entity hierarchy
```

Entity source-local IDs are stored in the hierarchy's `uuid` fields. Runtime
instantiation treats those values as source identity and allocates fresh entity
UUIDs for every concrete instance. Source editing materializes the hierarchy
without remapping so that save preserves stable entity and component source
identities.

Readers accept exactly `3.0`. Versions `1.0` and `2.0` require an explicit
migration tool and are never upgraded as a side effect of load or save.

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

The native property-key grammar is deliberately separate from the legacy
Python `PropertyPath` traversal syntax:

- an empty component ID addresses the source entity. Supported base paths are
  `name`, `visible`, `enabled`, `pickable`, `selectable`, `priority`, `layer`
  and `flags`; transform paths are `transform.position`,
  `transform.rotation` and `transform.scale`;
- a non-empty component ID addresses exactly that component `source_id`, and
  the path is its registered inspect field path without a hierarchy/type
  prefix;
- child names, component types and list indices are never identity fallbacks.

## Instantiation and reconciliation

Instantiation is one native transaction:

1. Validate the document and target scene/parent.
2. Allocate all entities with fresh runtime UUIDs.
3. Build the source-to-runtime mapping.
4. Attach the hierarchy.
5. Create native components and remap internal references.
6. Apply instance overrides, if loading saved instance state.
7. Publish the instance record only after the hierarchy is complete.

Reconciliation compares the current document with the instance by stable
source-local identity. A mapped entity/component is source-owned; an unmapped
one is local. The structural phase creates missing source-owned targets,
replaces changed component types through checked factories, removes disappeared
source targets, converges parent and order, and then runs the property source
and override passes. Unmapped local structure is never removed merely because
it is absent from the source.

Structural intent is stored as versioned tombstone and placement records.
Entity/component tombstones suppress source recreation. Entity placements name
an explicit source or local parent plus a source/local/end order anchor;
component placements use a source/local/end component anchor. Tombstones make
property overrides below the suppressed target dormant rather than deleting
them. Removing a tombstone reactivates the same stable identities. Placement
records win over canonical source parent/order and survive generic clone and
scene serialization through real `Entity` handles for local anchors.

Ordering uses a stable slot merge: local siblings retain their positions and
relative order, while source-owned siblings occupy the source-owned slots in
the current source order. Source entity removal splices local children into the
nearest surviving parent. If a removed source entity owns local components,
the runtime entity is demoted to an unmapped local shell instead of being
destroyed. Source removal conflicts with retained property/placement intent
unless a tombstone explicitly authorizes suppression.

The operation is deterministic best effort. A global document/asset/state
preflight happens before mutation. Independent source and override fields then
run in property-key order through checked native setters. Failed override
records remain untouched, successful override records also remain because they
continue to define instance intent. The instance revision advances to the
document revision only when every structural operation, planned source field and
every override all succeed. Explicit reconciliation is not skipped merely
because revisions already match, so it can repair accidental live drift.

Canonical instantiation options such as an explicit root name and position are
recorded immediately as typed overrides. They therefore obey the same rules as
later editor changes instead of relying on a special-case exclusion during
refresh.

Clearing a property override is itself a narrow reconciliation operation. The
caller supplies the current `PrefabDocument`; the runtime resolves the source
entity/component and current serialized field value, applies it through a
checked native setter, and erases metadata only after confirmed success. It
does not require source revision equality and does not update the instance
revision, because clearing several fields is not a full source reconciliation.

`clear_all_property_overrides` is deterministic best effort, not falsely
atomic: keys are processed in `(source entity ID, source component ID, field
path)` order, successful entries are restored and erased, and failed entries
remain serialized with structured diagnostics. Arbitrary component setters do
not currently provide a reversible transaction protocol, so rolling back
already successful independent setters would be less reliable than retaining
only the failures. The operation never creates, deletes, reparents or reorders
entities/components and therefore preserves unrelated local structural edits.

Entity references in source component values are translated through the
instance source-to-runtime mapping before assignment. Native handle kinds also
carry an inspect-registry capability marker: a non-empty UUID that resolves to
an invalid handle fails before assignment. Names are diagnostic only and are
not resource lookup fallbacks. Metadata-only deletion remains available under
the explicit `discard_*` API solely for repair/migration tooling.

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
  substrate required by `PrefabDocument` schema `3.0`;
- native `PrefabDocument` owns strict `3.0` parsing, validation, canonical JSON
  serialization, source capture and direct source materialization. It rejects
  legacy schemas and duplicate entity/component source identities;
- editor persistence is now a thin `termin.prefab.persistence` transaction:
  reads validate without modifying the source, writes validate before an
  `fsync` plus same-directory atomic replace, and failures retain the previous
  file;
- prefab edit mode creates a fresh isolation scene and materializes the source
  document directly into it. A failed load closes that temporary scene and
  leaves the normal editor scene and play state untouched;
- `PrefabAsset` and editor persistence use the same native document parser and
  serializer; the duplicate `termin.editor_core.prefab_persistence` serializer
  has been removed;
- instantiated roots now carry native `PrefabInstanceState`. It serializes the
  prefab asset UUID, deterministic source revision and ordered source IDs plus
  entity references; generic hierarchy cloning therefore remaps its runtime
  references without a prefab-specific scene serializer;
- live instance lookup uses the exact `PrefabInstanceState` component index
  already owned by each scene and returns snapshots of generation-checked
  entity handles. Entity/component removal and scene teardown remove records
  through the ordinary native lifecycle; the Python `WeakSet` registry and
  `PrefabInstanceMarker` have been removed.
- native `PrefabOverrideValue` now owns codec version 1 as a strict tagged tree
  over `tc_value`. It preserves `none`, scalar width, list/tuple distinction,
  ordered string-key dictionaries, dense-array dtype/shape, registered inspect
  kinds and typed UUID resource references. Invalid versions, tags, shapes,
  duplicate keys, unsupported Python objects and non-finite numbers fail
  explicitly;
- `PrefabInstanceState` stores typed property overrides by source entity ID,
  optional source component ID, field path and target inspect kind. Generic
  clone and scene serialization round-trip this metadata without Python.
- clearing native property overrides now restores values from an explicit
  current `PrefabDocument`. Entity/transform fields use a closed native path
  grammar; component fields resolve strictly by source IDs and checked inspect
  metadata. Single clear is erase-on-success, while clear-all restores every
  resolvable entry in stable order and retains diagnosed failures;
- native handle-kind deserialization now rejects unresolved non-empty UUIDs,
  allowing component resource restoration to fail without overwriting the
  live value. Entity source references are remapped to the concrete instance;
  scalar/container/reference/resource, malformed source and mixed batch tests
  run in the Python-disabled native target.
- native reconciliation now performs global preflight, convergent structural
  mutation, a source-value pass that skips exact override keys, and a typed
  override pass. It creates/removes/reparents/reorders source-owned entities
  and components by stable IDs, preserves unmapped local structure, supports
  tombstone and placement intent, and keeps mappings coherent for retry after
  partial failure. Failures are returned in stable phase/key order and keep the
  previous source revision; a complete pass advances it. Explicit root
  name/position instantiation options are published as ordinary typed
  property overrides;
- `PrefabAsset` hot reload now calls this native transaction for each live
  instance. The old Python `PropertyPath` traversal, resource-name heuristics
  and unconditional revision assignment are no longer part of refresh.

The remaining violations and gaps are:

- the low-level hierarchy overload on `PrefabInstantiator` remains as a legacy
  adapter for existing native callers. Canonical asset/editor callers pass a
  validated `PrefabDocument`;
- the Python runtime asset plugin remains until native asset registration and
  packaged loading replace it;
- `termin-runtime` itself is already a native, Python-free library and is the
  correct packaged-project loading boundary, but it does not yet load prefab
  resources;
- structural and property reconciliation are native and complete for recorded
  source ownership and override intent. Editor mutation capture is still
  separate: editor commands do not yet atomically create tombstone/placement
  records when the user deletes, reparents or reorders prefab-owned structure.

`termin_player` requiring and packaging Python is intentional for its role as
an editor-adjacent development/source host and is not a violation of this
architecture. The violation would be implementing prefab semantics only in
that host's Python modules or making native `termin-prefab`/`termin-runtime`
link against Python.

## Migration order

1. Introduce the native prefab document and identity contracts, with
   Python-free unit tests. **Done for schema `3.0`; the typed override value
   contract remains part of the override/reconciliation phase.**
2. Move hierarchy instantiation to the native clone/deserialization path and
   prove multiple instances, full hierarchy and reference remapping. **Done.**
3. Replace `PrefabInstanceMarker` and `PrefabRegistry` with native instance
   state and scene-owned tracking. **Done.**
4. Make editor persistence and UI consume bindings to the canonical native
   document; remove the second serializer and old runtime plugin. **Persistence
   and prefab edit isolation are done; removal of the Python runtime plugin is
   coupled to steps 3 and 5.**
5. Add native prefab resources to runtime-package export, validation and
   `termin-runtime` loading.
6. Add native reconciliation and editor override capture, then retire the old
   Python implementation and schemas. **The versioned value codec, native
   property/structural override storage and full native reconciliation are
   done. Editor mutation capture remains.**

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
- Kanboard #467: checked inspect setter failure propagation. **Done.**
