# Runtime Type Registry Refactor Plan

Date: 2026-06-28

## Status

Active target architecture and migration plan.

Implementation progress:

- common runtime type registry storage lives in C in `termin-inspect`
  (`tc_runtime_type_registry.c`);
- public registry access is exposed through the C ABI
  (`tc_runtime_type_registry_*`);
- the former C++ `RuntimeTypeRegistry` storage/wrapper layer has been removed;
- inspect/component/pass registries publish runtime type facets;
- owner, parent, facet ids, and debug snapshots are available through the
  common registry;
- module unload now removes module-owned runtime type records through the
  common registry and relies on facet cleanup callbacks for domain registries;
- inspect field, backend, and metadata storage now lives in the
  `termin.inspect.fields` facet payload instead of parallel compatibility maps;
- component factory, kind, abstract flag, requirements, and type-level
  capability storage now live in the `termin.scene.component` facet payload;
- Python module cleanup still handles Python-only class/kind side storage
  separately, then delegates runtime type cleanup to the common registry.

Remaining migration pressure:

- trim now-obsolete component-specific fields from the low-level
  `tc_type_entry` once pass-registry users are audited;
- migrate project modules away from static registration macros.

This document captures the direction after the Play-mode module reload
regression where C++ component instances remained alive but their concrete
inspect fields disappeared from the editor inspector.

The immediate symptom is not the target fix. The target is to remove the
architectural split where `ComponentRegistry`, `InspectRegistry`,
`FramePassRegistry`, and Python module cleanup each own different lifecycle
state for the same runtime type.

## Problem Statement

Runtime type identity is currently fragmented:

- `ComponentRegistry` owns component factory, component parent, kind,
  capabilities, requirements, owner, and live instance linkage.
- `InspectRegistry` owns inspect fields, inspect parent, backend, metadata,
  owner, and serialization callbacks.
- pass registries own their own class/factory state and module cleanup state.
- Python module context records module-owned resources separately from the
  native registries.

These registries all describe the same conceptual object:

```text
runtime type "ObjectController"
runtime type "MaterialPass"
runtime type "SomeProjectFramePass"
```

but they do not share a single lifecycle record. During module reload this can
create partial states:

- component type exists, but inspect fields were removed;
- inspect type exists, but component factory was removed;
- parent differs between component and inspect worlds;
- owner maps disagree;
- unload cleanup removes one registry entry while another registry still keeps
  enough data to make the type look valid.

The current guard/adoption patches can reduce damage, but they do not fix the
core issue. The system needs one owner/lifecycle model for runtime type records.

## Core Decision

Introduce a low-level runtime type registry in `termin-inspect` or a sibling
library below `termin-scene`, `termin-render`, and `termin-app`.

The registry is domain-agnostic. It must not know what a component, frame pass,
drawable, material, or editor object is.

It owns only generic type state:

```text
RuntimeTypeRecord
  name
  owner/module_id
  parent
  version/generation
  facets: map<facet_id, opaque payload>
  instances: intrusive list of opaque runtime instance links
```

Domain systems publish facets into the record:

```text
termin.inspect.fields
termin.scene.component
termin.render.frame_pass
termin.render.drawable
termin.app.resource_component
```

The registry treats all facet ids as opaque strings. It can store, replace,
remove, and destroy facets, but it cannot interpret their meaning. It may also
own an opaque live-instance index for each type record, because module unload
must be able to find all live instances before removing the type's facets.

## Non-Goals

- Do not move component instance semantics into `termin-inspect`.
- Do not move scene ownership, entity pools, render execution, or pass runtime
  state into the type registry.
- Do not make `termin-inspect` include headers from `termin-scene` or
  `termin-render`.
- Do not add component/pass-specific branches to the common registry.
- Do not solve static module registration by adding more fallback cleanup rules.
  Static registration should be migrated away, not normalized.

## Layer Ownership

### Runtime Type Registry

Owns:

- type name identity;
- owner/module id;
- parent relationship;
- generation/version;
- opaque live-instance link storage;
- facet storage and facet lifecycle callbacks;
- owner-scoped cleanup;
- conflict diagnostics.

Does not own:

- component factory semantics;
- component-to-Unknown mutation semantics;
- pass execution semantics;
- inspect field rendering;
- scene instances;
- render graph state;
- editor UI policy.

