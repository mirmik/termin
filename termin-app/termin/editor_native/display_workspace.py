"""Native tabbed workspace owning editor and runtime display surfaces."""

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
    surface: object
    input_manager: object


class NativeDisplayWorkspace:
    """Own the tab-to-display mapping and every display surface lifetime."""

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
    ) -> None:
        self.document = document
        self.tabs = tabs
        self.root = root
        self.editor_page = editor_page
        self.editor_viewport = editor_viewport
        self.device = device
        self.rendering_manager = rendering_manager
        self.request_render = request_render
        self.on_display_selected: Callable[[object], None] | None = None
        self._pages: list[NativeDisplayPage] = []
        self._closed = False
        weak_owner = weakref.ref(self)

        def selection_changed(index: int) -> None:
            owner = weak_owner()
            if owner is not None:
                owner._on_tab_selected(index)

        self._selection_connection = tabs.connect_selection_changed(selection_changed)

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
        )

    @property
    def displays(self) -> tuple[object, ...]:
        return (self.editor_viewport.display, *(page.display for page in self._pages))

    def contains_display(self, display: object) -> bool:
        pointer = self._display_pointer(display)
        return any(self._display_pointer(candidate) == pointer for candidate in self.displays)

    def is_editor_display(self, display: object) -> bool:
        return self._display_pointer(display) == self._display_pointer(self.editor_viewport.display)

    def create_display(self, name: str | None = None) -> object:
        """Create, register and project one runtime display into a native tab."""

        self._require_open()
        from termin.display import BasicDisplayInputManager, Display, FBOSurface

        display_name = name or self._next_display_name()
        surface = FBOSurface(self.device, 800, 600)
        display = None
        input_manager = None
        widget = None
        registered = False
        tab_added = False
        try:
            if not surface.is_valid():
                raise RuntimeError("native display FBO surface is invalid")
            display = Display(surface=surface, name=display_name)
            input_manager = BasicDisplayInputManager(display.tc_display_ptr)
            surface.set_input_manager(input_manager.tc_input_manager_ptr)
            widget = self.document.create_viewport3d()
            widget.widget.stable_id = f"editor.display-workspace.display-{display.tc_display_ptr}"
            widget.widget.preferred_size = Size(800.0, 600.0)
            widget.set_surface_host(surface)
            self.rendering_manager.add_display(display, display_name)
            registered = True
            self.tabs.add_page(display_name, widget.widget)
            tab_added = True
            page = NativeDisplayPage(
                display=display,
                widget=widget,
                root=widget.widget,
                surface=surface,
                input_manager=input_manager,
            )
            self._pages.append(page)
            self.tabs.selected_index = self.tabs.page_count - 1
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
            surface.set_input_manager(0)
            surface.close()
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
        self._close_page(page)
        self.request_render()
        return True

    def select_display(self, display: object) -> bool:
        pointer = self._display_pointer(display)
        if pointer == self._display_pointer(self.editor_viewport.display):
            self.tabs.selected_index = 0
            return True
        page_index = self._page_index(display)
        if page_index is None:
            return False
        self.tabs.selected_index = page_index + 1
        return True

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
        cleanup("input detach", lambda: page.surface.set_input_manager(0))
        cleanup("input manager close", page.input_manager.close)
        cleanup("rendering manager removal", lambda: self.rendering_manager.remove_display(page.display))
        cleanup("display destroy", page.display.destroy)
        cleanup("surface close", page.surface.close)
        cleanup("widget destroy", lambda: self.document.destroy_widget_recursive(page.root.handle))
        if first_error is not None:
            raise RuntimeError("native display page cleanup failed") from first_error

    def _on_tab_selected(self, index: int) -> None:
        if self._closed:
            return
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

    def _next_display_name(self) -> str:
        existing = {display.name for display in self.displays}
        index = 0
        while f"Display {index}" in existing:
            index += 1
        return f"Display {index}"

    def _page_index(self, display: object) -> int | None:
        pointer = self._display_pointer(display)
        for index, page in enumerate(self._pages):
            if self._display_pointer(page.display) == pointer:
                return index
        return None

    @staticmethod
    def _display_pointer(display: object) -> int:
        return int(display.tc_display_ptr)

    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeError("native display workspace is closed")


__all__ = ["NativeDisplayPage", "NativeDisplayWorkspace"]
