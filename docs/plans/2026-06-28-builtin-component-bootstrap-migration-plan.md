# Built-in Component Bootstrap Migration Plan

Date: 2026-06-28

Status: Implemented. Scope is intentionally limited to built-in scene components
and their inspect metadata.

Related taskboard card: `#138 [arch/bootstrap] Уйти от static registration`.

## Goal

Migrate built-in Termin C++ components away from static registration macros
such as `REGISTER_COMPONENT`, `REGISTER_ABSTRACT_COMPONENT`,
`REQUIRE_COMPONENT`, header-level `INSPECT_FIELD`, and related inspect field
registrars.

Built-in engine/component libraries should register their component types from
explicit bootstrap code. The composition root is `termin_bootstrap`, not a
project module `module_init()`.

Project modules should keep using the ChronoSquad-style pattern:

```cpp
extern "C" void module_init() {
    SomeProjectComponent::register_type();
}
```

Built-in components should use the same local shape, but the final call chain
must be:

```text
termin::bootstrap::bootstrap_runtime/player/editor()
  -> register built-in component package entrypoints
     -> ComponentClass::register_type()
```

## Non-Goals

- Do not migrate frame pass registration in this plan.
- Do not change `TC_REGISTER_FRAME_PASS`, pass inspect metadata,
  `INSPECT_TYPE_METADATA` for passes, or pass factory ownership here.
- Do not redesign the runtime type registry. This plan assumes the current
  common registry/facet model remains available.
- Do not keep compatibility fallback paths for old static registration once a
  component family is migrated. During active development it is better to fail
  loudly if a required bootstrap call is missing.
- Do not move component registration implementation into headers.

## Core Decisions

### Registration Methods Live In `.cpp`

Headers may declare:

```cpp
static void register_type();
```

but should not define registration logic inline. The implementation belongs in
the component's `.cpp` file or in a dedicated package registration `.cpp`.

This keeps public headers free of registration code and avoids recreating the
old include-time side effect pattern with a different spelling.

### Package Entrypoints Own Package Lists

Each component package should expose one explicit registration entrypoint, for
example:

```cpp
namespace termin {
void register_builtin_mesh_component_types();
void register_builtin_render_component_types();
}
```

The package entrypoint is responsible for calling all local component
`register_type()` functions in deterministic dependency order.

`termin_bootstrap` should call package entrypoints. It should not become a
large file that directly knows every field of every component.

### Use Direct Registration APIs Internally

Inside `.cpp` implementations prefer the existing direct APIs:

- `termin::register_component_type<T>(name, parent)`;
- `ComponentRegistry::register_abstract(...)`;
- `termin::register_component_requirement(...)`;
- `tc::register_inspect_field(...)`;
- `tc::register_inspect_field_choices(...)`;
- `tc::register_inspect_button_method(...)`;
- explicit `InspectFieldInfo` construction where callbacks, choices, or
  serializability flags require it.

Avoid adding new static-style macros for built-ins. If a tiny helper is needed,
make it a normal function or template, not a static registrar.

## Current Inventory

Component registration macros currently remain in production code under:

- `termin-scene/cpp/entity/unknown_component.cpp`
- `termin-components/termin-components-mesh`
- `termin-components/termin-components-collision`
- `termin-components/termin-components-kinematic`
- `termin-components/termin-components-render`
- `termin-components/termin-components-skeleton`
- `termin-components/termin-components-animation`
- `termin-components/termin-components-foliage`
- `termin-navmesh`

Some classes already have partial explicit `register_type()` implementations:

- `MeshComponent`
- `KinematicUnitComponent`
- `ActuatorComponent`
- `XrOriginComponent`
- `XrThumbstickLocomotionComponent`
- `FoliageLayerComponent`

These are good migration seeds, but old static macros and static inspect field
registrars still need to be removed from their headers/source files.

## Implementation Result

Completed on 2026-06-28.

- Built-in component packages now expose explicit package registration
  entrypoints.
- `termin_bootstrap` calls those entrypoints from `bootstrap_runtime()`.
- Registration method implementations live in `.cpp` files; headers only
  declare `register_type()` where needed.
- `UnknownComponent` is registered through the scene built-in entrypoint.
- Foliage's `foliage_data_handle` kind registration was also moved out of a
  static registrar because `termin_bootstrap` now links the foliage component
  package.
- Frame pass registration macros intentionally remain unchanged.

## Migration Phases

### Phase 0: Audit And Guardrails

Objective: freeze the exact component scope before editing registrations.

Work:

- Re-run a focused search for component static registrations:
  `REGISTER_COMPONENT`, `REGISTER_ABSTRACT_COMPONENT`, `REQUIRE_COMPONENT`,
  component `INSPECT_FIELD*`, component `SERIALIZABLE_FIELD`,
  component `INSPECT_BUTTON`.
- Exclude frame pass types from this inventory even if they use the same inspect
  macros.
- Add or update a short checklist in this document if the inventory changes
  before implementation starts.
- Identify package dependency order:
  scene base, mesh, collision, kinematic, skeleton, animation, render, foliage,
  navmesh components.

