# WorldController and EngineCore RuntimeSession

## Status

This document records the accepted second design for persistent gameplay state
outside scenes.

The language-neutral `WorldController` registry, instance lifecycle, native
adapter, and Python declaration transaction are implemented in `termin-engine`.
Hosting the controller inside an `EngineCore`-owned `RuntimeSession` remains the
next integration step.

The earlier host-owned `RuntimeSession`/`SceneFlow` design is retired. The new
design deliberately has no public `SceneFlow`, scene providers, host binding
list, session service dictionary, or mandatory build-profile selection.

## Mental model and ownership

`EngineCore` is the execution container for one live world even though it is
broader than the old `World` object and also owns rendering.

```text
EngineCore
|-- SceneManager
|   `-- owns registered scene instances and their lifecycle/mode
|-- RenderingManager
|   `-- owns render topology, viewports, targets and scene attachments
`-- optional RuntimeSession
    |-- owns an optional project-defined WorldController
    |-- owns one narrow WorldContext
    |-- associates one primary gameplay scene with the run
    `-- stores at most one pending primary-scene request
```

`RuntimeSession` is an activation record and supervisor for one gameplay run,
not another `World`, a service locator, or an owner of scene objects. An editor
`EngineCore` can outlive many Play sessions. A standalone player normally has
one session for its complete run.

One Play/start creates a fresh controller instance. It survives scene rotation
inside that session and does not survive Stop.

## Naming

The engine contract is named `WorldController`, not `GameApplication`:

- it belongs to the live world rather than the executable/application shell;
- it carries world-level state and policy across scene changes;
- it may coordinate scene rotation without owning the scene subsystem;
- `GameDirector` remains a suitable project-specific implementation name.

The registry root, facet, C/C++ symbols, Python base class and documentation
migrated together. The active-development API does not retain a public
`GameApplication` compatibility alias.

## Optional selection

The project settings file is the authoritative selection source:

```json
{
  "world_controller": null
}
```

or:

```json
{
  "world_controller": {
    "module": "avalon.game",
    "type": "avalon.GameDirector"
  }
}
```

An absent key and explicit `null` both mean that the project intentionally has
no controller. `RuntimeSession` remains valid in that case and stores a null
controller. There is no registered `NullWorldController` or
`SceneOnlyGameApplication` placeholder.

An explicit selection is strict. A missing module, unpublished type, abstract
type, failed factory, or failed `start()` blocks startup and is never silently
reinterpreted as no controller.

Build profiles do not select the controller in the first version. A build
copies the resolved project selection into its runtime manifest and includes
or validates the selected module as part of the packaged module closure.
Future profiles may overlay controller configuration without necessarily
replacing its class.

## Construction and teardown order

The host is responsible for project composition and transfers an already
created controller instance, or null, into `EngineCore`. `EngineCore` and its
`RuntimeSession` then own the instance unconditionally.

Startup order:

```text
load project modules and publish controller types
create the selected WorldController instance, or null
create RuntimeSession inside EngineCore and transfer ownership
create WorldContext and call WorldController.start(context), if present
create/load a runtime scene
bind the scene's transient WorldContext extension
prepare gameplay rendering
publish the scene as primary and activate it
run the first component start/update tick
```

The controller is started before the initial scene is loaded. Scene components
can therefore reach persistent world state from their first runtime lifecycle
callback.

Shutdown first rejects new requests, deactivates and detaches session-bound
scenes while the controller is still alive, unbinds their contexts, calls
`WorldController.stop()`, destroys the controller, and finally removes the
session. Physical scene destruction remains the responsibility of
`SceneManager` and the scene's actual owner. Module unload happens only after
the session and all project-owned scene/component instances have been released.

`EngineCore::shutdown()` is the final backstop and must end an active session
before closing scenes and rendering resources.

## WorldContext scene extension

`RuntimeSession` owns one `WorldContext`. A `WorldController` receives it
directly during `start()` because no scene exists yet. Each runtime scene gets
a transient extension that refers to the same context, allowing components to
reach it through their own scene.

The initial public surface is intentionally narrow:

