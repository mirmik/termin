"""
RenderingController — manages displays and viewports in the editor.

Handles:
- Display list management (add, remove, rename)
- Viewport management (add, remove, configure)
- Connecting ViewportListWidget with InspectorController
- Central viewport tab management
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, List, Optional

from PyQt6.QtWidgets import QTabWidget, QWidget

if TYPE_CHECKING:
    from termin.visualization.core.display import Display
    from termin.visualization.core.viewport import Viewport
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.camera import CameraComponent
    from termin.visualization.platform.backends.base import GraphicsBackend
    from termin.editor.viewport_list_widget import ViewportListWidget
    from termin.editor.inspector_controller import InspectorController


class RenderingController:
    """
    Controller for managing rendering displays and viewports.

    Provides:
    - Display lifecycle management
    - Viewport configuration
    - Integration with ViewportListWidget and InspectorController
    - Central tab widget management for display switching
    """

    def __init__(
        self,
        viewport_list_widget: "ViewportListWidget",
        inspector_controller: "InspectorController",
        center_tab_widget: Optional[QTabWidget] = None,
        get_scene: Optional[Callable[[], "Scene"]] = None,
        get_graphics: Optional[Callable[[], "GraphicsBackend"]] = None,
        on_display_selected: Optional[Callable[["Display"], None]] = None,
        on_viewport_selected: Optional[Callable[["Viewport"], None]] = None,
        on_request_update: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize RenderingController.

        Args:
            viewport_list_widget: Widget showing display/viewport tree.
            inspector_controller: Controller for inspector panels.
            center_tab_widget: Optional tab widget for display switching.
            get_scene: Callback to get current scene.
            get_graphics: Callback to get GraphicsBackend for creating surfaces.
            on_display_selected: Callback when display is selected.
            on_viewport_selected: Callback when viewport is selected.
            on_request_update: Callback to request viewport redraw.
        """
        self._viewport_list = viewport_list_widget
        self._inspector = inspector_controller
        self._center_tabs = center_tab_widget
        self._get_scene = get_scene
        self._get_graphics = get_graphics
        self._on_display_selected = on_display_selected
        self._on_viewport_selected = on_viewport_selected
        self._on_request_update = on_request_update

        self._displays: List["Display"] = []
        self._display_names: dict[int, str] = {}
        self._selected_display: Optional["Display"] = None
        self._selected_viewport: Optional["Viewport"] = None

        self._connect_signals()

    def _connect_signals(self) -> None:
        """Connect ViewportListWidget signals."""
        self._viewport_list.display_selected.connect(self._on_display_selected_from_list)
        self._viewport_list.viewport_selected.connect(self._on_viewport_selected_from_list)
        self._viewport_list.display_add_requested.connect(self._on_add_display_requested)
        self._viewport_list.viewport_add_requested.connect(self._on_add_viewport_requested)
        self._viewport_list.display_remove_requested.connect(self._on_remove_display_requested)
        self._viewport_list.viewport_remove_requested.connect(self._on_remove_viewport_requested)

        # Connect inspector signals
        self._inspector.display_inspector.name_changed.connect(self._on_display_name_changed)
        self._inspector.viewport_inspector.display_changed.connect(self._on_viewport_display_changed)
        self._inspector.viewport_inspector.camera_changed.connect(self._on_viewport_camera_changed)
        self._inspector.viewport_inspector.rect_changed.connect(self._on_viewport_rect_changed)
        self._inspector.viewport_inspector.depth_changed.connect(self._on_viewport_depth_changed)

    @property
    def displays(self) -> List["Display"]:
        """List of managed displays."""
        return list(self._displays)

    @property
    def selected_display(self) -> Optional["Display"]:
        """Currently selected display."""
        return self._selected_display

    @property
    def selected_viewport(self) -> Optional["Viewport"]:
        """Currently selected viewport."""
        return self._selected_viewport

    def add_display(self, display: "Display", name: Optional[str] = None) -> None:
        """
        Add a display to management.

        Args:
            display: Display to add.
            name: Optional display name.
        """
        if display in self._displays:
            return

        self._displays.append(display)
        if name is not None:
            self._display_names[id(display)] = name
        else:
            idx = len(self._displays) - 1
            self._display_names[id(display)] = f"Display {idx}"

        self._viewport_list.add_display(display, self._display_names[id(display)])
        self._update_center_tabs()

    def remove_display(self, display: "Display") -> None:
        """
        Remove a display from management.

        Args:
            display: Display to remove.
        """
        if display not in self._displays:
            return

        self._displays.remove(display)
        self._display_names.pop(id(display), None)
        self._viewport_list.remove_display(display)

        if self._selected_display is display:
            self._selected_display = None
            self._selected_viewport = None

        self._update_center_tabs()

    def get_display_name(self, display: "Display") -> str:
        """Get display name."""
        return self._display_names.get(id(display), "Display")

    def set_display_name(self, display: "Display", name: str) -> None:
        """Set display name."""
        self._display_names[id(display)] = name
        self._viewport_list.set_display_name(display, name)
        self._update_center_tabs()

    def refresh(self) -> None:
        """Refresh all UI components."""
        self._viewport_list.set_displays(self._displays)
        for display in self._displays:
            name = self._display_names.get(id(display), "")
            self._viewport_list.set_display_name(display, name)
        self._update_center_tabs()

    # --- Selection handling ---

    def _on_display_selected_from_list(self, display: Optional["Display"]) -> None:
        """Handle display selection from list."""
        self._selected_display = display
        self._selected_viewport = None

        if display is not None:
            name = self._display_names.get(id(display), "")
            self._inspector.show_display_inspector(display, name)

            if self._on_display_selected is not None:
                self._on_display_selected(display)

    def _on_viewport_selected_from_list(self, viewport: Optional["Viewport"]) -> None:
        """Handle viewport selection from list."""
        self._selected_viewport = viewport

        if viewport is not None:
            # Update selected display from viewport's parent
            self._selected_display = viewport.display

            scene = self._get_scene() if self._get_scene is not None else None
            self._inspector.show_viewport_inspector(
                viewport=viewport,
                displays=self._displays,
                display_names=self._display_names,
                scene=scene,
            )

            if self._on_viewport_selected is not None:
                self._on_viewport_selected(viewport)

    # --- Add/Remove requests ---

    def _on_add_display_requested(self) -> None:
        """Handle request to add new display."""
        if self._get_graphics is None:
            return

        graphics = self._get_graphics()
        if graphics is None:
            return

        # Create offscreen surface for new display
        from termin.visualization.render.surface import OffscreenRenderSurface
        from termin.visualization.core.display import Display

        surface = OffscreenRenderSurface(graphics, width=800, height=600)
        display = Display(surface)

        # Generate unique name
        existing_names = set(self._display_names.values())
        idx = 0
        while True:
            name = f"Display {idx}"
            if name not in existing_names:
                break
            idx += 1

        self.add_display(display, name)
        self._request_update()

    def _on_add_viewport_requested(self, display: "Display") -> None:
        """Handle request to add viewport to display."""
        scene = self._get_scene() if self._get_scene is not None else None
        if scene is None:
            return

        # Find first available camera in scene
        from termin.visualization.core.camera import CameraComponent

        camera: Optional[CameraComponent] = None
        for entity in scene.entities:
            cam = entity.get_component(CameraComponent)
            if cam is not None:
                camera = cam
                break

        if camera is None:
            return

        # Create viewport
        viewport = display.create_viewport(
            scene=scene,
            camera=camera,
            rect=(0.0, 0.0, 1.0, 1.0),
        )

        self._viewport_list.refresh()
        self._request_update()

    def _on_remove_display_requested(self, display: "Display") -> None:
        """Handle request to remove display."""
        self.remove_display(display)
        self._request_update()

    def _on_remove_viewport_requested(self, viewport: "Viewport") -> None:
        """Handle request to remove viewport."""
        if viewport.display is not None:
            viewport.display.remove_viewport(viewport)

        if self._selected_viewport is viewport:
            self._selected_viewport = None

        self._viewport_list.refresh()
        self._request_update()

    # --- Inspector change handlers ---

    def _on_display_name_changed(self, new_name: str) -> None:
        """Handle display name change from inspector."""
        if self._selected_display is not None:
            self.set_display_name(self._selected_display, new_name)

    def _on_viewport_display_changed(self, new_display: "Display") -> None:
        """Handle viewport display change from inspector."""
        if self._selected_viewport is None:
            return

        old_display = self._selected_viewport.display
        if old_display is not None and old_display is not new_display:
            old_display.remove_viewport(self._selected_viewport)

        if new_display is not None:
            new_display.add_viewport(self._selected_viewport)

        self._viewport_list.refresh()
        self._request_update()

    def _on_viewport_camera_changed(self, new_camera: "CameraComponent") -> None:
        """Handle viewport camera change from inspector."""
        if self._selected_viewport is None:
            return

        viewport = self._selected_viewport

        # Remove viewport from old camera's list
        old_camera = viewport.camera
        if old_camera is not None and old_camera is not new_camera:
            old_camera.remove_viewport(viewport)

        # Update viewport camera and add to new camera's list
        viewport.camera = new_camera
        new_camera.add_viewport(viewport)

        self._viewport_list.refresh()
        self._request_update()

    def _on_viewport_rect_changed(self, new_rect: tuple) -> None:
        """Handle viewport rect change from inspector."""
        if self._selected_viewport is None:
            return

        # Viewport.rect is a tuple, need to replace it
        # Since Viewport is a dataclass, we can assign directly
        self._selected_viewport.rect = new_rect
        self._request_update()

    def _on_viewport_depth_changed(self, new_depth: int) -> None:
        """Handle viewport depth change from inspector."""
        if self._selected_viewport is None:
            return

        self._selected_viewport.depth = new_depth
        self._request_update()

    # --- Center tabs management ---

    def _update_center_tabs(self) -> None:
        """Update center tab widget with current displays."""
        if self._center_tabs is None:
            return

        # Keep first tab (Editor view), remove others
        while self._center_tabs.count() > 1:
            self._center_tabs.removeTab(1)

        # Add tabs for each display
        for display in self._displays:
            name = self._display_names.get(id(display), "Display")
            # For now, add placeholder widgets
            # Later, these will be actual render previews
            placeholder = QWidget()
            self._center_tabs.addTab(placeholder, name)

    def _request_update(self) -> None:
        """Request viewport update."""
        if self._on_request_update is not None:
            self._on_request_update()
