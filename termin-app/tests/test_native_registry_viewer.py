from tcbase import Key
from termin.editor_core.registry_viewer_model import (
    RegistryCatalogController,
    RegistryCollectionController,
    RegistryColumn,
    RegistryPage,
    RegistryRow,
)
from termin.editor_native import (
    build_native_editor_shell,
    build_native_registry_catalog_viewer,
    build_native_registry_viewer,
    connect_registry_viewer_command,
    resolve_native_ui_font,
)
from termin.gui_native import (
    Document,
    DrawList,
    DrawListRenderer,
    PaintContext,
    Rect,
)


class LargeRegistrySource:
    def load_rows(self):
        return [
            RegistryRow(
                f"type.{index:05d}",
                (f"Type {index}", "Python", "Component", "2/4"),
                f"Details {index}",
            )
            for index in range(10_000)
        ]


class HierarchySource:
    def load_rows(self):
        return [
            RegistryRow("leaf", ("Leaf", "1 component"), "needle", parent_id="child"),
            RegistryRow("root", ("Scene", "2 entities"), "scene details"),
            RegistryRow("child", ("Parent", "1 child"), "parent details", parent_id="root"),
        ]


def _bind_font(document: Document) -> DrawListRenderer:
    renderer = DrawListRenderer()
    assert renderer.set_default_font_path(str(resolve_native_ui_font()), 15)
    renderer.bind_text_measurer(document)
    return renderer


def test_native_registry_viewer_production_command_filter_selection_and_virtualization():
    document = Document()
    renderer = _bind_font(document)
    shell = build_native_editor_shell(document)
    clipboard = []
    controller = RegistryCollectionController(LargeRegistrySource(), copy_text=clipboard.append)
    renders = []
    viewer = build_native_registry_viewer(
        document,
        controller,
        viewport=lambda: Rect(0.0, 0.0, 1280.0, 720.0),
        request_render=lambda: renders.append(True),
    )
    connect_registry_viewer_command(
        shell.menu_bar,
        shell.inspect_registry_command,
        viewer,
    )

    document.layout_roots(Rect(0.0, 0.0, 1280.0, 720.0))
    assert shell.menu_bar.dispatch_shortcut(Key.F8.value, 0)
    assert viewer.dialog.open
    assert viewer.table_model.row_count == 10_000
    assert "10000" in viewer.status_bar.text
    assert viewer.table_widget.visible_range[1] < 30

    viewer.filter_input.text = "type.09999"
    assert viewer.table_model.row_count == 1
    assert viewer.table_widget.select(0)
    assert viewer.details_model.text == "Details 9999"
    assert viewer.show_context_menu(0, 80.0, 100.0)
    viewer.execute_context_action("copy-name")
    assert clipboard == ["type.09999"]

    draw_list = DrawList()
    document.paint(PaintContext(draw_list))
    assert draw_list.command_count > 20
    assert renders
    renderer.release_gpu()


def test_native_registry_viewer_context_menu_uses_table_row_index():
    document = Document()
    renderer = _bind_font(document)
    controller = RegistryCollectionController(LargeRegistrySource(), copy_text=lambda _text: None)
    viewer = build_native_registry_viewer(
        document,
        controller,
        viewport=lambda: Rect(0.0, 0.0, 900.0, 600.0),
        request_render=lambda: None,
    )
    assert viewer.show()
    document.layout_roots(Rect(0.0, 0.0, 900.0, 600.0))
    assert viewer.show_context_menu(0, 80.0, 100.0)
    assert viewer.context_menu.open
    assert viewer.context_model.command_count == 3
    renderer.release_gpu()


def test_native_registry_catalog_switches_page_rows_columns_and_filter_state():
    document = Document()
    renderer = _bind_font(document)
    columns = (RegistryColumn("name", "Name"), RegistryColumn("kind", "Kind", 90.0))
    controller = RegistryCatalogController(
        (
            RegistryPage("large", "Large", columns, LargeRegistrySource()),
            RegistryPage(
                "small",
                "Small",
                (RegistryColumn("name", "Name"),),
                LargeRegistrySource(),
            ),
        )
    )
    viewer = build_native_registry_catalog_viewer(
        document,
        controller,
        title="Catalog",
        viewport=lambda: Rect(0.0, 0.0, 900.0, 600.0),
        request_render=lambda: None,
    )

    assert viewer.show()
    assert viewer.page_selector is not None
    assert viewer.table_model.row_count == 10_000
    assert viewer.column_model.column_count == 2
    viewer.filter_input.text = "type.09999"
    assert viewer.table_model.row_count == 1
    viewer.page_selector.selected_index = 1
    assert controller.current_page.stable_id == "small"
    assert viewer.column_model.column_count == 1
    assert viewer.table_model.row_count == 10_000
    assert viewer.filter_input.text == ""
    viewer.page_selector.selected_index = 0
    assert viewer.table_model.row_count == 1
    assert viewer.filter_input.text == "type.09999"
    renderer.release_gpu()


def test_native_registry_catalog_projects_hierarchy_into_virtualized_tree():
    document = Document()
    renderer = _bind_font(document)
    controller = RegistryCatalogController(
        (
            RegistryPage(
                "scenes",
                "Scenes",
                (RegistryColumn("name", "Name"), RegistryColumn("summary", "Summary")),
                HierarchySource(),
                hierarchical=True,
            ),
        )
    )
    viewer = build_native_registry_catalog_viewer(
        document,
        controller,
        title="Core Registry",
        viewport=lambda: Rect(0.0, 0.0, 900.0, 600.0),
        request_render=lambda: None,
    )

    assert viewer.show()
    document.layout_roots(Rect(0.0, 0.0, 900.0, 600.0))
    assert viewer.tree_root.visible
    assert not viewer.table_root.visible
    assert viewer.tree_model.node_count == 3
    assert viewer.tree_widget.visible_count == 2
    viewer.filter_input.text = "needle"
    assert viewer.tree_widget.visible_count == 3
    leaf_index = next(index for index, row in enumerate(controller.snapshot().rows) if row.stable_id == "leaf")
    leaf_node = next(node for node, index in viewer.tree_node_indices.items() if index == leaf_index)
    assert viewer.tree_widget.select(leaf_node)
    assert viewer.details_model.text == "needle"
    renderer.release_gpu()


def test_native_registry_catalog_is_opened_by_production_core_registry_command():
    document = Document()
    renderer = _bind_font(document)
    shell = build_native_editor_shell(document)
    controller = RegistryCatalogController(
        (
            RegistryPage(
                "scenes",
                "Scenes",
                (RegistryColumn("name", "Name"),),
                HierarchySource(),
                hierarchical=True,
            ),
        )
    )
    viewer = build_native_registry_catalog_viewer(
        document,
        controller,
        title="Core Registry",
        viewport=lambda: Rect(0.0, 0.0, 1280.0, 720.0),
        request_render=lambda: None,
    )
    connect_registry_viewer_command(shell.menu_bar, shell.core_registry_command, viewer)

    assert shell.menu_bar.dispatch_shortcut(Key.F9.value, 0)
    assert viewer.dialog.open
    assert viewer.tree_model.node_count == 3
    renderer.release_gpu()