```text
WorldContext
|-- controller() -> optional WorldController
|-- primary_scene() -> optional scene handle
`-- request_primary_scene(...)
```

The context is not a string-to-pointer service dictionary. It may internally
retain an engine-owned link, so exposing additional `EngineCore` facilities in
the future does not require changing scene ownership or lifecycle. Direct
public access to all of `EngineCore`, `RenderingManager`, or `RenderTopology`
is not part of the first contract.

The extension:

- is implemented and registered by `termin-engine`;
- is opaque to the lower-level `tc_scene` core;
- is attached only to scenes bound to a live runtime session;
- has no persistence key and is never serialized or copied as authored data;
- uses an invalidatable/generation-safe link so a scene cannot dereference a
  destroyed session;
- is guaranteed to be valid by component `on_start`, `on_scene_active`, and
  the first update, but not from a language object constructor that may not yet
  have an owning entity or scene.

Authoring scenes do not receive a live world context. An editor runtime copy is
bound only after a session exists.

## Primary-scene transition

Scene-management authority remains split by domain:

- `SceneManager` owns existence, registration, destruction, mode, and ticking;
- `RenderingManager` owns render attachment and topology;
- `RuntimeSession` records the current primary gameplay association and a
  pending request;
- `EngineCore` is the safe coordination boundary between its managers.

A request records intent and does not mutate managers immediately. At the very
start of `EngineCore::tick_and_render()`, before `SceneManager::tick()`, the
engine processes at most one request synchronously:

1. Resolve and validate an already registered inactive candidate scene.
2. Prepare its gameplay rendering while the old scene remains untouched.
3. If preparation fails, clean the candidate attachment and leave the old
   primary scene active.
4. Deactivate and detach the old primary scene.
5. Publish the candidate as the new primary scene.
6. Activate it before the frame's scene tick.

The first version rotates only already materialized scenes. Physical loading,
reloading, retaining, and destruction are separate `SceneManager`/source-owner
operations. If `SceneManager` needs a better scene loading API, it is extended
directly rather than hidden behind a session-owned provider abstraction.

There is no staged state spanning frames and no public transition object.
Preparation and commit run consecutively at one engine safe point with local
rollback bookkeeping. Hosts do not pump transitions from `poll_events()`.

The primary gameplay scene is only one session-owned association. Auxiliary,
editor, overlay, or additive scene/render attachments are not implicitly
detached.

## Play and Pause

Editor Play/Stop creates and ends `RuntimeSession`. Pause is not a session
state. It remains a `SceneManager` mode change (`PLAY`/`STOP`) on the relevant
scene. The controller and session remain alive while a scene is paused.

If a transition must preserve a paused mode, the transition reads the current
scene mode at commit time; it does not maintain a second pause flag.

## Editor boundary

Editor Play is a composition adapter, not a transition participant:

1. Resolve project settings, prepare modules and create the optional controller.
2. Transfer it into a new `EngineCore` runtime session.
3. Create the runtime copy of the authoring scene.
4. Bind that copy to the session and activate it through the engine's ordinary
   primary-scene operation.
5. Observe the published primary scene for hierarchy/viewport presentation.

Editor observers live in the editor session and are never stored inside
`RuntimeSession`. Editor presentation failure is logged as an editor failure;
it does not roll back an otherwise valid gameplay transition. Before closing a
runtime copy, Stop first makes editor-owned views release or rebind their
references.

No runtime-session state contains authoring paths, copy provenance, editor
selection, undo state, view models, editor callbacks, or host binding arrays.

## Dependency placement

The existing dependency direction is `termin-runtime -> termin-engine`, so an
`EngineCore` field cannot depend on the current `termin-runtime`
`GameApplication` implementation without a cycle.

The C ABI, registry facet, instance wrapper, native convenience class and
engine-owned Python adapter live in `termin-engine` as `WorldController`.
Runtime package loading remains in the higher-level `termin-runtime` library.

## Non-goals for the first implementation

- a general application/service container;
- asynchronous or multi-frame scene staging;
- scene source/provider interfaces owned by `RuntimeSession`;
- build-profile class selection;
- automatic configuration-file interpretation;
- editor-specific transition bindings inside the engine;
- a public null-controller class;
- direct public exposure of every `EngineCore` manager through `WorldContext`.

## Implementation cards

Umbrella: #1780.

Independent foundations:

- #1781 moves and renames the complete native/Python controller contract
  (implemented);
- #1782 adds the optional project-settings selection (implemented).

Engine sequence:

- #1783 adds the `EngineCore`-owned session lifecycle;
- #1787 adds the transient scene extension;
- #1790 adds synchronous primary-scene switching at the engine safe point.

Composition and host sequence:

- #1788 transports project selection through build/package manifests;
- #1785 integrates editor Play/Stop;
- #1786 integrates the packaged player;
- #1789 integrates source and headless runs;
- #1784 performs the final cross-host lifecycle and cleanup verification.
