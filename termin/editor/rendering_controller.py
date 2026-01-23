"""
RenderingController — manages displays and viewports in the editor.

Handles:
- Display list management (add, remove, rename)
- Viewport management (add, remove, configure)
- Connecting ViewportListWidget with InspectorController
- Central viewport tab management with OpenGL widgets
- Rendering additional displays
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, List, Optional, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QWindow
from PyQt6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from termin.visualization.core.display import Display
    from termin.visualization.core.viewport import Viewport
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.camera import CameraComponent
    from termin.visualization.core.entity import Entity
    from termin.visualization.platform.backends.base import BackendWindow, GraphicsBackend, WindowBackend
    from termin.visualization.platform.backends.sdl_embedded import SDLEmbeddedWindowBackend
    from termin.visualization.render import RenderEngine, ViewportRenderState
    from termin.visualization.render.framegraph import RenderPipeline
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

    Delegates core rendering to RenderingManager singleton.
    """

    _instance: Optional["RenderingController"] = None

    @classmethod
    def instance(cls) -> Optional["RenderingController"]:
        """Get the singleton instance."""
        return cls._instance

    def __init__(
        self,
        viewport_list_widget: "ViewportListWidget",
        inspector_controller: "InspectorController",
        center_tab_widget: Optional[QTabWidget] = None,
        get_scene: Optional[Callable[[], "Scene"]] = None,
        get_graphics: Optional[Callable[[], "GraphicsBackend"]] = None,
        get_window_backend: Optional[Callable[[], "WindowBackend"]] = None,
        get_sdl_backend: Optional[Callable[[], "SDLEmbeddedWindowBackend"]] = None,
        on_display_selected: Optional[Callable[["Display"], None]] = None,
        on_viewport_selected: Optional[Callable[["Viewport"], None]] = None,
        on_entity_selected: Optional[Callable[["Entity"], None]] = None,
        on_request_update: Optional[Callable[[], None]] = None,
        make_editor_pipeline: Optional[Callable[[], "RenderPipeline"]] = None,
        on_display_input_mode_changed: Optional[Callable[["Display", str], None]] = None,
    ):
        """
        Initialize RenderingController.

        Args:
            viewport_list_widget: Widget showing display/viewport tree.
            inspector_controller: Controller for inspector panels.
            center_tab_widget: Tab widget for display switching.
            get_scene: Callback to get current scene.
            get_graphics: Callback to get GraphicsBackend for creating surfaces.
            get_window_backend: Callback to get WindowBackend for creating GL widgets.
            get_sdl_backend: Callback to get SDLEmbeddedWindowBackend for creating SDL windows.
            on_display_selected: Callback when display is selected.
            on_viewport_selected: Callback when viewport is selected.
            on_request_update: Callback to request viewport redraw.
        """
        # Set singleton instance
        RenderingController._instance = self

        # Core rendering manager (singleton)
        from termin.visualization.render.manager import RenderingManager
        self._manager = RenderingManager.instance()

        self._viewport_list = viewport_list_widget
        self._inspector = inspector_controller
        self._center_tabs = center_tab_widget
        self._get_scene = get_scene
        self._get_graphics = get_graphics
        self._get_window_backend = get_window_backend
        self._get_sdl_backend = get_sdl_backend
        self._on_display_selected = on_display_selected
        self._on_viewport_selected = on_viewport_selected
        self._on_entity_selected = on_entity_selected
        self._on_request_update = on_request_update
        self._make_editor_pipeline = make_editor_pipeline
        self._on_display_input_mode_changed_callback = on_display_input_mode_changed

        self._selected_display: Optional["Display"] = None
        self._selected_viewport: Optional["Viewport"] = None

        # Map display id -> (tab container widget, BackendWindow, QWindow)
        # QWindow is stored to prevent garbage collection
        self._display_tabs: dict[int, Tuple[QWidget, "BackendWindow", QWindow]] = {}

        # Map display id -> input manager (to prevent GC)
        self._display_input_managers: dict[int, object] = {}

        # Editor display ID (not serialized, created before scene)
        self._editor_display_id: Optional[int] = None

        # Register display factory with RenderingManager
        self._manager.set_display_factory(self._create_display_for_name)

        # Register pipeline factory with RenderingManager
        self._manager.set_pipeline_factory(self._create_pipeline_for_name)

        # Initialize offscreen rendering context
        # This creates dedicated GL context for rendering, shared by all displays
        self._manager.initialize()

        self._connect_signals()

    def _connect_signals(self) -> None:
        """Connect ViewportListWidget signals."""
        self._viewport_list.display_selected.connect(self._on_display_selected_from_list)
        self._viewport_list.viewport_selected.connect(self._on_viewport_selected_from_list)
        self._viewport_list.entity_selected.connect(self._on_entity_selected_from_list)
        self._viewport_list.display_add_requested.connect(self._on_add_display_requested)
        self._viewport_list.viewport_add_requested.connect(self._on_add_viewport_requested)
        self._viewport_list.display_remove_requested.connect(self._on_remove_display_requested)
        self._viewport_list.viewport_remove_requested.connect(self._on_remove_viewport_requested)

        # Connect inspector signals
        self._inspector.display_inspector.name_changed.connect(self._on_display_name_changed)
        self._inspector.display_inspector.input_mode_changed.connect(self._on_display_input_mode_changed)
        self._inspector.display_inspector.block_input_in_editor_changed.connect(self._on_display_block_input_in_editor_changed)
        self._inspector.viewport_inspector.display_changed.connect(self._on_viewport_display_changed)
        self._inspector.viewport_inspector.camera_changed.connect(self._on_viewport_camera_changed)
        self._inspector.viewport_inspector.rect_changed.connect(self._on_viewport_rect_changed)
        self._inspector.viewport_inspector.pipeline_changed.connect(self._on_viewport_pipeline_changed)
        self._inspector.pipeline_inspector.pipeline_changed.connect(self._on_pipeline_inspector_changed)

        # Set editor pipeline getter for ViewportInspector
        if self._make_editor_pipeline is not None:
            self._inspector.viewport_inspector.set_editor_pipeline_getter(self._make_editor_pipeline)

        # Connect center tabs signal for tab switching
        if self._center_tabs is not None:
            self._center_tabs.currentChanged.connect(self._on_center_tab_changed)
        self._inspector.viewport_inspector.depth_changed.connect(self._on_viewport_depth_changed)
        self._inspector.viewport_inspector.enabled_changed.connect(self._on_viewport_enabled_changed)

    def set_editor_pipeline_maker(self, maker: Callable[[], "RenderPipeline"]) -> None:
        """Set callback for creating editor pipeline."""
        self._make_editor_pipeline = maker
        # Also update ViewportInspector
        self._inspector.viewport_inspector.set_editor_pipeline_getter(maker)

    # --- Factories ---

    def _create_pipeline_for_name(self, name: str) -> Optional["RenderPipeline"]:
        """
        Factory callback for RenderingManager.

        Creates a pipeline by special name (e.g., "(Editor)").

        Args:
            name: Pipeline special name.

        Returns:
            Created RenderPipeline or None if unknown name.
        """
        if name == "(Editor)":
            if self._make_editor_pipeline is not None:
                return self._make_editor_pipeline()
        return None

    def _create_display_for_name(self, name: str) -> Optional["Display"]:
        """
        Factory callback for RenderingManager.

        Creates a new display with SDL window embedded in Qt tab.

        Args:
            name: Display name.

        Returns:
            Created Display or None if creation failed.
        """
        if self._get_sdl_backend is None or self._center_tabs is None:
            return None

        sdl_backend = self._get_sdl_backend()
        if sdl_backend is None:
            return None

        # Ensure SDL backend is configured with shared context
        if self._manager.offscreen_context is not None:
            sdl_backend.set_share_context(
                share_context=self._manager.offscreen_context.gl_context,
                make_current_fn=self._manager.offscreen_context.make_current,
            )
            sdl_backend.set_graphics(self._manager.graphics)

        # Create tab container widget
        tab_container = QWidget()
        tab_layout = QVBoxLayout(tab_container)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(0)

        # Create SDL window with OpenGL context (shares context with offscreen)
        backend_window = sdl_backend.create_embedded_window(
            width=800,
            height=600,
            title=name,
        )

        # Embed SDL window into Qt via QWindow.fromWinId
        native_handle = backend_window.native_handle
        qwindow = QWindow.fromWinId(native_handle)
        gl_widget = QWidget.createWindowContainer(qwindow, tab_container)
        gl_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        gl_widget.setMinimumSize(50, 50)
        tab_layout.addWidget(gl_widget)

        # Set up focus callback: when SDL gets mouse click, request Qt focus
        backend_window.set_focus_callback(lambda w=gl_widget: w.setFocus())
        # Install Qt keyboard event filter to forward key events to SDL
        backend_window.install_qt_key_filter(gl_widget)

        # Create WindowRenderSurface and Display
        from termin.visualization.render.surface import WindowRenderSurface
        from termin.visualization.core.display import Display

        surface = WindowRenderSurface(backend_window)
        display = Display(surface, name=name)

        # Store mapping (include qwindow to prevent GC)
        display_id = id(display)
        self._display_tabs[display_id] = (tab_container, backend_window, qwindow)

        # Add tab to center widget
        self._center_tabs.addTab(tab_container, name)

        # Update viewport list
        self._viewport_list.add_display(display, name)

        return display

    def attach_scene(self, scene: "Scene") -> List["Viewport"]:
        """
        Attach scene using its viewport configuration.

        Creates displays via factory, mounts viewports, sets up input managers.

        Args:
            scene: Scene with viewport_configs to attach.

        Returns:
            List of created viewports.
        """
        from termin.visualization.core.viewport_config import ViewportConfig

        # Use RenderingManager to create viewports
        viewports = self._manager.attach_scene(scene)

        # Set up input managers for each display based on viewport configs
        # Group viewports by display
        display_viewports: dict[int, list[tuple["Viewport", ViewportConfig]]] = {}

        for viewport in viewports:
            display = self._manager.get_display_for_viewport(viewport)
            if display is None:
                continue
            display_id = id(display)

            # Find matching ViewportConfig
            config = self._find_viewport_config(scene, viewport, display)
            if config is None:
                continue

            if display_id not in display_viewports:
                display_viewports[display_id] = []
            display_viewports[display_id].append((viewport, config, display))

        # Set up input for each display
        for display_id, vp_configs in display_viewports.items():
            if not vp_configs:
                continue

            # Use first viewport's input mode for the display
            viewport, config, display = vp_configs[0]

            # Skip editor display - it has its own input handling
            if display_id == self._editor_display_id:
                continue

            self._setup_display_input(display, config.input_mode)

        # Refresh UI
        self._viewport_list.refresh()
        self._request_update()

        return viewports

    def _find_viewport_config(self, scene: "Scene", viewport: "Viewport", display: "Display" = None):
        """Find ViewportConfig that matches a viewport."""
        from termin.visualization.core.viewport_config import ViewportConfig

        if display is None:
            display = self._manager.get_display_for_viewport(viewport)
        if display is None or viewport.camera is None:
            return None

        display_name = display.name
        camera_uuid = ""
        if viewport.camera.entity is not None:
            camera_uuid = viewport.camera.entity.uuid

        for config in scene.viewport_configs:
            if config.display_name == display_name and config.camera_uuid == camera_uuid:
                return config

        return None

    def _setup_display_input(self, display: "Display", input_mode: str) -> None:
        """
        Set up input manager for a display.

        Args:
            display: Display to set up input for.
            input_mode: Input mode ("none", "simple", "editor").
        """
        display_id = id(display)

        # Get backend window
        tab_info = self._display_tabs.get(display_id)
        if tab_info is None:
            return

        _tab_container, backend_window, _qwindow = tab_info

        # Remove old input manager
        if display_id in self._display_input_managers:
            del self._display_input_managers[display_id]

        # Clear callbacks first
        backend_window.set_cursor_pos_callback(None)
        backend_window.set_scroll_callback(None)
        backend_window.set_mouse_button_callback(None)
        backend_window.set_key_callback(None)

        if input_mode == "none":
            pass
        elif input_mode == "simple":
            from termin.visualization.platform.input_manager import SimpleDisplayInputManager

            input_manager = SimpleDisplayInputManager(
                backend_window=backend_window,
                display=display,
                on_request_update=self._request_update,
            )
            self._display_input_managers[display_id] = input_manager
        elif input_mode == "editor":
            # Editor mode is handled by EditorWindow via callback
            if self._on_display_input_mode_changed_callback is not None:
                self._on_display_input_mode_changed_callback(display, input_mode)

    def sync_viewport_configs_to_scene(self, scene: "Scene") -> None:
        """
        Sync current viewport state to scene.viewport_configs.

        Call this before saving to ensure viewport_configs reflects current state.
        Excludes editor display viewports (they are managed separately).

        Args:
            scene: Scene to update viewport_configs for.
        """
        from termin.visualization.core.viewport_config import ViewportConfig

        scene.clear_viewport_configs()

        for display in self._manager.displays:
            # Skip editor display - it's managed separately
            if id(display) == self._editor_display_id:
                continue

            for viewport in display.viewports:
                if viewport.scene is not scene:
                    continue

                # Get camera UUID
                camera_uuid = ""
                if viewport.camera is not None and viewport.camera.entity is not None:
                    camera_uuid = viewport.camera.entity.uuid

                # Get pipeline UUID or special name
                pipeline_uuid = None
                pipeline_name = None
                if viewport.pipeline is not None:
                    pipeline_uuid = self._get_pipeline_uuid(viewport.pipeline)
                    # If no UUID found, check for special pipeline names
                    if pipeline_uuid is None:
                        if viewport.pipeline.name == "editor":
                            pipeline_name = "(Editor)"

                config = ViewportConfig(
                    name=viewport.name or "",
                    display_name=display.name,
                    camera_uuid=camera_uuid,
                    region=viewport.rect,
                    depth=viewport.depth,
                    input_mode=viewport.input_mode,
                    block_input_in_editor=viewport.block_input_in_editor,
                    pipeline_uuid=pipeline_uuid,
                    pipeline_name=pipeline_name,
                    layer_mask=viewport.layer_mask,
                    enabled=viewport.enabled,
                )
                scene.add_viewport_config(config)

    def detach_scene(self, scene: "Scene") -> None:
        """
        Detach scene from all displays.

        Removes viewports and cleans up input managers for non-editor displays.

        Args:
            scene: Scene to detach.
        """
        # Get displays that will lose all viewports
        displays_to_check = set()
        for display in self._manager.displays:
            for viewport in display.viewports:
                if viewport.scene is scene:
                    displays_to_check.add(id(display))

        # Detach scene
        self._manager.detach_scene(scene)

        # Clean up input managers for displays that now have no viewports
        for display_id in displays_to_check:
            # Find display
            display = None
            for d in self._manager.displays:
                if id(d) == display_id:
                    display = d
                    break

            if display is not None and not display.viewports:
                # Remove input manager
                if display_id in self._display_input_managers:
                    del self._display_input_managers[display_id]

        # Refresh UI
        self._viewport_list.refresh()
        self._request_update()

    @property
    def displays(self) -> List["Display"]:
        """List of managed displays."""
        return self._manager.displays

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
        if display in self._manager.displays:
            return

        self._manager.add_display(display, name)
        self._viewport_list.add_display(display, self._manager.get_display_name(display))
        self._update_center_tabs()

    def remove_display(self, display: "Display") -> None:
        """
        Remove a display from management.

        Args:
            display: Display to remove.
        """
        if display not in self._manager.displays:
            return

        display_id = id(display)

        self._manager.remove_display(display)
        self._viewport_list.remove_display(display)

        # Clean up tab resources
        if display_id in self._display_tabs:
            tab_container, backend_window, _qwindow = self._display_tabs.pop(display_id)
            # Close backend window
            if backend_window is not None:
                backend_window.close()

        if self._selected_display is display:
            self._selected_display = None
            self._selected_viewport = None

        self._update_center_tabs()

    def get_display_name(self, display: "Display") -> str:
        """Get display name."""
        return self._manager.get_display_name(display)

    def set_display_name(self, display: "Display", name: str) -> None:
        """Set display name."""
        self._manager.set_display_name(display, name)
        self._viewport_list.set_display_name(display, name)
        self._update_center_tabs()

    def refresh(self) -> None:
        """Refresh all UI components."""
        self._viewport_list.set_displays(self._manager.displays)
        for display in self._manager.displays:
            name = self._manager.get_display_name(display)
            self._viewport_list.set_display_name(display, name)
        self._update_center_tabs()

    def remove_viewports_for_scene(self, scene: "Scene") -> None:
        """
        Remove all viewports that reference the given scene.

        Called before scene is destroyed or deactivated.
        Destroys pipelines to clear callbacks, clears FBOs, then removes viewports.
        """
        for display in self._manager.displays:
            display_id = id(display)
            viewports_to_remove = [vp for vp in display.viewports if vp.scene is scene]
            if not viewports_to_remove:
                continue

            # Make GL context current for this display before deleting resources
            tab_info = self._display_tabs.get(display_id)
            if tab_info is not None:
                _tab_container, backend_window, _qwindow = tab_info
                if backend_window is not None:
                    backend_window.make_current()

            for vp in viewports_to_remove:
                # Destroy pipeline
                if vp.pipeline is not None:
                    vp.pipeline.destroy()
                # Clear FBOs and remove viewport state
                state = self._manager.get_viewport_state(vp)
                if state is not None:
                    state.clear_fbos()
                self._manager.remove_viewport_state(vp)
                display.remove_viewport(vp)
        self._viewport_list.refresh()

    # --- Editor display ---

    def create_editor_display(
        self,
        container: QWidget,
        sdl_backend: "SDLEmbeddedWindowBackend",
        width: int = 800,
        height: int = 600,
    ) -> Tuple["Display", "BackendWindow"]:
        """
        Create the main editor display.

        This display is not serialized and is created before scene loading.
        Should be called once at editor startup.

        Args:
            container: Qt container widget for embedding SDL window.
            sdl_backend: SDL backend for creating embedded window.
            width: Initial window width.
            height: Initial window height.

        Returns:
            Tuple of (Display, BackendWindow) for editor use.
        """
        from termin.visualization.render.surface import WindowRenderSurface
        from termin.visualization.core.display import Display

        # Configure SDL backend to share GL context with offscreen rendering context
        # This ensures all displays use the same GL resources
        if self._manager.offscreen_context is not None:
            sdl_backend.set_share_context(
                share_context=self._manager.offscreen_context.gl_context,
                make_current_fn=self._manager.offscreen_context.make_current,
            )
            # Also set graphics from offscreen context
            sdl_backend.set_graphics(self._manager.graphics)

        # Create SDL window (will share context with offscreen context)
        backend_window = sdl_backend.create_embedded_window(
            width=width,
            height=height,
            title="Editor Viewport",
        )

        # Embed SDL window into Qt
        native_handle = backend_window.native_handle
        qwindow = QWindow.fromWinId(native_handle)
        gl_widget = QWidget.createWindowContainer(qwindow, container)
        gl_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        gl_widget.setMinimumSize(50, 50)

        # Set up focus callback: when SDL gets mouse click, request Qt focus
        backend_window.set_focus_callback(lambda w=gl_widget: w.setFocus())
        # Install Qt keyboard event filter to forward key events to SDL
        backend_window.install_qt_key_filter(gl_widget)

        # Add to container layout
        layout = container.layout()
        if layout is None:
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            container.setLayout(layout)
        layout.addWidget(gl_widget)

        # Create surface and display (editor_only=True by default)
        surface = WindowRenderSurface(backend_window)
        display = Display(surface, name="Editor", editor_only=True)

        # Store mapping
        display_id = id(display)
        self._display_tabs[display_id] = (container, backend_window, qwindow)
        self._editor_display_id = display_id

        # Add to displays list (editor display input is managed by EditorViewportFeatures)
        self.add_display(display, "Editor")

        return display, backend_window

    def is_editor_display(self, display: "Display") -> bool:
        """Check if display is the editor display (not serialized)."""
        return id(display) == self._editor_display_id

    @property
    def editor_display(self) -> Optional["Display"]:
        """Get the editor display."""
        if self._editor_display_id is None:
            return None
        for display in self._manager.displays:
            if id(display) == self._editor_display_id:
                return display
        return None

    @property
    def editor_backend_window(self) -> Optional["BackendWindow"]:
        """Get the editor backend window."""
        if self._editor_display_id is None:
            return None
        if self._editor_display_id not in self._display_tabs:
            return None
        _container, backend_window, _qwindow = self._display_tabs[self._editor_display_id]
        return backend_window

    def create_editor_viewport(
        self,
        scene: "Scene",
        camera: "CameraComponent",
        pipeline: Optional["RenderPipeline"] = None,
    ) -> Optional["Viewport"]:
        """
        Create a viewport in the editor display for a scene.

        Called when switching to a new scene to create its editor viewport.
        Uses editor pipeline getter if no pipeline specified.

        Args:
            scene: Scene to display.
            camera: Camera component for the viewport.
            pipeline: Optional pipeline. If None, uses editor pipeline.

        Returns:
            Created Viewport or None if editor display doesn't exist.
        """
        display = self.editor_display
        if display is None:
            return None

        # Get pipeline from maker if not specified
        if pipeline is None and self._make_editor_pipeline is not None:
            pipeline = self._make_editor_pipeline()

        viewport = display.create_viewport(
            scene=scene,
            camera=camera,
            rect=(0.0, 0.0, 1.0, 1.0),
        )
        viewport.name = "(Editor)"
        viewport.pipeline = pipeline

        self._viewport_list.refresh()
        return viewport

    def remove_editor_viewports(self) -> None:
        """
        Remove all viewports from the editor display.

        Called when detaching from a scene to clean up viewports.
        Destroys pipelines and clears FBOs before removing.
        """
        display = self.editor_display
        if display is None:
            return

        # Make GL context current
        if self._editor_display_id is not None:
            tab_info = self._display_tabs.get(self._editor_display_id)
            if tab_info is not None:
                _tab_container, backend_window, _qwindow = tab_info
                if backend_window is not None:
                    backend_window.make_current()

        for vp in list(display.viewports):
            # Destroy pipeline
            if vp.pipeline is not None:
                vp.pipeline.destroy()
            # Clear FBOs and remove viewport state
            state = self._manager.get_viewport_state(vp)
            if state is not None:
                state.clear_fbos()
            self._manager.remove_viewport_state(vp)
            display.remove_viewport(vp)

        self._viewport_list.refresh()

    @property
    def editor_gl_widget(self) -> Optional[QWidget]:
        """Get the Qt widget containing the editor GL surface."""
        if self._editor_display_id is None:
            return None
        if self._editor_display_id not in self._display_tabs:
            return None
        container, _backend_window, _qwindow = self._display_tabs[self._editor_display_id]
        # The gl_widget is the first child of the container layout
        layout = container.layout()
        if layout is not None and layout.count() > 0:
            return layout.itemAt(0).widget()
        return None

    def get_editor_fbo_pool(self) -> dict:
        """Get FBO pool for the editor viewport (for picking)."""
        return self.get_display_fbo_pool(self.editor_display)

    def get_display_fbo_pool(self, display: Optional["Display"]) -> dict:
        """Get FBO pool for a display's primary viewport (for picking)."""
        if display is None or not display.viewports:
            return {}
        viewport = display.viewports[0]
        state = self.get_viewport_state(viewport)
        if state is None:
            return {}
        return state.fbos

    def get_display_backend_window(self, display: "Display") -> Optional["BackendWindow"]:
        """Get backend window for a display."""
        display_id = id(display)
        tab_info = self._display_tabs.get(display_id)
        if tab_info is None:
            return None
        _tab_container, backend_window, _qwindow = tab_info
        return backend_window

    # --- Selection handling ---

    def _on_display_selected_from_list(self, display: Optional["Display"]) -> None:
        """Handle display selection from list."""
        self._selected_display = display
        self._selected_viewport = None

        if display is not None:
            name = self._manager.get_display_name(display)
            self._inspector.show_display_inspector(display, name)

            # Get input mode from first viewport (if any)
            input_mode = "none"
            block_in_editor = False
            if display.viewports:
                first_vp = display.viewports[0]
                input_mode = first_vp.input_mode
                block_in_editor = first_vp.block_input_in_editor

            self._inspector.display_inspector.set_input_mode(input_mode)
            self._inspector.display_inspector.set_block_input_in_editor(block_in_editor)

            if self._on_display_selected is not None:
                self._on_display_selected(display)

    def _on_viewport_selected_from_list(self, viewport: Optional["Viewport"]) -> None:
        """Handle viewport selection from list."""
        self._selected_viewport = viewport

        if viewport is not None:
            # Update selected display from viewport's parent
            self._selected_display = self._manager.get_display_for_viewport(viewport)

            scene = self._get_scene() if self._get_scene is not None else None
            # Build display_names dict for inspector
            display_names = {id(d): self._manager.get_display_name(d) for d in self._manager.displays}
            self._inspector.show_viewport_inspector(
                viewport=viewport,
                displays=self._manager.displays,
                display_names=display_names,
                scene=scene,
                current_display=self._selected_display,
            )

            if self._on_viewport_selected is not None:
                self._on_viewport_selected(viewport)

    def _on_entity_selected_from_list(self, entity: Optional["Entity"]) -> None:
        """Handle entity selection from viewport's internal_entities."""
        if entity is not None and self._on_entity_selected is not None:
            self._on_entity_selected(entity)

    # --- Add/Remove requests ---

    def _on_add_display_requested(self) -> None:
        """Handle request to add new display."""
        if self._get_graphics is None or self._get_sdl_backend is None:
            return
        if self._center_tabs is None:
            return

        graphics = self._get_graphics()
        sdl_backend = self._get_sdl_backend()
        if graphics is None or sdl_backend is None:
            return

        # Generate unique name
        existing_names = {self._manager.get_display_name(d) for d in self._manager.displays}
        idx = 0
        while True:
            name = f"Display {idx}"
            if name not in existing_names:
                break
            idx += 1

        # Create tab container widget
        tab_container = QWidget()
        tab_layout = QVBoxLayout(tab_container)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(0)

        # Create SDL window with OpenGL context
        backend_window = sdl_backend.create_embedded_window(
            width=800,
            height=600,
            title=name,
        )

        # Embed SDL window into Qt via QWindow.fromWinId
        native_handle = backend_window.native_handle
        qwindow = QWindow.fromWinId(native_handle)
        gl_widget = QWidget.createWindowContainer(qwindow, tab_container)
        gl_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        gl_widget.setMinimumSize(50, 50)
        tab_layout.addWidget(gl_widget)

        # Set up focus callback: when SDL gets mouse click, request Qt focus
        backend_window.set_focus_callback(lambda w=gl_widget: w.setFocus())
        # Install Qt keyboard event filter to forward key events to SDL
        backend_window.install_qt_key_filter(gl_widget)

        # Create WindowRenderSurface and Display
        from termin.visualization.render.surface import WindowRenderSurface
        from termin.visualization.core.display import Display

        surface = WindowRenderSurface(backend_window)
        display = Display(surface)

        # Store mapping (include qwindow to prevent GC)
        display_id = id(display)
        self._display_tabs[display_id] = (tab_container, backend_window, qwindow)

        # Create input manager for this display (default: simple mode)
        from termin.visualization.platform.input_manager import SimpleDisplayInputManager

        input_manager = SimpleDisplayInputManager(
            backend_window=backend_window,
            display=display,
            on_request_update=self._request_update,
        )
        # Store input manager to prevent GC
        self._display_input_managers[display_id] = input_manager

        # Add display (this will call _update_center_tabs)
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
        display = self._manager.get_display_for_viewport(viewport)
        if display is not None:
            display.remove_viewport(viewport)

        if self._selected_viewport is viewport:
            self._selected_viewport = None

        self._viewport_list.refresh()
        self._request_update()

    # --- Inspector change handlers ---

    def _on_display_name_changed(self, new_name: str) -> None:
        """Handle display name change from inspector."""
        if self._selected_display is not None:
            self.set_display_name(self._selected_display, new_name)

    def _on_display_input_mode_changed(self, mode: str) -> None:
        """Handle display input mode change from inspector."""
        if self._selected_display is None:
            return

        display = self._selected_display
        display_id = id(display)

        # Get backend_window for this display
        tab_info = self._display_tabs.get(display_id)
        if tab_info is None:
            return

        _tab_container, backend_window, _qwindow = tab_info

        self._apply_display_input_mode(display, backend_window, mode)

        # Notify EditorWindow to handle editor mode setup/teardown
        if self._on_display_input_mode_changed_callback is not None:
            self._on_display_input_mode_changed_callback(display, mode)

        self._request_update()

    def _apply_display_input_mode(self, display: "Display", backend_window, mode: str) -> None:
        """Apply input mode to a display."""
        display_id = id(display)

        # Check if blocked from first viewport
        is_blocked = False
        if display.viewports:
            is_blocked = display.viewports[0].block_input_in_editor

        # Remove old input manager (if managed here, not by EditorViewportFeatures)
        if display_id in self._display_input_managers:
            del self._display_input_managers[display_id]

        # Clear callbacks first
        backend_window.set_cursor_pos_callback(None)
        backend_window.set_scroll_callback(None)
        backend_window.set_mouse_button_callback(None)
        backend_window.set_key_callback(None)

        # Create new input manager based on mode (unless blocked in editor)
        if mode == "none" or (mode == "editor" and is_blocked):
            # No input handling - callbacks already cleared
            pass
        elif mode == "simple":
            from termin.visualization.platform.input_manager import SimpleDisplayInputManager

            input_manager = SimpleDisplayInputManager(
                backend_window=backend_window,
                display=display,
                on_request_update=self._request_update,
            )
            self._display_input_managers[display_id] = input_manager
        elif mode == "editor":
            # Editor mode is handled by EditorWindow via callback
            # It will create EditorViewportFeatures which owns EditorDisplayInputManager
            pass

        # Update viewport input_mode
        for viewport in display.viewports:
            viewport.input_mode = mode

    def _on_display_block_input_in_editor_changed(self, blocked: bool) -> None:
        """Handle 'block input in editor' checkbox change from inspector."""
        if self._selected_display is None:
            return

        display = self._selected_display

        # Update blocked state on all viewports
        for viewport in display.viewports:
            viewport.block_input_in_editor = blocked

        # Reapply current mode (which will check blocked flag)
        mode = "simple"
        if display.viewports:
            mode = display.viewports[0].input_mode
        self._on_display_input_mode_changed(mode)

    def _on_viewport_display_changed(self, new_display: "Display") -> None:
        """Handle viewport display change from inspector."""
        if self._selected_viewport is None:
            return

        old_display = self._manager.get_display_for_viewport(self._selected_viewport)
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

    def _on_viewport_enabled_changed(self, enabled: bool) -> None:
        """Handle viewport enabled change from inspector."""
        if self._selected_viewport is None:
            return

        self._selected_viewport.enabled = enabled
        self._request_update()

    def _on_viewport_pipeline_changed(self, pipeline: "RenderPipeline") -> None:
        """Handle viewport pipeline change from ViewportInspector."""
        if self._selected_viewport is None:
            return

        self.set_viewport_pipeline(self._selected_viewport, pipeline)

    def _on_pipeline_inspector_changed(self, pipeline: "RenderPipeline") -> None:
        """Handle pipeline change from PipelineInspector (file editor)."""
        # Pipeline is edited in-place, just trigger redraw for all displays
        self._request_update()

    def set_viewport_pipeline(self, viewport: "Viewport", pipeline: "RenderPipeline | None") -> None:
        """
        Set pipeline for a specific viewport.

        Args:
            viewport: Viewport to set pipeline for.
            pipeline: Pipeline to use, or None to disable rendering.
        """
        old_pipeline = viewport.pipeline
        viewport.pipeline = pipeline

        # Clear FBO pool and destroy old pipeline when pipeline changes
        if old_pipeline is not pipeline:
            state = self._manager.get_viewport_state(viewport)
            if state is not None:
                state.fbos.clear()
            # Destroy old pipeline to release GL resources
            if old_pipeline is not None:
                old_pipeline.destroy()

        self._request_update()

    def _get_pipeline_uuid(self, pipeline: "RenderPipeline") -> str | None:
        """Get UUID for a pipeline by looking up its asset."""
        from termin.assets.resources import ResourceManager

        rm = ResourceManager.instance()
        asset = rm.get_pipeline_asset(pipeline.name)
        if asset is not None:
            return asset.uuid
        return None

    def _get_pipeline_by_uuid(self, uuid: str) -> "RenderPipeline | None":
        """Get pipeline by UUID."""
        from termin.assets.resources import ResourceManager

        rm = ResourceManager.instance()
        return rm.get_pipeline_by_uuid(uuid)

    # --- Center tabs management ---

    def _on_center_tab_changed(self, index: int) -> None:
        """Handle center tab widget tab change."""
        # Request redraw when switching tabs
        self._request_update()

    def _get_or_create_viewport_state(self, display_id: int, viewport: "Viewport"):
        """Get or create ViewportRenderState for a viewport."""
        return self._manager.get_or_create_viewport_state(viewport)

    def get_viewport_state(self, viewport: "Viewport") -> Optional["ViewportRenderState"]:
        """Get ViewportRenderState for a viewport."""
        return self._manager.get_viewport_state(viewport)

    def get_all_viewports_info(self) -> list[tuple["Viewport", str]]:
        """
        Get list of all viewports with display names for UI selection.

        Viewports managed by scene pipelines are shown under the pipeline name.
        Unmanaged viewports are shown under the display name.

        Returns:
            List of (viewport, label) tuples.
        """
        result: list[tuple["Viewport", str]] = []

        # Group viewports by scene pipeline
        scene_pipeline_viewports: dict[str, list[tuple["Viewport", str, int]]] = {}
        unmanaged_viewports: list[tuple["Viewport", str, int]] = []

        for display in self._manager.displays:
            display_name = self._manager.get_display_name(display)
            for i, viewport in enumerate(display.viewports):
                if viewport.managed_by_scene_pipeline:
                    # Group by scene pipeline
                    pipeline_name = viewport.managed_by_scene_pipeline
                    if pipeline_name not in scene_pipeline_viewports:
                        scene_pipeline_viewports[pipeline_name] = []
                    scene_pipeline_viewports[pipeline_name].append((viewport, display_name, i))
                else:
                    unmanaged_viewports.append((viewport, display_name, i))

        # Add scene pipeline viewports first
        for pipeline_name, viewports in sorted(scene_pipeline_viewports.items()):
            for viewport, display_name, i in viewports:
                vp_name = viewport.name or f"Viewport {i}"
                label = f"[{pipeline_name}] {vp_name}"
                result.append((viewport, label))

        # Add unmanaged viewports
        for viewport, display_name, i in unmanaged_viewports:
            vp_name = viewport.name or f"Viewport {i}"
            label = f"{display_name} / {vp_name}"
            result.append((viewport, label))

        return result

    def _update_center_tabs(self) -> None:
        """Update center tab widget with current displays."""
        if self._center_tabs is None:
            return

        # Keep first tab (Editor view), remove others
        while self._center_tabs.count() > 1:
            self._center_tabs.removeTab(1)

        # Add tabs for additional displays (not Editor)
        for display in self._manager.displays:
            display_id = id(display)

            # Skip Editor display (it's already the first tab, managed externally)
            if display_id == self._editor_display_id:
                continue

            # Skip displays not in _display_tabs (legacy external displays)
            if display_id not in self._display_tabs:
                continue

            name = self._manager.get_display_name(display)
            tab_container, _backend_window, _qwindow = self._display_tabs[display_id]
            self._center_tabs.addTab(tab_container, name)

    def _request_update(self) -> None:
        """Request viewport update."""
        if self._on_request_update is not None:
            self._on_request_update()

        # Also request update for all additional displays
        for display_id in self._display_tabs:
            _tab_container, backend_window, _qwindow = self._display_tabs[display_id]
            if backend_window is not None:
                backend_window.request_update()

    def any_additional_display_needs_render(self) -> bool:
        """Check if any additional display needs rendering (excluding editor)."""
        for display_id in self._display_tabs:
            if display_id == self._editor_display_id:
                continue
            _tab_container, backend_window, _qwindow = self._display_tabs[display_id]
            if backend_window is not None and backend_window.needs_render():
                return True
        return False

    def any_display_needs_render(self) -> bool:
        """Check if any display needs rendering (including editor)."""
        for display_id in self._display_tabs:
            _tab_container, backend_window, _qwindow = self._display_tabs[display_id]
            if backend_window is not None and backend_window.needs_render():
                return True
        return False

    def render_all_displays(self) -> None:
        """Render all displays using offscreen rendering."""
        if self._get_graphics is None:
            return

        from termin.core.profiler import Profiler
        profiler = Profiler.instance()

        frame_started_here = profiler._current_frame is None
        profiler.begin_frame()

        # Phase 1: Render all viewports to output_fbos
        self._manager.render_all_offscreen()

        # Phase 2: Present to displays
        for display in self._manager.displays:
            display_id = id(display)

            if display_id not in self._display_tabs:
                continue

            _tab_container, backend_window, _qwindow = self._display_tabs[display_id]
            if backend_window is None:
                continue

            backend_window.make_current()
            backend_window.check_resize()
            self._manager._present_display(display)
            backend_window.clear_render_flag()

        if frame_started_here:
            profiler.end_frame()

        # Завершаем frame только если мы его начали (не в game mode)
        if frame_started_here:
            profiler.end_frame()
