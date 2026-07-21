"""Native tabbed workspace owning editor and runtime displays."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
import weakref

from termin.gui_native import Document, Size, WidgetRef

from .editor_viewport import NativeEditorViewport


_logger = logging.getLogger(__name__)


@dataclass
class NativeDisplayPage:
    """One non-editor display page and its explicit native resources."""

    display: object
    widget: object
    root: WidgetRef
    input_manager: object


class NativeDisplayWorkspace:
    """Own the tab-to-display mapping and explicit display lifetime."""

    def __init__(
        self,
        *,
        document: Document,
        tabs,
        root: WidgetRef,
        editor_page: WidgetRef,
        editor_viewport: NativeEditorViewport,
        device,
        rendering_manager,
        request_render: Callable[[], None],
        render_only_active_display: bool = True,
    ) -> None:
        self.document = document
        self.tabs = tabs
        self.root = root
        self.editor_page = editor_page
        self.editor_viewport = editor_viewport
        self.device = device
        self.rendering_manager = rendering_manager
        self.request_render = request_render
        self._render_only_active_display = bool(render_only_active_display)
        self.on_display_selected: Callable[[object], None] | None = None
        self._pages: list[NativeDisplayPage] = []
        self._closed = False
        weak_owner = weakref.ref(self)

        def selection_changed(index: int) -> None:
            owner = weak_owner()
            if owner is not None:
                owner._on_tab_selected(index)

        self._selection_connection = tabs.connect_selection_changed(selection_changed)
        self._sync_display_rendering()

    @classmethod
    def create(
        cls,
        document: Document,
        parent: WidgetRef,
        *,
        device,
        rendering_manager,
        scene,
        request_render: Callable[[], None],
        render_only_active_display: bool = True,
    ) -> "NativeDisplayWorkspace":
        tabs = document.create_tab_view("native-display-workspace")
        root = tabs.widget
        root.stable_id = "editor.display-workspace"
        root.preferred_size = Size(800.0, 600.0)
        parent.add_stretch_child(root)
        editor_page = document.create_vstack("native-editor-display-page")
        editor_page.stable_id = "editor.display-workspace.editor"
        tabs.add_page("Editor", editor_page)
        try:
            editor_viewport = NativeEditorViewport.create(
                document,
                editor_page,
                device=device,
                rendering_manager=rendering_manager,
                scene=scene,
                request_render=request_render,
            )
        except Exception:
            _logger.exception("Native display workspace failed to create its editor page")
            document.destroy_widget_recursive(root.handle)
            raise
        return cls(
            document=document,
            tabs=tabs,
            root=root,
            editor_page=editor_page,
            editor_viewport=editor_viewport,
            device=device,
            rendering_manager=rendering_manager,
            request_render=request_render,
            render_only_active_display=render_only_active_display,
        )

    @property
    def displays(self) -> tuple[object, ...]:
        return (self.editor_viewport.display, *(page.display for page in self._pages))

    @property
    def editor_display(self):
        return self.editor_viewport.display

    def contains_display(self, display: object) -> bool:
        handle = self._display_handle(display)
        return any(self._display_handle(candidate) == handle for candidate in self.displays)

    def is_editor_display(self, display: object) -> bool:
        return self._display_handle(display) == self._display_handle(self.editor_viewport.display)

    def create_display(self, name: str | None = None) -> object:
        """Create, register and project one runtime display into a native tab."""

        self._require_open()
        from termin.display import BasicDisplayInputManager, Display

        display_name = name or self._next_display_name()
        display = None
        input_manager = None
        widget = None
        registered = False
        tab_added = False
        try:
            display = Display.offscreen(self.device, 800, 600, name=display_name)
            input_manager = BasicDisplayInputManager(display.handle)
            widget = self.document.create_viewport3d()
            widget.widget.stable_id = (
                f"editor.display-workspace.display-{display.index}-{display.generation}"
            )
            widget.widget.preferred_size = Size(800.0, 600.0)
            widget.set_surface_host(display)
            self.rendering_manager.add_display(display, display_name)
            registered = True
            self.tabs.add_page(display_name, widget.widget)
            tab_added = True
            page = NativeDisplayPage(
                display=display,
                widget=widget,
                root=widget.widget,
                input_manager=input_manager,
            )
            self._pages.append(page)
            self._sync_display_rendering()
            # Displays are also created by RenderingManager while a scene is
            # restored or a game-scene is attached. Factory side effects must
            # not steal the user's active tab in either case. Explicit editor
            # commands select their newly-created display at the call site.
            self.request_render()
            return display
        except Exception:
            _logger.exception("Native display workspace failed to create '%s'", display_name)
            if tab_added:
                self.tabs.remove_page(self.tabs.page_count - 1)
            if widget is not None:
                widget.detach_surface()
                self.document.destroy_widget_recursive(widget.handle)
            if registered and display is not None:
                self.rendering_manager.remove_display(display)
            if input_manager is not None:
                input_manager.close()
            if display is not None:
                display.destroy()
            raise

    def remove_display(self, display: object) -> bool:
        """Remove a runtime display and release its tab, input and GPU resources."""

        self._require_open()
        if self.is_editor_display(display):
            raise ValueError("the editor display is owned by the workspace")
        page_index = self._page_index(display)
        if page_index is None:
            _logger.error("Native display workspace cannot remove an unknown display")
            return False
        page = self._pages[page_index]
        tab_index = page_index + 1
        if not self.tabs.remove_page(tab_index):
            raise RuntimeError("native display workspace failed to remove its display tab")
        self._pages.pop(page_index)
        self._sync_display_rendering()
        self._close_page(page)
        self.request_render()
        return True

    def select_display(self, display: object) -> bool:
        handle = self._display_handle(display)
        if handle == self._display_handle(self.editor_viewport.display):
            self.tabs.selected_index = 0
            return True
        page_index = self._page_index(display)
        if page_index is None:
            return False
        self.tabs.selected_index = page_index + 1
        return True

    @property
    def render_only_active_display(self) -> bool:
        return self._render_only_active_display

    def set_render_only_active_display(self, enabled: bool) -> None:
        """Apply the transient editor rendering policy to every display tab."""

        enabled = bool(enabled)
        if self._render_only_active_display == enabled:
            return
        self._render_only_active_display = enabled
        self._sync_display_rendering()
        self.request_render()

    def configure_viewport_input(self, display: object, viewport: object) -> None:
        """Attach simple scene input routing for a runtime viewport."""

        page_index = self._page_index(display)
        if page_index is None:
            if self.is_editor_display(display):
                return
            raise ValueError("viewport display is not owned by the native workspace")
        index, generation = viewport._viewport_handle()
        if not self._pages[page_index].input_manager.add_viewport(index, generation):
            raise RuntimeError("failed to create native input manager for viewport")

    def release_viewport_input(self, display: object, viewport: object) -> None:
        page_index = self._page_index(display)
        if page_index is None:
            return
        index, generation = viewport._viewport_handle()
        self._pages[page_index].input_manager.remove_viewport(index, generation)

    def can_move_viewport(self, viewport: object) -> bool:
        """Return whether a viewport uses a movable runtime-display input route."""

        editor_viewport = self.editor_viewport.attachment.viewport
        return (
            editor_viewport is not None
            and viewport._viewport_handle() != editor_viewport._viewport_handle()
        )

    def move_viewport(self, viewport: object, source: object, target: object) -> None:
        """Move one runtime viewport while preserving its input-manager ownership."""

        self._require_open()
        if not self.can_move_viewport(viewport):
            _logger.error("Native display workspace cannot move the editor-owned viewport")
            raise ValueError("editor-owned viewport cannot move between displays")
        if self.is_editor_display(source) or self.is_editor_display(target):
            _logger.error("Native display workspace cannot attach runtime viewports to editor display")
            raise ValueError("runtime viewports cannot move to or from the editor display")
        if source is target:
            return

        self.release_viewport_input(source, viewport)
        self.rendering_manager.unregister_viewport_attachment(viewport)
        source.remove_viewport(viewport)
        try:
            target.add_viewport(viewport)
            if not self.rendering_manager.register_viewport_attachment(target, viewport):
                raise RuntimeError("failed to register moved viewport attachment")
            self.configure_viewport_input(target, viewport)
        except Exception:
            _logger.exception("Native display workspace failed to move viewport; restoring source")
            try:
                self.rendering_manager.unregister_viewport_attachment(viewport)
                target.remove_viewport(viewport)
                source.add_viewport(viewport)
                if not self.rendering_manager.register_viewport_attachment(source, viewport):
                    raise RuntimeError("failed to restore viewport attachment")
                self.configure_viewport_input(source, viewport)
            except Exception:
                _logger.exception("Native display workspace failed to restore viewport after move")
            raise

    def set_display_title(self, display: object, title: str) -> None:
        normalized = title.strip()
        if not normalized:
            raise ValueError("display title cannot be empty")
        if self.is_editor_display(display):
            tab_index = 0
        else:
            page_index = self._page_index(display)
            if page_index is None:
                raise ValueError("display is not owned by the native workspace")
            tab_index = page_index + 1
        display.name = normalized
        self.tabs.set_page_title(tab_index, normalized)
        self.request_render()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        first_error: BaseException | None = None
        while self._pages:
            page = self._pages.pop()
            tab_index = self.tabs.page_count - 1
            if not self.tabs.remove_page(tab_index):
                _logger.error("Native display workspace failed to detach a display tab at shutdown")
            try:
                self._close_page(page)
            except Exception as error:
                _logger.exception("Native display workspace page shutdown failed")
                if first_error is None:
                    first_error = error
        try:
            self.editor_viewport.close()
        except Exception as error:
            _logger.exception("Native display workspace editor page shutdown failed")
            if first_error is None:
                first_error = error
        if first_error is not None:
            raise RuntimeError("native display workspace shutdown failed") from first_error

    def _close_page(self, page: NativeDisplayPage) -> None:
        first_error: BaseException | None = None

        def cleanup(label: str, callback: Callable[[], None]) -> None:
            nonlocal first_error
            try:
                callback()
            except Exception as error:
                _logger.exception("Native display page cleanup failed during %s", label)
                if first_error is None:
                    first_error = error

        cleanup("surface detach", page.widget.detach_surface)
        cleanup("input manager close", page.input_manager.close)
        cleanup("rendering manager removal", lambda: self.rendering_manager.remove_display(page.display))
        cleanup("display destroy", page.display.destroy)
        cleanup("widget destroy", lambda: self.document.destroy_widget_recursive(page.root.handle))
        if first_error is not None:
            raise RuntimeError("native display page cleanup failed") from first_error

    def _on_tab_selected(self, index: int) -> None:
        if self._closed:
            return
        self._sync_display_rendering()
        if index == 0:
            display = self.editor_viewport.display
        elif index - 1 < len(self._pages):
            display = self._pages[index - 1].display
        else:
            _logger.error("Native display workspace selected an unmapped tab index %d", index)
            return
        if self.on_display_selected is not None:
            self.on_display_selected(display)
        self.request_render()

    def _sync_display_rendering(self) -> None:
        """Project tab visibility into the display's transient enable flag."""

        selected = self.tabs.selected_index
        for index, display in enumerate(self.displays):
            display.enabled = (
                not self._render_only_active_display
                or index == selected
            )

    def _next_display_name(self) -> str:
        existing = {display.name for display in self.displays}
        index = 0
        while f"Display {index}" in existing:
            index += 1
        return f"Display {index}"

    def _page_index(self, display: object) -> int | None:
        handle = self._display_handle(display)
        for index, page in enumerate(self._pages):
            if self._display_handle(page.display) == handle:
                return index
        return None

    @staticmethod
    def _display_handle(display: object) -> tuple[int, int]:
        return display.handle

    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeError("native display workspace is closed")


__all__ = ["NativeDisplayPage", "NativeDisplayWorkspace"]
