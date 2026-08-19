# GameApplication and Per-Run RuntimeSession

## Status

Accepted architecture for umbrella card #1748. The native registry and instance
lifecycle (#1749) and optional Python publication/factory adapter (#1750) are
implemented. Scene context, profile selection, `SceneFlow`, host composition
and rendered rotation remain separate dependent slices.

## Problem

A scene is disposable runtime content. Game-wide state and orchestration must
survive replacing one scene with another, but must not survive leaving the
current Play/player run. Storing this state in an editor model, `EngineCore`, a
process-global singleton or a distinguished scene makes scene rotation,
embedding, tests and multiple simultaneous runs disagree about ownership.

The engine therefore distinguishes three concepts:

- `GameApplication` is the project-selected root/director. There is exactly one
  live instance in one execution session.
- `RuntimeSession` is the engine-owned composition and lifetime boundary for
  one run. The host owns it; it owns the application, scene flow and persistent
  session services.
- `SceneFlow` performs transactional scene transitions. It is a service used
  by the application, not logic embedded in the application base class.

`GameDirector` remains a good project-level name for an implementation. The
engine contract is named `GameApplication` because it is the composition root,
not necessarily a monolithic gameplay system.

## Ownership and dependency direction

```text
editor Play / packaged player / source player / custom host
                         |
                         v
                  RuntimeSession
                    /          \
                   v            v
          GameApplication     SceneFlow
                                  |
                                  v
                            runtime scenes

termin-runtime -> termin-scene
project gameplay -> termin-runtime + termin-scene
termin-scene -X-> termin-runtime
```

The host creates one `RuntimeSession` per run and destroys it before unloading
project modules. Neither `EngineCore` nor a process-global variable stores the
active session. Independent embedded hosts may therefore own independent
sessions in the same process.

`termin-runtime` remains native and embeddable. Optional Python registration
and invocation lives in an adapter above its C contract; editor and player
code only provide host-specific policies and bindings.

## Canonical type and instance ABI

The canonical registration surface is the common C `RuntimeTypeRegistry`:

- facet: `termin.runtime.game_application`;
- abstract root type: `GameApplication`, owned by `termin-runtime`;
- project types: explicit stable names with their real module owner;
- factory ownership: `tc_runtime_owned_factory`;
- live lifetime: `tc_runtime_type_instance_link`.

`tc_game_application_registry_init()` explicitly publishes the abstract root.
It is idempotent and may be called again after the common registry is reset. It
does not use static initialization. Hosts must run this runtime-domain
bootstrap before project modules publish application types.

A concrete factory receives a versioned context containing the host-owned
`tc_runtime_session*` and returns:

- its language-owned object;
- an unconditional object destroy callback;
- a versioned `start`/`stop` operations table.

The destroy callback is deliberately outside the lifecycle table. The engine
can therefore release a created object even when its operations version or
shape is rejected. The engine-owned opaque instance copies the context and
links itself to the selected type record before it is returned to a host.

C++ `GameApplication` and its descriptor builder are convenience adapters over
this contract. They catch exceptions at the C boundary. Python uses the same C
result and operations model through an optional adapter; no C++ subclass
trampoline or inspector facet is required.

## Python declaration and module publication

A project application remains an ordinary Python class:

```python
from termin.runtime import GameApplication


class AvalonGameDirector(GameApplication):
    game_application_type_name = "avalon.GameDirector"

    def start(self, context) -> None:
        ...

    def stop(self, context) -> None:
        ...
```

Creating the subclass records an owner-scoped declaration but does not mutate
the live runtime type registry. The `.pymodule` backend first establishes its
package-to-owner claims, imports every declared package, and only then asks all
commit-capable `OwnerContributionParticipant`s to publish their declarations.
Consequently, a package import failure cannot expose a half-loaded application
type. The backend runs the same participant revoke/audit path before evicting
the exact imported objects from `sys.modules`.

The native factory retains the class object. Construction, `start`, `stop` and
destruction acquire the GIL inside the adapter. Python exceptions are logged
with their traceback and returned to the native lifecycle as explicit errors;
`start` and `stop` must return `None`. A live native instance link prevents both
same-owner descriptor replacement and module-owner unload until the host has
stopped and destroyed the application.

`publish_game_application` and `publish_game_applications` provide the same
registration path for tests and custom hosts outside `.pymodule` loading. The
module path remains canonical for project code because it supplies the real
owner identity and the transactional import boundary.

## Lifecycle contract

The public instance state machine is:

```text
CREATED --start--> STARTED --------stop-------> STOPPED
    |                 |                           |
    | start fails     | destroy performs stop    | destroy
    v                 v                           v
START_FAILED ------stop/destroy--------------> released
```

Rules:

1. `start` is attempted at most once.
2. Once `start` has been entered, `stop` is invoked at most once, including
   after a failed `start`, so partially initialized implementations can unwind.
3. Explicit duplicate `start` and `stop` calls fail and are logged.
4. Destroying a started or start-failed instance performs one best-effort stop
   before destroying the language object.
5. The runtime type link remains live until after the language object has been
   destroyed.
6. A GameApplication facet strictly refuses owner unload while any linked
   instance remains. It does not convert the instance into an unknown or
   tombstoned application.
7. Every host destroys `RuntimeSession` before project module unload and before
   the global runtime-type registry is cleared.

The last rule is stronger than generic component tombstoning: the application
is the code that coordinates shutdown, so letting its implementation unload
while it is alive cannot be made useful or safe.

## Session and scene order

The full session slice will use this order:

Startup:

1. bootstrap native runtime domains;
2. load modules and publish registered types;
3. resolve the profile-selected `{module, type}` and verify the facet/owner;
4. create `RuntimeSession` and the GameApplication instance;
5. stage the entry scene while inactive and attach its session context;
6. call `GameApplication.start`;
7. enter and activate the staged scene.

Shutdown:

1. stop accepting transitions;
2. leave, detach and destroy runtime scenes;
3. call `GameApplication.stop` and destroy its object;
4. destroy session services;
5. unload project modules;
6. shut down process-wide runtime registries when the host itself exits.

Failure cleanup runs completed steps in reverse order and logs both the primary
failure and any cleanup failure.

## Scene access without an inverted dependency

`termin-scene` must not gain knowledge of `RuntimeSession` or
`GameApplication`. A later slice adds a generic opaque, non-persistent
execution-context scene extension. `termin-runtime` attaches its own body to
runtime scenes and exposes lookup helpers in the `termin.runtime` API.

Consequences:

- generic scene components keep depending only on `termin-scene`;
- project gameplay that needs the session deliberately depends on both scene
  and runtime APIs;
- session pointers are never serialized or cloned into authored scene data;
- a component reaches the session through its concrete scene, not through a
  process-global current-session lookup.

## Selection and settings

The build/run profile will explicitly store `{module, type}` and carry it into
the artifact manifest. `entry_scene` remains only the default startup-scene
policy. Runtime startup never picks the first discovered subclass and never
infers an application from platform or environment.

This selection is composition metadata, not game configuration. There is no
special editable-defaults file. A GameApplication loads any number of ordinary
project resources for game settings using the same resource mechanisms as
other systems.

## SceneFlow boundary

`SceneManager::set_mode()` alone is not a scene transition. `SceneFlow` stages
and commits all affected state together: scene instance/identity, execution
context, component lifecycle, rendering, input and host/native bridges. Failed
staging leaves the current scene active; failed commit either rolls back fully
or marks the whole session failed. Editor and player adapters consume this
service instead of each growing a private transition state machine.

## Implementation slices

1. #1749: native C registry, instance lifecycle, C++ adapter and unload guard.
2. #1751: non-persistent generic scene execution-context extension.
3. #1750: Python publication and symmetric module-owner cleanup participants.
4. #1752: explicit profile and artifact-manifest selection.
5. #1753: host-neutral transactional `SceneFlow`.
6. #1754: `RuntimeSession` composition and failure cleanup.
7. #1755, #1756 and #1757: editor, packaged, source and headless host adapters.
8. #1744: rendered/input-active packaged scene rotation over `SceneFlow`.
