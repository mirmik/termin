"""
MeshPreviewWidget — embedded 3D viewport for mesh preview.

Uses SDL window with shared OpenGL context to render a preview scene
with orbit camera controls.
"""

from __future__ import annotations

import numpy as np
from typing import TYPE_CHECKING, Optional

from PyQt6 import QtWidgets, QtCore
from PyQt6.QtGui import QWindow

if TYPE_CHECKING:
    from termin.visualization.platform.backends.sdl_embedded import SDLEmbeddedWindowBackend
    from termin.visualization.platform.backends.base import GraphicsBackend
    from termin.mesh.mesh import Mesh3


class MeshPreviewWidget(QtWidgets.QWidget):
    """
    Widget displaying 3D mesh preview with orbit camera.

    Embeds SDL window with shared OpenGL context for rendering.
    Supports mouse interaction for orbit/pan/zoom.
    """

    def __init__(
        self,
        window_backend: "SDLEmbeddedWindowBackend",
        graphics: "GraphicsBackend",
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._window_backend = window_backend
        self._graphics = graphics

        self._sdl_window = None
        self._display = None
        self._viewport = None
        self._scene = None
        self._camera_entity = None
        self._camera_component = None
        self._orbit_controller = None
        self._mesh_entity = None
        self._light_entity = None
        self._render_engine = None
        self._viewport_state = None

        self._initialized = False
        self._mesh_loaded = False

        # Mouse tracking for orbit
        self._last_mouse_pos = None
        self._mouse_button_pressed = QtCore.Qt.MouseButton.NoButton

        self.setMinimumSize(200, 150)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        self._create_sdl_window()

    def _create_sdl_window(self) -> None:
        """Create embedded SDL window."""
        self._sdl_window = self._window_backend.create_embedded_window(
            width=300, height=200, title="Mesh Preview"
        )

        # Embed SDL window into Qt
        native_handle = self._sdl_window.native_handle
        self._qwindow = QWindow.fromWinId(native_handle)
        self._gl_container = QtWidgets.QWidget.createWindowContainer(self._qwindow, self)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._gl_container)

    def _ensure_initialized(self) -> None:
        """Initialize rendering resources on first use."""
        if self._initialized:
            return

        self._sdl_window.make_current()
        self._init_scene()
        self._init_display()
        self._init_render_engine()
        self._initialized = True

    def _init_scene(self) -> None:
        """Create preview scene with camera and light."""
        from termin.visualization.core.scene import Scene
        from termin.visualization.core.entity import Entity
        from termin.visualization.core.camera import PerspectiveCameraComponent, OrbitCameraController
        from termin.visualization.render.components.light_component import LightComponent
        from termin.lighting import LightType
        from termin.geombase import Pose3

        self._scene = Scene()

        # Camera entity
        self._camera_entity = Entity(pose=Pose3.identity(), name="preview_camera")
        self._camera_component = PerspectiveCameraComponent(
            fov=45.0,
            near=0.01,
            far=1000.0,
        )
        self._camera_entity.add_component(self._camera_component)

        self._orbit_controller = OrbitCameraController(
            target=np.array([0.0, 0.0, 0.0], dtype=np.float32),
            radius=3.0,
            azimuth=45.0,
            elevation=30.0,
            min_radius=0.1,
            max_radius=100.0,
        )
        self._camera_entity.add_component(self._orbit_controller)
        self._scene.add(self._camera_entity)

        # Directional light
        self._light_entity = Entity(pose=Pose3.identity(), name="preview_light")
        light_component = LightComponent(
            light_type=LightType.DIRECTIONAL,
            color=(1.0, 1.0, 1.0),
            intensity=1.0,
        )
        self._light_entity.add_component(light_component)
        self._scene.add(self._light_entity)

    def _init_display(self) -> None:
        """Create display and viewport for preview rendering."""
        from termin.visualization.core.display import Display
        from termin.visualization.render.surface import WindowRenderSurface

        surface = WindowRenderSurface(self._sdl_window)
        self._display = Display(surface)

        # Create viewport with simple pipeline
        self._viewport = self._display.create_viewport(
            scene=self._scene,
            camera=self._camera_component,
            rect=(0.0, 0.0, 1.0, 1.0),
            pipeline=self._make_preview_pipeline(),
        )

    def _make_preview_pipeline(self):
        """Create simplified render pipeline for preview."""
        from termin.visualization.render.framegraph import (
            ColorPass,
            PresentToScreenPass,
            RenderPipeline,
        )
        from termin.visualization.render.framegraph.passes.skybox import SkyBoxPass

        passes = [
            SkyBoxPass(input_res="empty", output_res="skybox", pass_name="Skybox"),
            ColorPass(
                input_res="skybox",
                output_res="color",
                shadow_res=None,
                pass_name="Color",
                phase_mark="opaque",
            ),
            PresentToScreenPass(
                input_res="color",
                pass_name="Present",
            ),
        ]

        return RenderPipeline(name="preview", passes=passes)

    def _init_render_engine(self) -> None:
        """Initialize render engine and viewport state."""
        from termin.visualization.render.engine import RenderEngine
        from termin.visualization.render.state import ViewportRenderState

        self._render_engine = RenderEngine(self._graphics)
        self._viewport_state = ViewportRenderState()

    def set_mesh(self, mesh3: "Mesh3") -> None:
        """Set mesh to display in preview."""
        self._ensure_initialized()

        from termin.visualization.core.entity import Entity
        from termin.visualization.core.mesh_handle import MeshHandle
        from termin.visualization.core.material import Material
        from termin.visualization.render.components import MeshRenderer
        from termin.geombase import Pose3

        # Remove old mesh entity if exists
        if self._mesh_entity is not None:
            self._scene.remove(self._mesh_entity)
            self._mesh_entity = None

        if mesh3 is None:
            self._mesh_loaded = False
            return

        # Create mesh handle
        mesh_handle = MeshHandle.from_mesh3(mesh3, name="preview_mesh")

        # Create default material (gray)
        material = Material(color=np.array([0.7, 0.7, 0.7, 1.0], dtype=np.float32))

        # Create mesh entity
        self._mesh_entity = Entity(pose=Pose3.identity(), name="preview_mesh")
        self._mesh_entity.add_component(MeshRenderer(mesh_handle, material))
        self._scene.add(self._mesh_entity)

        # Auto-fit camera to mesh bounds
        self._fit_camera_to_mesh(mesh3)

        self._mesh_loaded = True

    def _fit_camera_to_mesh(self, mesh3: "Mesh3") -> None:
        """Adjust camera to fit mesh in view."""
        vertices = mesh3.vertices
        if vertices is None or len(vertices) == 0:
            return

        # Calculate bounding box
        min_bound = np.min(vertices, axis=0)
        max_bound = np.max(vertices, axis=0)
        center = (min_bound + max_bound) / 2
        size = max_bound - min_bound
        max_dim = np.max(size)

        # Set orbit controller target and radius
        if self._orbit_controller is not None:
            self._orbit_controller.target = center.astype(np.float32)
            # Distance to fit object in view (rough approximation)
            self._orbit_controller.radius = max(max_dim * 1.5, 0.5)
            self._orbit_controller._update_pose()

    def render(self) -> None:
        """Render the preview scene."""
        if not self._initialized:
            return

        self._sdl_window.make_current()

        # Build render view
        from termin.visualization.render.view import RenderView

        width, height = self._display.get_size()
        if width <= 0 or height <= 0:
            return

        render_view = RenderView(
            viewport=self._viewport,
            surface_size=(width, height),
        )

        # Render
        self._render_engine.render_views(
            surface=self._display.surface,
            views=[(render_view, self._viewport_state)],
        )

        self._display.present()

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(300, 200)

    def resizeEvent(self, event) -> None:
        """Handle resize - update SDL window size."""
        super().resizeEvent(event)
        if self._sdl_window is not None:
            size = event.size()
            self._sdl_window.resize(size.width(), size.height())

    def mousePressEvent(self, event) -> None:
        """Handle mouse press for orbit control."""
        self._last_mouse_pos = event.position()
        self._mouse_button_pressed = event.button()
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        """Handle mouse release."""
        self._mouse_button_pressed = QtCore.Qt.MouseButton.NoButton
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        """Handle mouse move for orbit/pan."""
        if self._last_mouse_pos is None or self._orbit_controller is None:
            return

        pos = event.position()
        dx = pos.x() - self._last_mouse_pos.x()
        dy = pos.y() - self._last_mouse_pos.y()
        self._last_mouse_pos = pos

        if self._mouse_button_pressed == QtCore.Qt.MouseButton.LeftButton:
            # Orbit
            self._orbit_controller.orbit(-dx * 0.5, -dy * 0.5)
        elif self._mouse_button_pressed == QtCore.Qt.MouseButton.MiddleButton:
            # Pan
            self._orbit_controller.pan(-dx * 0.01, dy * 0.01)
        elif self._mouse_button_pressed == QtCore.Qt.MouseButton.RightButton:
            # Zoom (vertical drag)
            self._orbit_controller.zoom(-dy * 0.05)

        event.accept()

    def wheelEvent(self, event) -> None:
        """Handle mouse wheel for zoom."""
        if self._orbit_controller is None:
            return

        delta = event.angleDelta().y()
        self._orbit_controller.zoom(delta * 0.005)
        event.accept()

    def cleanup(self) -> None:
        """Clean up resources."""
        if self._sdl_window is not None:
            self._sdl_window.destroy()
            self._sdl_window = None
