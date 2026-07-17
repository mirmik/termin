from pathlib import Path

import pytest

from termin.editor_core.project_browser_model import ProjectBrowserController
from termin.editor_native import build_native_project_browser, resolve_native_ui_font
from termin.gui_native import (
    Document,
    DrawList,
    DrawListRenderer,
    PaintContext,
    PointerEvent,
    PointerEventType,
    Rect,
)


def _project(root: Path, file_count: int = 20) -> None:
    (root / "Assets" / "Nested").mkdir(parents=True)
    (root / "Scripts").mkdir()
    for index in range(file_count):
        (root / f"asset-{index:04d}.scene").write_text("{}", encoding="utf-8")
    (root / "Assets" / "mesh.stl").write_text("solid", encoding="utf-8")


def _bind_font(document: Document) -> DrawListRenderer:
    renderer = DrawListRenderer()
    assert renderer.set_default_font_path(str(resolve_native_ui_font()), 15)
    renderer.bind_text_measurer(document)
    return renderer


def test_native_project_browser_tree_grid_navigation_context_and_virtualization(tmp_path: Path):
    _project(tmp_path, file_count=2_000)
    document = Document()
    renderer = _bind_font(document)
    clipboard = []
    selected = []
    activated = []
    controller = ProjectBrowserController(
        on_file_selected=selected.append,
        on_file_activated=activated.append,
        copy_text=clipboard.append,
    )
    renders = []
    drops = []
    browser = build_native_project_browser(
        document,
        controller,
        viewport=lambda: Rect(0.0, 0.0, 900.0, 600.0),
        request_render=lambda: renders.append(True),
        file_drop_handler=lambda path, x, y, modifiers: drops.append(
            (path, x, y, modifiers)
        ) or True,
    )
    assert document.add_root(browser.root.handle)
    browser.set_root(tmp_path)
    document.layout_roots(Rect(0.0, 0.0, 900.0, 600.0))

    assert browser.tree_model.node_count >= 4
    assert browser.file_model.item_count == 2_002
    assert next(item.icon for item in browser.file_model.items if item.text == "Assets") == "folder"
    assert next(item.icon for item in browser.file_model.items if item.text == "asset-0000.scene") == "file"
    assert browser.file_grid.visible_range[1] < 100
    assert [command.data.label for command in browser.breadcrumb_model.commands] == [tmp_path.name]
    assert not browser.breadcrumb_model.commands[0].data.enabled
    assert "2000 files" in browser.status_bar.text
    tree_bounds = browser.tree_widget.widget.bounds
    breadcrumb_bounds = browser.breadcrumb.widget.bounds
    grid_bounds = browser.file_grid.widget.bounds
    assert tree_bounds.y == pytest.approx(browser.root.bounds.y + 4.0)
    assert breadcrumb_bounds.x == pytest.approx(grid_bounds.x)
    assert breadcrumb_bounds.width == pytest.approx(grid_bounds.width)
    assert tree_bounds.y == pytest.approx(breadcrumb_bounds.y)
    assert grid_bounds.y >= breadcrumb_bounds.y + breadcrumb_bounds.height
    initial_tree_width = browser.tree_widget.widget.bounds.width
    browser.content_splitter.split_fraction = 0.32
    document.layout_roots(Rect(0.0, 0.0, 900.0, 600.0))
    assert browser.tree_widget.widget.bounds.width > initial_tree_width
    assert browser.file_grid.widget.bounds.x > browser.tree_widget.widget.bounds.x
    browser.content_splitter.split_fraction = 0.085
    document.layout_roots(Rect(0.0, 0.0, 2048.0, 600.0))
    assert browser.tree_widget.widget.bounds.width == pytest.approx(173.0, abs=3.0)

    assets = next(
        index
        for index, item in enumerate(browser.file_model.items)
        if item.text == "Assets"
    )
    browser.activate_file(assets)
    assert controller.selected_directory == tmp_path / "Assets"
    assert [command.data.label for command in browser.breadcrumb_model.commands] == [
        tmp_path.name,
        "›  Assets",
    ]
    assert browser.breadcrumb_model.commands[0].data.enabled
    assert not browser.breadcrumb_model.commands[1].data.enabled
    assert browser.file_model.item_count == 2

    nested = next(
        index for index, item in enumerate(browser.file_model.items) if item.text == "Nested"
    )
    browser.activate_file(nested)
    document.layout_roots(Rect(0.0, 0.0, 900.0, 600.0))
    assert controller.selected_directory == tmp_path / "Assets" / "Nested"
    assets_crumb = browser.breadcrumb.item_rects[1]
    pointer = PointerEvent()
    pointer.type = PointerEventType.Down
    pointer.x = assets_crumb.x + 4.0
    pointer.y = assets_crumb.y + 4.0
    assert document.dispatch_pointer_event(pointer)
    pointer.type = PointerEventType.Up
    assert document.dispatch_pointer_event(pointer)
    assert controller.selected_directory == tmp_path / "Assets"
    assert browser.breadcrumb_model.command_count == 2

    mesh = next(
        index for index, item in enumerate(browser.file_model.items) if item.text == "mesh.stl"
    )
    browser.select_file(mesh)
    browser.activate_file(mesh)
    assert selected == [tmp_path / "Assets" / "mesh.stl"]
    assert activated == [tmp_path / "Assets" / "mesh.stl"]
    mesh_rect = browser.file_grid.item_rect(mesh)
    pointer = PointerEvent()
    pointer.type = PointerEventType.Down
    pointer.x = mesh_rect.x + 4.0
    pointer.y = mesh_rect.y + 4.0
    assert document.dispatch_pointer_event(pointer)
    pointer.type = PointerEventType.Move
    pointer.x = 20.0
    pointer.y = 20.0
    assert document.dispatch_pointer_event(pointer)
    pointer.type = PointerEventType.Up
    assert document.dispatch_pointer_event(pointer)
    assert drops == [(str(tmp_path / "Assets" / "mesh.stl"), 20.0, 20.0, 0)]
    browser.show_file_context(mesh, 300.0, 180.0)
    assert browser.context_menu.open
    browser.execute_context_action("copy-path")
    assert clipboard == [str((tmp_path / "Assets" / "mesh.stl").resolve())]

    draw_list = DrawList()
    document.paint(PaintContext(draw_list))
    assert draw_list.command_count > 20
    assert renders
    renderer.release_gpu()
