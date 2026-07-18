from __future__ import annotations

import gc
from types import SimpleNamespace
import weakref

from termin.editor_native.display_workspace import NativeDisplayWorkspace
from termin.gui_native import Document


class _Surface:
    instances = []

    def __init__(self, device, width: int, height: int) -> None:
        self.device = device
        self.size = (width, height)
        self.input_manager = None
        self.closed = False
        self.__class__.instances.append(self)

    def is_valid(self) -> bool:
        return not self.closed

    def get_tgfx_color_tex_id(self) -> int:
        return 17

    def framebuffer_size(self) -> tuple[int, int]:
        return self.size

    def resize(self, width: int, height: int) -> bool:
        self.size = (width, height)
        return True

    def dispatch_pointer_move(self, _x: float, _y: float) -> bool:
        return True

    def dispatch_pointer_button(
        self,
        _button: int,
        _action: int,
        _modifiers: int,
        _click_count: int,
    ) -> bool:
        return True

    def dispatch_scroll(self, _x: float, _y: float, _modifiers: int) -> bool:
        return True

    def dispatch_key(self, _key: int, _scancode: int, _action: int, _modifiers: int) -> bool:
        return True

    def dispatch_text(self, _codepoint: int) -> bool:
        return True

    def set_input_manager(self, pointer: int) -> None:
        self.input_manager = pointer

    def close(self) -> None:
        self.closed = True


class _Display:
    next_pointer = 10

    def __init__(self, *, surface, name: str) -> None:
        self.surface = surface
        self.name = name
        self.tc_display_ptr = self.__class__.next_pointer
        self.__class__.next_pointer += 1
        self.destroyed = False
        self.enabled = True
        self.viewports = []

    def add_viewport(self, viewport) -> None:
        self.viewports.append(viewport)

    def remove_viewport(self, viewport) -> None:
        self.viewports.remove(viewport)

    def destroy(self) -> None:
        self.destroyed = True


class _InputManager:
    instances = []

    def __init__(self, display_pointer: int) -> None:
        self.display_pointer = display_pointer
        self.tc_input_manager_ptr = display_pointer + 100
        self.added = []
        self.removed = []
        self.closed = False
        self.__class__.instances.append(self)

    def add_viewport(self, index: int, generation: int) -> bool:
        self.added.append((index, generation))
        return True

    def remove_viewport(self, index: int, generation: int) -> bool:
        self.removed.append((index, generation))
        return True

    def close(self) -> None:
        self.closed = True


class _RenderingManager:
    def __init__(self) -> None:
        self.added = []
        self.removed = []
        self.registered_viewports = []
        self.unregistered_viewports = []

    def add_display(self, display, name: str) -> None:
        self.added.append((display, name))

    def remove_display(self, display) -> None:
        self.removed.append(display)

    def register_viewport_attachment(self, display, viewport) -> bool:
        self.registered_viewports.append((display, viewport))
        return True

    def unregister_viewport_attachment(self, viewport) -> None:
        self.unregistered_viewports.append(viewport)


def test_native_display_workspace_owns_tabs_input_and_display_cleanup(monkeypatch):
    import termin.display
    import termin.editor_native.display_workspace as workspace_module

    document = Document()
    parent = document.create_vstack("workspace-parent")
    editor_display = SimpleNamespace(name="Editor", tc_display_ptr=1)
    editor_runtime = SimpleNamespace(
        display=editor_display,
        camera=object(),
        attachment=SimpleNamespace(
            viewport=SimpleNamespace(_viewport_handle=lambda: (1, 1)),
        ),
        closed=False,
    )

    def close_editor() -> None:
        editor_runtime.closed = True

    editor_runtime.close = close_editor

    def create_editor(document, parent, **_kwargs):
        parent.add_stretch_child(document.create_panel("editor-viewport-placeholder"))
        return editor_runtime

    monkeypatch.setattr(workspace_module.NativeEditorViewport, "create", create_editor)
    monkeypatch.setattr(termin.display, "FBOSurface", _Surface)
    monkeypatch.setattr(termin.display, "Display", _Display)
    monkeypatch.setattr(termin.display, "BasicDisplayInputManager", _InputManager)
    _Surface.instances.clear()
    _InputManager.instances.clear()
    _Display.next_pointer = 10
    manager = _RenderingManager()
    renders = []
    workspace = NativeDisplayWorkspace.create(
        document,
        parent,
        device="device",
        rendering_manager=manager,
        scene="scene",
        request_render=lambda: renders.append(True),
    )

    assert workspace.tabs.page_count == 1
    assert editor_display.enabled is True
    display = workspace.create_display()
    assert display.name == "Display 0"
    assert workspace.tabs.page_count == 2
    # Display factories are also used during scene restoration; creating a
    # display must not move focus away from the editor page.
    assert workspace.tabs.selected_index == 0
    assert display.enabled is False
    assert manager.added == [(display, "Display 0")]
    assert _Surface.instances[0].input_manager == display.tc_display_ptr + 100

    selections = []
    workspace.on_display_selected = selections.append
    assert workspace.select_display(editor_display)
    assert workspace.select_display(display)
    assert selections == [display]
    assert editor_display.enabled is False
    assert display.enabled is True

    second_display = workspace.create_display()
    assert workspace.tabs.selected_index == 1
    assert second_display.enabled is False
    workspace.set_render_only_active_display(False)
    assert all(candidate.enabled for candidate in workspace.displays)
    workspace.set_render_only_active_display(True)
    assert editor_display.enabled is False
    assert display.enabled is True
    assert second_display.enabled is False
    viewport = SimpleNamespace(_viewport_handle=lambda: (7, 3))
    display.add_viewport(viewport)
    workspace.configure_viewport_input(display, viewport)
    assert workspace.can_move_viewport(viewport)
    workspace.move_viewport(viewport, display, second_display)
    assert manager.unregistered_viewports == [viewport]
    assert manager.registered_viewports == [(second_display, viewport)]
    assert viewport not in display.viewports
    assert viewport in second_display.viewports
    assert _InputManager.instances[0].added == [(7, 3)]
    assert _InputManager.instances[0].removed == [(7, 3)]
    assert _InputManager.instances[1].added == [(7, 3)]

    assert workspace.remove_display(display)
    assert workspace.remove_display(second_display)
    assert workspace.tabs.page_count == 1
    assert manager.removed == [display, second_display]
    assert display.destroyed
    assert second_display.destroyed
    assert all(manager.closed for manager in _InputManager.instances)
    assert all(surface.input_manager == 0 for surface in _Surface.instances)
    assert all(surface.closed for surface in _Surface.instances)

    workspace.close()
    workspace.close()
    assert editor_runtime.closed
    assert renders
    workspace_ref = weakref.ref(workspace)
    del workspace
    gc.collect()
    assert workspace_ref() is None
