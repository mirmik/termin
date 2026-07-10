from pathlib import Path

from termin.editor_core.project_browser_model import ProjectBrowserController
from termin.editor_native import build_native_project_browser, resolve_native_ui_font
from termin.gui_native import Document, DrawList, DrawListRenderer, PaintContext, Rect


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
    browser = build_native_project_browser(
        document,
        controller,
        viewport=lambda: Rect(0.0, 0.0, 900.0, 600.0),
        request_render=lambda: renders.append(True),
    )
    assert document.add_root(browser.root.handle)
    browser.set_root(tmp_path)
    document.layout_roots(Rect(0.0, 0.0, 900.0, 600.0))

    assert browser.tree_model.node_count >= 4
    assert browser.file_model.item_count == 2_002
    assert browser.file_grid.visible_range[1] < 100
    assert browser.breadcrumb.text == tmp_path.name
    assert "2000 files" in browser.status_bar.text

    assets = next(
        index
        for index, item in enumerate(browser.file_model.items)
        if item.text == "Assets"
    )
    browser.activate_file(assets)
    assert controller.selected_directory == tmp_path / "Assets"
    assert browser.breadcrumb.text.endswith("Assets")
    assert browser.file_model.item_count == 2

    mesh = next(
        index for index, item in enumerate(browser.file_model.items) if item.text == "mesh.stl"
    )
    browser.select_file(mesh)
    browser.activate_file(mesh)
    assert selected == [tmp_path / "Assets" / "mesh.stl"]
    assert activated == [tmp_path / "Assets" / "mesh.stl"]
    browser.show_file_context(mesh, 300.0, 180.0)
    assert browser.context_menu.open
    browser.execute_context_action("copy-path")
    assert clipboard == [str((tmp_path / "Assets" / "mesh.stl").resolve())]

    draw_list = DrawList()
    document.paint(PaintContext(draw_list))
    assert draw_list.command_count > 20
    assert renders
    renderer.release_gpu()
