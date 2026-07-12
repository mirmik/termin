from __future__ import annotations

from types import SimpleNamespace

import pytest

from termin.editor_native.project_extensions import NativeProjectEditorContext
from termin.gui_native import CommandData, CommandModel


class FakeMenuBar:
    def __init__(self) -> None:
        self.entries = []
        self.callbacks = []

    def connect_activated(self, callback):
        self.callbacks.append(callback)
        return callback

    def activate(self, menu_index: int, command_id: int, command) -> None:
        for callback in tuple(self.callbacks):
            callback(menu_index, command_id, command)


class FakeExtensionContext:
    def __init__(self) -> None:
        self.click_interceptors = []
        self.overlay_drawers = []
        self.active_tools = 0
        self.tool_panels = {}
        self.shown_tools = []

    def add_viewport_click_interceptor(self, callback) -> None:
        self.click_interceptors.append(callback)

    def remove_viewport_click_interceptor(self, callback) -> None:
        self.click_interceptors.remove(callback)

    def add_viewport_overlay_drawer(self, callback) -> None:
        self.overlay_drawers.append(callback)

    def remove_viewport_overlay_drawer(self, callback) -> None:
        self.overlay_drawers.remove(callback)

    def begin_viewport_tool(self) -> None:
        self.active_tools += 1

    def end_viewport_tool(self) -> None:
        self.active_tools -= 1


def make_context():
    menu_bar = FakeMenuBar()
    extension_context = FakeExtensionContext()
    renders = []
    selected = [SimpleNamespace(name="selected")]
    context = NativeProjectEditorContext(
        document=object(),
        menu_bar=menu_bar,
        dialog_service=object(),
        viewport=lambda: object(),
        request_render=lambda: renders.append(True),
        extension_context=extension_context,
        get_scene=lambda: "scene",
        get_selected_entity=lambda: selected[0],
        select_scene_object=lambda entity: selected.__setitem__(0, entity),
        register_tool_inspector=lambda key, panel: extension_context.tool_panels.__setitem__(key, panel),
        unregister_tool_inspector=lambda key: extension_context.tool_panels.pop(key, None),
        show_tool_inspector=lambda key, label: extension_context.shown_tools.append((key, label)),
    )
    return context, menu_bar, extension_context, renders, selected


def test_native_project_context_registers_and_routes_project_menu() -> None:
    context, menu_bar, _extension_context, renders, _selected = make_context()
    model = CommandModel()
    command_id = model.append(CommandData("action", "Action"))
    activated = []

    menu_index = context.add_project_menu(
        "project.chronosquad",
        "ChronoSquad",
        model,
        lambda selected_id, command: activated.append((selected_id, command.data.stable_id)),
    )

    assert menu_index == 0
    assert menu_bar.entries[0].stable_id == "project.chronosquad"
    menu_bar.activate(menu_index, command_id, model.command(command_id))
    assert activated == [(command_id, "action")]
    assert renders == [True]
    with pytest.raises(ValueError, match="already registered"):
        context.add_project_menu("project.chronosquad", "Duplicate", model, lambda *_: None)


def test_native_project_context_delegates_viewport_tools_and_selection() -> None:
    context, _menu_bar, extension_context, renders, selected = make_context()
    first = lambda _event: False
    second = lambda _event: True

    context.set_viewport_click_interceptor(first)
    context.set_viewport_click_interceptor(second)
    assert extension_context.click_interceptors == [second]
    context.add_viewport_overlay_drawer(first)
    context.begin_viewport_tool()
    assert extension_context.overlay_drawers == [first]
    assert extension_context.active_tools == 1
    context.end_viewport_tool()
    context.select_entity("next")
    context.request_viewport_update()

    assert extension_context.active_tools == 0
    assert selected == ["next"]
    assert context.scene == "scene"
    assert context.selected_entity == "next"


def test_native_project_context_delegates_tool_inspector_lifecycle() -> None:
    context, _menu_bar, extension_context, renders, _selected = make_context()
    panel = object()

    context.register_tool_inspector_panel("terrain", panel)
    context.show_tool_inspector_panel("terrain", "Terrain")
    assert extension_context.tool_panels == {"terrain": panel}
    assert extension_context.shown_tools == [("terrain", "Terrain")]
    assert renders == [True]
    assert context.unregister_tool_inspector_panel("terrain") is panel
    assert renders == [True]
