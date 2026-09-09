"""Editor orientation cube, hosted by an ordinary native SceneView3D."""

from __future__ import annotations

import logging

from termin.geombase import LinearColor, Mat44, SrgbColor, Vec3
from termin.gui_native import (
    OverlayAnchor, Point, SceneView3DCamera, Size, StyleField, StyleOverride,
)
from termin.render_components import OrbitCameraController, ViewDirection
from termin.visual_scene import (
    TargetPointerEventKind3D,
    tc_visual_scene3d_create,
    tc_visual_scene3d_destroy,
)

from termin.editor_core.orientation_cube_geometry import build_orientation_cube

_logger = logging.getLogger(__name__)


class NativeOrientationCube:
    """Own the cube's scene and callbacks; borrow the current editor camera."""

    def __init__(self, viewport) -> None:
        self._viewport = viewport
        self._closed = False
        self._camera = None
        self._controller = None
        self._hovered = None
        self._pressed = None
        self._activation_button = None
        self._patches = {patch.key: patch for patch in build_orientation_cube()}
        self._items = {}
        self.scene = tc_visual_scene3d_create()
        self.view = None
        self.root = None
        try:
            document = viewport.document
            panel = document.create_vstack("editor-orientation-cube-panel")
            self.root = panel.widget
            self.root.preferred_size = Size(160.0, 182.0)
            self.root.max_size = Size(160.0, 182.0)
            self.root.mouse_transparent = True
            self.view = document.create_scene_view3d(self.scene)
            self.view.widget.stable_id = "editor.viewport.orientation-cube"
            self.view.widget.preferred_size = Size(160.0, 160.0)
            # SceneView3D paints its themed widget background below the texture.
            # Both layers must be transparent for a viewport overlay.
            background = StyleOverride()
            background.fields = StyleField.Background
            background.value.background = SrgbColor(0.0, 0.0, 0.0, 0.0)
            self.view.widget.style_override = background
            self.view.set_clear_color(LinearColor(0.0, 0.0, 0.0, 0.0))
            panel.add_fixed_child(self.view.widget, 160.0)
            self._caption = document.create_label("", "orientation-cube-caption")
            self._caption.set_font_size(11.0)
            self._caption.widget.mouse_transparent = True
            panel.add_fixed_child(self._caption.widget, 22.0)
            for key in self._patches:
                vertices, triangles, colors = self._geometry(key)
                item = self.scene.create_primitive(vertices, triangles, colors=colors)
                self._items[key] = item
                self.view.set_target_pointer_handler(
                    item.handle, lambda event, key=key: self._pointer(key, event)
                )
                self.view.set_action_handler(
                    item.handle, lambda part, action, key=key: self._activate(key, action)
                )
            if not viewport.composition.add_child(
                self.root, OverlayAnchor.TopRight, Point(-10.0, 42.0)
            ):
                raise RuntimeError("viewport rejected orientation cube")
            self.rebind_camera()
        except Exception:
            _logger.exception("Failed to create editor orientation cube")
            self.close()
            raise

    def _geometry(self, key):
        patch = self._patches[key]
        color = patch.color
        if key == self._pressed:
            color = (0.95, 0.66, 0.22)
        elif key == self._hovered:
            color = (0.38, 0.70, 0.96)
        count = len(patch.vertices)
        vertices = patch.vertices + patch.label_vertices
        triangles = patch.triangles + tuple(
            tuple(index + count for index in triangle)
            for triangle in patch.label_triangles
        )
        colors = (SrgbColor(*color, 1.0),) * count + (
            SrgbColor(0.96, 0.97, 1.0, 1.0),
        ) * len(patch.label_vertices)
        return vertices, triangles, colors

    def _pointer(self, key, event) -> None:
        kind = TargetPointerEventKind3D
        previous = {self._hovered, self._pressed}
        if event.kind == kind.Enter:
            self._hovered = key
        elif event.kind == kind.Leave:
            if self._hovered == key:
                self._hovered = None
        elif event.kind == kind.Down:
            self._activation_button = event.pointer_event.button
            if self._activation_button == 0:
                self._pressed = key
        elif event.kind in (kind.Up, kind.Cancel):
            self._pressed = None
            if event.kind == kind.Cancel:
                self._activation_button = None
                self._hovered = None
        changed = previous.symmetric_difference({self._hovered, self._pressed})
        # Hover -> pressed also changes color while the same item stays active.
        if event.kind in (kind.Down, kind.Up):
            changed.add(key)
        for changed_key in changed - {None}:
            vertices, triangles, colors = self._geometry(changed_key)
            self._items[changed_key].set_geometry(vertices, triangles, colors=colors)
        self._caption.text = (
            "From " + self._hovered.replace("_", " ").title()
            if self._hovered else ""
        )
        if changed:
            self.view.invalidate_scene()
            self._viewport._request_render()

    def _activate(self, key, action) -> None:
        if action != "activate" or self._activation_button != 0:
            return
        if self._controller is None:
            _logger.error("Cannot snap orientation cube without an editor camera")
            return
        self._controller.snap_view(ViewDirection[key])
        if sum(value != 0 for value in self._patches[key].direction) == 1:
            self._camera.enter_axis_view(self._controller.radius)
        else:
            self._camera.leave_axis_view()
        self.view.invalidate_view()
        self._viewport._request_render()

    def _provide_camera(self, size):
        rotation = self._camera.entity.transform.global_rotation
        eye = rotation.rotate(Vec3(0.0, -5.0, 0.0))
        up = rotation.rotate(Vec3(0.0, 0.0, 1.0))
        aspect = size.width / max(size.height, 1)
        return SceneView3DCamera(
            Mat44.look_at(eye, Vec3(0.0, 0.0, 0.0), up),
            Mat44.orthographic(-1.65 * aspect, 1.65 * aspect, -1.65, 1.65, 0.1, 10.0),
            eye,
        )

    def rebind_camera(self) -> None:
        self.unbind_camera()
        camera = self._viewport.camera
        if camera is None or camera.entity is None:
            raise RuntimeError("orientation cube requires an editor camera")
        controller = camera.entity.get_component(OrbitCameraController)
        if controller is None:
            raise RuntimeError("orientation cube requires OrbitCameraController")
        self._camera = camera
        self._controller = controller
        self.view.set_camera_provider(self._provide_camera)
        self.view.widget.enabled = True

    def unbind_camera(self) -> None:
        if self.view is not None:
            self.view.widget.enabled = False
            self.view.set_camera_provider(None)
        self._controller = None
        self._camera = None

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.unbind_camera()
        if self.view is not None:
            for item in self._items.values():
                self.view.set_target_pointer_handler(item.handle, None)
                self.view.set_action_handler(item.handle, None)
            self.view.detach_scene()
        if self.root is not None and self.root.alive:
            self._viewport.document.destroy_widget_recursive(self.root.handle)
        self._items.clear()
        tc_visual_scene3d_destroy(self.scene)


__all__ = ["NativeOrientationCube"]