### `InspectRegistry`

Becomes the owner of the `termin.inspect.fields` facet API.

It keeps the public inspect-facing operations:

- register inspect fields;
- register serializable fields;
- register buttons/actions;
- read/write field values;
- enumerate inherited fields.

But storage moves from independent maps to the common type record facet. Parent
and owner must come from the common record.

### `ComponentRegistry`

Becomes the owner of the `termin.scene.component` facet API.

It keeps the public component-facing operations:

- register native component factory;
- register Python component factory;
- register abstract component;
- create component instance by type;
- query component kind/capabilities/requirements;
- publish component instances into the common runtime type record;
- provide the callback that mutates component instances to `UnknownComponent`
  before component facet removal.

But type owner, parent, and lifecycle must come from the common record.

### Frame/Pass Registries

Become owners of pass-related facets.

They keep pass-specific APIs, but no longer maintain separate owner/lifecycle
maps for runtime type identity.

### Module Runtime

Module load/unload/reload talks to the common type registry for ownership
cleanup.

The module system should not need to know whether a type has component, inspect,
pass, or app-resource facets. It should say:

```text
remove every facet/type record owned by module X
```

or, during staged reload:

```text
snapshot module-owned type records
prepare live instances for unload through facet callbacks
remove module-owned facets after live instances are safe
reload module
validate required facets are restored
restore scene instances
```

## Facet Model

Current C ABI shape:

```c
typedef void (*tc_runtime_type_facet_destroy_fn)(void* payload);
typedef bool (*tc_runtime_type_iter_fn)(const char* type_name, void* user_data);
typedef bool (*tc_runtime_type_facet_iter_fn)(const char* facet_id, void* user_data);

bool tc_runtime_type_registry_ensure_type(const char* type_name);
bool tc_runtime_type_registry_set_facet(
    const char* type_name,
    const char* facet_id,
    void* payload,
    tc_runtime_type_facet_destroy_fn destroy,
    uint32_t abi_version);
void* tc_runtime_type_registry_get_facet(const char* type_name, const char* facet_id);
void tc_runtime_type_registry_foreach_type_with_facet(
    const char* facet_id,
    tc_runtime_type_iter_fn callback,
    void* user_data);
bool tc_runtime_type_registry_link_instance(
    const char* type_name,
    tc_runtime_type_instance_link* link,
    void* instance);
void tc_runtime_type_registry_unlink_instance(tc_runtime_type_instance_link* link);
size_t tc_runtime_type_registry_instance_count(const char* type_name);
void tc_runtime_type_registry_foreach_instance(
    const char* type_name,
    tc_runtime_type_instance_iter_fn callback,
    void* user_data);
```

The common registry only promises:

- payload pointer lifetime;
- destroy callback invocation;
- owner-scoped removal;
- live-instance unload preparation before removal;
- replacement semantics;
- diagnostics when two owners try to write the same facet.

Typed domain APIs own their payloads and publish them into the C registry:

```text
tc_component_registry_register_with_parent(...)
  -> tc_runtime_type_registry_ensure_type(...)
  -> tc_runtime_type_registry_set_facet("termin.scene.component", payload)

InspectRegistry::add_field(...)
  -> tc_runtime_type_registry_ensure_type(...)
  -> tc_runtime_type_registry_get_facet("termin.inspect.fields")
  -> tc_runtime_type_registry_set_facet("termin.inspect.fields", payload)

FramePassRegistry::register(...)
  -> tc_runtime_type_registry_ensure_type(...)
  -> tc_runtime_type_registry_set_facet("termin.render.frame_pass", payload)
```

C++ code may keep thin template helpers and binding facades, but it must not be
the storage owner for runtime type records or build runtime-side mirror lists
just to talk to the registry.

## Live Instance Index

The common runtime type record owns the live-instance list for the type.
This is required for unload/reload correctness: when a module-owned type is
unloaded, the system must find every live instance of that type before removing
the type's component/pass/inspect facets.

The index is still domain-agnostic. A runtime instance link contains only:

```c
typedef struct tc_runtime_type_instance_link {
    tc_dlist_node node;
    const char* type_name;
    uint64_t generation;
    void* instance;
} tc_runtime_type_instance_link;
```

