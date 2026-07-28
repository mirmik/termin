# Native SceneView Bridge

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

`SceneView::paint` prepends its camera transform and asks `TcVisualScene` to
append the live tree to a `DrawList2DBuilder`. The resulting canonical draw
list is recorded in the UI draw list and executed by `UiDrawListRenderer`.
Exact affine transforms, geometric clips, opacity and stable scene ordering
therefore remain visual-scene behavior.

The scene is thread-confined and has no observer, revision or dirty-state
subsystem. A caller that mutates it calls `SceneView::invalidate_scene`
(`SceneView.invalidate_scene()` in Python). Replacing the scene or changing a
portal association invalidates the view automatically.

## Interaction

The view converts pointer positions to world coordinates and forwards the raw
event to an optional callback. If a domain handles pointer down, the view
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

During layout, a portal widget receives the camera-projected world bounds of
its item. Portal widgets paint above scene primitives in stable visual order
and remain clipped by the `SceneView` bounds. Passing portal/tree information
through a more general scene projection may be designed later; it is not
encoded as concrete-item knowledge in the view.
