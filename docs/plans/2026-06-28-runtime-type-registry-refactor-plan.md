# Runtime Type Registry Refactor Plan

Date: 2026-06-28

## Status

Active target architecture and migration plan.

Implementation progress:

- common `RuntimeTypeRegistry` skeleton exists in `termin-inspect`;
- inspect/component/pass registries publish runtime type facets;
- owner, parent, facet ids, and debug snapshots are available through the
  common registry;
- module unload now removes module-owned runtime type records through the
  common registry and relies on facet cleanup callbacks for domain registries;
- Python module cleanup still handles Python-only class/kind side storage
  separately, then delegates runtime type cleanup to the common registry.

Remaining migration pressure:

- move inspect field storage fully into the inspect facet instead of keeping
  compatibility maps;
- move component factory/capability/requirement storage fully into the
  component facet;
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
  backend/runtime
  parent
  version/generation
  facets: map<facet_id, opaque payload>
  metadata: generic key/value data
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
remove, and destroy facets, but it cannot interpret their meaning.

## Non-Goals

- Do not move component instances into `termin-inspect`.
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
- backend/runtime tag;
- generation/version;
- facet storage and facet lifecycle callbacks;
- owner-scoped cleanup;
- conflict diagnostics.

Does not own:

- component factory semantics;
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
- iterate live instances through the existing type-entry linkage or a migrated
  equivalent.

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
remove module-owned facets
reload module
validate required facets are restored
restore scene instances
```

## Facet Model

Initial C ABI shape:

```c
typedef void (*tc_type_facet_destroy_fn)(void* payload);

typedef struct tc_runtime_type_facet {
    const char* facet_id;
    void* payload;
    tc_type_facet_destroy_fn destroy;
    uint32_t abi_version;
} tc_runtime_type_facet;
```

The common registry only promises:

- payload pointer lifetime;
- destroy callback invocation;
- owner-scoped removal;
- replacement semantics;
- diagnostics when two owners try to write the same facet.

Typed wrappers live in domain modules:

```cpp
ComponentRegistry::register_native(...)
  -> RuntimeTypeRegistry::upsert_type(...)
  -> RuntimeTypeRegistry::set_facet("termin.scene.component", payload)

InspectRegistry::add_field(...)
  -> RuntimeTypeRegistry::upsert_type(...)
  -> RuntimeTypeRegistry::get_or_create_facet("termin.inspect.fields")

FramePassRegistry::register(...)
  -> RuntimeTypeRegistry::upsert_type(...)
  -> RuntimeTypeRegistry::set_facet("termin.render.frame_pass", payload)
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
- Move owner, parent, backend, generation, and metadata into the common record.
- Keep old registries as wrappers backed by compatibility maps where needed.
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
- Keep live instance linkage working through either the existing type entry or
  a migrated component facet structure.
- Remove independent component owner and parent maps.

### Phase 4: Pass Facets

- Move frame/pass type ownership into common type records.
- Keep pass-specific factory/spec APIs in render/app layers.
- Remove pass-specific module owner cleanup where it duplicates common cleanup.

### Phase 5: Module Lifecycle Transaction

- Replace separate component/inspect cleanup calls with common type cleanup.
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

- Moving live component instance linkage too early may destabilize scene
  runtime. Keep instance storage in `termin-scene` until the component facet is
  stable.
- Existing tests may rely on unowned ad-hoc type registration. These should be
  made explicit bootstrap/test-owner registrations.
- Python cleanup currently mixes runtime type state and app resource state.
  Split these carefully so app-only registries are not accidentally removed.
- ChronoSquad also directly loads `libchrono_controllers.so` through
  `ctypes.CDLL` in UI/editor helpers. This bypasses module runtime ownership and
  must be migrated, otherwise lifecycle bugs can survive the registry refactor.

## Immediate Next Step

Start with Phase 0 and Phase 1 in engine tests, not ChronoSquad first:

1. add runtime type debug dumps;
2. add a regression for C++ component inspect fields after module reload;
3. introduce the common record skeleton with owner/parent/facet ids;
4. adapt `InspectRegistry` and `ComponentRegistry` only enough to read/write
   shared owner/parent state.

Only after that should ChronoSquad controller registration be converted to
explicit `module_init`, because otherwise the project module will keep exposing
timing bugs from static registration.
