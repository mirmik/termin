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
    from termin.visualization.platform.backends.base import BackendWindow, GraphicsBackend, WindowBackend
    from termin.visualization.platform.backends.sdl_embedded import SDLEmbeddedWindowBackend
    from termin.visualization.render import RenderEngine, ViewportRenderState
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
        get_window_backend: Optional[Callable[[], "WindowBackend"]] = None,
        get_sdl_backend: Optional[Callable[[], "SDLEmbeddedWindowBackend"]] = None,
        on_display_selected: Optional[Callable[["Display"], None]] = None,
        on_viewport_selected: Optional[Callable[["Viewport"], None]] = None,
        on_request_update: Optional[Callable[[], None]] = None,
        get_editor_pipeline: Optional[Callable[[], "RenderPipeline"]] = None,
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
        self._viewport_list = viewport_list_widget
        self._inspector = inspector_controller
        self._center_tabs = center_tab_widget
        self._get_scene = get_scene
        self._get_graphics = get_graphics
        self._get_window_backend = get_window_backend
        self._get_sdl_backend = get_sdl_backend
        self._on_display_selected = on_display_selected
        self._on_viewport_selected = on_viewport_selected
        self._on_request_update = on_request_update
        self._get_editor_pipeline = get_editor_pipeline

        self._displays: List["Display"] = []
        self._display_names: dict[int, str] = {}
        self._selected_display: Optional["Display"] = None
        self._selected_viewport: Optional["Viewport"] = None

        # Map display id -> (tab container widget, BackendWindow, QWindow)
        # QWindow is stored to prevent garbage collection
        self._display_tabs: dict[int, Tuple[QWidget, "BackendWindow", QWindow]] = {}

        # Map display id -> dict of viewport id -> ViewportRenderState
        self._display_render_states: dict[int, dict[int, "ViewportRenderState"]] = {}

        # Editor display ID (not serialized, created before scene)
        self._editor_display_id: Optional[int] = None

        # RenderEngine (created lazily when graphics is available)
        self._render_engine: Optional["RenderEngine"] = None

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
        self._inspector.viewport_inspector.pipeline_changed.connect(self._on_viewport_pipeline_changed)
        self._inspector.pipeline_inspector.pipeline_changed.connect(self._on_pipeline_inspector_changed)

        # Set editor pipeline getter for ViewportInspector
        if self._get_editor_pipeline is not None:
            self._inspector.viewport_inspector.set_editor_pipeline_getter(self._get_editor_pipeline)

        # Connect center tabs signal for tab switching
        if self._center_tabs is not None:
            self._center_tabs.currentChanged.connect(self._on_center_tab_changed)
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

        display_id = id(display)

        self._displays.remove(display)
        self._display_names.pop(display_id, None)
        self._viewport_list.remove_display(display)

        # Clean up tab resources
        if display_id in self._display_tabs:
            tab_container, backend_window, _qwindow = self._display_tabs.pop(display_id)
            # Close backend window
            if backend_window is not None:
                backend_window.close()

        # Clean up render states
        self._display_render_states.pop(display_id, None)

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

        # Create SDL window
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

        # Add to container layout
        layout = container.layout()
        if layout is None:
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            container.setLayout(layout)
        layout.addWidget(gl_widget)

        # Create surface and display (editor_only=True by default)
        surface = WindowRenderSurface(backend_window)
        display = Display(surface, editor_only=True)

        # Store mapping
        display_id = id(display)
        self._display_tabs[display_id] = (container, backend_window, qwindow)
        self._display_render_states[display_id] = {}
        self._editor_display_id = display_id

        # Add to displays list
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
        for display in self._displays:
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
        editor_display = self.editor_display
        if editor_display is None or not editor_display.viewports:
            return {}
        viewport = editor_display.viewports[0]
        state = self.get_viewport_state(viewport)
        if state is None:
            return {}
        return state.fbos

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
        if self._get_graphics is None or self._get_sdl_backend is None:
            return
        if self._center_tabs is None:
            return

        graphics = self._get_graphics()
        sdl_backend = self._get_sdl_backend()
        if graphics is None or sdl_backend is None:
            return

        # Generate unique name
        existing_names = set(self._display_names.values())
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

        # Create WindowRenderSurface and Display
        from termin.visualization.render.surface import WindowRenderSurface
        from termin.visualization.core.display import Display

        surface = WindowRenderSurface(backend_window)
        display = Display(surface)

        # Store mapping (include qwindow to prevent GC)
        display_id = id(display)
        self._display_tabs[display_id] = (tab_container, backend_window, qwindow)

        # Initialize render states dict for this display
        self._display_render_states[display_id] = {}

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
            pipeline: Pipeline to use, or None to use default.
        """
        display = viewport.display
        if display is None:
            return

        display_id = id(display)
        viewport_id = id(viewport)

        # Get or create viewport state
        if display_id not in self._display_render_states:
            self._display_render_states[display_id] = {}

        viewport_states = self._display_render_states[display_id]

        if viewport_id not in viewport_states:
            from termin.visualization.render import ViewportRenderState
            from termin.visualization.core.viewport import make_default_pipeline

            default_pipeline = pipeline if pipeline is not None else make_default_pipeline()
            viewport_states[viewport_id] = ViewportRenderState(pipeline=default_pipeline)
        else:
            state = viewport_states[viewport_id]
            if pipeline is not None:
                state.pipeline = pipeline
                # Clear FBO pool when pipeline changes
                state.fbos.clear()
            else:
                # Reset to default
                from termin.visualization.core.viewport import make_default_pipeline
                state.pipeline = make_default_pipeline()
                state.fbos.clear()

        self._request_update()

    # --- Center tabs management ---

    def _on_center_tab_changed(self, index: int) -> None:
        """Handle center tab widget tab change."""
        # Request redraw when switching tabs
        self._request_update()

    def _get_or_create_viewport_state(self, display_id: int, viewport: "Viewport"):
        """Get or create ViewportRenderState for a viewport."""
        from termin.visualization.render import ViewportRenderState
        from termin.visualization.core.viewport import make_default_pipeline

        viewport_states = self._display_render_states.get(display_id)
        if viewport_states is None:
            return None

        viewport_id = id(viewport)
        if viewport_id not in viewport_states:
            viewport_states[viewport_id] = ViewportRenderState(
                pipeline=make_default_pipeline()
            )

        return viewport_states[viewport_id]

    def get_viewport_state(self, viewport: "Viewport") -> Optional["ViewportRenderState"]:
        """Get ViewportRenderState for a viewport."""
        display = viewport.display
        if display is None:
            return None

        display_id = id(display)
        if display_id not in self._display_render_states:
            return None

        viewport_id = id(viewport)
        return self._display_render_states[display_id].get(viewport_id)

    def _update_center_tabs(self) -> None:
        """Update center tab widget with current displays."""
        if self._center_tabs is None:
            return

        # Keep first tab (Editor view), remove others
        while self._center_tabs.count() > 1:
            self._center_tabs.removeTab(1)

        # Add tabs for additional displays (not Editor)
        for display in self._displays:
            display_id = id(display)

            # Skip Editor display (it's already the first tab, managed externally)
            if display_id == self._editor_display_id:
                continue

            # Skip displays not in _display_tabs (legacy external displays)
            if display_id not in self._display_tabs:
                continue

            name = self._display_names.get(display_id, "Display")
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

    # --- Serialization ---

    def serialize_displays(self) -> list:
        """
        Сериализует конфигурацию всех дисплеев.

        Возвращает список дисплеев с их viewport'ами.
        """
        result = []
        for display in self._displays:
            display_id = id(display)
            name = self._display_names.get(display_id, "Display")

            # Сериализуем все viewport'ы дисплея
            viewports_data = []
            for viewport in display.viewports:
                viewports_data.append(viewport.serialize())

            result.append({
                "name": name,
                "editor_only": display.editor_only,
                "viewports": viewports_data,
            })

        return result

    def restore_displays(self, data: list, scene: "Scene") -> None:
        """
        Восстанавливает конфигурацию дисплеев из сериализованных данных.

        Args:
            data: Сериализованные данные дисплеев
            scene: Текущая сцена для поиска камер
        """
        from termin.visualization.core.camera import CameraComponent

        # Удаляем все дополнительные дисплеи (кроме Editor)
        additional_displays = [
            d for d in self._displays
            if id(d) != self._editor_display_id
        ]
        for display in additional_displays:
            self.remove_display(display)

        # Находим Editor display по _editor_display_id
        editor_display = self.editor_display

        # Индекс для сопоставления данных с первым дисплеем
        first_display_restored = False

        for display_data in data:
            # Обратная совместимость: is_editor → editor_only
            editor_only = display_data.get("editor_only", display_data.get("is_editor", False))
            name = display_data.get("name", "Display")
            viewports_data = display_data.get("viewports", [])

            # Первый дисплей из данных восстанавливаем в editor_display
            if not first_display_restored and editor_display is not None:
                first_display_restored = True

                # Обновляем имя и editor_only флаг
                self.set_display_name(editor_display, name)
                editor_display.editor_only = editor_only

                # Очищаем существующие viewport'ы (кроме первого, он управляется EditorViewportFeatures)
                while len(editor_display.viewports) > 1:
                    vp = editor_display.viewports[-1]
                    editor_display.remove_viewport(vp)

                # Восстанавливаем свойства первого viewport'а если есть данные
                if viewports_data and editor_display.viewports:
                    vp_data = viewports_data[0]
                    main_vp = editor_display.viewports[0]
                    main_vp.rect = tuple(vp_data.get("rect", [0.0, 0.0, 1.0, 1.0]))
                    main_vp.depth = vp_data.get("depth", 0)
                    # Камеру Editor viewport'а не меняем - она управляется EditorCameraManager
            else:
                # Запоминаем количество дисплеев до создания
                count_before = len(self._displays)

                # Создаём дополнительный дисплей
                self._on_add_display_requested()

                # Проверяем, что дисплей был создан
                if len(self._displays) <= count_before:
                    continue

                # Берём последний добавленный дисплей
                new_display = self._displays[-1]
                self.set_display_name(new_display, name)
                new_display.editor_only = editor_only

                # Создаём viewport'ы
                for vp_data in viewports_data:
                    camera_entity_name = vp_data.get("camera_entity")
                    rect = tuple(vp_data.get("rect", [0.0, 0.0, 1.0, 1.0]))
                    depth = vp_data.get("depth", 0)

                    # Ищем камеру по имени сущности
                    camera = None
                    for entity in scene.entities:
                        if entity.name == camera_entity_name:
                            cam = entity.get_component(CameraComponent)
                            if cam is not None:
                                camera = cam
                                break

                    if camera is not None:
                        viewport = new_display.create_viewport(
                            scene=scene,
                            camera=camera,
                            rect=rect,
                        )
                        viewport.depth = depth

        # Обновляем UI
        self._viewport_list.refresh()
        self._update_center_tabs()
        self._request_update()

    def render_additional_displays(self) -> None:
        """Render all additional displays excluding editor (legacy method)."""
        self._render_displays(skip_editor=True)

    def render_all_displays(self) -> None:
        """Render all displays including editor (unified render loop)."""
        self._render_displays(skip_editor=False)

    def _render_displays(self, skip_editor: bool = False) -> None:
        """
        Internal method to render displays.

        Args:
            skip_editor: If True, skip editor display (legacy mode).
        """
        if self._get_graphics is None:
            return

        graphics = self._get_graphics()
        if graphics is None:
            return

        # Lazy creation of RenderEngine
        if self._render_engine is None:
            from termin.visualization.render import RenderEngine
            self._render_engine = RenderEngine(graphics)

        render_engine = self._render_engine

        from termin.visualization.render import RenderView

        for display in self._displays:
            display_id = id(display)

            # Skip editor display if requested (legacy mode)
            if skip_editor and display_id == self._editor_display_id:
                continue

            # All displays must be in _display_tabs now
            if display_id not in self._display_tabs:
                continue

            # Get the backend window for this display
            _tab_container, backend_window, _qwindow = self._display_tabs[display_id]
            if backend_window is None:
                continue

            # Make SDL context current
            backend_window.make_current()

            # Check resize
            backend_window.check_resize()

            graphics.ensure_ready()

            # Get surface from display
            surface = display.surface
            if surface is None:
                continue

            # Collect views and states
            if display_id not in self._display_render_states:
                continue

            views_and_states = []
            sorted_viewports = sorted(display.viewports, key=lambda v: v.depth)

            for viewport in sorted_viewports:
                state = self._get_or_create_viewport_state(display_id, viewport)
                if state is None:
                    continue
                view = RenderView(
                    scene=viewport.scene,
                    camera=viewport.camera,
                    rect=viewport.rect,
                    canvas=viewport.canvas,
                )
                views_and_states.append((view, state))

            # Render
            if views_and_states:
                render_engine.render_views(
                    surface=surface,
                    views=views_and_states,
                    present=False,
                )
            else:
                # No viewports - just clear the screen
                from OpenGL import GL as gl
                gl.glClearColor(0.1, 0.1, 0.1, 1.0)
                gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

            backend_window.swap_buffers()
            backend_window.clear_render_flag()