The common registry may:

- link/unlink opaque instances to a type record;
- count and iterate instances for a type record;
- keep tombstoned type records alive while instance links still exist;
- call facet lifecycle hooks before removing module-owned type facets.

The common registry must not:

- include component, scene, pass, or render headers;
- know what `UnknownComponent` is;
- serialize component state;
- remove scene-owned objects directly;
- call component/pass factories.

Domain facets provide unload behavior. For `termin.scene.component`, the facet
owns the logic that receives a type record and its live instance links, locates
the scene/entity ownership, serializes the component, replaces it with
`UnknownComponent`, and unlinks the old instance. For `termin.render.frame_pass`,
the facet can provide a different unload policy or reject unload while pass
instances are alive.

Unregistration must therefore be two-phase:

```text
prepare_unload(type record, facet callbacks, live instances)
  -> domain facet mutates or rejects live instances
remove module-owned facets
keep tombstoned type record while live links remain
remove type record when no facets and no live links remain
```

## Parent And Inheritance

There must be one parent relationship per runtime type record.

Rules:

- component inheritance and inspect inheritance must use the same parent;
- registering a different parent for an existing type is an error unless the
  caller is the same owner and the type has no live instances;
- inherited inspect fields are resolved through the common parent chain;
- component `is_a` checks are resolved through the common parent chain;
- pass/resource types may also use the parent chain when useful, but the common
  registry does not interpret why.

This removes the current state where component parent and inspect parent can
silently diverge.

## Ownership Rules

Owner is a property of the type record, not of each domain registry.

Initial rules:

- engine/bootstrap registrations may be unowned only during bootstrap.
- project module registrations must run with an explicit owner.
- a module may update its own type records and facets.
- a module may not mutate unowned engine records.
- replacing a facet owned by another module is an error.
- creating a type without owner after bootstrap is a warning or error depending
  on build/profile.

Open design point:

- Facets may need per-facet ownership only for advanced sharing. Avoid this
  until a real use case appears. The first migration should use one owner per
  type record.

## Reload Transaction

Target reload sequence:

```text
capture module-owned type names and live component state
degrade live component instances for affected component facets
remove module-owned type records/facets
load module in owner scope
validate required facets came back
upgrade live unknown components
restore reload state
```

Validation must catch partial reload states:

- component facet restored but inspect facet missing when the type previously
  had inspect fields;
- inspect facet restored but component facet missing for scene component types;
- parent changed unexpectedly;
- backend changed unexpectedly;
- stale static registration attempted outside owner scope.

Failed reload should leave scene instances degraded to `UnknownComponent` with
clear diagnostics instead of silently losing inspect fields.

## Static Registration Policy

Static registration macros are the wrong default for project modules because
they hide registration timing from module lifecycle code.

Target:

- engine/bootstrap may keep controlled static registration temporarily;
- project modules should register explicit functions from `module_init`;
- `REGISTER_COMPONENT` should become a bootstrap helper, not the project module
  standard path;
- static registrars must log when they run outside an explicit owner scope
  after bootstrap.

ChronoSquad currently contains module headers with `REGISTER_COMPONENT(...)`
and `INSPECT_FIELD(...)` static registrars. This is a known migration pressure
point and should be one of the first real-world conversion targets.

## Python Module Context

Python module context should stop maintaining a separate source of truth for
type ownership.

It should:

- set the current common type owner before importing module packages;
- record app-only resources that are not runtime type records;
- ask the common registry to remove module-owned records on unload;
- avoid separate component/inspect cleanup lists once the common registry owns
  those records.

## Migration Plan

### Phase 0: Diagnostics And Safety

- Add debug dump APIs for runtime type records:
  - type name;
  - owner;
  - parent;
  - backend;
  - facet ids;
  - generation;
  - source/debug provenance.
- Add logs when component and inspect parent/owner disagree in the current code.
- Add a Play-mode reload regression that asserts C++ component inspect fields
  survive reload.
- Add a test for partial state detection: component restored without inspect
  fields must be reported as a reload error.

### Phase 1: Common Type Record Skeleton

- Introduce the common record type and registry storage below domain modules.
- Move owner, parent, generation, and facet storage into the common C record.
- Keep backend/runtime tags and metadata inside domain-owned facets unless a
  truly generic use case appears.
