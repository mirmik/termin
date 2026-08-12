# Native SceneView Bridge

The broader target boundary is defined by
[Shared 2D Composition](2026-08-11-shared-2d-composition.md). This document
describes the current `SceneView` vertical slice; its portal side table is
planned to become a reusable projection bridge without changing ownership.

`SceneView` is the deliberately small `termin-gui-native` host for
`termin-visual-scene`. It is a widget, not a second scene model.

The public ownership chain is:

```text
tc_visual_scene_handle / TcVisualScene
    resolves a pooled tc_visual_scene
    the pooled scene owns graphic-item objects
    exposes generation-checked GraphicItemHandle values

SceneView widget
    retains only the scene handle
    owns camera and grid state
    forwards input in world coordinates
    keeps temporary widget-portal associations

domain owner (for example nodegraph)
    creates and mutates items
    owns stable IDs, selection and drag policy
    invalidates SceneView after mutations
```

There is no GUI-side `GraphicsScene`, `GraphicItemRef`, item metadata store or
creation API. C++ callers adopt ordinary `GraphicItem2D` objects into
`TcVisualScene`; Python callers use the creation surface exposed by the same
visual-scene binding. `SceneView` accepts or returns this non-owning handle
facade and does not know which concrete item classes it contains.

## Rendering and invalidation

Without portals, `SceneView::paint` prepends its camera transform and asks
`TcVisualScene` to append the live tree to a `DrawList2DBuilder`. With portals,
the scene emits balanced per-item draw layers in the same canonical traversal;
the GUI-facing bridge inserts each widget at its source item's own paint slot.
The resulting interleaved stream is recorded in the UI draw list and executed
by `UiDrawListRenderer`.
Exact affine transforms, geometric clips, opacity and stable scene ordering
therefore remain visual-scene behavior.

The scene is thread-confined and has no observer, revision or dirty-state
subsystem. A caller that mutates it calls `SceneView::invalidate_scene`
(`SceneView.invalidate_scene()` in Python). Replacing the scene or changing a
portal association invalidates the view automatically.

## Interaction

The view converts pointer positions to world coordinates and forwards the raw
event to an optional callback. Portal hit testing follows the reverse of the
same scene paint-layer traversal, so graphic items above a portal source win
and the source portal wins over the source item's own hit shape. If a domain handles pointer down, the view
captures the pointer until up or cancel; it does not hit-test, select,
classify or move items itself. Middle-button pan and anchored wheel zoom are
viewport policies and remain in the widget.

Optional `SceneInteraction2D`, `SelectionController2D` and
`DragController2D` remain reusable visual-scene policies, but a domain owns
them when it chooses to use them. Nodegraph currently owns its semantic ID,
selection, connection and drag state directly.

## Widget portals

Full widgets are not graphic items. A temporary portal side-table entry
associates one `GraphicItemHandle` with one `tc_widget_handle`.

- `tc_ui_document` remains the only widget owner;
- `TcVisualScene` remains the only graphic-item owner;
- destroying a scene item detaches but does not destroy its widget;
- destroying a widget removes the stale portal during reconciliation;
- destroying the view detaches portal widgets without destroying them;
- one widget cannot be associated with two scene items in the same view.

During layout, a portal widget receives the logical world bounds of its item.
The view applies camera translation and uniform zoom through the widget
subtree-transform contract, so paint and input use the same mapping. Portal
widgets paint at their source item's stable tree-local visual position and
remain clipped by the `SceneView` bounds. Ordered children are above a portal
attached to their parent, while later or higher-z siblings are above the
entire earlier sibling slot. The reusable projection bridge preserves this
behavior and keeps concrete-item knowledge out of the view.
