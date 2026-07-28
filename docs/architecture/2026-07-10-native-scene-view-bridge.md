# Native SceneView Adapter

`SceneView` is the `termin-gui-native` host for the canonical retained scene
implemented by `termin-visual-scene`. It is not a second retained scene core.

The public ownership chain is:

```text
shared_ptr<termin::gui_native::GraphicsScene>
    metadata + invalidation adapter
    owns one termin::visual::VisualScene2D
        generation-checked GraphicItemHandle values

GraphicItemRef
    non-owning scene pointer
    scene lifetime token
    GraphicItemHandle

SceneView widget
    camera and grid state
    SceneInteraction2D
    SelectionController2D
    DragController2D
    widget portal side table
```

The `GraphicsScene` name remains as the small GUI-facing adapter used by the
C++ and Python widget APIs. It owns no item tree or paint callbacks. Topology,
payloads, affine composition, ordering, hit testing and render snapshots all
come from its one `VisualScene2D`.

## Items and rendering

Callers create typed rectangles, rounded rectangles, ellipses, paths,
polylines and text. Creation returns a `GraphicItemRef`, which is a
scene-plus-generation-handle value. It becomes invalid when the item or scene
is destroyed and never owns the item.

`SceneView::paint` prepares the canonical immutable `DrawList2D`, prepends the
view camera transform and records it in order inside the UI draw list.
`UiDrawListRenderer` executes that frozen list through the same
`Canvas2DRenderer` used by other retained-scene hosts. This preserves exact
affine transforms, geometric clips, opacity and stable scene ordering without
reintroducing GUI paint callbacks.

## Interaction

Pointer input is mapped from widget coordinates into scene world coordinates.
The canonical interaction router supplies exact hit testing and per-pointer
capture. Selection and dragging are explicit controllers owned by the view;
middle-button pan and wheel zoom remain view camera policies.

GUI metadata only marks semantic items selectable or draggable. When a
non-selectable visual child is hit, the view walks generation-checked parents
to the nearest eligible semantic item. Dragging delegates affine mutation to
`DragController2D`, so rotation, non-uniform scale and shear are preserved.

## Widget portals

Full widgets are not graphic items. A portal side-table entry associates one
`GraphicItemHandle` with one `tc_widget_handle`.

- `tc_ui_document` remains the only widget owner.
- `VisualScene2D` remains the only graphic-item owner.
- destroying a scene item detaches but does not destroy its widget;
- destroying a widget removes the stale portal during reconciliation;
- destroying the view detaches portal widgets without destroying them;
- one widget cannot be associated with two scene items in the same view.

During layout, a portal widget receives the camera-projected world bounds of
its item. Portal widgets paint above scene primitives in stable visual order
and remain clipped by the `SceneView` bounds. Widget focus, keyboard/text
input, accessibility and recursive hit testing continue through
`tc_ui_document`.

## Python contract

Python uses `GraphicsScene` creation methods and `GraphicItemRef` values. The
old constructible `GraphicsItem`, `shared_ptr<GraphicsItem>` ownership,
`set_paint_callback`, `set_hit_test_callback` and embedded-widget fields were
removed. Node graph rendering now projects its model into typed scene payloads
and registers parameter editors through `SceneView.set_widget_portal`.
