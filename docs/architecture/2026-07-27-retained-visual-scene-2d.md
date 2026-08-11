# Retained Visual Scene 2D

## Status

Accepted and implemented. The original snapshot/state-RPC design was replaced
by the same direct object model used by native widgets.

## Purpose and boundary

Interactive plot annotations and GUI tool scenes need persistent visual
identity, arbitrary affine placement, clipping, hit testing and pointer
capture. They do not need widget layout, focus, keyboard semantics or a second
rendering vocabulary.

The dependency direction is:

```text
tcplot / termin-gui-native
            |
            v
termin-visual-scene
            |
            v
termin-graphics
            |
            v
termin-base
```

`termin-base` owns exact `Affine2f` and geometry values.
`termin-graphics` owns paths, paints, draw commands and their executor.
`termin-visual-scene` owns only retained visual objects and interaction.
Plots and GUI adapters retain their domain semantics above it.

## Decision

`tc_visual_scene` is a thread-confined owning collection of
`tc_graphic_item*`. Each item implementation embeds the C base and supplies:

- one vtable for local bounds, paint, hit testing and destruction;
- a language body and native-language tag;
- a creator-supplied deleter;
- optional concrete geometry, paint and resource fields.

The embedded base stores common transform/presentation state and direct
parent/child pointers. The scene supplies generation handles for external
references. The item tree itself does not route its internal work through
handles.

C++ `GraphicItem2D` is the ordinary object facade. Built-ins are separate
classes in separate files and override virtual behavior through
`NativeGraphicItem2D`'s single adapter vtable. The core, traversal and renderer
do not name or enumerate concrete item types. Custom language implementations
use the same base/vtable/adopt/deleter contract.

`tc_visual_scene` instances live in a generation-checked process pool.
`TcVisualScene` is a copyable, non-owning C++ handle facade. It provides
adoption, replacement, resolution, world/effective value calculation, bounds,
paint and hit testing. Scene creation and destruction are explicit pool
operations; no owning scene object crosses a language boundary.

## Rendering and resources

`TcVisualScene::paint` immediately traverses the live tree and appends to the
caller's `tgfx::DrawList2DBuilder`. For each item it pushes the local affine
transform, opacity and clip, invokes the paint vtable and then visits ordered
children.

The scene does not prepare a detached render snapshot and does not postpone
item callbacks. Resource resolution for text, images and custom batches is
synchronous during traversal. The surrounding widget or plot render pipeline
may freeze the canonical draw list when its own renderer requires an owned
command value; that is not retained scene state.

## Lifetime

Adoption transfers ownership and requires a deleter. Destruction recursively
destroys the item's child subtree. Before calling `on_destroy` and the deleter,
the scene removes the item from topology, invalidates its handle and unlinks
its runtime type. Exactly one deleter is called.

Parenting affects visual topology, not heap ownership: the scene owns all
adopted objects. A handle contains scene ID, slot index and generation, so stale
and cross-scene references fail safely.

`replace` supports projections such as plot marker visuals that need stable
external identity while replacing a concrete item object. It preserves the
handle, direct topology and common placement state, relinks children and
destroys the former object exactly once.

## Interaction

Hit testing traverses the live tree in reverse visual order, applies inherited
clips, uses a fallible inverse of the exact world `Affine2f` and invokes the
item hit-test vtable. Singular transforms are non-hittable.

Hover, press, capture, selection and drag state live in optional controllers
as generation handles. They are policies above items. Detach/reparent keeps
identity valid; disabled or destroyed targets are reconciled.

## Explicit exclusions

The visual scene has:

- no mutex or implicit cross-thread contract;
- no `std::variant` or other closed sum of item types;
- no `std::visit` or concrete-type renderer dispatch;
- no `dynamic_cast`;
- no detached snapshots or inspection records;
- no scene serialization or type-factory registry;
- no revisions, dirty-state RPC or deferred renderer;
- no widget ownership and no plot-domain coordinate model.

Serialization belongs to a domain document when one exists. Immutable
`PlotFrame2D` and `PlotAnnotationSnapshot2D` remain valid tcplot domain values;
they are unrelated to the removed visual-scene snapshots.

## Integration

The accepted target for shared placement, draw lowering and cross-tree
projections is documented in
[Shared 2D Composition](2026-08-11-shared-2d-composition.md). Visual-scene
remains a separate owner and semantic tree while its value-level composition
mechanics converge with GUI on `termin-base`/`termin-graphics`.

`termin-gui-native::SceneView` accepts a `TcVisualScene` handle facade,
paints it generically and never inspects concrete graphic item types. It owns
camera behavior and forwards input in world coordinates; selection, dragging,
stable IDs and other domain policies remain in the scene owner. Because the
thread-confined scene has no observer/revision subsystem, a mutating owner
explicitly invalidates the view. Widget portal associations currently remain
in a GUI side table keyed by `GraphicItemHandle`. That working vertical slice
is planned to become a reusable handle-based scene-to-widget projection owned
by the GUI-facing composition layer; it does not move widget ownership into
the visual scene.

`PlotAnnotationLayer2D` owns semantic annotation handles and projects each
annotation into one or more ordinary visual items. A minimal tcplot consumer
still links `tcplot::tcplot`; it does not directly compose visual-scene APIs.

Python and future C# wrappers carry only generation-checked scene and item
handles. They expose live object properties and explicit operations, not
owning native objects or detached state copies.
