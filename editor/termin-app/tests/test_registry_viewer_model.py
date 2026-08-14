import pytest

from termin.editor_core.registry_viewer_model import (
    RegistryCatalogController,
    RegistryCollectionController,
    RegistryColumn,
    RegistryPage,
    RegistryRow,
)


class FakeSource:
    def __init__(self, count=3):
        self.count = count
        self.loads = 0

    def load_rows(self):
        self.loads += 1
        return [
            RegistryRow(
                stable_id=f"type.{index}",
                cells=(f"Type {index}", "Python" if index % 2 else "C++"),
                details=f"Details for type {index}",
            )
            for index in range(self.count)
        ]


def test_registry_controller_refresh_filter_selection_activation_and_context_actions():
    source = FakeSource()
    clipboard = []
    activated = []
    controller = RegistryCollectionController(
        source,
        copy_text=clipboard.append,
        activate=lambda row: activated.append(row.stable_id),
    )

    snapshot = controller.refresh()
    assert snapshot.total_count == 3
    assert snapshot.status == "Registry entries: 3"
    snapshot = controller.set_filter("python")
    assert [row.stable_id for row in snapshot.rows] == ["type.1"]
    assert snapshot.status == "Registry entries: 1 of 3"
    snapshot = controller.select_index(0)
    assert snapshot.selected_id == "type.1"
    assert snapshot.selected_details == "Details for type 1"
    controller.activate_index(0)
    assert activated == ["type.1"]

    actions = controller.context_actions(0)
    assert [action.stable_id for action in actions] == [
        "copy-name",
        "copy-details",
        "refresh",
    ]
    controller.execute_context_action("copy-name", 0)
    controller.execute_context_action("copy-details", 0)
    assert clipboard == ["type.1", "Details for type 1"]
    controller.execute_context_action("refresh", 0)
    assert source.loads == 3


def test_registry_controller_reconciles_selection_and_rejects_invalid_sources():
    source = FakeSource(2)
    controller = RegistryCollectionController(source)
    controller.refresh()
    assert controller.select_index(1).selected_id == "type.1"
    source.count = 1
    assert controller.refresh().selected_id is None
    assert not controller.context_actions(-1)[0].enabled
    with pytest.raises(IndexError):
        controller.execute_context_action("copy-name", -1)

    class DuplicateSource:
        def load_rows(self):
            return [
                RegistryRow("same", ("A",), "A"),
                RegistryRow("same", ("B",), "B"),
            ]

    with pytest.raises(ValueError, match="unique"):
        RegistryCollectionController(DuplicateSource()).refresh()


def test_registry_catalog_owns_independent_page_state_and_validates_pages():
    first = FakeSource(2)
    second = FakeSource(4)
    columns = (RegistryColumn("name", "Name"),)
    catalog = RegistryCatalogController(
        (
            RegistryPage("first", "First", columns, first),
            RegistryPage("second", "Second", columns, second),
        )
    )

    assert catalog.refresh().total_count == 2
    catalog.set_filter("type.1")
    assert catalog.select_page(1).total_count == 4
    catalog.set_filter("type.3")
    assert [row.stable_id for row in catalog.snapshot().rows] == ["type.3"]
    assert catalog.select_page(0).filter_text == "type.1"
    assert [row.stable_id for row in catalog.snapshot().rows] == ["type.1"]

    with pytest.raises(ValueError, match="at least one"):
        RegistryCatalogController(())
    with pytest.raises(ValueError, match="unique"):
        RegistryCatalogController(
            (
                RegistryPage("same", "First", columns, first),
                RegistryPage("same", "Second", columns, second),
            )
        )


def test_registry_hierarchy_filter_keeps_ancestors_and_rejects_invalid_graphs():
    class HierarchySource:
        def load_rows(self):
            return [
                RegistryRow("root", ("Root",), "root details"),
                RegistryRow("child", ("Child",), "child details", parent_id="root"),
                RegistryRow("leaf", ("Leaf",), "needle", parent_id="child"),
            ]

    controller = RegistryCollectionController(HierarchySource())
    controller.refresh()
    assert [row.stable_id for row in controller.set_filter("needle").rows] == [
        "root",
        "child",
        "leaf",
    ]

    class MissingParentSource:
        def load_rows(self):
            return [RegistryRow("child", ("Child",), "", parent_id="missing")]

    with pytest.raises(ValueError, match="parent"):
        RegistryCollectionController(MissingParentSource()).refresh()

    class CycleSource:
        def load_rows(self):
            return [
                RegistryRow("first", ("First",), "", parent_id="second"),
                RegistryRow("second", ("Second",), "", parent_id="first"),
            ]

    with pytest.raises(ValueError, match="acyclic"):
        RegistryCollectionController(CycleSource()).refresh()
