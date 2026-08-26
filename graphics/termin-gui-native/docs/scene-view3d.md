# SceneView3D

`SceneView3D` embeds a small `VisualScene3D` in the native retained widget
tree. It is intended for compact, item-oriented views such as object tools,
previews and the orientation cube. A full engine `tc_scene` remains the right
abstraction for entity/component simulation and framegraph-driven worlds.

The widget borrows its `TcVisualScene3D`. The owner must keep the scene alive
until it calls `set_scene({})` or destroys the widget. The widget owns its
offscreen color/depth textures, built-in packet renderers and
`SceneInteraction3D`; it releases those GPU resources through the canonical
`RenderPreparedWidget` lifecycle.

Textured `StaticMeshItem3D` packets carry immutable CPU RGBA8 sRGB data rather
than a device handle. `SceneView3D` uploads one cached texture per shared
snapshot on its current render device and releases stale entries after item
replacement/destruction or during widget/device teardown. This keeps a visual
scene portable across hosts and preserves the Python ownership boundary.

Static meshes follow the same retained-device policy. `SceneView3D` uploads
each shared immutable `Mesh3` snapshot once as indexed vertex and index
buffers. Camera and item transforms are draw uniforms, and flat preview
lighting is evaluated in the fragment shader, so camera-only repaints do not
expand or transform triangle vertices on the CPU. Mesh buffers are evicted
when the snapshot is no longer submitted and are released on device teardown.

`SceneView3DShadingMode::Flat` derives one normal per rasterized face.
`SceneView3DShadingMode::Smooth` consumes authored vertex normals; if a mesh
has none, the widget generates and uploads them once when smooth mode is first
requested. The position-only buffer is then replaced by the enriched retained
buffer, so later camera movement and mode switches do not repeat that work.
`set_wireframe_enabled(true)` selects the backend's indexed triangle line
rasterization and does not build a second edge mesh. Textured and untextured
static meshes share these preview-lighting and display-mode rules.

```cpp
auto scene_handle = tc_visual_scene3d_create();
termin::visual::TcVisualScene3D scene{scene_handle};

auto* view = new termin::gui_native::SceneView3D(scene);
document.adopt(view);
document.add_root(*view);

view->set_camera_provider([](termin::gui_native::ViewportSurfaceSize size)
    -> std::optional<termin::gui_native::SceneView3DCamera> {
    return make_camera(size.width, size.height);
});
view->set_shading_mode(termin::gui_native::SceneView3DShadingMode::Smooth);
view->set_wireframe_enabled(true);
```

`set_camera()` installs fixed view/projection matrices. A camera provider is
sampled during render preparation after layout, so it sees the actual integer
framebuffer size. `invalidate_view()` requests a new offscreen frame after
external camera state changes; `invalidate_scene()` does the same after items
are mutated.

Widget coordinates are unprojected with the current matrices using Termin's
top-left, Y-down and Z-in-`[0, 1]` clip convention. Pointer events are then
routed to `SceneInteraction3D`. An item hit owns that pointer sequence and the
widget-level fallback is not called. If the viewport or camera becomes invalid
after an item captured the pointer, the widget sends `Cancel` using the last
valid interaction state, releases UI capture and consumes the remaining
sequence through its terminal `Up`; the fallback never inherits half of an
item-owned drag. Auxiliary `Wheel` and `Leave` events are consumed while the
item owns the sequence. Replacing the borrowed scene follows the same terminal
Cancel/release/quarantine contract, including when replacement happens
reentrantly from the target's `Down` callback. When no item accepts the down
event, an optional fallback may accept the sequence and implement an orbit
camera:

```cpp
view->set_fallback_pointer_handler(
    [](auto& view, const tc_ui_pointer_event& event, const auto& world_ray) {
        return camera_controller.handle(event, world_ray, view.framebuffer_size());
    });
```

The fallback is a widget policy only; neither `VisualScene3D` nor its items
know about cameras or gizmos. A gizmo is an ordinary scene item implementing
paint and hit-test contracts.

For a corner orientation control, place a small `SceneView3D` above a larger
`Viewport3D` with `OverlayLayout`. Normal retained-tree ordering and hit testing
keep pointer capture local to the small view; no special 3D overlay primitive
is required.
