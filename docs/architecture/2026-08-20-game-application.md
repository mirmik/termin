# GameApplication

## Status

The language-neutral type registry and standalone instance lifecycle are
implemented. Integration with `EngineCore`, application selection, and the
precise start/stop point in the engine lifecycle are intentionally unresolved.

The earlier design that combined `GameApplication`, a host-owned
`RuntimeSession`, transactional `SceneFlow`, scene providers, render/input
bindings, and build-profile selection was removed. Those concerns do not form
one abstraction.

## Purpose

`GameApplication` is a project-defined object for state and orchestration that
must outlive individual scenes. `GameDirector` remains a suitable project-level
name for one implementation.

The current contract deliberately answers only these questions:

- how a native or Python application class is registered;
- how one object is constructed, started, stopped, and destroyed;
- how its defining module is kept loaded while an instance is alive.

It does not own scenes, rendering, input, or product configuration.

## Registry and ABI

The canonical registration surface is the common C `RuntimeTypeRegistry`:

- facet: `termin.runtime.game_application`;
- abstract root: `GameApplication`, owned by `termin-runtime`;
- concrete types retain their real module owner;
- factories use `tc_runtime_owned_factory`;
- live instances use `tc_runtime_type_instance_link`.

`tc_game_application_registry_init()` explicitly and idempotently publishes the
root descriptor. Concrete factories return a language-owned object, an
unconditional destroy callback, and versioned `start`/`stop` operations. No
engine, session, scene, or host pointer is part of this ABI.

The opaque instance wrapper enforces this lifecycle:

```text
CREATED --start--> STARTED --------stop-------> STOPPED
    |                 |                           |
    | start fails     | destroy performs stop    | destroy
    v                 v                           v
START_FAILED ------stop/destroy--------------> released
```

Once `start` is attempted, `stop` is attempted at most once. Destroy performs a
best-effort stop after either successful or failed startup. The type link is
released only after the language object is destroyed. Module unload and
same-owner replacement are refused while an instance remains live.

C++ `GameApplication` and `GameApplicationTypeDescriptorBuilder` are
convenience adapters over the C ABI. They do not define the cross-module ABI.

## Python publication

A Python implementation is an ordinary class:

```python
from termin.runtime import GameApplication


class AvalonGameDirector(GameApplication):
    game_application_type_name = "avalon.GameDirector"

    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...
```

`__init_subclass__` records a declaration without publishing it during import.
The `.pymodule` owner contribution transaction publishes declarations only
after all module packages import successfully. The same owner-scoped
participant revokes and audits them before module objects are evicted.

The native adapter retains the Python class and acquires the GIL for
construction, lifecycle calls, and destruction. Python exceptions are logged
and cross the C boundary as explicit errors. Lifecycle methods must return
`None`.

## Deliberately open integration questions

The next design step must decide, independently of this registry contract:

1. whether `EngineCore` directly owns the application instance;
2. whether a small `RuntimeSession` is useful as EngineCore-owned per-run state;
3. who selects the concrete application type for editor, player, tests, and
   embedded hosts;
4. exactly when creation, `start`, `stop`, and destruction occur relative to
   module loading and engine startup/shutdown.

Until those questions are settled, no host automatically creates a
`GameApplication`. There is no `SceneFlow`, scene service, host binding layer,
or mandatory build-profile field attached to this feature.