Deliverable:

- Confirmed component-only inventory and dependency order.

### Phase 1: Add Package Registration Entrypoints

Objective: create explicit entrypoints without changing behavior yet.

Work:

- Add public package bootstrap headers where needed, e.g.
  `termin/components_mesh/bootstrap.hpp`,
  `termin/components_render/bootstrap.hpp`, or package-local naming consistent
  with existing include layout.
- Implement entrypoints in `.cpp` files.
- For packages with existing `register_type()` methods, call those methods.
- For packages without `register_type()` methods yet, leave local TODO comments
  only if the entrypoint cannot call them until the next phase.
- Make entrypoints idempotent through the underlying registry checks, not
  through silent global "already did everything" flags that hide partial
  failures.

Deliverable:

- Component package entrypoints compile and can be called explicitly.

### Phase 2: Move Component Type Registration Out Of Headers

Objective: remove include-time component registration side effects.

Work:

- For every built-in component class:
  - declare `static void register_type();` in the header;
  - implement it in `.cpp`;
  - register the component factory/abstract component;
  - register the inspect parent;
  - register component requirements;
  - register all inspect fields/buttons/serializable component fields that used
    to live in header-level macros.
- Delete corresponding `REGISTER_COMPONENT`, `REGISTER_ABSTRACT_COMPONENT`,
  `REQUIRE_COMPONENT`, `INSPECT_FIELD*`, `INSPECT_BUTTON`, and component
  `SERIALIZABLE_FIELD` macro uses from component headers.
- Keep manual field registration blocks in `.cpp`, but move static registrar
  structs into ordinary functions called by `register_type()`.

Deliverable:

- Including a built-in component header no longer mutates component or inspect
  registries.

### Phase 3: Wire `termin_bootstrap`

Objective: make runtime/player/editor bootstrap register built-in components.

Work:

- Extend `termin_bootstrap` dependencies only through package entrypoint
  libraries that are intended to be part of the standard SDK runtime.
- Call built-in component package entrypoints from `bootstrap_runtime()` after
  inspect adapters and runtime kinds are initialized.
- Keep optional packages guarded by existing build options, e.g. animation or
  platform-specific packages.
- Ensure `tc_shutdown()` cleanup remains sufficient and reset paths do not
  preserve stale built-in component records across shutdown/rebootstrap tests.

Deliverable:

- `bootstrap_runtime()`, `bootstrap_player()`, and `bootstrap_editor()` produce
  the same built-in component availability that static initializers used to
  provide.

### Phase 4: Tests And Regression Coverage

Objective: prove that bootstrap owns built-in component registration.

Work:

- Add focused tests that importing/loading component libraries does not by
  itself register component types.
- Add tests that `termin.bootstrap.bootstrap_player()` registers expected
  built-in component types and inspect fields.
- Add a C++ module hot-reload regression where a project module includes a
  built-in component header, reloads, and engine-owned component/inspect fields
  remain present afterward.
- Ensure shutdown/rebootstrap tests verify built-in component records are
  cleaned and restored deterministically.

Suggested commands:

```bash
./build-sdk.sh --no-wheels
./setup-test-venv.sh --force
./run-tests.sh
```

For focused iteration before the full run:

```bash
./run-tests-python.sh termin-bootstrap
./run-tests-python.sh termin-app
scripts/smoke-cpp-module-cascade-hot-reload
```

Deliverable:

- Tests cover no-import-side-effect, explicit bootstrap availability, and
  module reload ownership safety.

### Phase 5: Cleanup And Diagnostics

Objective: make future regressions obvious.

Work:

- Add diagnostics to legacy static component macros so any remaining use is
  visible during development.
- Consider making static component macros unavailable to normal project module
  code once all intended built-ins are migrated.
- Update docs that still recommend `REGISTER_COMPONENT` for new code.
- Update `#138` with current state and close or split follow-up work if frame
  pass migration remains the only large static-registration layer.

Deliverable:

- New component code has a documented explicit registration path, and remaining
  static registration debt is intentionally scoped.

## Acceptance Criteria

- Built-in C++ component headers do not create registry side effects when
  included.
- Built-in component registration is reachable from `termin_bootstrap`.
- Built-in component inspect metadata is registered from explicit
  `register_type()`/package entrypoints, not from static header registrars.
- Component registration method implementations live in `.cpp` files.
- Project module unload cannot unregister built-in component or inspect records
  merely because a module included a built-in component header.
- Frame pass static registration is unchanged except for documentation stating
  that it is out of scope for this migration.

## Suggested Goal Prompt

Use this when assigning the implementation as a goal:

```text
Implement docs/plans/2026-06-28-builtin-component-bootstrap-migration-plan.md.
Keep scope limited to built-in component registration and component inspect
metadata. Do not migrate frame pass registration. Keep registration method
implementations in .cpp files, with headers declaring only the explicit
register_type/package entrypoints. Verify with focused bootstrap/module reload
tests and then the standard build/test scripts where feasible.
```