- Keep old public APIs as wrappers where needed, but do not keep parallel
  owner/lifecycle maps.
- Add owner-scoped cleanup on the common registry.

### Phase 2: Inspect Facet

- Move `InspectRegistry` field storage into `termin.inspect.fields` facet.
- Resolve inherited fields via the common parent chain.
- Remove independent inspect owner and parent maps.
- Keep the current Python/C++ inspect APIs source-compatible.

### Phase 3: Component Facet

- Move component factory/kind/capability/requirement storage into
  `termin.scene.component` facet.
- Resolve `ComponentRegistry::is_a` and descendant queries through the common
  parent chain.
- Move component live instance linkage from `tc_type_entry` to common runtime
  type instance links. This is now the active component `instance_count` source;
  `tc_type_entry/type_version` remain only as compatibility metadata until the
  legacy registry shell is removed.
- Provide a component facet unload hook that degrades live component instances
  to `UnknownComponent` before the component facet is removed.
- Remove independent component owner and parent maps.

### Phase 4: Pass Facets

- Move frame/pass type ownership into common type records.
- Move frame/pass factory/kind storage into `termin.render.frame_pass` facet.
- Move frame/pass live instance linkage from `tc_type_entry` to common runtime
  type instance links. This is now the active pass `instance_count` source.
- Decide pass live-instance unload policy explicitly: degrade, reject unload,
  or require owner pipeline teardown before type removal.
- Keep pass-specific factory/spec APIs in render/app layers.
- Remove pass-specific module owner cleanup where it duplicates common cleanup.

### Phase 5: Module Lifecycle Transaction

- Replace separate component/inspect cleanup calls with common type cleanup
  that first prepares live instances through facet callbacks.
- Add reload validation for expected facets.
- Make failed reload leave components degraded with explicit diagnostics.
- Remove adoption fallbacks that only exist to paper over split registries.

### Phase 6: Static Registration Migration

- Convert ChronoSquad `chrono_controllers` to explicit `module_init`
  registration.
- Convert engine project-module samples/tests.
- Demote static macros to bootstrap-only helpers.
- Add diagnostics for static registration outside explicit owner/bootstrap
  scope.

## Acceptance Criteria

- A runtime type has one owner and one parent.
- `ObjectController` cannot exist as a component type while its concrete inspect
  fields are silently missing after successful reload.
- Module unload removes all module-owned type records/facets through one API.
- Module reload validates that previously present facets were restored.
- `ComponentRegistry`, `InspectRegistry`, and pass registries expose their old
  public APIs while sharing the same underlying type record.
- The common registry does not include component/pass/render headers and does
  not branch on domain-specific facet ids.
- Static project-module registration is no longer required for ChronoSquad
  controllers.

## Risks

- Moving live component instance linkage without tombstone semantics can leave
  dangling links during hot reload. Type records must survive facet removal
  while any live instance links remain.
- Existing tests may rely on unowned ad-hoc type registration. These should be
  made explicit bootstrap/test-owner registrations.
- Python cleanup currently mixes runtime type state and app resource state.
  Split these carefully so app-only registries are not accidentally removed.
- ChronoSquad also directly loads `libchrono_controllers.so` through
  `ctypes.CDLL` in UI/editor helpers. This bypasses module runtime ownership and
  must be migrated, otherwise lifecycle bugs can survive the registry refactor.

## Immediate Next Step

Phase 1, Phase 2, and the semantic storage part of Phase 3 are now in place:
the common record is C-owned, inspect fields are facet-backed, component
factory/kind/requirement/capability state lives in the component facet, and
component/pass live instance counts come from common runtime type links.

Next migration steps:

1. Add component facet unload hooks that degrade live instances to
   `UnknownComponent` before facet removal.
2. Implement `UnknownPass` or an explicit pass unload rejection policy so module
   reload can preserve pipeline slots without executing unloaded code.
3. Move frame/pass ownership and semantic storage into runtime type facets.
4. Trim obsolete component/pass-specific fields from `tc_type_entry`, then
   remove the legacy registry shell.
5. Convert project modules away from static registration macros and toward
   explicit `module_init`/bootstrap registrations.
6. Remove adoption fallbacks that only existed to survive split registry state.
