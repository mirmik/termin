from __future__ import annotations
from termin.gui_native import tc_ui_document_create, tc_ui_document_destroy

from collections.abc import Callable

import pytest

from termin.bootstrap import bootstrap_player, shutdown_player
from termin.editor_core.dialog_service import DialogService
from termin.editor_core.scene_hierarchy_model import SceneHierarchyController
from termin.editor_core.undo_stack import UndoStack
from termin.editor_native.scene_tree import build_native_scene_tree
from termin.gui_native import Rect, TreeDropPosition
from termin.scene import TcScene


class ImmediateDialogService(DialogService):
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
        on_result("renamed")

    def show_choice(
        self,
        title: str,
        message: str,
        choices: list[str],
        on_result: Callable[[str | None], None],
        default: str | None = None,
        cancel: str | None = None,
    ) -> None:
        on_result(default)


@pytest.fixture(scope="module", autouse=True)
def player_runtime():
    bootstrap_player()
    yield
    shutdown_player()


def test_native_scene_tree_projects_selection_actions_and_drag_drop() -> None:
    scene = TcScene.create("native-scene-tree-test")
    try:
        parent = scene.create_entity("parent")
        child = scene.create_entity("child")
        sibling = scene.create_entity("sibling")
        child.transform.set_parent(parent.transform)
        selected: list[object | None] = []
        stack = UndoStack()
        controller = SceneHierarchyController(
            scene,
            undo_handler=stack.push,
            dialog_service=ImmediateDialogService(),
            on_object_selected=selected.append,
        )
        renders: list[bool] = []
        document = tc_ui_document_create()
        tree = build_native_scene_tree(
            document,
            controller,
            viewport=lambda: Rect(0.0, 0.0, 420.0, 320.0),
            request_render=lambda: renders.append(True),
        )
        assert document.add_root(tree.root.handle)
        document.layout_roots(Rect(0.0, 0.0, 420.0, 320.0))

        assert tree.tree_model.node_count == 3
        tree.tree_widget.select(tree.id_nodes[child.uuid])
        assert selected[-1].uuid == child.uuid
        assert controller.snapshot().selected_id == child.uuid

        tree.context_stable_id = sibling.uuid
        tree.execute_context_action("rename")
        assert sibling.name == "renamed"
        assert tree.tree_model.node(tree.id_nodes[sibling.uuid]).item.text == "renamed"

        tree.drop_node(
            tree.id_nodes[sibling.uuid],
            tree.id_nodes[parent.uuid],
            TreeDropPosition.Inside,
        )
        assert sibling.transform.parent.entity.uuid == parent.uuid
        assert tree.tree_model.node(tree.id_nodes[sibling.uuid]).parent == tree.id_nodes[parent.uuid]
        assert renders
    finally:
        scene.destroy()
    tc_ui_document_destroy(document)


def test_native_scene_tree_external_drop_hit_testing() -> None:
    scene = TcScene.create("native-scene-tree-drop-test")
    try:
        scene.create_entity("root")
        controller = SceneHierarchyController(
            scene,
            undo_handler=UndoStack().push,
            dialog_service=ImmediateDialogService(),
            on_object_selected=lambda _obj: None,
        )
        document = tc_ui_document_create()
        tree = build_native_scene_tree(
            document,
            controller,
            viewport=lambda: Rect(0.0, 0.0, 420.0, 320.0),
            request_render=lambda: None,
        )
        assert document.add_root(tree.root.handle)
        document.layout_roots(Rect(0.0, 0.0, 420.0, 320.0))

        assert not tree.drop_file("texture.png", 10.0, 80.0)
        assert not tree.drop_file("model.glb", 800.0, 80.0)
        target_id, position = tree._drop_target(tree.tree_root.bounds.y + 14.0)
        assert target_id is not None
        assert position == "inside"
    finally:
        scene.destroy()
    tc_ui_document_destroy(document)


def test_native_scene_tree_collapse_all_keeps_selected_branch_collapsed() -> None:
    scene = TcScene.create("native-scene-tree-collapse-test")
    try:
        parent = scene.create_entity("parent")
        child = scene.create_entity("child")
        child.transform.set_parent(parent.transform)
        controller = SceneHierarchyController(
            scene,
            undo_handler=UndoStack().push,
            dialog_service=ImmediateDialogService(),
            on_object_selected=lambda _obj: None,
        )
        document = tc_ui_document_create()
        tree = build_native_scene_tree(
            document,
            controller,
            viewport=lambda: Rect(0.0, 0.0, 420.0, 320.0),
            request_render=lambda: None,
        )
        assert document.add_root(tree.root.handle)
        document.layout_roots(Rect(0.0, 0.0, 420.0, 320.0))

        tree.select_object(child)
        parent_node = tree.id_nodes[parent.uuid]
        child_node = tree.id_nodes[child.uuid]
        assert tree.tree_widget.expanded(parent_node)
        assert tree.tree_widget.selected_node == child_node

        tree.collapse_all()

        assert controller.snapshot().expanded_ids == frozenset()
        assert not tree.tree_widget.expanded(tree.id_nodes[parent.uuid])
        assert tree.tree_widget.selected_node == tree.id_nodes[child.uuid]
    finally:
        scene.destroy()
    tc_ui_document_destroy(document)
