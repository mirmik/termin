# Native SceneView Bridge

Status: implemented for `termin-gui-native`; the legacy `tcgui` adapter remains
until the editor root migration can move `tcnodegraph` as one coherent UI tree.

## Decision

`GraphicsScene` is a small retained 2D interaction scene for tools such as the
node-graph editor. It is not a plot model, render scene or alternative widget
tree. Plot annotations remain retained domain data in `tcplot`, while 3D scene
presentation remains behind `Viewport3D`.

The only production consumer of the legacy `tcgui.scene` package is
`tcnodegraph.NodeGraphView`, used by the pipeline editor. The native bridge is
therefore data-oriented: generic UI owns transforms, z-order, hit testing,
selection, dragging, pan/zoom and embedded-widget composition; node shapes,
sockets, Bezier edges and graph mutation stay in a `tcnodegraph` adapter.

## Ownership

```text
Python/C++ adapter
    shared_ptr<GraphicsScene>
        shared_ptr<GraphicsItem> roots
            shared_ptr<GraphicsItem> children
            weak_ptr<GraphicsItem> parent

tc_ui_document
    SceneView widget
        canonical tc_widget children for embedded widget handles
```

- `GraphicsScene` exclusively owns roots. A root cannot simultaneously belong
  to another scene or item.
- An item exclusively owns its children; the parent link is weak. Reparenting
  is explicit remove-then-add and cycles are rejected.
- `SceneView` retains a shared scene and never copies item state.
- Selection retains only items already owned by the scene and is cleared when
  their root leaves the scene.
- An embedded widget is represented by a generation-checked `WidgetHandle`.
  The scene does not own the widget object. During layout `SceneView` attaches
  live handles as its canonical `tc_widget` children, so normal document
  focus, hover, capture, key and text routing remains authoritative. Removing
  an item or destroying the view detaches the widget without destroying it;
  the document/caller controls object lifetime. Stale and foreign-parent
  handles are logged and skipped.

## Coordinates And Interaction

`SceneTransform` is the only world/screen mapping:

```text
screen = view.bounds.origin + offset + world * zoom
world  = (screen - view.bounds.origin - offset) / zoom
```

Wheel zoom preserves the world point under the pointer. Middle-button capture
pans. Left-button selection and dragging use reverse stable z-order; children
are tested before parents. Ctrl toggles selection. Custom hit callbacks receive
item-local coordinates, allowing edge and socket geometry without teaching
generic UI about node graphs.

Custom pointer/key/text handlers run before default scene interaction and can
consume events. This is the explicit adapter boundary for socket connections,
context menus and model commands. Item-moved and transform-changed signals let
the adapter update its domain model without polling.

## Rendering

`SceneView` records background, bounded grid and item callbacks into the same
backend-neutral UI draw list. Item callbacks receive the retained item and
`SceneTransform`; they do not receive a render device or own GPU resources.
Embedded widgets are laid out and painted through their normal native widget
vtable. Stable z-order is preserved for equal z values.

The bridge deliberately does not define node, socket, edge, plot annotation or
3D entity classes. Those stay with their domain owners.

## Migration

`tcnodegraph` can build a parallel native adapter using `GraphicsItem` paint
and hit callbacks while keeping `Graph`/`GraphController` unchanged. The
production pipeline editor cannot switch just its `NodeGraphView` while its
window is still a `tcgui` tree: native embedded widgets must belong to the same
`tc_ui_document`. The consumer switch therefore belongs to the editor UI
migration phase and should replace the whole pipeline-editor tree atomically,
after which `tcgui.scene` has no production consumers and can be retired.
