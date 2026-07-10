from __future__ import annotations

from collections.abc import Callable

import pytest

from termin.bootstrap import bootstrap_player, shutdown_player
from termin.editor_core.dialog_service import DialogService
from termin.editor_core.scene_hierarchy_model import SceneHierarchyController
from termin.editor_core.undo_stack import UndoStack
from termin.scene import TcScene


class ImmediateDialogService(DialogService):
    def __init__(self) -> None:
        self.input_result: str | None = None
        self.choice_result: str | None = None

    def show_error(
        self,
        title: str,
        message: str,
        on_close: Callable[[], None] | None = None,
    ) -> None:
        if on_close is not None:
            on_close()

    def show_input(
        self,
        title: str,
        message: str,
        default: str,
        on_result: Callable[[str | None], None],
    ) -> None:
        on_result(self.input_result)

    def show_choice(
        self,
        title: str,
        message: str,
        choices: list[str],
        on_result: Callable[[str | None], None],
        default: str | None = None,
        cancel: str | None = None,
    ) -> None:
        on_result(self.choice_result if self.choice_result is not None else default)


@pytest.fixture(scope="module", autouse=True)
def player_runtime():
    bootstrap_player()
    yield
    shutdown_player()


@pytest.fixture
def scene():
    value = TcScene.create("scene-hierarchy-model-test")
    yield value
    value.destroy()


def _controller(scene):
    stack = UndoStack()
    dialog = ImmediateDialogService()
    selected: list[object | None] = []
    controller = SceneHierarchyController(
        scene,
        undo_handler=stack.push,
        dialog_service=dialog,
        on_object_selected=selected.append,
    )
    return controller, stack, dialog, selected


def test_snapshot_is_preorder_and_selection_expands_ancestors(scene) -> None:
    root = scene.create_entity("root")
    child = scene.create_entity("child")
    grandchild = scene.create_entity("grandchild")
    child.transform.set_parent(root.transform)
    grandchild.transform.set_parent(child.transform)
    scene.create_entity("other")

    controller, _stack, _dialog, selected = _controller(scene)
    snapshot = controller.select_object(grandchild)

    assert [node.name for node in snapshot.nodes] == ["root", "child", "grandchild", "other"]
    assert snapshot.selected_id == grandchild.uuid
    assert snapshot.expanded_ids == {root.uuid, child.uuid}
    assert selected == [grandchild]
    assert snapshot.status == "Scene entities: 4"


def test_context_actions_are_undoable_and_refresh_projection(scene) -> None:
    entity = scene.create_entity("source")
    controller, stack, dialog, _selected = _controller(scene)

    dialog.input_result = "renamed"
    controller.execute_context_action("rename", entity.uuid)
    assert entity.name == "renamed"
    assert controller.snapshot().nodes[0].name == "renamed"

    controller.execute_context_action("toggle-visible", entity.uuid)
    assert not entity.visible
    assert not controller.snapshot().nodes[0].visible

    stack.undo()
    assert entity.visible
    controller.rebuild()
    assert controller.snapshot().nodes[0].visible

    stack.undo()
    assert entity.name == "source"


def test_internal_drop_reparents_reorders_and_rejects_cycles(scene) -> None:
    parent = scene.create_entity("parent")
    first = scene.create_entity("first")
    second = scene.create_entity("second")
    child = scene.create_entity("child")
    child.transform.set_parent(parent.transform)

    controller, stack, _dialog, _selected = _controller(scene)
    snapshot = controller.drop_entity(second.uuid, first.uuid, "before")
    assert [node.name for node in snapshot.nodes] == ["parent", "child", "second", "first"]
    assert [item["name"] for item in scene.serialize()["entities"]] == [
        "parent",
        "second",
        "first",
    ]

    snapshot = controller.drop_entity(first.uuid, parent.uuid, "inside")
    assert first.transform.parent.entity.uuid == parent.uuid
    assert [node.name for node in snapshot.nodes] == ["parent", "child", "first", "second"]
    assert [item["name"] for item in scene.serialize()["entities"][0]["children"]] == [
        "child",
        "first",
    ]

    stack.undo()
    controller.rebuild()
    assert first.transform.parent is None

    with pytest.raises(ValueError, match="cycle"):
        controller.drop_entity(parent.uuid, child.uuid, "inside")


def test_external_drop_contract_filters_extensions_and_positions(scene) -> None:
    controller, _stack, _dialog, _selected = _controller(scene)

    assert controller.can_drop_project_file(".GLB")
    assert controller.can_drop_project_file(".prefab")
    assert not controller.can_drop_project_file(".png")
    with pytest.raises(ValueError, match="unsupported"):
        controller.drop_project_file("texture.png", ".png", None, "root")
    with pytest.raises(ValueError, match="position"):
        controller.drop_project_file("model.glb", ".glb", None, "sideways")


def test_collapse_and_restore_expansion_are_stable_id_based(scene) -> None:
    root = scene.create_entity("root")
    child = scene.create_entity("child")
    child.transform.set_parent(root.transform)
    controller, _stack, _dialog, _selected = _controller(scene)

    controller.set_expanded(root.uuid, True)
    assert controller.get_expanded_entity_uuids() == [root.uuid]
    controller.collapse_all()
    assert controller.snapshot().expanded_ids == frozenset()
    controller.set_expanded_entity_uuids([root.uuid, "missing"])
    assert controller.snapshot().expanded_ids == {root.uuid}
