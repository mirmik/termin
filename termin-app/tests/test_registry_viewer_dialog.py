from termin.editor_tcgui.dialogs.registry_viewer_dialog import RegistryViewerDialog
from tcgui.widgets.table_widget import TableColumn
from tcgui.widgets.tree import TreeWidget


def test_registry_viewer_modules_import_without_opening_dialogs():
    from termin.editor_tcgui.dialogs import core_registry_viewer
    from termin.editor_tcgui.dialogs import resource_manager_viewer

    assert core_registry_viewer.show_core_registry_viewer is not None
    assert resource_manager_viewer.show_resource_manager_viewer is not None


def test_registry_viewer_dialog_builds_common_shell_and_wires_actions():
    viewer = RegistryViewerDialog(
        "Test Registry",
        {
            "First": [TableColumn("Name"), TableColumn("Count", 80)],
            "Second": [TableColumn("Type")],
        },
        details_width=320,
        content_height=420,
        min_width=700,
    )

    assert viewer.title == "Test Registry"
    assert viewer.min_width == 700
    assert viewer.content.preferred_height.to_pixels(0) == 420
    assert viewer.right_panel.preferred_width.to_pixels(0) == 320
    assert list(viewer.tab_lists) == ["First", "Second"]
    assert viewer.tabs.tab_bar.tabs == ["First", "Second"]
    assert viewer.details.read_only is True
    assert viewer.details.word_wrap is False

    selected = []
    viewer.set_table_select_handler(lambda index, data: selected.append((index, data)))
    viewer.tab_lists["First"].on_select(3, {"name": "row"})
    assert selected == [(3, {"name": "row"})]

    clicked = []
    button = viewer.add_button("Refresh", lambda: clicked.append("refresh"))
    button.on_click()
    assert clicked == ["refresh"]
    assert button in viewer.button_row.children

    tree = TreeWidget()
    viewer.add_tab("Tree", tree)
    assert viewer.tabs.tab_bar.tabs == ["First", "Second", "Tree"]
    assert viewer.tabs.pages[-1] is tree
